"""
Agent provider abstraction.

All coding agent backends implement ``AgentProvider``.
The orchestrator (``core.py``) is 100% provider-agnostic — it only ever calls
``provider.run_iteration(...)`` and ``provider.dockerfile_snippet()``.

Two execution modes exist:

* **Container** — the provider runs a CLI tool inside the Docker sandbox
  (Claude Code, Aider, or a custom command).  ``docker_runner.ContainerRunner``
  handles the Docker mechanics; the provider supplies the command + Dockerfile
  snippet.

* **API** — the provider calls a remote API directly from the host, reads
  files from the worktree, writes changes back, and commits them.
  No Docker is required.  ``file_collector`` handles context assembly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


# ── Result produced by one iteration ──────────────────────────────────


class IterationResult(BaseModel):
    stdout: str
    completion_signal_detected: bool
    files_modified: list[str] = []   # populated by API-based providers


# ── Provider ABC ───────────────────────────────────────────────────────


class AgentProvider(ABC):
    """
    Base class for all agent backends.

    Subclasses must implement:
      - ``execution_mode``  — ``"container"`` or ``"api"``
      - ``run_iteration()`` — run one agent pass and return ``IterationResult``
      - ``dockerfile_snippet()`` — lines to add to the sandbox Dockerfile
      - ``required_env_vars()`` — env vars the provider needs at runtime
    """

    # ------------------------------------------------------------------ #
    # Abstract interface
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def execution_mode(self) -> Literal["container", "api"]:
        """Whether this provider runs inside Docker or calls an API on the host."""

    @abstractmethod
    async def run_iteration(
        self,
        *,
        prompt: str,
        worktree_path: Path,
        env: dict[str, str],
        completion_signal: str,
        # Container-mode extras (ignored by API providers)
        image_name: str | None = None,
        container_runner: object | None = None,
    ) -> IterationResult:
        """Execute one agent iteration and return its result."""

    @abstractmethod
    def dockerfile_snippet(self) -> str:
        """
        Dockerfile lines required to install this provider's tooling.

        Return an empty string for API-based providers (no Docker needed).
        The snippet is injected into the default Dockerfile template produced
        by ``treeport init``.
        """

    @abstractmethod
    def required_env_vars(self) -> list[str]:
        """
        Env var names this provider needs (used for validation warnings).

        Example: ``["ANTHROPIC_API_KEY"]`` for Claude Code.
        """

    # ------------------------------------------------------------------ #
    # Shared helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def _signal_in(text: str, completion_signal: str) -> bool:
        return completion_signal in text
