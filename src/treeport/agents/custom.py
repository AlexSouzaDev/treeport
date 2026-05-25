"""
Custom agent provider.

Runs an arbitrary shell command inside the Docker sandbox.
The command template supports ``{model}`` and ``{prompt_file}`` placeholders.

Example
-------
.. code-block:: python

    from treeport.agents import CustomProvider

    provider = CustomProvider(
        command="my-agent --model {model} --prompt {prompt_file}",
        model="gpt-4o",
        dockerfile_snippet_text=(
            "RUN pip install my-agent"
        ),
    )

Placeholders in ``command``
---------------------------
* ``{prompt_file}``  — absolute in-container path to the prompt file
  (``/home/agent/repo/.treeport_prompt.md``)
* ``{model}``        — value of ``model``
* ``{repo}``         — in-container repo path (``/home/agent/repo``)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from treeport.agents.base import AgentProvider, IterationResult


_PROMPT_FILE = "/home/agent/repo/.treeport_prompt.md"
_REPO_PATH = "/home/agent/repo"


class CustomProvider(AgentProvider):
    """Runs a user-supplied shell command inside the Docker sandbox."""

    def __init__(
        self,
        command: str,
        model: str = "",
        dockerfile_snippet_text: str = "",
        env_vars: list[str] | None = None,
    ) -> None:
        self._command = command
        self.model = model
        self._dockerfile_snippet = dockerfile_snippet_text
        self._env_vars = env_vars or []

    # ------------------------------------------------------------------ #
    # AgentProvider interface
    # ------------------------------------------------------------------ #

    @property
    def execution_mode(self) -> Literal["container"]:
        return "container"

    async def run_iteration(
        self,
        *,
        prompt: str,
        worktree_path: Path,
        env: dict[str, str],
        completion_signal: str,
        image_name: str | None = None,
        container_runner: object | None = None,
    ) -> IterationResult:
        from treeport.docker_runner import ContainerRunner

        runner: ContainerRunner = container_runner  # type: ignore[assignment]

        stdout, detected = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: runner.container_exec(
                command=self._build_command(),
                worktree_path=worktree_path,
                env=env,
                completion_signal=completion_signal,
            ),
        )
        return IterationResult(stdout=stdout, completion_signal_detected=detected)

    def dockerfile_snippet(self) -> str:
        return self._dockerfile_snippet

    def required_env_vars(self) -> list[str]:
        return self._env_vars

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _build_command(self) -> list[str]:
        rendered = self._command.format(
            prompt_file=_PROMPT_FILE,
            model=self.model,
            repo=_REPO_PATH,
        )
        return ["sh", "-c", rendered]
