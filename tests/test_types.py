"""Tests for RunOptions Pydantic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from treeport.types import RunOptions, StdoutLogging, FileLogging, ClaudeCodeConfig


def test_prompt_required():
    with pytest.raises(ValidationError, match="prompt"):
        RunOptions()  # neither prompt nor prompt_file


def test_prompt_exclusive():
    with pytest.raises(ValidationError, match="mutually exclusive"):
        RunOptions(prompt="hello", prompt_file="p.md")


def test_prompt_inline_valid():
    opts = RunOptions(prompt="do the thing")
    assert opts.prompt == "do the thing"
    assert opts.max_iterations == 1  # default


def test_prompt_file_valid(tmp_path):
    f = tmp_path / "p.md"
    f.write_text("hello")
    opts = RunOptions(prompt_file=f)
    assert opts.prompt_file == f


def test_defaults():
    opts = RunOptions(prompt="x")
    # model is now on the agent config
    assert isinstance(opts.agent, ClaudeCodeConfig)
    assert opts.agent.model == "claude-opus-4-5"
    assert opts.completion_signal == "<promise>COMPLETE</promise>"
    assert opts.timeout_seconds == 1200
    assert opts.max_iterations == 1
    assert opts.hooks.on_sandbox_ready == []
    assert opts.copy_to_sandbox == []
    assert isinstance(opts.logging, FileLogging)


def test_stdout_logging():
    opts = RunOptions(prompt="x", logging=StdoutLogging())
    assert opts.logging.type == "stdout"


def test_max_iterations_must_be_positive():
    with pytest.raises(ValidationError):
        RunOptions(prompt="x", max_iterations=0)
