"""
Claude Code provider.

Runs the ``claude`` CLI inside the Docker sandbox.
This is the default provider — identical behaviour to the original treeport.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from treeport.agents.base import AgentProvider, IterationResult


class ClaudeCodeProvider(AgentProvider):
    """Runs ``claude --print --dangerously-skip-permissions`` inside Docker."""

    execution_mode: Literal["container"] = "container"  # type: ignore[assignment]

    def __init__(self, model: str = "claude-opus-4-5") -> None:
        self.model = model

    # ------------------------------------------------------------------ #
    # AgentProvider interface
    # ------------------------------------------------------------------ #

    @property
    def execution_mode(self) -> Literal["container"]:  # type: ignore[override]
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
        return "# Claude Code CLI\nRUN npm install -g @anthropic-ai/claude-code\n"

    def required_env_vars(self) -> list[str]:
        return ["ANTHROPIC_API_KEY"]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _build_command(self) -> list[str]:
        return [
            "sh", "-c",
            f"claude --model {self.model} --print --dangerously-skip-permissions "
            f'"$(cat /home/agent/repo/.treeport_prompt.md)"',
        ]
