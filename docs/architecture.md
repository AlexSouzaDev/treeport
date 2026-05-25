# Architecture

This page explains how treeport works internally — the worktree + bind-mount design, the agent provider abstraction, and the two execution modes.

---

## The core loop

```
treeport run
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  core.py — run()                                       │
│                                                        │
│  1. Resolve repo root (git search_parent_directories)  │
│  2. Build AgentProvider from RunOptions.agent          │
│  3. Load env from .treeport/.env                       │
│  4. Create git worktree  ──────────────────────────┐   │
│  5. [Container mode] verify/build Docker image     │   │
│  6. Copy files into worktree                       │   │
│  7. Run on_sandbox_ready hooks                     │   │
│  8. Resolve prompt (substitute + expand)           │   │
│                                                    │   │
│  ┌─ Iteration loop ──────────────────────────────┐ │   │
│  │                                               │ │   │
│  │  provider.run_iteration()                     │ │   │
│  │       │                                       │ │   │
│  │       ▼                                       │ │   │
│  │  IterationResult { stdout, signal_detected }  │ │   │
│  │       │                                       │ │   │
│  │  signal detected or max_iterations reached?   │ │   │
│  │       │ yes → break                           │ │   │
│  │       │ no  → continue                        │ │   │
│  └───────┼───────────────────────────────────────┘ │   │
│          │                                          │   │
│  9. Collect commits from worktree  ◄────────────────┘   │
│  10. Fast-forward merge → target branch                 │
│  11. Clean up worktree                                  │
│  12. Return RunResult                                   │
└────────────────────────────────────────────────────────┘
```

---

## Git worktree design

treeport uses `git worktree add` to create an isolated checkout of your repository on a fresh branch:

```bash
# What treeport does internally:
git worktree add -b treeport-tmp/a1b2c3d4 .treeport/worktrees/a1b2c3d4 HEAD
```

**Why worktrees instead of cloning?**

- A worktree is a real checkout — no bundling, no copying, no tarball overhead.
- The worktree shares the `.git` object store with the main repo. Git operations inside the container (commits, branches) are visible on the host immediately.
- Cleanup is a single `git worktree remove` command.

**Directory layout during a run:**

```
your-repo/
├── .git/
├── .treeport/
│   ├── worktrees/
│   │   └── a1b2c3d4/          ← bind-mounted into Docker
│   │       ├── src/
│   │       ├── tests/
│   │       └── .treeport_prompt.md
│   └── logs/
│       └── run-a1b2c3d4-20260101-120000.log
└── src/
    └── ...                    ← your working directory — untouched
```

**After the run:**

```bash
# treeport does this:
git fetch . treeport-tmp/a1b2c3d4:agent/fix-42   # fast-forward merge
git worktree remove --force .treeport/worktrees/a1b2c3d4
git branch -D treeport-tmp/a1b2c3d4
```

---

## Bind-mount: zero-sync architecture

The worktree is bind-mounted into the Docker container:

```
Host filesystem           Docker container
─────────────────         ──────────────────────────────
.treeport/worktrees/  ←──  /home/agent/repo  (read-write)
    a1b2c3d4/
```

**Key properties:**

- The agent writes files directly to the host filesystem — there is no sync step.
- Git commits made inside the container are visible on the host immediately because the worktree's `.git` file points to the shared object store.
- The container uses a non-root `agent` user (required by Claude Code).

---

## Two execution modes

### Container mode

Used by `claude-code`, `aider`, and `custom` providers.

```
ContainerRunner.container_exec()
    │
    ├── docker run --rm \
    │       -v worktree:/home/agent/repo \
    │       -e ANTHROPIC_API_KEY=... \
    │       --user agent \
    │       treeport:myrepo \
    │       sh -c "claude --model ... --print ... $(cat .treeport_prompt.md)"
    │
    └── stream logs → detect completion_signal → return (stdout, bool)
```

The provider supplies `dockerfile_snippet()` (what to `RUN` during `treeport init`) and `_build_command()` (what to execute inside the container). `ContainerRunner` handles all Docker SDK calls.

### API mode

Used by `openai` and `gemini` providers. No Docker container is involved.

```
OpenAIProvider.run_iteration()
    │
    ├── 1. file_collector.collect_context(worktree_path)
    │       Walk worktree, filter by include/exclude patterns
    │       Respect token budget — prioritise git-changed files
    │       Return WorktreeContext with file contents
    │
    ├── 2. Build API message
    │       system: SYSTEM_PROMPT (file patch format instructions)
    │       user:   ## Repository files\n{ctx.to_prompt_block()}\n\n## Task\n{prompt}
    │
    ├── 3. Call OpenAI/Gemini API
    │
    ├── 4. file_collector.apply_file_patches(response, worktree_path)
    │       Parse <file path="...">content</file> blocks
    │       Write each file to worktree_path/rel_path
    │
    ├── 5. git add -A && git commit -m "treeport(openai): ..."
    │
    └── 6. Return IterationResult(stdout=response, files_modified=[...])
```

The file patch format instructs the model to return complete file contents:

```
<file path="src/auth.py">
...complete new file contents...
</file>
```

---

## Agent provider abstraction

All five agent backends implement the `AgentProvider` ABC:

```python
class AgentProvider(ABC):
    @property
    @abstractmethod
    def execution_mode(self) -> Literal["container", "api"]: ...

    @abstractmethod
    async def run_iteration(
        self, *, prompt, worktree_path, env, completion_signal,
        image_name, container_runner,
    ) -> IterationResult: ...

    @abstractmethod
    def dockerfile_snippet(self) -> str: ...

    @abstractmethod
    def required_env_vars(self) -> list[str]: ...
```

`core.py` is 100% provider-agnostic — it only calls `run_iteration()`. The registry maps `AgentConfig` → concrete provider:

```python
# registry.py
match config:
    case ClaudeCodeConfig(): return ClaudeCodeProvider(model=config.model)
    case AiderConfig():       return AiderProvider(model=config.model, ...)
    case OpenAIConfig():      return OpenAIProvider(model=config.model, ...)
    case GeminiConfig():      return GeminiProvider(model=config.model, ...)
    case CustomConfig():      return CustomProvider(command=config.command, ...)
```

---

## File collector (API mode)

`file_collector.collect_context()` assembles the source files sent to API-based providers:

1. **Walk** the worktree with `include_patterns` / `exclude_patterns` (supports `**` globs).
2. **Prioritise** git-modified and untracked files (so the relevant context fits within the budget).
3. **Token budget** — files are added until `max_tokens` is reached; oversized files are skipped (not truncated).
4. **Serialise** to `<file path="...">content</file>` blocks.

Default include patterns cover Python, TypeScript, JavaScript, Go, Rust, Java, Kotlin, Ruby, C/C++, Markdown, TOML, YAML, JSON, and common config files. Default excludes cover `node_modules`, `__pycache__`, `.venv`, `dist`, `.git`, and generated files.

---

## Prompt resolution pipeline

```
prompt / prompt_file
        │
        ▼
   load_prompt()          ← read file or return inline string
        │
        ▼
  substitute_args()       ← replace {{KEY}} with prompt_args values
        │
        ▼
expand_shell_expressions() ← replace !`cmd` with stdout of cmd
        │
        ▼
   resolved_prompt         → sent to agent
```

All three steps run on the **host** before any container starts (shell expressions in `expand_shell_expressions` run in the worktree directory).

---

## Adding a new agent provider

1. Create `src/treeport/agents/my_agent.py` implementing `AgentProvider`.
2. Add a config class to `types.py` with `type: Literal["my-agent"]`.
3. Add the new config to the `AgentConfig` union in `types.py`.
4. Add a `case MyAgentConfig():` branch in `registry.py`.
5. Export the provider and config from `agents/__init__.py` and `__init__.py`.
6. Add tests in `tests/test_agents.py`.
