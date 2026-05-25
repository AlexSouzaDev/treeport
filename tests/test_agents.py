"""
Tests for the multi-agent system.

Covers:
- AgentConfig Pydantic validation
- Registry resolution (config → provider)
- Provider properties (execution_mode, required_env_vars, dockerfile_snippet)
- File collector (walk, token budget, patch application)
- RunOptions with agent configs
"""

from __future__ import annotations

from pathlib import Path
import pytest

from treeport.types import (
    AiderConfig,
    ClaudeCodeConfig,
    CustomConfig,
    GeminiConfig,
    OpenAIConfig,
    RunOptions,
)
from treeport.agents import (
    AiderProvider,
    ClaudeCodeProvider,
    CustomProvider,
    GeminiProvider,
    OpenAIProvider,
    provider_from_config,
)
from treeport.file_collector import (
    WorktreeContext,
    apply_file_patches,
    collect_context,
    FileEntry,
)


# ── AgentConfig validation ─────────────────────────────────────────────


def test_claude_code_config_defaults():
    cfg = ClaudeCodeConfig()
    assert cfg.type == "claude-code"
    assert cfg.model == "claude-opus-4-5"


def test_aider_config_defaults():
    cfg = AiderConfig()
    assert cfg.type == "aider"
    assert cfg.model == "gpt-4o"
    assert cfg.extra_args == []
    assert cfg.auto_commit is True


def test_openai_config_defaults():
    cfg = OpenAIConfig()
    assert cfg.type == "openai"
    assert cfg.model == "gpt-4o"
    assert cfg.max_tokens == 4096
    assert cfg.context_token_budget == 80_000


def test_gemini_config_defaults():
    cfg = GeminiConfig()
    assert cfg.type == "gemini"
    assert cfg.model == "gemini-2.0-flash"


def test_custom_config_required_command():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CustomConfig()  # command is required

    cfg = CustomConfig(command="my-agent --prompt {prompt_file}")
    assert cfg.type == "custom"


def test_run_options_default_agent():
    opts = RunOptions(prompt="do stuff")
    assert isinstance(opts.agent, ClaudeCodeConfig)


def test_run_options_aider_agent():
    opts = RunOptions(
        prompt="fix it",
        agent=AiderConfig(model="gemini/gemini-2.0-flash"),
    )
    assert isinstance(opts.agent, AiderConfig)
    assert opts.agent.model == "gemini/gemini-2.0-flash"


def test_run_options_agent_discriminator_from_dict():
    opts = RunOptions(
        prompt="x",
        agent={"type": "openai", "model": "gpt-4o-mini"},
    )
    assert isinstance(opts.agent, OpenAIConfig)
    assert opts.agent.model == "gpt-4o-mini"


# ── Registry ───────────────────────────────────────────────────────────


def test_registry_claude_code():
    p = provider_from_config(ClaudeCodeConfig(model="claude-haiku-4-5"))
    assert isinstance(p, ClaudeCodeProvider)
    assert p.model == "claude-haiku-4-5"


def test_registry_aider():
    p = provider_from_config(AiderConfig(model="gpt-4o-mini"))
    assert isinstance(p, AiderProvider)
    assert p.model == "gpt-4o-mini"


def test_registry_openai():
    p = provider_from_config(OpenAIConfig())
    assert isinstance(p, OpenAIProvider)


def test_registry_gemini():
    p = provider_from_config(GeminiConfig())
    assert isinstance(p, GeminiProvider)


def test_registry_custom():
    p = provider_from_config(CustomConfig(command="echo {prompt_file}"))
    assert isinstance(p, CustomProvider)


# ── Provider properties ────────────────────────────────────────────────


@pytest.mark.parametrize("provider,expected_mode", [
    (ClaudeCodeProvider(), "container"),
    (AiderProvider(), "container"),
    (CustomProvider(command="echo"), "container"),
    (OpenAIProvider(), "api"),
    (GeminiProvider(), "api"),
])
def test_execution_modes(provider, expected_mode):
    assert provider.execution_mode == expected_mode


def test_claude_required_env_vars():
    assert "ANTHROPIC_API_KEY" in ClaudeCodeProvider().required_env_vars()


def test_aider_env_vars_by_model():
    assert "OPENAI_API_KEY" in AiderProvider(model="gpt-4o").required_env_vars()
    assert "ANTHROPIC_API_KEY" in AiderProvider(model="claude-opus-4-5").required_env_vars()
    assert "GEMINI_API_KEY" in AiderProvider(model="gemini/gemini-2.0-flash").required_env_vars()
    assert AiderProvider(model="ollama/codellama").required_env_vars() == []


def test_openai_required_env_vars():
    assert "OPENAI_API_KEY" in OpenAIProvider().required_env_vars()


def test_gemini_required_env_vars():
    assert "GEMINI_API_KEY" in GeminiProvider().required_env_vars()


def test_api_providers_have_empty_dockerfile_snippet():
    assert OpenAIProvider().dockerfile_snippet() == ""
    assert GeminiProvider().dockerfile_snippet() == ""


def test_container_providers_have_dockerfile_snippets():
    assert "claude-code" in ClaudeCodeProvider().dockerfile_snippet()
    assert "aider" in AiderProvider().dockerfile_snippet()


# ── File collector ─────────────────────────────────────────────────────


def test_collect_context_basic(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Docs")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("ignored")

    ctx = collect_context(tmp_path)

    paths = {f.path for f in ctx.files}
    assert "main.py" in paths
    assert "README.md" in paths
    assert not any("node_modules" in p for p in paths)


def test_collect_context_token_budget(tmp_path: Path):
    # Create a file much larger than the budget
    big = "x" * 10_000
    (tmp_path / "big.py").write_text(big)
    (tmp_path / "small.py").write_text("x = 1")

    ctx = collect_context(tmp_path, max_tokens=100)

    # Big file should be excluded, small one should fit
    paths = {f.path for f in ctx.files}
    assert "small.py" in paths
    assert ctx.truncated  # big file was skipped


def test_worktree_context_to_prompt_block():
    ctx = WorktreeContext(files=[
        FileEntry(path="foo.py", content="x = 1", token_estimate=2),
    ])
    block = ctx.to_prompt_block()
    assert '<file path="foo.py">' in block
    assert "x = 1" in block


def test_worktree_context_truncation_note():
    ctx = WorktreeContext(files=[], truncated=True)
    assert "omitted" in ctx.to_prompt_block()


def test_apply_file_patches(tmp_path: Path):
    response = '''\
Here are the changes:

<file path="src/foo.py">
def hello():
    return "world"
</file>

<file path="README.md">
# Updated
</file>
'''
    written = apply_file_patches(response, tmp_path)

    assert "src/foo.py" in written
    assert "README.md" in written
    assert (tmp_path / "src" / "foo.py").read_text() == 'def hello():\n    return "world"'
    assert (tmp_path / "README.md").read_text() == "# Updated"


def test_apply_file_patches_no_blocks(tmp_path: Path):
    written = apply_file_patches("No changes needed. <no-changes/>", tmp_path)
    assert written == []
