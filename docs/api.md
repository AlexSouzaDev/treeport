# API Reference

treeport exposes a single async function — `run()` — plus a set of Pydantic models for configuration and results.

---

## `run(options) → RunResult`

The main entry point. Orchestrates the full worktree → container → agent → merge loop.

```python
from treeport import run
from treeport.types import RunOptions

result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
))
```

**Accepts:** A `RunOptions` instance **or** a plain `dict` (Pydantic coerces it automatically).

```python
# Dict form — useful for dynamic config
result = await run({
    "prompt": "fix the bug",
    "agent": {"type": "aider", "model": "gpt-4o"},
    "max_iterations": 3,
})
```

---

## `RunOptions`

All orchestration behaviour is controlled through `RunOptions`.

```python
from treeport.types import (
    RunOptions,
    ClaudeCodeConfig,
    AiderConfig,
    OpenAIConfig,
    GeminiConfig,
    CustomConfig,
    Hooks,
    Hook,
    FileLogging,
    StdoutLogging,
)
```

### Full example

```python
result = await run(RunOptions(
    # ── Prompt ──────────────────────────────────────────────────────
    prompt_file=".treeport/prompt.md",       # or: prompt="inline text"
    prompt_args={"ISSUE": "42"},             # fills {{ISSUE}} in prompt

    # ── Agent ───────────────────────────────────────────────────────
    agent=AiderConfig(model="gpt-4o"),       # default: ClaudeCodeConfig()

    # ── Loop control ────────────────────────────────────────────────
    max_iterations=5,
    completion_signal="<promise>COMPLETE</promise>",
    timeout_seconds=1200,

    # ── Git / Docker ─────────────────────────────────────────────────
    branch="agent/fix-42",                  # default: treeport/<uuid>
    image_name="treeport:myproject",        # default: treeport:<repo-dir>
    name="fix-issue-42",                    # display name in logs

    # ── Lifecycle ────────────────────────────────────────────────────
    hooks=Hooks(
        on_sandbox_ready=[
            Hook(command="pip install -r requirements.txt"),
            Hook(command="npm install"),
        ]
    ),
    copy_to_sandbox=[".env", "secrets.json"],

    # ── Logging ──────────────────────────────────────────────────────
    logging=StdoutLogging(),                # or: FileLogging(path="run.log")
))
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | `str \| None` | `None` | Inline prompt. Mutually exclusive with `prompt_file`. |
| `prompt_file` | `str \| Path \| None` | `None` | Path to a `.md` prompt file. Mutually exclusive with `prompt`. |
| `prompt_args` | `dict[str, str]` | `{}` | Values substituted for `{{KEY}}` placeholders in the prompt. |
| `agent` | `AgentConfig` | `ClaudeCodeConfig()` | Which agent backend to use. |
| `max_iterations` | `int` | `1` | Maximum agent iterations before stopping. |
| `completion_signal` | `str` | `"<promise>COMPLETE</promise>"` | String in agent output that stops the loop early. |
| `timeout_seconds` | `int` | `1200` | Wall-clock timeout for the entire run (seconds). |
| `branch` | `str \| None` | `"treeport/<uuid>"` | Target git branch for agent commits. |
| `image_name` | `str \| None` | `"treeport:<repo-dir>"` | Docker image name. |
| `name` | `str \| None` | `None` | Display name shown as prefix in log output. |
| `hooks` | `Hooks` | `Hooks()` | Lifecycle hooks. |
| `copy_to_sandbox` | `list[str]` | `[]` | Host-relative file paths to copy into the worktree before the run starts. |
| `logging` | `FileLogging \| StdoutLogging` | `FileLogging()` | Where to write log output. |

---

## `RunResult`

Returned by `run()`.

```python
result = await run(options)

print(result.iterations_run)                  # int
print(result.was_completion_signal_detected)  # bool
print(result.agent_type)                      # "claude-code" | "aider" | ...
print(result.branch)                          # "agent/fix-42"
print(result.stdout)                          # full combined agent output

for commit in result.commits:
    print(commit.sha, commit.message)

print(result.files_modified)   # ["src/foo.py", ...] — API providers only
print(result.log_file_path)    # Path | None
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `iterations_run` | `int` | Number of iterations that were executed. |
| `was_completion_signal_detected` | `bool` | `True` if the agent emitted the completion signal. |
| `stdout` | `str` | Combined stdout from all iterations. |
| `commits` | `list[CommitInfo]` | Commits created during the run. |
| `branch` | `str` | Target branch name. |
| `agent_type` | `str` | Which agent was used (`"claude-code"`, `"aider"`, etc.). |
| `files_modified` | `list[str]` | Relative paths of files written (API-mode providers only). |
| `log_file_path` | `Path \| None` | Path to the log file (file logging only). |

---

## `CommitInfo`

```python
class CommitInfo(BaseModel):
    sha: str
    message: str | None
```

---

## Agent config models

See [Agents](agents.md) for full field documentation.

```python
from treeport.types import (
    ClaudeCodeConfig,   # type="claude-code"
    AiderConfig,        # type="aider"
    OpenAIConfig,       # type="openai"
    GeminiConfig,       # type="gemini"
    CustomConfig,       # type="custom"
)
```

All five are members of the `AgentConfig` discriminated union. Pydantic resolves the right class from a plain dict using the `"type"` key.

---

## Logging config models

```python
from treeport.types import FileLogging, StdoutLogging

# Write to an auto-generated file under .treeport/logs/
logging = FileLogging()

# Write to a specific file
logging = FileLogging(path=".treeport/logs/my-run.log")

# Print to stdout (good for CI or interactive use)
logging = StdoutLogging()
```

---

## Hooks

```python
from treeport.types import Hooks, Hook

hooks = Hooks(
    on_sandbox_ready=[
        Hook(command="pip install -r requirements.txt"),
        Hook(command="npm install", description="Install JS deps"),
    ]
)
```

`on_sandbox_ready` hooks run **inside the container** after the worktree is mounted and before the agent starts. If any hook exits with a non-zero code, the run fails immediately.

---

## Direct provider instantiation (advanced)

If you need to call a provider directly — for testing, custom orchestration, or building your own loop — you can instantiate providers without going through `run()`:

```python
from treeport.agents import ClaudeCodeProvider, AiderProvider, OpenAIProvider

provider = OpenAIProvider(model="gpt-4o", context_token_budget=50_000)
result = await provider.run_iteration(
    prompt="Fix the bug",
    worktree_path=Path("/path/to/worktree"),
    env={"OPENAI_API_KEY": "sk-..."},
    completion_signal="<promise>COMPLETE</promise>",
)
print(result.stdout)
print(result.files_modified)
```
