"""Tests for prompt.py — load, substitute, expand."""

from __future__ import annotations

import textwrap
from pathlib import Path
import pytest

from treeport.prompt import (
    load_prompt,
    substitute_args,
    expand_shell_expressions,
    resolve_prompt,
)


# ── load_prompt ────────────────────────────────────────────────────────


def test_load_prompt_inline():
    assert load_prompt("hello world", None) == "hello world"


def test_load_prompt_file(tmp_path: Path):
    f = tmp_path / "p.md"
    f.write_text("# My Prompt\n")
    assert load_prompt(None, f) == "# My Prompt\n"


def test_load_prompt_neither_raises():
    with pytest.raises(ValueError):
        load_prompt(None, None)


# ── substitute_args ────────────────────────────────────────────────────


def test_substitute_basic():
    result = substitute_args("Fix issue #{{NUMBER}}", {"NUMBER": "42"})
    assert result == "Fix issue #42"


def test_substitute_missing_key_raises():
    with pytest.raises(KeyError, match="MISSING"):
        substitute_args("{{MISSING}}", {})


def test_substitute_unused_key_warns():
    with pytest.warns(UserWarning, match="EXTRA"):
        substitute_args("no placeholders", {"EXTRA": "value"})


def test_substitute_multiple():
    text = "{{A}} and {{B}}"
    assert substitute_args(text, {"A": "foo", "B": "bar"}) == "foo and bar"


# ── expand_shell_expressions ───────────────────────────────────────────


def test_expand_echo():
    result = expand_shell_expressions("Value: !`echo hello`")
    assert result == "Value: hello"


def test_expand_nonzero_raises():
    with pytest.raises(RuntimeError, match="exit 1"):
        expand_shell_expressions("!`exit 1`")


def test_expand_multiple():
    result = expand_shell_expressions("!`echo foo` !`echo bar`")
    assert result == "foo bar"


# ── resolve_prompt (full pipeline) ────────────────────────────────────


def test_resolve_full(tmp_path: Path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Issue #{{N}}: !`echo done`")
    result = resolve_prompt(
        prompt=None,
        prompt_file=prompt_file,
        prompt_args={"N": "7"},
    )
    assert result == "Issue #7: done"
