# Prompts

treeport has a flexible prompt system. You write the prompt — treeport resolves it, substitutes variables, expands shell expressions, and hands it to the agent.

---

## Prompt sources

You must provide exactly one of:

```python
# Option 1 — inline string
RunOptions(prompt="Fix the failing tests in src/auth/")

# Option 2 — file path
RunOptions(prompt_file=".treeport/prompt.md")
```

Providing both raises a `ValidationError`. Providing neither raises a `ValidationError`.

> **Convention:** `treeport init` scaffolds `.treeport/prompt.md` and uses `prompt_file` in `main.py`. This is a convention, not an automatic fallback — treeport does not read `.treeport/prompt.md` unless you explicitly pass it as `prompt_file`.

---

## Argument substitution — `{{KEY}}`

Use `{{KEY}}` placeholders in your prompt to inject values from `prompt_args`. This lets you reuse the same prompt file across different runs.

**In `.treeport/prompt.md`:**
```markdown
Implement the feature described in GitHub issue #{{ISSUE_NUMBER}}.
Priority: {{PRIORITY}}.
Make sure all existing tests still pass.
When done: <promise>COMPLETE</promise>
```

**In your code:**
```python
result = await run(RunOptions(
    prompt_file=".treeport/prompt.md",
    prompt_args={
        "ISSUE_NUMBER": "42",
        "PRIORITY": "high",
    },
))
```

**Rules:**
- A `{{KEY}}` with no matching `prompt_args` entry raises `KeyError`.
- An unused `prompt_args` key emits a `UserWarning`.
- Substitution runs on the host **before** shell expression expansion, so placeholders inside `` !`command` `` expressions are resolved first.

---

## Dynamic context — `` !`command` ``

Use `` !`command` `` expressions to pull live data into your prompt. Each expression is replaced with the command's stdout before the prompt is sent to the agent.

Commands run **inside the sandbox** after `on_sandbox_ready` hooks complete, so they see the same environment the agent sees (installed dependencies, the repo state, etc.).

```markdown
## Open issues
!`gh issue list --state open --label bug --json number,title,body --limit 10`

## Recent commits
!`git log --oneline -10`

## Failing tests
!`python -m pytest --tb=line -q 2>&1 | tail -30`

## Current coverage
!`python -m pytest --co -q 2>&1 | wc -l` files in test suite
```

**Rules:**
- If any command exits with a non-zero code, the run fails immediately with a `RuntimeError`.
- Commands that produce no output are replaced with an empty string.
- Commands run sequentially before any agent iteration starts.

---

## Combining substitution and shell expressions

`{{KEY}}` substitution runs first, so you can inject values into shell commands:

```markdown
!`gh issue view {{ISSUE_NUMBER}} --json body -q .body`
```

With `prompt_args={"ISSUE_NUMBER": "42"}`, this runs:
```bash
gh issue view 42 --json body -q .body
```

---

## Completion signal — `<promise>COMPLETE</promise>`

When running multiple iterations (`max_iterations > 1`), you usually want the agent to stop as soon as the task is done rather than always running the maximum number of loops.

Tell the agent in your prompt to output the signal when it's finished:

```markdown
Work through the task step by step.
Test your changes before finishing.

When you are confident the task is complete, output exactly:
<promise>COMPLETE</promise>
```

treeport stops the iteration loop as soon as it detects the signal in the agent's output, regardless of how many iterations remain.

**Custom signal:**

```python
RunOptions(
    prompt="...",
    completion_signal="TASK_DONE",
    max_iterations=10,
)
```

Tell the agent to output `TASK_DONE` instead. The default `<promise>COMPLETE</promise>` is an XML-style tag that most models won't accidentally output in the middle of normal text.

---

## Full example prompt

```markdown
# Task: Fix failing CI

## Repository context
!`git log --oneline -5`

## Failing tests
!`python -m pytest --tb=short 2>&1 | tail -50`

## Open issues tagged "ci"
!`gh issue list --label ci --state open --json number,title --limit 5`

---

You are working on issue #{{ISSUE_NUMBER}}.

Fix the failing tests shown above. Do not modify test files unless the test
itself is wrong. Run `python -m pytest` before finishing to confirm all tests
pass.

When complete, output: <promise>COMPLETE</promise>
```

Run with:
```python
RunOptions(
    prompt_file=".treeport/prompt.md",
    prompt_args={"ISSUE_NUMBER": "99"},
    max_iterations=5,
    completion_signal="<promise>COMPLETE</promise>",
)
```
