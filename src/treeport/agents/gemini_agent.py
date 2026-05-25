"""
Google Gemini provider (API-based).

Calls ``google-generativeai`` (or ``google-genai``) directly from the host.
No Docker required.

Supported models
----------------
``gemini-2.0-flash``, ``gemini-2.0-flash-lite``,
``gemini-1.5-pro``, ``gemini-1.5-flash``

Install the SDK::

    pip install google-generativeai
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from treeport.agents.base import AgentProvider, IterationResult
from treeport.file_collector import apply_file_patches, collect_context
from treeport.agents.openai_agent import _git_commit  # shared helper


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


class GeminiProvider(AgentProvider):
    """
    Calls the Google Gemini API directly from the host.

    No Docker image needed. Requires ``GEMINI_API_KEY`` in the environment.
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        max_output_tokens: int = 8192,
        context_token_budget: int = 100_000,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        commit_message_prefix: str = "treeport(gemini)",
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
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
        return ""  # API-based

    def required_env_vars(self) -> list[str]:
        return ["GEMINI_API_KEY"]

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
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "google-generativeai package required for GeminiProvider. "
                "Install it: pip install google-generativeai"
            ) from e

        import os
        api_key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=api_key)

        # Collect worktree context
        ctx = collect_context(
            worktree_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_tokens=self.context_token_budget,
        )

        full_prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"## Repository files\n\n{ctx.to_prompt_block()}\n\n"
            f"## Task\n\n{prompt}"
        )

        gemini_model = genai.GenerativeModel(
            model_name=self.model,
            generation_config=genai.GenerationConfig(
                max_output_tokens=self.max_output_tokens,
            ),
        )

        response = gemini_model.generate_content(full_prompt)
        response_text = response.text or ""

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
