"""
Treeport CLI — powered by Typer.

Commands:
  treeport init           Scaffold .treeport/ and build the Docker image
  treeport build-image    Rebuild the Docker image
  treeport remove-image   Remove the Docker image
  treeport run            Run the agent from the CLI (convenience wrapper)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from treeport.docker_runner import ContainerRunner

# ── ASCII banner ───────────────────────────────────────────────────────

BANNER = (
    " _                                  _   \n"
    "| |                                | |  \n"
    "| |_ _ __ ___  ___ _ __   ___  _ __| |_ \n"
    "| __| '__/ _ \\/ _ \\ '_ \\ / _ \\| '__| __|\n"
    "| |_| | |  __/  __/ |_) | (_) | |  | |_ \n"
    " \\__|_|  \\___|\\___| .__/ \\___/|_|   \\__|\n"
    "                  | |                   \n"
    "                  |_|                   \n"
    " [Git Worktree <-> Docker AI Orchestrator]"
)

def _print_banner() -> None:
    _console = Console()
    _console.print(Text(BANNER, style="bold cyan"))
    _console.print()


# ── App ────────────────────────────────────────────────────────────────


def _version_callback(value: bool) -> None:
    if value:
        from treeport import __version__
        rprint(f"treeport v[bold cyan]{__version__}[/]")
        raise typer.Exit()


app = typer.Typer(
    name="treeport",
    help="Orchestrate sandboxed AI coding agents in Python.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """
    [bold cyan]treeport[/] — run AI coding agents in isolated Docker sandboxes.

    Agents: [green]claude-code[/] · [green]aider[/] (gpt-4o/gemini/deepseek/ollama) · [green]openai[/] · [green]gemini[/] · [green]custom[/]
    """
    if ctx.invoked_subcommand is not None:
        _print_banner()

# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _repo_root() -> Path:
    import git

    return Path(git.Repo(".", search_parent_directories=True).working_dir)


# ---------------------------------------------------------------------- #
# init
# ---------------------------------------------------------------------- #


@app.command()
def init(
    image_name: Optional[str] = typer.Option(
        None, "--image-name", help="Docker image name (default: treeport:<repo-dir>)"
    ),
) -> None:
    """Scaffold .treeport/ and build the Docker sandbox image."""
    root = _repo_root()
    treeport_dir = root / ".treeport"

    if treeport_dir.exists():
        rprint("[bold red]Error:[/] .treeport/ already exists. Delete it first.")
        raise typer.Exit(code=1)

    # -- Copy template files --
    treeport_dir.mkdir(parents=True)

    _write_template(treeport_dir / "Dockerfile", _dockerfile_template())
    _write_template(treeport_dir / "prompt.md", _prompt_template())
    _write_template(treeport_dir / ".env.example", _env_example_template())
    _write_template(treeport_dir / "main.py", _main_py_template())

    gitignore = treeport_dir / ".gitignore"
    gitignore.write_text(".env\nworktrees/\nlogs/\n")

    logs_dir = treeport_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / ".gitkeep").touch()

    rprint(Panel("[bold green]✓ .treeport/ scaffolded[/]\n\n"
                 "Next steps:\n"
                 "  1. cp .treeport/.env.example .treeport/.env\n"
                 "  2. Fill in ANTHROPIC_API_KEY in .treeport/.env\n"
                 "  3. Edit .treeport/prompt.md\n"
                 "  4. Run: treeport build-image\n"
                 "  5. Run: python .treeport/main.py",
                 title="treeport init"))

    # -- Build image --
    resolved_image = image_name or ContainerRunner.default_image_name(root)
    rprint(f"[cyan]Building image[/] {resolved_image}…")
    runner = ContainerRunner(resolved_image, worktree_path=treeport_dir, env={})
    runner.build_image(treeport_dir / "Dockerfile", root)
    rprint(f"[bold green]✓ Image[/] {resolved_image} [bold green]built.[/]")


# ---------------------------------------------------------------------- #
# build-image
# ---------------------------------------------------------------------- #


@app.command(name="build-image")
def build_image(
    image_name: Optional[str] = typer.Option(None, "--image-name"),
    dockerfile: Optional[Path] = typer.Option(None, "--dockerfile"),
) -> None:
    """Rebuild the Docker sandbox image."""
    root = _repo_root()
    resolved_image = image_name or ContainerRunner.default_image_name(root)
    df = dockerfile or root / ".treeport" / "Dockerfile"

    if not df.exists():
        rprint(f"[bold red]Error:[/] Dockerfile not found at {df}")
        raise typer.Exit(code=1)

    rprint(f"[cyan]Building[/] {resolved_image}…")
    runner = ContainerRunner(resolved_image, worktree_path=root, env={})
    runner.build_image(df, root)
    rprint(f"[bold green]✓ Done.[/]")


# ---------------------------------------------------------------------- #
# remove-image
# ---------------------------------------------------------------------- #


@app.command(name="remove-image")
def remove_image(
    image_name: Optional[str] = typer.Option(None, "--image-name"),
) -> None:
    """Remove the Docker sandbox image."""
    import docker

    root = _repo_root()
    resolved_image = image_name or ContainerRunner.default_image_name(root)
    client = docker.from_env()
    try:
        client.images.remove(resolved_image, force=True)
        rprint(f"[bold green]✓ Removed[/] {resolved_image}")
    except docker.errors.ImageNotFound:
        rprint(f"[yellow]Image[/] {resolved_image} [yellow]not found.[/]")


# ---------------------------------------------------------------------- #
# run (CLI convenience)
# ---------------------------------------------------------------------- #

_AGENT_CHOICES = ["claude-code", "aider", "openai", "gemini", "custom"]


@app.command(name="run")
def run_cmd(
    prompt_file: Path = typer.Option(
        Path(".treeport/prompt.md"), "--prompt-file", "-f",
        help="Path to the prompt file."
    ),
    max_iterations: int = typer.Option(1, "--max-iterations", "-n"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    agent: str = typer.Option(
        "claude-code", "--agent", "-a",
        help=f"Agent backend. One of: {', '.join(_AGENT_CHOICES)}.",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model string (overrides per-agent default).",
    ),
    image_name: Optional[str] = typer.Option(None, "--image-name"),
    name: Optional[str] = typer.Option(None, "--name"),
    custom_command: Optional[str] = typer.Option(
        None, "--custom-command",
        help="Shell command for the 'custom' agent (use with --agent custom).",
    ),
) -> None:
    """Run the agent directly from the CLI.

    Examples:

      treeport run                                  # Claude Code (default)

      treeport run --agent aider --model gpt-4o     # Aider + GPT-4o

      treeport run --agent openai --model gpt-4o    # OpenAI API, no Docker

      treeport run --agent gemini                   # Gemini API, no Docker

      treeport run --agent aider --model gemini/gemini-2.0-flash

      treeport run --agent custom --custom-command "my-agent --prompt {prompt_file}"
    """
    import asyncio
    from treeport.core import run
    from treeport.types import (
        AiderConfig,
        ClaudeCodeConfig,
        CustomConfig,
        GeminiConfig,
        OpenAIConfig,
        RunOptions,
        StdoutLogging,
    )

    # Build agent config
    match agent:
        case "claude-code":
            agent_cfg = ClaudeCodeConfig(model=model or "claude-opus-4-5")
        case "aider":
            agent_cfg = AiderConfig(model=model or "gpt-4o")
        case "openai":
            agent_cfg = OpenAIConfig(model=model or "gpt-4o")
        case "gemini":
            agent_cfg = GeminiConfig(model=model or "gemini-2.0-flash")
        case "custom":
            if not custom_command:
                rprint("[bold red]Error:[/] --custom-command is required for --agent custom")
                raise typer.Exit(code=1)
            agent_cfg = CustomConfig(command=custom_command, model=model or "")
        case _:
            rprint(f"[bold red]Error:[/] Unknown agent '{agent}'. Choose from: {', '.join(_AGENT_CHOICES)}")
            raise typer.Exit(code=1)

    options = RunOptions(
        prompt_file=prompt_file,
        max_iterations=max_iterations,
        branch=branch,
        agent=agent_cfg,
        image_name=image_name,
        name=name,
        logging=StdoutLogging(),
    )
    result = asyncio.run(run(options))
    rprint(
        f"\n[bold green]Run complete[/] — "
        f"agent: [cyan]{result.agent_type}[/], "
        f"{result.iterations_run} iteration(s), "
        f"{len(result.commits)} commit(s) on [cyan]{result.branch}[/]"
    )
    if result.files_modified:
        rprint(f"Files modified: {', '.join(result.files_modified[:10])}")


# ---------------------------------------------------------------------- #
# Template strings
# ---------------------------------------------------------------------- #


def _write_template(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _dockerfile_template() -> str:
    return """\
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \\
    git curl jq nodejs npm \\
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \\
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \\
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \\
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \\
    && apt-get update && apt-get install -y gh \\
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Non-root agent user (required — Claude runs as this user)
RUN useradd -m -s /bin/bash agent
USER agent
WORKDIR /home/agent/repo
"""


def _prompt_template() -> str:
    return """\
# Your Treeport Prompt

Describe the task you want the agent to perform.

Use `!\\`command\\`` to inject dynamic context:

```
# Open issues
!\\`gh issue list --state open --json number,title,body --limit 10\\`
```

Use `{{KEY}}` for runtime substitutions (passed via `prompt_args`):

```
Work on issue #{{ISSUE_NUMBER}}.
```

When finished, output:
<promise>COMPLETE</promise>
"""


def _env_example_template() -> str:
    return """\
ANTHROPIC_API_KEY=your-key-here
GITHUB_TOKEN=your-github-token-here
"""


def _main_py_template() -> str:
    return """\
import asyncio
from treeport import run
from treeport.types import RunOptions

async def main():
    result = await run(RunOptions(
        prompt_file=".treeport/prompt.md",
        max_iterations=1,
        logging={"type": "stdout"},
    ))
    print(f"Iterations: {result.iterations_run}")
    print(f"Commits: {[c.sha[:8] for c in result.commits]}")
    print(f"Branch: {result.branch}")

if __name__ == "__main__":
    asyncio.run(main())
"""


def main() -> None:
    app()
"""

if __name__ == "__main__":
    main()
"""
