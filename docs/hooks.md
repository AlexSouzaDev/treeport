# Hooks

treeport provides lifecycle hooks to prepare the sandbox before the agent starts, and a mechanism to copy files from the host into the worktree.

---

## `on_sandbox_ready`

Runs **inside the container** after the worktree is bind-mounted but before the agent starts. Use it for dependency installation, build steps, or any other setup the agent needs.

Each hook is a shell command. Hooks run sequentially. If any command exits with a non-zero code, the entire run fails immediately.

### Python API

```python
from treeport.types import RunOptions, Hooks, Hook

result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
    hooks=Hooks(
        on_sandbox_ready=[
            Hook(command="pip install -r requirements.txt"),
            Hook(command="npm install"),
            Hook(command="python -m pytest --collect-only -q"),  # verify setup
        ]
    ),
))
```

### CLI

The CLI does not expose hooks directly. Use the programmatic API in `.treeport/main.py` for hook configuration.

### Common hook patterns

**Install Python dependencies:**
```python
Hook(command="pip install -r requirements.txt")
```

**Install Node.js dependencies:**
```python
Hook(command="npm install")
# or
Hook(command="yarn install --frozen-lockfile")
```

**Run database migrations:**
```python
Hook(command="python manage.py migrate --run-syncdb")
```

**Build before the agent runs:**
```python
Hook(command="make build")
```

**Verify the environment is healthy:**
```python
Hook(command="python -c 'import mypackage; print(\"env OK\")'")
```

### Hook fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | `str` | ✅ | Shell command to run inside the container |
| `description` | `str \| None` | | Optional description shown in log output |

---

## `copy_to_sandbox`

Copies files from the **host** into the worktree before the container starts. Useful for secrets and config files that you don't want to commit to git.

```python
result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
    copy_to_sandbox=[
        ".env",              # copies .env → worktree/.env
        "config/local.json", # copies config/local.json → worktree/config/local.json
        "secrets.toml",
    ],
))
```

Paths are **host-relative** to the repo root. The directory structure is preserved inside the worktree.

### Common patterns

**Share the project `.env`:**
```python
copy_to_sandbox=[".env"]
```

**Copy local config that isn't committed:**
```python
copy_to_sandbox=["config/local.yml", ".env.local"]
```

### Notes

- Files are copied **before** `on_sandbox_ready` hooks run, so hooks can reference them.
- Files are copied into the **worktree**, not the container image — they disappear after the run.
- `.treeport/.env` is loaded automatically as environment variables and does **not** need to be in `copy_to_sandbox`.

---

## Hook execution order

The full sandbox preparation sequence:

```
treeport run
    │
    ├── 1. git worktree add (create isolated branch + checkout)
    │
    ├── 2. copy_to_sandbox files → worktree/
    │
    ├── 3. on_sandbox_ready hooks (inside container, sequential)
    │       hook[0]: "pip install -r requirements.txt"
    │       hook[1]: "npm install"
    │       ...
    │
    ├── 4. resolve prompt (substitute args + expand !`cmd` expressions)
    │
    └── 5. agent iteration loop begins
```
