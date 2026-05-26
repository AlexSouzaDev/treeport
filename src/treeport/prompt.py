"""
Prompt resolution pipeline:

  1. Load raw text (inline string or file)
  2. Substitute {{KEY}} placeholders with prompt_args
  3. Expand !`command` shell expressions (run inside sandbox)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
_SHELL_EXPR_RE = re.compile(r"!`([^`]+)`")


def load_prompt(prompt: str | None, prompt_file: str | Path | None) -> str:
    """Return raw prompt text from either an inline string or a file path."""
    if prompt is not None:
        return prompt
    if prompt_file is not None:
        return Path(prompt_file).read_text(encoding="utf-8")
    raise ValueError("No prompt source provided.")


def substitute_args(text: str, args: dict[str, str]) -> str:
    """Replace ``{{KEY}}`` placeholders with values from *args*.

    Raises ``KeyError`` for placeholders with no matching argument.
    Emits a warning for unused arguments.
    """
    found_keys: set[str] = set()

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        found_keys.add(key)
        if key not in args:
            raise KeyError(
                f"Prompt placeholder '{{{{{key}}}}}' has no matching prompt_args entry."
            )
        return args[key]

    result = _PLACEHOLDER_RE.sub(_replace, text)

    unused = set(args.keys()) - found_keys
    if unused:
        import warnings

        warnings.warn(
            f"Unused prompt_args keys: {', '.join(sorted(unused))}",
            UserWarning,
            stacklevel=2,
        )

    return result


def expand_shell_expressions(text: str, cwd: str | Path | None = None) -> str:
    """Replace ``!`command``` expressions with the command's stdout.

    Commands are run in *cwd* (the sandbox working directory when called
    from inside the container, or the repo root during local preview).
    Raises ``RuntimeError`` if any command exits with a non-zero code.
    """

    def _run(match: re.Match) -> str:
        command = match.group(1)
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Shell expression failed (exit {result.returncode}): `{command}`\n"
                f"stderr: {result.stderr.strip()}"
            )
        return result.stdout.rstrip("\n")

    return _SHELL_EXPR_RE.sub(_run, text)


def resolve_prompt(
    *,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: dict[str, str],
    cwd: str | Path | None = None,
) -> str:
    """Full resolution pipeline: load → expand shell expressions → substitute args.

    Shell expansion runs first so that prompt_args values are never interpreted
    as shell syntax — preventing injection via metacharacters like ``$(cmd)``.
    """
    raw = load_prompt(prompt, prompt_file)
    after_shell = expand_shell_expressions(raw, cwd=cwd)
    return substitute_args(after_shell, prompt_args)
