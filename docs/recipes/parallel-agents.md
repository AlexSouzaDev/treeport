# Recipe: Parallel Agents

Run multiple agents concurrently on separate branches, then review and merge the best result.

---

## When to use this

- You have several independent tasks and want them done simultaneously.
- You want to compare implementations from different models (GPT-4o vs Claude vs Gemini).
- You want redundancy — run three agents on the same task and take the best commit.

---

## Parallel tasks on separate branches

```python
import asyncio
from treeport import run
from treeport.types import RunOptions, AiderConfig, StdoutLogging

TASKS = [
    {"issue": "42", "desc": "Add dark mode toggle"},
    {"issue": "43", "desc": "Fix pagination bug"},
    {"issue": "44", "desc": "Add CSV export"},
]

async def run_task(task: dict):
    result = await run(RunOptions(
        prompt=f"""
Implement the following feature: {task['desc']}

Related issue: #{task['issue']}

Run the tests when done. Output <promise>COMPLETE</promise> when finished.
""",
        agent=AiderConfig(model="gpt-4o"),
        branch=f"agent/issue-{task['issue']}",
        name=f"issue-{task['issue']}",
        max_iterations=3,
        logging=StdoutLogging(),
    ))
    return task["issue"], result

async def main():
    # Run all tasks concurrently
    results = await asyncio.gather(
        *[run_task(task) for task in TASKS],
        return_exceptions=True,
    )

    print("\n=== Results ===")
    for issue, result in results:
        if isinstance(result, Exception):
            print(f"Issue #{issue}: FAILED — {result}")
        else:
            print(
                f"Issue #{issue}: "
                f"{'✓' if result.was_completion_signal_detected else '~'} "
                f"{len(result.commits)} commit(s) on {result.branch}"
            )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Compare models on the same task

```python
import asyncio
from treeport import run
from treeport.types import RunOptions, AiderConfig, ClaudeCodeConfig

PROMPT = """
Refactor the authentication module in src/auth/ to use JWT tokens.
Keep the existing API surface. Add tests for the new implementation.
Output <promise>COMPLETE</promise> when done.
"""

async def main():
    results = await asyncio.gather(
        run(RunOptions(
            prompt=PROMPT,
            agent=ClaudeCodeConfig(model="claude-opus-4-5"),
            branch="agent/auth-claude",
            name="claude",
        )),
        run(RunOptions(
            prompt=PROMPT,
            agent=AiderConfig(model="gpt-4o"),
            branch="agent/auth-gpt4o",
            name="gpt4o",
        )),
        run(RunOptions(
            prompt=PROMPT,
            agent=AiderConfig(model="gemini/gemini-2.0-flash"),
            branch="agent/auth-gemini",
            name="gemini",
        )),
    )

    for result in results:
        print(f"{result.agent_type}: {len(result.commits)} commits on {result.branch}")

    print("\nReview each branch and merge your favourite:")
    for result in results:
        print(f"  git diff main..{result.branch}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Notes

- Each parallel run gets its own git worktree and Docker container — they cannot interfere with each other.
- The main branch is never touched during parallel runs.
- Use `asyncio.gather(..., return_exceptions=True)` to prevent one failure from cancelling others.
- Docker Desktop limits concurrent containers — if you're running many parallel agents, increase the resource limits in Docker settings.
