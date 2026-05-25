# Getting Started

This guide takes you from zero to running your first AI agent in under five minutes.

---

## Prerequisites

- **Python 3.11+**
- **Docker Desktop** — [download here](https://www.docker.com/products/docker-desktop/) (required for container-based agents)
- **Git**

---

## Install

```bash
pip install treeport
```

Verify the install:

```bash
treeport --version
```

---

## Scaffold your project

Run this once inside any git repository:

```bash
cd your-repo
treeport init
```

This creates a `.treeport/` directory with everything you need:

```
.treeport/
├── Dockerfile        # Sandbox environment — customise as needed
├── prompt.md         # Your agent instructions go here
├── .env.example      # API key placeholders
├── main.py           # Programmatic entry point
└── .gitignore        # Ignores .env, worktrees/, logs/
```

> **Note:** `.treeport/` is safe to commit except for `.env`. The scaffolded `.gitignore` handles this automatically.

---

## Add your API key

```bash
cp .treeport/.env.example .treeport/.env
```

Edit `.treeport/.env` and fill in your key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Write your first prompt

Edit `.treeport/prompt.md`:

```markdown
Look at the open TODO comments in the codebase and implement one of them.
Run the tests after to make sure nothing is broken.

When you are done, output: <promise>COMPLETE</promise>
```

---

## Run

```bash
treeport run
```

You'll see the ASCII banner, then live output from the agent. When it finishes, treeport reports the branch and commits created:

```
Run complete — agent: claude-code, 1 iteration(s), 2 commit(s) on treeport/a1b2c3d4
```

Check the result:

```bash
git log treeport/a1b2c3d4 --oneline
git diff main..treeport/a1b2c3d4
```

Merge it when you're happy:

```bash
git merge treeport/a1b2c3d4
```

---

## Next steps

- Change the agent: `treeport run --agent aider --model gpt-4o`
- Run multiple iterations: `treeport run --max-iterations 5`
- Use the Python API: see [API Reference](api.md)
- Understand prompt features: see [Prompts](prompts.md)
