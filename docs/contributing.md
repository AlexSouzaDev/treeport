# Contributing

Contributions are welcome — bug reports, documentation improvements, new agent providers, and new recipes.

---

## Development setup

```bash
# Clone
git clone https://github.com/yourusername/treeport
cd treeport

# Install with dev dependencies
pip install hatch
hatch run test   # verify everything works before you start
```

---

## Project structure

```
src/treeport/
├── __init__.py          Public API — exports from here
├── core.py              run() orchestration loop
├── types.py             All Pydantic models
├── prompt.py            Prompt loading / substitution / shell expansion
├── git_manager.py       Worktree lifecycle
├── docker_runner.py     Docker SDK wrapper
├── file_collector.py    Context assembly for API providers
├── logging.py           Rich terminal + file logging
├── cli.py               Typer CLI
└── agents/
    ├── base.py          AgentProvider ABC
    ├── registry.py      Config → provider dispatch
    ├── claude_code.py
    ├── aider.py
    ├── openai_agent.py
    ├── gemini_agent.py
    └── custom.py

tests/
├── conftest.py          Shared fixtures (tmp_git_repo)
├── test_agents.py       Provider + registry + file collector
├── test_prompt.py       Prompt resolution pipeline
└── test_types.py        RunOptions validation
```

---

## Running tests

```bash
hatch run test              # run all 48 tests
hatch run test -k prompt    # run matching tests only
hatch run test -v           # verbose output
```

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. Docker and live API calls are **not** required — all tests mock or avoid them.

---

## Linting and type checking

```bash
hatch run lint       # ruff check
hatch run typecheck  # mypy --strict
```

Both must pass before submitting a PR.

---

## Adding a new agent provider

1. **Create the provider** in `src/treeport/agents/my_provider.py`:

```python
from treeport.agents.base import AgentProvider, IterationResult

class MyProvider(AgentProvider):

    def __init__(self, model: str = "my-default") -> None:
        self.model = model

    @property
    def execution_mode(self) -> Literal["container"]:   # or "api"
        return "container"

    async def run_iteration(self, *, prompt, worktree_path,
                            env, completion_signal,
                            image_name, container_runner) -> IterationResult:
        from treeport.docker_runner import ContainerRunner
        runner: ContainerRunner = container_runner
        stdout, detected = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: runner.container_exec(
                command=["sh", "-c", f"my-agent --prompt {prompt}"],
                worktree_path=worktree_path,
                env=env,
                completion_signal=completion_signal,
            ),
        )
        return IterationResult(stdout=stdout, completion_signal_detected=detected)

    def dockerfile_snippet(self) -> str:
        return "RUN pip install my-agent\n"

    def required_env_vars(self) -> list[str]:
        return ["MY_AGENT_API_KEY"]
```

2. **Add a config class** to `src/treeport/types.py`:

```python
class MyAgentConfig(BaseModel):
    type: Literal["my-agent"] = "my-agent"
    model: str = "my-default"
```

3. **Add to the union** in `types.py`:

```python
AgentConfig = Annotated[
    ClaudeCodeConfig | AiderConfig | OpenAIConfig | GeminiConfig
    | CustomConfig | MyAgentConfig,   # ← add here
    Field(discriminator="type"),
]
```

4. **Register** in `src/treeport/agents/registry.py`:

```python
from treeport.agents.my_provider import MyProvider

match config:
    ...
    case MyAgentConfig():
        return MyProvider(model=config.model)
```

5. **Export** from `src/treeport/agents/__init__.py` and `src/treeport/__init__.py`.

6. **Write tests** in `tests/test_agents.py` covering config defaults, execution mode, env vars, and dockerfile snippet.

---

## Commit style

```
feat: add MyAgent provider
fix: handle empty prompt_args dict
docs: add parallel agents recipe
test: cover AiderProvider ollama model env var
refactor: simplify file_collector token budget logic
```

---

## Pull request checklist

- [ ] `hatch run test` passes (48+ tests)
- [ ] `hatch run lint` passes
- [ ] `hatch run typecheck` passes
- [ ] New behaviour is covered by tests
- [ ] Docs updated if adding a new feature
