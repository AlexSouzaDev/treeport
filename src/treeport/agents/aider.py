"""
Aider provider.

Aider (https://aider.chat) is a terminal coding agent that supports virtually
every major model — Claude, GPT-4o, Gemini, DeepSeek, and local Ollama models
— through a unified CLI.

Model string examples
---------------------
* Claude:   ``claude-opus-4-5``, ``claude-sonnet-4-5``, ``claude-haiku-4-5``
* OpenAI:   ``gpt-4o``, ``gpt-4o-mini``, ``o1``
* Gemini:   ``gemini/gemini-2.0-flash``, ``gemini/gemini-1.5-pro``
* DeepSeek: ``deepseek/deepseek-coder``
* Ollama:   ``ollama/codellama``, ``ollama/llama3``

The required env var changes depending on the model:
* Claude  → ``ANTHROPIC_API_KEY``
* OpenAI  → ``OPENAI_API_KEY``
* Gemini  → ``GEMINI_API_KEY``
* DeepSeek → ``DEEPSEEK_API_KEY``
* Ollama  → no key needed
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from treeport.agents.base import AgentProvider, IterationResult


_MODEL_ENV_MAP: dict[str, str] = {
    "claude":   "ANTHROPIC_API_KEY",
    "gpt":      "OPENAI_API_KEY",
    "o1":       "OPENAI_API_KEY",
    "o3":       "OPENAI_API_KEY",
    "gemini":   "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


class AiderProvider(AgentProvider):
    """
    Runs ``aider`` CLI inside Docker.

    Supports all models aider supports — change ``model`` to switch providers.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        extra_args: list[str] | None = None,
        auto_commit: bool = True,
    ) -> None:
        self.model = model
        self.extra_args = extra_args or []
        self.auto_commit = auto_commit

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
        return (
            "# Aider coding agent\n"
            "RUN pip install --no-cache-dir aider-chat\n"
        )

    def required_env_vars(self) -> list[str]:
        model_lower = self.model.lower()
        for prefix, var in _MODEL_ENV_MAP.items():
            if model_lower.startswith(prefix):
                return [var]
        # Ollama or unknown — no key needed
        return []

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _build_command(self) -> list[str]:
        base = [
            "aider",
            "--model", self.model,
            "--message", "$(cat /home/agent/repo/.treeport_prompt.md)",
            "--yes-always",      # never prompt for confirmation
            "--no-pretty",       # machine-readable output
            "--no-stream",       # buffer full output
        ]
        if not self.auto_commit:
            base.append("--no-auto-commits")

        base.extend(self.extra_args)

        # Wrap in sh -c so the $() subshell works
        return ["sh", "-c", " ".join(base)]
