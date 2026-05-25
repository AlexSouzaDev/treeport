"""
OpenAI provider (API-based).

Calls the OpenAI Chat Completions API directly — no Docker required.

The provider:
  1. Collects relevant source files from the worktree
  2. Sends them + the prompt to the model
  3. Parses ``<file path="...">...</file>`` blocks from the response
  4. Writes patched files back to the worktree
  5. Commits the changes with git

Supported models
----------------
``gpt-4o``, ``gpt-4o-mini``, ``gpt-4-turbo``, ``o1``, ``o3-mini``, and any
future OpenAI model accessible via the Chat Completions endpoint.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from treeport.agents.base import AgentProvider, IterationResult
from treeport.file_collector import WorktreeContext, apply_file_patches, collect_context


_SYSTEM_PROMPT = """\
You are an expert software engineer working inside a git repository.
You will be given the contents of relevant source files and a task description.

Your response MUST follow this exact format:
1. A brief explanation of what you changed and why (plain text).
2. For EVERY file you modify or create, output a block like this:

<file path="relative/path/to/file.py">
...complete new file contents...
</file>

Rules:
- Always output the COMPLETE file contents, never partial updates or diffs.
- Only include files you actually modified or created.
- Use the exact relative paths shown in the provided file blocks.
- If no file changes are needed, output: <no-changes/>
"""


class OpenAIProvider(AgentProvider):
    """
    Calls OpenAI Chat Completions API directly from the host.

    No Docker image needed. Requires ``OPENAI_API_KEY`` in the environment.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        context_token_budget: int = 80_000,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        commit_message_prefix: str = "treeport(openai)",
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.context_token_budget = context_token_budget
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.commit_message_prefix = commit_message_prefix

    # ------------------------------------------------------------------ #
    # AgentProvider interface
    # ------------------------------------------------------------------ #

    @property
    def execution_mode(self) -> Literal["api"]:
        return "api"

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
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._run_sync(prompt, worktree_path, env, completion_signal),
        )

    def dockerfile_snippet(self) -> str:
        return ""  # API-based — no Docker tooling needed

    def required_env_vars(self) -> list[str]:
        return ["OPENAI_API_KEY"]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _run_sync(
        self,
        prompt: str,
        worktree_path: Path,
        env: dict[str, str],
        completion_signal: str,
    ) -> IterationResult:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai package required for OpenAIProvider. "
                "Install it: pip install openai"
            ) from e

        api_key = env.get("OPENAI_API_KEY") or __import__("os").environ.get("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)

        # Collect worktree context
        ctx: WorktreeContext = collect_context(
            worktree_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_tokens=self.context_token_budget,
        )

        user_message = f"## Repository files\n\n{ctx.to_prompt_block()}\n\n## Task\n\n{prompt}"

        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        response_text = response.choices[0].message.content or ""

        # Apply file patches
        modified = apply_file_patches(response_text, worktree_path)

        if modified:
            _git_commit(
                worktree_path,
                f"{self.commit_message_prefix}: {prompt[:72]}",
            )

        signal_detected = self._signal_in(response_text, completion_signal)

        return IterationResult(
            stdout=response_text,
            completion_signal_detected=signal_detected,
            files_modified=modified,
        )


# ── Git helper ─────────────────────────────────────────────────────────


def _git_commit(worktree_path: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=worktree_path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=worktree_path,
        check=True,
    )
