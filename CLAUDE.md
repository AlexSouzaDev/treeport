# CLAUDE.md

Guidelines for Claude Code agents working on the treeport repository.

## Architecture

- `src/treeport/types.py` — Pydantic v2 models (`RunOptions`, `RunResult`, etc.)
- `src/treeport/prompt.py` — Prompt loading, `{{KEY}}` substitution, `!\\`cmd\\`` expansion
- `src/treeport/git_manager.py` — Git worktree create/merge/cleanup via GitPython
- `src/treeport/docker_runner.py` — Docker SDK wrapper; hooks, agent execution, env loading
- `src/treeport/logging.py` — Rich-based terminal and file logging
- `src/treeport/core.py` — `run()` — the main orchestration loop
- `src/treeport/cli.py` — Typer CLI (`treeport init`, `build-image`, `remove-image`, `run`)

## Dev commands

```bash
hatch run test        # pytest
hatch run lint        # ruff check
hatch run typecheck   # mypy --strict
```

## Key constraints

- Python 3.11+ only; use `from __future__ import annotations` in all modules.
- All public async functions are `async def`; use `asyncio.get_event_loop().run_in_executor` for blocking Docker/Git calls.
- `RunOptions` is the single source of truth — never accept raw kwargs in `run()`.
- The Docker container always runs as the non-root `agent` user.
- Do not modify `.treeport/` scaffolded files without a corresponding update to the template strings in `cli.py`.

## Testing

- Tests live in `tests/`; use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Mock Docker and Git calls with `pytest-mock`; never require a live Docker daemon in unit tests.
- `conftest.py` provides a `tmp_git_repo` fixture for git tests.
