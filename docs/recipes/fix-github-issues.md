# Recipe: Fix GitHub Issues

Automatically pick open GitHub issues, implement them one by one, and close them on success.

---

## Prerequisites

- `gh` CLI authenticated (`gh auth login`)
- `ANTHROPIC_API_KEY` in `.treeport/.env`

---

## Prompt — `.treeport/prompt.md`

```markdown
## Open issues
!`gh issue list --state open --assignee @me --json number,title,body,labels --limit 5`

## Recent commits
!`git log --oneline -10`

## Current test status
!`python -m pytest --tb=line -q 2>&1 | tail -20`

---

Pick the highest-priority open issue from the list above and implement it.

Follow these steps:
1. Read the issue body carefully.
2. Make the necessary code changes.
3. Run the test suite: `python -m pytest`
4. If tests pass, commit your changes with a message referencing the issue number.
5. Close the issue: `gh issue close <number> --comment "Implemented in this commit."`

When done, output: <promise>COMPLETE</promise>
```

---

## `main.py`

```python
import asyncio
from treeport import run
from treeport.types import RunOptions, ClaudeCodeConfig, StdoutLogging, Hooks, Hook

async def main():
    result = await run(RunOptions(
        prompt_file=".treeport/prompt.md",
        agent=ClaudeCodeConfig(model="claude-opus-4-5"),
        max_iterations=5,
        branch="agent/auto-fix",
        hooks=Hooks(
            on_sandbox_ready=[
                Hook(command="pip install -r requirements.txt"),
            ]
        ),
        logging=StdoutLogging(),
    ))

    print(f"\n{'='*50}")
    print(f"Completed: {result.was_completion_signal_detected}")
    print(f"Iterations: {result.iterations_run}")
    print(f"Commits: {[c.sha[:8] for c in result.commits]}")
    print(f"Branch: {result.branch}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Run it

```bash
python .treeport/main.py
```

---

## Run on a schedule (GitHub Actions)

```yaml
# .github/workflows/auto-fix.yml
name: Auto-fix issues

on:
  schedule:
    - cron: "0 9 * * 1-5"   # every weekday at 9am
  workflow_dispatch:

jobs:
  fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install treeport
        run: pip install treeport

      - name: Run agent
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python .treeport/main.py
```
