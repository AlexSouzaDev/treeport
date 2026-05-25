"""
Core orchestration: the ``run()`` function.

Fully provider-agnostic — delegates all agent behaviour to the
``AgentProvider`` resolved from ``options.agent`` via the registry.

Flow:
  1. Resolve repo root + load .env
  2. Build the agent provider from options.agent
  3. Validate required env vars (warn only, don't hard-fail)
  4. Create a git worktree
  5. (Container providers) ensure Docker image exists
  6. Copy files into sandbox
  7. Run on_sandbox_ready hooks
  8. Resolve the prompt
  9. Iteration loop: provider.run_iteration() → check signal → repeat
 10. Collect commits, merge worktree back, cleanup
 11. Return RunResult
"""

from __future__ import annotations

import asyncio
import time
import warnings
from pathlib import Path

from treeport.agents.base import AgentProvider
from treeport.agents.registry import provider_from_config
from treeport.docker_runner import ContainerRunner
from treeport.git_manager import WorktreeManager
from treeport.logging import make_logger
from treeport.prompt import resolve_prompt
from treeport.types import (
    CommitInfo,
    FileLogging,
    RunOptions,
    RunResult,
)


async def run(options: RunOptions | dict) -> RunResult:
    """
    Orchestrate a treeport agent run.

    Accepts any configured agent backend via ``options.agent``:

    .. code-block:: python

        from treeport import run
        from treeport.types import RunOptions, AiderConfig, OpenAIConfig

        # Claude Code (default)
        result = await run(RunOptions(prompt="fix the bug"))

        # Aider with GPT-4o
        result = await run(RunOptions(
            prompt="fix the bug",
            agent=AiderConfig(model="gpt-4o"),
        ))

        # OpenAI API directly — no Docker needed
        result = await run(RunOptions(
            prompt="fix the bug",
            agent=OpenAIConfig(model="gpt-4o"),
        ))

    Args:
        options: A :class:`RunOptions` instance or a dict coerced to one.

    Returns:
        :class:`RunResult`
    """
    if isinstance(options, dict):
        options = RunOptions(**options)

    # ------------------------------------------------------------------ #
    # Repo root
    # ------------------------------------------------------------------ #
    import git as _git

    repo = _git.Repo(".", search_parent_directories=True)
    repo_root = Path(repo.working_dir)

    # ------------------------------------------------------------------ #
    # Logger
    # ------------------------------------------------------------------ #
    log_type = options.logging.type
    log_file_path = (
        options.logging.path
        if isinstance(options.logging, FileLogging)
        else None
    )
    logger, resolved_log_path = make_logger(
        log_type, log_file_path, options.name, repo_root
    )
    logger.start()

    # ------------------------------------------------------------------ #
    # Build agent provider
    # ------------------------------------------------------------------ #
    provider: AgentProvider = provider_from_config(options.agent)
    agent_type = options.agent.type  # type: ignore[union-attr]

    logger._write(
        f"Agent: {agent_type} | Mode: {provider.execution_mode}",
        style="cyan",
    )

    # ------------------------------------------------------------------ #
    # Load env from .treeport/.env
    # ------------------------------------------------------------------ #
    env = ContainerRunner.load_env_file(repo_root / ".treeport" / ".env")

    # Warn about missing required env vars
    for var in provider.required_env_vars():
        import os
        if not env.get(var) and not os.environ.get(var):
            warnings.warn(
                f"Required env var '{var}' for {agent_type!r} is not set. "
                "The run may fail.",
                UserWarning,
                stacklevel=2,
            )

    # ------------------------------------------------------------------ #
    # Timeout
    # ------------------------------------------------------------------ #
    deadline = time.monotonic() + options.timeout_seconds

    def _remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    # ------------------------------------------------------------------ #
    # Worktree
    # ------------------------------------------------------------------ #
    wt = WorktreeManager(
        repo_root=repo_root,
        branch=options.branch,
        run_name=options.name,
    )
    worktree_path = wt.create()

    # ------------------------------------------------------------------ #
    # Docker setup (container-based providers only)
    # ------------------------------------------------------------------ #
    runner: ContainerRunner | None = None

    if provider.execution_mode == "container":
        image_name = options.image_name or ContainerRunner.default_image_name(repo_root)
        runner = ContainerRunner(
            image_name=image_name,
            worktree_path=worktree_path,
            env=env,
        )

        if not runner.image_exists():
            dockerfile = repo_root / ".treeport" / "Dockerfile"
            if not dockerfile.exists():
                raise FileNotFoundError(
                    f"Docker image '{image_name}' not found and no Dockerfile at "
                    f"{dockerfile}. Run `treeport init` first."
                )
            logger._write(f"Building image {image_name}…", style="yellow")
            runner.build_image(dockerfile, repo_root)

    try:
        # ---------------------------------------------------------------- #
        # Copy files into sandbox
        # ---------------------------------------------------------------- #
        if options.copy_to_sandbox and runner:
            runner.copy_files_to_worktree(options.copy_to_sandbox, repo_root)

        # ---------------------------------------------------------------- #
        # on_sandbox_ready hooks (container-mode only)
        # ---------------------------------------------------------------- #
        if options.hooks.on_sandbox_ready and runner:
            logger._write("Running on_sandbox_ready hooks…", style="cyan")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: runner.run_hooks(options.hooks.on_sandbox_ready)
            )

        # ---------------------------------------------------------------- #
        # Resolve prompt
        # ---------------------------------------------------------------- #
        resolved_prompt = resolve_prompt(
            prompt=options.prompt,
            prompt_file=options.prompt_file,
            prompt_args=options.prompt_args,
            cwd=worktree_path,
        )

        # Write prompt file for container providers
        if runner:
            runner.write_prompt(resolved_prompt, worktree_path)

        # ---------------------------------------------------------------- #
        # Iteration loop
        # ---------------------------------------------------------------- #
        all_stdout: list[str] = []
        all_files_modified: list[str] = []
        completion_detected = False
        iteration = 0

        for iteration in range(1, options.max_iterations + 1):
            if _remaining() <= 0:
                logger._write("Timeout reached — stopping.", style="bold red")
                break

            logger.iteration_start(iteration, options.max_iterations)

            result = await asyncio.wait_for(
                provider.run_iteration(
                    prompt=resolved_prompt,
                    worktree_path=worktree_path,
                    env=env,
                    completion_signal=options.completion_signal,
                    image_name=options.image_name,
                    container_runner=runner,
                ),
                timeout=_remaining(),
            )

            logger.agent_output(result.stdout)
            logger.iteration_end(iteration, result.completion_signal_detected, result.stdout)
            all_stdout.append(result.stdout)
            all_files_modified.extend(result.files_modified)

            if result.completion_signal_detected:
                completion_detected = True
                break

        # ---------------------------------------------------------------- #
        # Collect commits & merge back
        # ---------------------------------------------------------------- #
        raw_commits = wt.get_new_commits()
        commits = [CommitInfo(sha=c["sha"], message=c.get("message")) for c in raw_commits]
        logger.commits_found(raw_commits)

        wt.merge_back()

    except Exception as exc:
        logger.error(str(exc))
        raise
    finally:
        wt.cleanup()

    logger.finish(wt.target_branch, resolved_log_path)

    return RunResult(
        iterations_run=iteration,
        was_completion_signal_detected=completion_detected,
        stdout="\n".join(all_stdout),
        commits=commits,
        branch=wt.target_branch,
        log_file_path=resolved_log_path,
        agent_type=agent_type,
        files_modified=list(dict.fromkeys(all_files_modified)),  # deduplicated
    )
