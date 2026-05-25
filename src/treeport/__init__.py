"""
treeport — Orchestrate sandboxed AI coding agents in Python.

Quick start::

    from treeport import run
    from treeport.types import RunOptions, AiderConfig

    # Default: Claude Code
    result = await run(RunOptions(prompt_file=".treeport/prompt.md"))

    # Aider with GPT-4o
    result = await run(RunOptions(
        prompt="fix the tests",
        agent=AiderConfig(model="gpt-4o"),
    ))

    # OpenAI direct (no Docker)
    from treeport.types import OpenAIConfig
    result = await run(RunOptions(
        prompt="refactor the auth module",
        agent=OpenAIConfig(model="gpt-4o"),
    ))
"""

from treeport.core import run
from treeport.types import (
    AiderConfig,
    ClaudeCodeConfig,
    CommitInfo,
    CustomConfig,
    FileLogging,
    GeminiConfig,
    Hook,
    Hooks,
    OpenAIConfig,
    RunOptions,
    RunResult,
    StdoutLogging,
)
from treeport.agents import (
    AgentProvider,
    AiderProvider,
    ClaudeCodeProvider,
    CustomProvider,
    GeminiProvider,
    IterationResult,
    OpenAIProvider,
)

__all__ = [
    # Core
    "run",
    # Options / result
    "RunOptions",
    "RunResult",
    "CommitInfo",
    "Hook",
    "Hooks",
    "FileLogging",
    "StdoutLogging",
    # Agent configs (use in RunOptions.agent=...)
    "ClaudeCodeConfig",
    "AiderConfig",
    "OpenAIConfig",
    "GeminiConfig",
    "CustomConfig",
    # Agent providers (advanced: instantiate directly)
    "AgentProvider",
    "IterationResult",
    "ClaudeCodeProvider",
    "AiderProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "CustomProvider",
]

__version__ = "0.2.0"
