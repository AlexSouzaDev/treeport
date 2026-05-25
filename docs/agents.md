# Agents

treeport ships five agent backends. You choose which one to use via `--agent` on the CLI or the `agent` field in `RunOptions`.

---

## Overview

| Agent | Execution | Docker needed | Key requirement |
|-------|-----------|---------------|-----------------|
| [`claude-code`](#claude-code) | Container | ✅ Yes | `ANTHROPIC_API_KEY` |
| [`aider`](#aider) | Container | ✅ Yes | Depends on model |
| [`openai`](#openai) | API direct | ❌ No | `OPENAI_API_KEY` |
| [`gemini`](#gemini) | API direct | ❌ No | `GEMINI_API_KEY` |
| [`custom`](#custom) | Container | ✅ Yes | Depends on tool |

---

## claude-code

The default agent. Runs [Claude Code](https://docs.anthropic.com/claude-code) CLI inside the Docker sandbox.

**CLI:**
```bash
treeport run --agent claude-code --model claude-opus-4-5
treeport run --agent claude-code --model claude-sonnet-4-5
```

**Python:**
```python
from treeport.types import ClaudeCodeConfig

agent = ClaudeCodeConfig(model="claude-opus-4-5")
```

**Config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `"claude-code"` | `"claude-code"` | Discriminator |
| `model` | `str` | `"claude-opus-4-5"` | Claude model string |

**Required env var:** `ANTHROPIC_API_KEY`

**Dockerfile snippet added automatically:**
```dockerfile
RUN npm install -g @anthropic-ai/claude-code
```

---

## aider

Runs [Aider](https://aider.chat) inside Docker. Aider supports virtually every major model provider through a single CLI — change the `model` string to switch providers without rebuilding the image.

**CLI:**
```bash
# OpenAI
treeport run --agent aider --model gpt-4o
treeport run --agent aider --model gpt-4o-mini

# Anthropic
treeport run --agent aider --model claude-opus-4-5
treeport run --agent aider --model claude-sonnet-4-5

# Google
treeport run --agent aider --model gemini/gemini-2.0-flash
treeport run --agent aider --model gemini/gemini-1.5-pro

# DeepSeek
treeport run --agent aider --model deepseek/deepseek-coder

# Local (Ollama — no API key needed)
treeport run --agent aider --model ollama/codellama
treeport run --agent aider --model ollama/llama3
```

**Python:**
```python
from treeport.types import AiderConfig

agent = AiderConfig(
    model="gpt-4o",
    extra_args=["--no-auto-lint"],   # pass extra aider flags
    auto_commit=True,                # let aider commit changes
)
```

**Config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `"aider"` | `"aider"` | Discriminator |
| `model` | `str` | `"gpt-4o"` | Any aider-supported model string |
| `extra_args` | `list[str]` | `[]` | Extra flags passed to the aider CLI |
| `auto_commit` | `bool` | `True` | Let aider commit changes automatically |

**Required env var by model prefix:**

| Model prefix | Env var |
|---|---|
| `claude-*` | `ANTHROPIC_API_KEY` |
| `gpt-*`, `o1`, `o3-*` | `OPENAI_API_KEY` |
| `gemini/*` | `GEMINI_API_KEY` |
| `deepseek/*` | `DEEPSEEK_API_KEY` |
| `ollama/*` | *(none)* |

**Dockerfile snippet added automatically:**
```dockerfile
RUN pip install --no-cache-dir aider-chat
```

---

## openai

Calls the OpenAI Chat Completions API **directly from the host** — no Docker required. The provider collects relevant source files from the worktree, sends them as context, parses `<file path="...">` blocks from the response, writes the files back, and commits.

**CLI:**
```bash
treeport run --agent openai --model gpt-4o
treeport run --agent openai --model gpt-4o-mini
treeport run --agent openai --model o1
```

**Python:**
```python
from treeport.types import OpenAIConfig

agent = OpenAIConfig(
    model="gpt-4o",
    max_tokens=4096,
    context_token_budget=80_000,     # max tokens of source files to send
    include_patterns=["**/*.py"],    # which files to include
    exclude_patterns=["**/tests/**"],
)
```

**Config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `"openai"` | `"openai"` | Discriminator |
| `model` | `str` | `"gpt-4o"` | OpenAI model |
| `max_tokens` | `int` | `4096` | Max tokens in the response |
| `context_token_budget` | `int` | `80_000` | Max source file tokens to include |
| `include_patterns` | `list[str] \| None` | `None` | Glob patterns for files to include |
| `exclude_patterns` | `list[str] \| None` | `None` | Glob patterns for files to exclude |

**Required env var:** `OPENAI_API_KEY`

**Install:** `pip install openai` (included if you `pip install treeport[openai]`)

---

## gemini

Calls the Google Gemini API **directly from the host** — no Docker required. Same file-patch workflow as the OpenAI provider. Gemini's large context window makes it well-suited to whole-codebase tasks.

**CLI:**
```bash
treeport run --agent gemini --model gemini-2.0-flash
treeport run --agent gemini --model gemini-1.5-pro
```

**Python:**
```python
from treeport.types import GeminiConfig

agent = GeminiConfig(
    model="gemini-2.0-flash",
    max_output_tokens=8192,
    context_token_budget=100_000,    # Gemini handles large contexts well
    include_patterns=["**/*.py", "**/*.ts"],
)
```

**Config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `"gemini"` | `"gemini"` | Discriminator |
| `model` | `str` | `"gemini-2.0-flash"` | Gemini model |
| `max_output_tokens` | `int` | `8192` | Max tokens in the response |
| `context_token_budget` | `int` | `100_000` | Max source file tokens to include |
| `include_patterns` | `list[str] \| None` | `None` | Glob patterns for files to include |
| `exclude_patterns` | `list[str] \| None` | `None` | Glob patterns for files to exclude |

**Required env var:** `GEMINI_API_KEY`

**Install:** `pip install google-generativeai` (included if you `pip install treeport[gemini]`)

---

## custom

Run any shell command inside the Docker sandbox. Use placeholders in the command string:

| Placeholder | Expands to |
|---|---|
| `{prompt_file}` | `/home/agent/repo/.treeport_prompt.md` |
| `{model}` | The value of `model` |
| `{repo}` | `/home/agent/repo` |

**CLI:**
```bash
treeport run --agent custom \
  --custom-command "my-agent --model {model} --prompt {prompt_file}" \
  --model my-model-v2
```

**Python:**
```python
from treeport.types import CustomConfig

agent = CustomConfig(
    command="my-agent --model {model} --prompt {prompt_file} --repo {repo}",
    model="my-model-v2",
    dockerfile_snippet_text="RUN pip install my-agent",
    env_vars=["MY_AGENT_API_KEY"],
)
```

**Config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `"custom"` | `"custom"` | Discriminator |
| `command` | `str` | *(required)* | Shell command with optional `{prompt_file}`, `{model}`, `{repo}` |
| `model` | `str` | `""` | Fills the `{model}` placeholder |
| `dockerfile_snippet_text` | `str` | `""` | Dockerfile lines to install your tool |
| `env_vars` | `list[str]` | `[]` | Env var names this agent needs (for validation warnings) |

---

## Switching agents at runtime

The `agent` field in `RunOptions` accepts a plain dict too, so you can switch without importing config classes:

```python
from treeport import run
from treeport.types import RunOptions

# As a dict — Pydantic resolves the right config via the "type" discriminator
result = await run(RunOptions(
    prompt="fix the bug",
    agent={"type": "aider", "model": "gemini/gemini-2.0-flash"},
))
```
