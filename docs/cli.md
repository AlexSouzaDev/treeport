# CLI Reference

treeport ships a full CLI powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).

Every command prints the ASCII banner on startup:

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

---

## `treeport init`

Scaffold the `.treeport/` config directory and build the Docker sandbox image.

```bash
treeport init
treeport init --image-name myproject:agent
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--image-name` | `treeport:<repo-dir>` | Docker image name to build |

**What it creates:**

```
.treeport/
├── Dockerfile        # Customise to add your project's dependencies
├── prompt.md         # Edit this — the agent reads it on every run
├── .env.example      # Copy to .env and fill in your API keys
├── main.py           # Programmatic entry point
└── .gitignore        # Keeps .env, worktrees/, logs/ out of git
```

**Errors if `.treeport/` already exists** to prevent overwriting your customisations. Delete it first if you want to re-scaffold.

---

## `treeport run`

Run the agent. This is the command you'll use most.

```bash
treeport run
treeport run --agent aider --model gpt-4o --max-iterations 5
treeport run --agent openai --model gpt-4o --branch fix/auth-bug
treeport run --agent custom --custom-command "my-agent --prompt {prompt_file}"
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--prompt-file` | `-f` | `.treeport/prompt.md` | Path to the prompt file |
| `--agent` | `-a` | `claude-code` | Agent backend: `claude-code`, `aider`, `openai`, `gemini`, `custom` |
| `--model` | `-m` | *(agent default)* | Model string (overrides the agent's default) |
| `--max-iterations` | `-n` | `1` | Maximum agent iterations |
| `--branch` | `-b` | `treeport/<uuid>` | Target git branch |
| `--name` | | | Display name shown in log output |
| `--image-name` | | `treeport:<repo-dir>` | Docker image name |
| `--custom-command` | | | Shell command (required when `--agent custom`) |

**Agent + model examples:**

```bash
# Claude Code
treeport run --agent claude-code --model claude-opus-4-5
treeport run --agent claude-code --model claude-sonnet-4-5

# Aider (any model)
treeport run --agent aider --model gpt-4o
treeport run --agent aider --model gemini/gemini-2.0-flash
treeport run --agent aider --model ollama/codellama

# API-direct (no Docker)
treeport run --agent openai --model gpt-4o
treeport run --agent gemini --model gemini-2.0-flash

# Custom
treeport run --agent custom --custom-command "aicoder --file {prompt_file}"
```

---

## `treeport build-image`

Rebuild the Docker sandbox image after modifying the `Dockerfile`.

```bash
treeport build-image
treeport build-image --image-name myproject:agent
treeport build-image --dockerfile path/to/Dockerfile
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--image-name` | `treeport:<repo-dir>` | Docker image name to build |
| `--dockerfile` | `.treeport/Dockerfile` | Path to a custom Dockerfile |

**When to use this:** Whenever you add project-specific dependencies to `.treeport/Dockerfile` (e.g., `RUN pip install -r requirements.txt`).

---

## `treeport remove-image`

Remove the Docker sandbox image.

```bash
treeport remove-image
treeport remove-image --image-name myproject:agent
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--image-name` | `treeport:<repo-dir>` | Docker image name to remove |

---

## `treeport --version` / `-V`

Print the installed version and exit.

```bash
treeport --version
# treeport v0.2.0
```

---

## Environment variables

treeport loads API keys and other secrets from `.treeport/.env` automatically. You never need to pass them via CLI flags.

```bash
# .treeport/.env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
GITHUB_TOKEN=ghp_...
```

Variables in `.treeport/.env` are merged with `process.env` — `process.env` takes precedence, so CI secrets work out of the box.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Run completed successfully |
| `1` | Error (bad arguments, Docker not running, timeout, etc.) |
