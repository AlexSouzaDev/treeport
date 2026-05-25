![treeport banner](banner.png)

# treeport

> **Docker-based AI coding agent orchestrator** — Create git worktrees. Spin up isolated containers. Run your agent. Merge back. Repeat.

[![CI](https://github.com/yourusername/treeport/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/treeport/actions)
[![PyPI](https://img.shields.io/pypi/v/treeport)](https://pypi.org/project/treeport/)
[![Python](https://img.shields.io/pypi/pyversions/treeport)](https://pypi.org/project/treeport/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is treeport?

treeport orchestrates AI coding agents — Claude Code, Aider, OpenAI, Gemini, or your own custom agent — inside **isolated Docker containers** backed by **git worktrees**.

Every run follows the same four-step loop:

| Step | What happens |
|------|-------------|
| **1. Worktree** | A fresh git worktree is created on a new branch — no risk to `main` |
| **2. Container** | The worktree is bind-mounted into a Docker container — fully isolated |
| **3. Agent** | Your chosen AI agent runs inside the container and implements the task |
| **4. Merge back** | Commits are fast-forward merged to the target branch; the worktree is cleaned up |

Built with modern Python: `asyncio` · `Pydantic v2` · `Typer CLI` · `Docker SDK`

---

## Prerequisites

- Python ≥ 3.11
- [Docker Desktop](https://www.docker.com/) (for container-based agents)
- [Git](https://git-scm.com/)

---

## Installation

```bash
pip install treeport
```

---

## Quick start

### 1. Scaffold your project

Run this once inside any git repo:

```bash
treeport init
```

This creates a `.treeport/` directory:

```
.treeport/
├── Dockerfile        # Sandbox environment — customise freely
├── prompt.md         # Agent instructions
├── .env.example      # API key placeholders
├── main.py           # Programmatic entry point
└── .gitignore        # Ignores .env, worktrees/, logs/
```

### 2. Add your API key

```bash
cp .treeport/.env.example .treeport/.env
# Edit .treeport/.env — add ANTHROPIC_API_KEY (or whichever key your agent needs)
```

### 3. Write your prompt

Edit `.treeport/prompt.md`:

```markdown
Fix all failing tests in the repository.
Run the test suite and make sure everything passes before finishing.
When complete, output: <promise>COMPLETE</promise>
```

### 4. Run

```bash
# Via CLI
treeport run

# Or programmatically
python .treeport/main.py
```

---

## CLI reference

```
 _                                  _
| |                                | |
| |_ _ __ ___  ___ _ __   ___  _ __| |_
| __| '__/ _ \/ _ \ '_ \ / _ \| '__| __|
| |_| | |  __/  __/ |_) | (_) | |  | |_
 \__|_|  \___|\___| .__/ \___/|_|   \__|
                  | |
                  |_|
 [Git Worktree <-> Docker AI Orchestrator]
```

| Command | Description |
|---------|-------------|
| `treeport init` | Scaffold `.treeport/` and build the Docker image |
| `treeport run` | Run the agent (see flags below) |
| `treeport build-image` | Rebuild the Docker image after Dockerfile changes |
| `treeport remove-image` | Remove the Docker sandbox image |
| `treeport --version` | Print version |

### `treeport run` flags

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt-file` / `-f` | `.treeport/prompt.md` | Path to prompt file |
| `--agent` / `-a` | `claude-code` | Agent backend (see below) |
| `--model` / `-m` | *(agent default)* | Model string |
| `--max-iterations` / `-n` | `1` | Max agent iterations |
| `--branch` / `-b` | `treeport/<uuid>` | Target git branch |
| `--name` | — | Display name for this run |
| `--image-name` | `treeport:<repo>` | Docker image name |
| `--custom-command` | — | Shell command for `--agent custom` |

---

## Supported agents

treeport ships five agent backends. Switch between them with `--agent`:

### Claude Code *(default)*

Runs [Claude Code](https://docs.anthropic.com/claude-code) inside Docker.

```bash
treeport run --agent claude-code --model claude-opus-4-5
```

```python
from treeport import run
from treeport.types import RunOptions, ClaudeCodeConfig

result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
    agent=ClaudeCodeConfig(model="claude-opus-4-5"),
))
```

**Requires:** `ANTHROPIC_API_KEY`

---

### Aider *(multi-model, Docker)*

[Aider](https://aider.chat) supports virtually every major model through a single CLI. Just change the `model` string — the Docker image stays the same.

```bash
# GPT-4o
treeport run --agent aider --model gpt-4o

# Gemini
treeport run --agent aider --model gemini/gemini-2.0-flash

# DeepSeek
treeport run --agent aider --model deepseek/deepseek-coder

# Local Ollama (no API key needed)
treeport run --agent aider --model ollama/codellama
```

```python
from treeport.types import AiderConfig

agent=AiderConfig(model="gpt-4o", auto_commit=True)
```

| Model prefix | Required env var |
|---|---|
| `claude-*` | `ANTHROPIC_API_KEY` |
| `gpt-*`, `o1`, `o3-*` | `OPENAI_API_KEY` |
| `gemini/*` | `GEMINI_API_KEY` |
| `deepseek/*` | `DEEPSEEK_API_KEY` |
| `ollama/*` | *(none)* |

---

### OpenAI *(API-direct, no Docker)*

Calls the OpenAI API directly from the host. Collects source files from the worktree as context, applies `<file>` block patches, and commits.

```bash
treeport run --agent openai --model gpt-4o
```

```python
from treeport.types import OpenAIConfig

agent=OpenAIConfig(
    model="gpt-4o",
    context_token_budget=80_000,
    include_patterns=["**/*.py"],
)
```

**Requires:** `OPENAI_API_KEY` · No Docker needed

---

### Gemini *(API-direct, no Docker)*

Calls the Google Gemini API directly. Same file-patch workflow as the OpenAI provider.

```bash
treeport run --agent gemini --model gemini-2.0-flash
```

```python
from treeport.types import GeminiConfig

agent=GeminiConfig(model="gemini-2.0-flash", context_token_budget=100_000)
```

**Requires:** `GEMINI_API_KEY` · No Docker needed · `pip install google-generativeai`

---

### Custom *(your own command, Docker)*

Run any shell command inside the Docker sandbox. Use `{prompt_file}`, `{model}`, and `{repo}` placeholders.

```bash
treeport run --agent custom --custom-command "my-agent --prompt {prompt_file}"
```

```python
from treeport.types import CustomConfig

agent=CustomConfig(
    command="my-agent --model {model} --prompt {prompt_file}",
    model="my-model",
    dockerfile_snippet_text="RUN pip install my-agent",
)
```

---

## Programmatic API

### `run(options) → RunResult`

```python
import asyncio
from treeport import run
from treeport.types import RunOptions, AiderConfig, StdoutLogging

async def main():
    result = await run(RunOptions(
        prompt_file=".treeport/prompt.md",
        prompt_args={"ISSUE": "42"},       # fills {{ISSUE}} in prompt
        agent=AiderConfig(model="gpt-4o"),
        max_iterations=5,
        branch="agent/fix-42",
        completion_signal="<promise>COMPLETE</promise>",
        timeout_seconds=1200,
        hooks={"on_sandbox_ready": [{"command": "pip install -r requirements.txt"}]},
        copy_to_sandbox=[".env"],
        logging=StdoutLogging(),
    ))

    print(f"Iterations run:  {result.iterations_run}")
    print(f"Completed:       {result.was_completion_signal_detected}")
    print(f"Agent used:      {result.agent_type}")
    print(f"Branch:          {result.branch}")
    print(f"Commits:         {[c.sha[:8] for c in result.commits]}")
    print(f"Files modified:  {result.files_modified}")   # API-mode only

asyncio.run(main())
```

### `RunOptions` reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | `str` | — | Inline prompt *(exclusive with `prompt_file`)* |
| `prompt_file` | `str \| Path` | — | Path to a `.md` prompt file |
| `prompt_args` | `dict[str, str]` | `{}` | Values for `{{KEY}}` placeholders in the prompt |
| `agent` | `AgentConfig` | `ClaudeCodeConfig()` | Which agent to use |
| `max_iterations` | `int` | `1` | Max agent loops before stopping |
| `completion_signal` | `str` | `<promise>COMPLETE</promise>` | String that stops the loop early |
| `timeout_seconds` | `int` | `1200` | Wall-clock timeout for the entire run |
| `branch` | `str` | `treeport/<uuid>` | Target git branch |
| `image_name` | `str` | `treeport:<repo-dir>` | Docker image name |
| `name` | `str` | — | Display name shown in logs |
| `hooks` | `Hooks` | — | `on_sandbox_ready` hook list |
| `copy_to_sandbox` | `list[str]` | `[]` | Host-relative files to copy into the worktree |
| `logging` | `FileLogging \| StdoutLogging` | `FileLogging()` | Log destination |

### `RunResult` reference

| Field | Type | Description |
|-------|------|-------------|
| `iterations_run` | `int` | Number of iterations executed |
| `was_completion_signal_detected` | `bool` | Whether the agent signalled completion |
| `stdout` | `str` | Combined agent output |
| `commits` | `list[CommitInfo]` | Commits created during the run |
| `branch` | `str` | Target branch name |
| `agent_type` | `str` | Which agent was used |
| `files_modified` | `list[str]` | Files written (API-mode providers only) |
| `log_file_path` | `Path \| None` | Path to the log file (file logging only) |

---

## Prompt features

### Dynamic context with `` !`command` ``

Commands run inside the sandbox after `on_sandbox_ready` hooks complete:

```markdown
## Open issues
!`gh issue list --state open --json number,title,body --limit 20`

## Recent commits
!`git log --oneline -10`

## Current test failures
!`python -m pytest --tb=short 2>&1 | tail -40`
```

### Argument substitution with `{{KEY}}`

```markdown
Work on issue #{{ISSUE_NUMBER}} with priority {{PRIORITY}}.
```

```python
RunOptions(
    prompt_file=".treeport/prompt.md",
    prompt_args={"ISSUE_NUMBER": "42", "PRIORITY": "high"},
)
```

### Early exit with `<promise>COMPLETE</promise>`

Tell the agent in your prompt to output `<promise>COMPLETE</promise>` when done. treeport stops the iteration loop immediately.

---

## How it works

treeport uses a **worktree + bind-mount** architecture:

1. **Worktree** — `git worktree add` creates a real checkout at `.treeport/worktrees/<slug>/`. No file copying or bundling.
2. **Bind-mount** — The worktree directory is bind-mounted into the container. The agent writes directly to the host filesystem through the mount.
3. **No sync needed** — Commits appear on the host instantly. There are no sync-in / sync-out steps.
4. **Merge back** — After the run, the temp branch is fast-forward merged into the target branch and the worktree is removed.

---

## Project structure

```
src/treeport/
├── __init__.py          Public API surface
├── core.py              run() orchestration loop
├── types.py             Pydantic models (RunOptions, RunResult, AgentConfig…)
├── prompt.py            Prompt loading, {{KEY}} substitution, !`cmd` expansion
├── git_manager.py       Worktree create / merge / cleanup
├── docker_runner.py     Docker SDK wrapper — hooks, container_exec
├── file_collector.py    Smart worktree context assembly for API providers
├── logging.py           Rich terminal + file logging
├── cli.py               Typer CLI
└── agents/
    ├── base.py          AgentProvider ABC + IterationResult
    ├── claude_code.py   Claude Code (container)
    ├── aider.py         Aider (container, all models)
    ├── openai_agent.py  OpenAI (API-direct)
    ├── gemini_agent.py  Gemini (API-direct)
    ├── custom.py        Custom command (container)
    └── registry.py      AgentConfig → provider dispatch
```

---

## Development

```bash
pip install hatch

hatch run test        # pytest (48 tests)
hatch run lint        # ruff check
hatch run typecheck   # mypy --strict
```

---

## License

MIT — see [LICENSE](LICENSE)
