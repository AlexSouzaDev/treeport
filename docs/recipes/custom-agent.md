# Recipe: Custom Agent

Bring your own CLI coding tool and run it inside the treeport sandbox.

---

## When to use `custom`

- You have an internal or proprietary coding agent CLI.
- You want to use a tool treeport doesn't have a built-in provider for.
- You want full control over the exact command invoked inside the container.

---

## Basic example

Any CLI tool that accepts a prompt via a file or stdin works.

```python
from treeport import run
from treeport.types import RunOptions, CustomConfig, StdoutLogging

result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
    agent=CustomConfig(
        command="my-agent --prompt-file {prompt_file} --repo {repo}",
        model="my-model-v2",
        dockerfile_snippet_text="RUN pip install my-agent==1.2.3",
        env_vars=["MY_AGENT_API_KEY"],
    ),
    logging=StdoutLogging(),
))
```

---

## Command placeholders

| Placeholder | Expands to |
|---|---|
| `{prompt_file}` | `/home/agent/repo/.treeport_prompt.md` |
| `{model}` | The value of `CustomConfig.model` |
| `{repo}` | `/home/agent/repo` |

---

## Dockerfile snippet

The `dockerfile_snippet_text` is injected into the sandbox `Dockerfile` during `treeport init`. You can also edit `.treeport/Dockerfile` directly.

**Examples:**

Install a pip package:
```python
dockerfile_snippet_text="RUN pip install my-agent==1.2.3"
```

Install from a private registry:
```python
dockerfile_snippet_text="""
ARG AGENT_TOKEN
RUN pip install my-agent --index-url https://pypi.mycompany.com/simple/ --extra-index-url https://pypi.org/simple/
"""
```

Install a Node.js tool:
```python
dockerfile_snippet_text="RUN npm install -g @mycompany/agent-cli"
```

---

## Full Dockerfile example

After `treeport init`, edit `.treeport/Dockerfile`:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git curl jq nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Your custom agent
RUN pip install my-agent==1.2.3

# Non-root agent user (required)
RUN useradd -m -s /bin/bash agent
USER agent
WORKDIR /home/agent/repo
```

Rebuild after editing:

```bash
treeport build-image
```

---

## Using Aider as a custom provider

If you want finer control over Aider than the built-in `aider` provider offers, use `custom`:

```python
CustomConfig(
    command=(
        "aider "
        "--model {model} "
        "--message \"$(cat {prompt_file})\" "
        "--yes-always "
        "--no-auto-commits "        # manage commits yourself
        "--edit-format diff "       # use diff format
        "--map-tokens 2048"
    ),
    model="gpt-4o",
    dockerfile_snippet_text="RUN pip install aider-chat",
)
```

---

## Wrapping a REST API agent

For agents that expose a REST API instead of a CLI, write a thin wrapper script:

```python
# .treeport/run_agent.py
import sys, json, requests, subprocess

prompt = open(sys.argv[1]).read()
repo   = sys.argv[2]

response = requests.post("http://localhost:8080/run", json={
    "prompt": prompt,
    "repo":   repo,
})
data = response.json()

for file in data["files"]:
    (Path(repo) / file["path"]).write_text(file["content"])

subprocess.run(["git", "add", "-A"], cwd=repo)
subprocess.run(["git", "commit", "-m", data["summary"]], cwd=repo)

print(data["output"])
print("<promise>COMPLETE</promise>")
```

Then in your config:

```python
CustomConfig(
    command="python /home/agent/repo/.treeport/run_agent.py {prompt_file} {repo}",
    dockerfile_snippet_text="RUN pip install requests",
)
```
