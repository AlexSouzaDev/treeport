# Recipe: Sequential Implement → Review Loop

Implement a feature with one agent, then pass the diff to a second agent for code review. Only merge if review passes.

---

## The pattern

```
Agent 1 (Implementer)
    │  implements feature, commits
    ▼
Agent 2 (Reviewer)
    │  reviews the diff, writes feedback
    ▼
Decision: merge, revise, or reject
```

---

## Implementation

```python
import asyncio
from treeport import run
from treeport.types import (
    RunOptions, ClaudeCodeConfig, AiderConfig, StdoutLogging
)

FEATURE = "Add rate limiting to the /api/login endpoint (max 5 attempts per minute per IP)"

async def main():
    # ── Step 1: Implement ────────────────────────────────────────────
    print("=== Step 1: Implementing feature ===")

    impl_result = await run(RunOptions(
        prompt=f"""
Implement the following feature:
{FEATURE}

Steps:
1. Write the implementation.
2. Write tests.
3. Run `python -m pytest` to verify.
4. Commit your changes.
5. Output <promise>COMPLETE</promise> when done.
""",
        agent=ClaudeCodeConfig(model="claude-opus-4-5"),
        branch="agent/feature-impl",
        name="implementer",
        max_iterations=5,
        logging=StdoutLogging(),
    ))

    if not impl_result.commits:
        print("Implementer made no commits — aborting.")
        return

    print(f"Implementation: {len(impl_result.commits)} commit(s) on {impl_result.branch}")

    # ── Step 2: Review ───────────────────────────────────────────────
    print("\n=== Step 2: Reviewing implementation ===")

    review_result = await run(RunOptions(
        prompt=f"""
You are a senior engineer performing a code review.

## Feature request
{FEATURE}

## Implementation diff
!`git diff main..agent/feature-impl`

## New or changed tests
!`git diff main..agent/feature-impl -- tests/`

---

Review the implementation above. Check for:
- Correctness: does it fully implement the feature?
- Security: any vulnerabilities or edge cases?
- Code quality: readability, naming, structure
- Test coverage: are the important cases covered?

Write your review as:

### Summary
[APPROVED / NEEDS REVISION / REJECTED]

### Findings
- ...

### Verdict
[Approved with no changes / Approved with minor suggestions / Requires revision / Rejected]

Output <promise>COMPLETE</promise> when your review is written.
""",
        agent=AiderConfig(model="gpt-4o"),
        branch="agent/code-review",
        name="reviewer",
        max_iterations=2,
        logging=StdoutLogging(),
    ))

    # ── Step 3: Decision ─────────────────────────────────────────────
    review_output = review_result.stdout.upper()

    if "APPROVED" in review_output and "REJECTED" not in review_output:
        print("\n✅ Review APPROVED — merging to main")
        import subprocess
        subprocess.run(["git", "checkout", "main"], check=True)
        subprocess.run(["git", "merge", "--ff-only", "agent/feature-impl"], check=True)
        print("Merged successfully.")
    elif "REJECTED" in review_output:
        print("\n❌ Review REJECTED — see reviewer output above")
    else:
        print("\n⚠️  Review NEEDS REVISION — see reviewer output above")
        print(f"Implementation branch: {impl_result.branch}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Variations

**Revision loop:** If the review returns NEEDS REVISION, pass the feedback back to the implementer for another round:

```python
for attempt in range(3):
    impl_result = await run(RunOptions(
        prompt=f"... implement ... previous feedback: {review_output}",
        branch=f"agent/feature-v{attempt + 1}",
    ))
    review_result = await run(...)
    if "APPROVED" in review_result.stdout.upper():
        break
```

**Self-review:** Use the same model for both steps — it often catches its own issues when given the reviewer persona.
