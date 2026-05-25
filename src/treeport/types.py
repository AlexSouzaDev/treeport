"""
Pydantic models for agent configs, RunOptions, and RunResult.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


# ── Hooks & Logging (unchanged) ────────────────────────────────────────


class Hook(BaseModel):
    command: str
    description: str | None = None


class Hooks(BaseModel):
    on_sandbox_ready: list[Hook] = Field(default_factory=list)


class FileLogging(BaseModel):
    type: Literal["file"] = "file"
    path: str | None = None


class StdoutLogging(BaseModel):
    type: Literal["stdout"] = "stdout"


LoggingConfig = FileLogging | StdoutLogging


# ── Agent configs ──────────────────────────────────────────────────────


class ClaudeCodeConfig(BaseModel):
    """Run Claude Code CLI inside Docker (default)."""
    type: Literal["claude-code"] = "claude-code"
    model: str = "claude-opus-4-5"


class AiderConfig(BaseModel):
    """
    Run Aider CLI inside Docker.

    Aider supports virtually every major model provider through a single CLI.
    Set ``model`` to any Aider-supported string:

    * Claude:    ``claude-opus-4-5``, ``claude-sonnet-4-5``
    * OpenAI:    ``gpt-4o``, ``o1``, ``o3-mini``
    * Gemini:    ``gemini/gemini-2.0-flash``, ``gemini/gemini-1.5-pro``
    * DeepSeek:  ``deepseek/deepseek-coder``
    * Ollama:    ``ollama/codellama``, ``ollama/llama3``
    """
    type: Literal["aider"] = "aider"
    model: str = "gpt-4o"
    extra_args: list[str] = Field(default_factory=list)
    auto_commit: bool = True


class OpenAIConfig(BaseModel):
    """Call OpenAI Chat Completions API directly (no Docker required)."""
    type: Literal["openai"] = "openai"
    model: str = "gpt-4o"
    max_tokens: int = 4096
    context_token_budget: int = 80_000
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None


class GeminiConfig(BaseModel):
    """Call Google Gemini API directly (no Docker required)."""
    type: Literal["gemini"] = "gemini"
    model: str = "gemini-2.0-flash"
    max_output_tokens: int = 8192
    context_token_budget: int = 100_000
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None


class CustomConfig(BaseModel):
    """
    Run an arbitrary shell command inside Docker.

    Use ``{prompt_file}``, ``{model}``, ``{repo}`` placeholders in ``command``.
    """
    type: Literal["custom"] = "custom"
    command: str
    model: str = ""
    dockerfile_snippet_text: str = ""
    env_vars: list[str] = Field(default_factory=list)


# Discriminated union — used as the type for RunOptions.agent
AgentConfig = Annotated[
    ClaudeCodeConfig | AiderConfig | OpenAIConfig | GeminiConfig | CustomConfig,
    Field(discriminator="type"),
]


# ── RunOptions ─────────────────────────────────────────────────────────


class RunOptions(BaseModel):
    # Prompt — exactly one must be provided
    prompt: str | None = None
    prompt_file: str | Path | None = None

    # Substitutions for {{KEY}} placeholders
    prompt_args: dict[str, str] = Field(default_factory=dict)

    # Agent configuration
    agent: AgentConfig = Field(default_factory=ClaudeCodeConfig)

    # Orchestration control
    max_iterations: int = Field(default=1, ge=1)
    completion_signal: str = "<promise>COMPLETE</promise>"
    timeout_seconds: int = Field(default=1200, ge=1)

    # Git / Docker
    branch: str | None = None
    image_name: str | None = None
    name: str | None = None

    # Lifecycle
    hooks: Hooks = Field(default_factory=Hooks)
    copy_to_sandbox: list[str] = Field(default_factory=list)

    # Logging
    logging: LoggingConfig = Field(default_factory=FileLogging)

    @model_validator(mode="after")
    def _check_prompt_exclusivity(self) -> "RunOptions":
        if self.prompt is None and self.prompt_file is None:
            raise ValueError("Provide exactly one of `prompt` or `prompt_file`.")
        if self.prompt is not None and self.prompt_file is not None:
            raise ValueError("`prompt` and `prompt_file` are mutually exclusive.")
        return self


# ── RunResult ──────────────────────────────────────────────────────────


class CommitInfo(BaseModel):
    sha: str
    message: str | None = None


class RunResult(BaseModel):
    iterations_run: int
    was_completion_signal_detected: bool
    stdout: str
    commits: list[CommitInfo]
    branch: str
    log_file_path: Path | None = None
    agent_type: str = "claude-code"   # which agent was used
    files_modified: list[str] = Field(default_factory=list)  # API-mode only
