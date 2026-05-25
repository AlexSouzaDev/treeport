"""
File collector for API-based agent providers.

When a provider calls the LLM API directly (no Docker), it needs to supply
the relevant source files as context.  This module handles:

* Collecting files from the worktree (git-tracked + untracked, filtered by
  include/exclude glob patterns)
* Respecting a token budget so huge repos don't blow the context window
* Returning a structured ``WorktreeContext`` ready to be serialised into
  an API message

The output format uses XML-like fenced blocks that most LLMs understand well::

    <file path="src/foo.py">
    ...contents...
    </file>
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path


# ── Types ──────────────────────────────────────────────────────────────


@dataclass
class FileEntry:
    path: str          # relative to worktree root
    content: str
    token_estimate: int


@dataclass
class WorktreeContext:
    files: list[FileEntry] = field(default_factory=list)
    truncated: bool = False
    total_tokens: int = 0

    def to_prompt_block(self) -> str:
        """Serialise files into an XML-fenced block for the API message."""
        parts: list[str] = []
        for f in self.files:
            parts.append(f'<file path="{f.path}">\n{f.content}\n</file>')
        block = "\n\n".join(parts)
        if self.truncated:
            block += "\n\n<!-- Some files were omitted due to context size limits -->"
        return block


# ── Collector ──────────────────────────────────────────────────────────


_DEFAULT_INCLUDE = [
    "**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
    "**/*.go", "**/*.rs", "**/*.java", "**/*.kt", "**/*.rb",
    "**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp",
    "**/*.md", "**/*.toml", "**/*.yaml", "**/*.yml",
    "**/*.json", "**/*.env.example",
    "Dockerfile", "Makefile", "pyproject.toml", "package.json",
]

_DEFAULT_EXCLUDE = [
    "**/node_modules/**", "**/.venv/**", "**/venv/**",
    "**/__pycache__/**", "**/*.pyc",
    "**/.git/**", "**/.treeport/worktrees/**", "**/.treeport/logs/**",
    "**/dist/**", "**/build/**", "**/.next/**",
    "**/*.min.js", "**/*.map",
    "**/*.lock",  # package-lock.json, poetry.lock, etc.
]


def collect_context(
    worktree_path: Path,
    *,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    max_tokens: int = 80_000,
    prioritise_changed: bool = True,
) -> WorktreeContext:
    """
    Walk *worktree_path* and collect source files up to *max_tokens*.

    Args:
        worktree_path: Root of the git worktree.
        include_patterns: Glob patterns for files to include.
        exclude_patterns: Glob patterns for files to exclude.
        max_tokens: Rough token budget (4 chars ≈ 1 token).
        prioritise_changed: If True, git-modified/added files are collected
                            first so they fit within the budget.

    Returns:
        :class:`WorktreeContext` with collected files.
    """
    includes = include_patterns or _DEFAULT_INCLUDE
    excludes = exclude_patterns or _DEFAULT_EXCLUDE

    all_files = _walk(worktree_path, includes, excludes)

    if prioritise_changed:
        changed = _get_changed_files(worktree_path)
        all_files = sorted(
            all_files,
            key=lambda p: (p not in changed, str(p)),
        )

    ctx = WorktreeContext()
    budget = max_tokens

    for abs_path in all_files:
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        tokens = max(1, len(content) // 4)

        if tokens > budget:
            ctx.truncated = True
            continue  # skip this file but keep looking for smaller ones

        rel = str(abs_path.relative_to(worktree_path))
        ctx.files.append(FileEntry(path=rel, content=content, token_estimate=tokens))
        ctx.total_tokens += tokens
        budget -= tokens

    return ctx


# ── Helpers ────────────────────────────────────────────────────────────


def _glob_to_regex(pattern: str) -> re.Pattern:
    """
    Convert a glob pattern (supporting ``**``) to a compiled regex.

    Rules:
    * ``**``  — matches any number of path components, including zero
    * ``*``   — matches any characters except ``/``
    * ``?``   — matches one character except ``/``
    * ``.``   — literal dot
    """
    import re

    def _translate(pat: str) -> str:
        result = ""
        i = 0
        while i < len(pat):
            if pat[i : i + 2] == "**":
                i += 2
                if i < len(pat) and pat[i] == "/":
                    # **/ at start or middle: optional "anything/" prefix
                    i += 1
                    result += "(?:.*/)?"
                else:
                    # ** at end or before non-slash: match everything remaining
                    result += ".*"
            elif pat[i] == "*":
                result += "[^/]*"
                i += 1
            elif pat[i] == "?":
                result += "[^/]"
                i += 1
            else:
                result += re.escape(pat[i])
                i += 1
        return result

    return re.compile(_translate(pattern) + "$")


def _walk(root: Path, includes: list[str], excludes: list[str]) -> list[Path]:
    import re

    inc_re = [_glob_to_regex(p) for p in includes]
    exc_re = [_glob_to_regex(p) for p in excludes]

    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if any(r.match(rel) for r in exc_re):
            continue
        if any(r.match(rel) for r in inc_re):
            results.append(path)
    return results


def _get_changed_files(worktree_path: Path) -> set[Path]:
    """Return absolute paths of files modified/added vs HEAD (best-effort)."""
    try:
        import git

        repo = git.Repo(worktree_path)
        changed: set[Path] = set()

        # Staged + unstaged diffs
        for diff in repo.index.diff(None):
            changed.add(worktree_path / diff.a_path)
        for diff in repo.index.diff("HEAD"):
            changed.add(worktree_path / diff.a_path)

        # Untracked
        for u in repo.untracked_files:
            changed.add(worktree_path / u)

        return changed
    except Exception:
        return set()


# ── XML patch parser ───────────────────────────────────────────────────


def apply_file_patches(response_text: str, worktree_path: Path) -> list[str]:
    """
    Parse ``<file path="...">content</file>`` blocks from an LLM response
    and write each file to *worktree_path*.

    Returns the list of relative file paths that were written.
    """
    import re

    pattern = re.compile(
        r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>',
        re.DOTALL,
    )

    written: list[str] = []
    for match in pattern.finditer(response_text):
        rel_path = match.group(1)
        content = match.group(2)

        abs_path = worktree_path / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        written.append(rel_path)

    return written
