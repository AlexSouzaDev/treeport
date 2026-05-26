"""
Docker container mechanics for treeport.

ContainerRunner handles everything Docker-related:
- Image build/check
- Hook execution (on_sandbox_ready)
- Generic container_exec() — runs any command, streams output, detects signal

Provider-specific logic (which CLI to invoke, which env vars to pass) lives
entirely in the agent providers under treeport/agents/.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import docker  # type: ignore
from docker.errors import ImageNotFound  # type: ignore

from treeport.types import Hook


_AGENT_WORKDIR = "/home/agent/repo"
_AGENT_USER = "agent"


class ContainerRunner:
    """Wraps Docker SDK to manage sandbox containers for one treeport run."""

    DEFAULT_IMAGE_SUFFIX = "treeport"

    def __init__(
        self,
        image_name: str,
        worktree_path: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        self.client = docker.from_env()
        self.image_name = image_name
        self.worktree_path = worktree_path
        self.env = env or {}

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ContainerRunner":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    @classmethod
    def default_image_name(cls, repo_root: Path) -> str:
        return f"{cls.DEFAULT_IMAGE_SUFFIX}:{repo_root.name.lower()}"

    def image_exists(self) -> bool:
        try:
            self.client.images.get(self.image_name)
            return True
        except ImageNotFound:
            return False

    def build_image(
        self,
        dockerfile_path: Path,
        build_context: Path | None = None,
        *,
        quiet: bool = False,
    ) -> None:
        ctx = build_context or dockerfile_path.parent
        self.client.images.build(
            path=str(ctx),
            dockerfile=str(dockerfile_path),
            tag=self.image_name,
            rm=True,
            quiet=quiet,
        )

    # ------------------------------------------------------------------
    # Hook execution
    # ------------------------------------------------------------------

    def run_hooks(self, hooks: list[Hook]) -> None:
        """Run each hook command sequentially inside a short-lived container."""
        for hook in hooks:
            try:
                result = self.client.containers.run(
                    self.image_name,
                    command=["sh", "-c", hook.command],
                    volumes=self._volume_spec(),
                    working_dir=_AGENT_WORKDIR,
                    environment=self.env,
                    remove=True,
                    user=_AGENT_USER,
                )
            except docker.errors.ContainerError as exc:
                desc = hook.description or hook.command
                raise RuntimeError(
                    f"on_sandbox_ready hook failed: {desc!r}\n"
                    f"stderr: {exc.stderr.decode(errors='replace') if exc.stderr else ''}"
                ) from exc
            if isinstance(result, bytes) and result.strip():
                print(result.decode(errors="replace").strip())

    # ------------------------------------------------------------------
    # Generic container execution (called by container-based providers)
    # ------------------------------------------------------------------

    def container_exec(
        self,
        command: list[str],
        worktree_path: Path,
        env: dict[str, str],
        completion_signal: str,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[str, bool]:
        """
        Run *command* inside the sandbox container bound to *worktree_path*.

        Streams stdout line-by-line, checks for *completion_signal* in output.

        Returns:
            ``(stdout_text, signal_detected)``
        """
        merged_env = {**self.env, **env, **(extra_env or {})}

        # Write the prompt to disk so the command can read it without
        # shell-escaping issues.
        prompt_path = worktree_path / ".treeport_prompt.md"
        container = None

        try:
            container = self.client.containers.run(
                self.image_name,
                command=command,
                volumes={
                    str(worktree_path): {"bind": _AGENT_WORKDIR, "mode": "rw"},
                },
                working_dir=_AGENT_WORKDIR,
                environment=merged_env,
                detach=True,
                user=_AGENT_USER,
            )

            stdout_lines: list[str] = []
            signal_detected = False

            for chunk in container.logs(stream=True, follow=True):
                line = chunk.decode(errors="replace")
                stdout_lines.append(line)
                if completion_signal in line:
                    signal_detected = True

            container.wait()

        finally:
            if container is not None:
                container.remove(force=True)
            prompt_path.unlink(missing_ok=True)

        return "".join(stdout_lines), signal_detected

    # ------------------------------------------------------------------
    # Prompt injection helper
    # ------------------------------------------------------------------

    def write_prompt(self, prompt: str, worktree_path: Path) -> Path:
        """Write *prompt* to a temp file in the worktree. Returns the path."""
        path = worktree_path / ".treeport_prompt.md"
        path.write_text(prompt, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # File copy helpers
    # ------------------------------------------------------------------

    def copy_files_to_worktree(
        self,
        host_paths: list[str],
        repo_root: Path,
    ) -> None:
        import shutil

        for rel_path in host_paths:
            src = repo_root / rel_path
            dst = self.worktree_path / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # ------------------------------------------------------------------
    # Env helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_env_file(env_file: Path) -> dict[str, str]:
        env: dict[str, str] = {}
        if not env_file.exists():
            return env
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[key.strip()] = value
        return env

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _volume_spec(self) -> dict:
        return {
            str(self.worktree_path): {"bind": _AGENT_WORKDIR, "mode": "rw"}
        }
