"""
treeport.agents — all agent provider classes and the registry.
"""

from treeport.agents.base import AgentProvider, IterationResult
from treeport.agents.claude_code import ClaudeCodeProvider
from treeport.agents.aider import AiderProvider
from treeport.agents.openai_agent import OpenAIProvider
from treeport.agents.gemini_agent import GeminiProvider
from treeport.agents.custom import CustomProvider
from treeport.agents.registry import provider_from_config

__all__ = [
    "AgentProvider",
    "IterationResult",
    "ClaudeCodeProvider",
    "AiderProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "CustomProvider",
    "provider_from_config",
]
