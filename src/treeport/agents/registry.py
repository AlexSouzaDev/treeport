"""
Agent registry.

Maps the ``AgentConfig`` discriminated union from ``types.py`` to concrete
``AgentProvider`` instances.

Usage::

    from treeport.agents.registry import provider_from_config
    from treeport.types import AiderConfig

    provider = provider_from_config(AiderConfig(model="gpt-4o"))
"""

from __future__ import annotations

from treeport.agents.base import AgentProvider


def provider_from_config(config: object) -> AgentProvider:
    """
    Instantiate the correct ``AgentProvider`` for *config*.

    Args:
        config: An ``AgentConfig`` instance (any of the tagged-union members
                defined in ``treeport.types``).

    Returns:
        A fully-configured ``AgentProvider`` ready to call ``run_iteration()``.

    Raises:
        ValueError: If the config type is unknown.
    """
    # Import here to avoid circular imports at module level
    from treeport.types import (
        AiderConfig,
        ClaudeCodeConfig,
        CustomConfig,
        GeminiConfig,
        OpenAIConfig,
    )
    from treeport.agents.aider import AiderProvider
    from treeport.agents.claude_code import ClaudeCodeProvider
    from treeport.agents.custom import CustomProvider
    from treeport.agents.gemini_agent import GeminiProvider
    from treeport.agents.openai_agent import OpenAIProvider

    match config:
        case ClaudeCodeConfig():
            return ClaudeCodeProvider(model=config.model)

        case AiderConfig():
            return AiderProvider(
                model=config.model,
                extra_args=config.extra_args,
                auto_commit=config.auto_commit,
            )

        case OpenAIConfig():
            return OpenAIProvider(
                model=config.model,
                max_tokens=config.max_tokens,
                context_token_budget=config.context_token_budget,
                include_patterns=config.include_patterns,
                exclude_patterns=config.exclude_patterns,
            )

        case GeminiConfig():
            return GeminiProvider(
                model=config.model,
                max_output_tokens=config.max_output_tokens,
                context_token_budget=config.context_token_budget,
                include_patterns=config.include_patterns,
                exclude_patterns=config.exclude_patterns,
            )

        case CustomConfig():
            return CustomProvider(
                command=config.command,
                model=config.model,
                dockerfile_snippet_text=config.dockerfile_snippet_text,
                env_vars=config.env_vars,
            )

        case _:
            raise ValueError(
                f"Unknown agent config type: {type(config).__name__!r}. "
                "Expected one of: ClaudeCodeConfig, AiderConfig, OpenAIConfig, "
                "GeminiConfig, CustomConfig."
            )
