"""
Manages git worktrees for treeport runs.

Flow:
  1. create_worktree()  — creates a new branch + worktree at .treeport/worktrees/<name>/
  2. [agent runs, writes commits]
  3. merge_back()       — fast-forward merges the worktree branch into the target branch
  4. cleanup()          — removes the worktree and deletes the temp branch
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import git


class WorktreeManager:
    """Manages a single ephemeral git worktree for one treeport run."""

    def __init__(
        self,
        repo_root: Path,
        branch: str | None = None,
        run_name: str | None = None,
    ) -> None:
        self.repo = git.Repo(repo_root, search_parent_directories=True)
        self.repo_root = Path(self.repo.working_dir)

        slug = run_name or uuid.uuid4().hex[:8]
        self.target_branch = branch or f"treeport/{slug}"
        self._worktree_path = self.repo_root / ".treeport" / "worktrees" / slug
        self._temp_branch = f"treeport-tmp/{slug}"
        self._cleaned_up = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def worktree_path(self) -> Path:
        return self._worktree_path

    def create(self) -> Path:
        """Create a worktree on a fresh branch based on the current HEAD."""
        self._worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the temp branch at current HEAD
        self.repo.git.worktree(
            "add",
            "-b",
            self._temp_branch,
            str(self._worktree_path),
            "HEAD",
        )
        return self._worktree_path

    def get_new_commits(self) -> list[dict[str, str]]:
        """Return commits on the temp branch not present on the base HEAD."""
        base = self.repo.commit("HEAD")
        worktree_repo = git.Repo(self._worktree_path)
        commits = list(
            worktree_repo.iter_commits(
                f"{base.hexsha}..{self._temp_branch}"
            )
        )
        return [
            {"sha": c.hexsha, "message": c.message.strip()}
            for c in reversed(commits)
        ]

    def merge_back(self) -> None:
        """Fast-forward merge the temp branch into ``target_branch``."""
        worktree_repo = git.Repo(self._worktree_path)
        temp_sha = worktree_repo.head.commit.hexsha

        # Ensure target branch exists (create from temp tip if brand-new)
        if self.target_branch not in [b.name for b in self.repo.branches]:
            self.repo.git.branch(self.target_branch, temp_sha)
        else:
            # Fast-forward only
            self.repo.git.fetch(".", f"{self._temp_branch}:{self.target_branch}")

    def cleanup(self) -> None:
        """Remove the worktree and delete the temp branch."""
        if self._cleaned_up:
            return
        try:
            self.repo.git.worktree("remove", "--force", str(self._worktree_path))
        except git.GitCommandError:
            pass
        try:
            self.repo.git.branch("-D", self._temp_branch)
        except git.GitCommandError:
            pass
        self._cleaned_up = True

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def session(self) -> Generator["WorktreeManager", None, None]:
        """Context manager that creates and cleans up the worktree automatically."""
        self.create()
        try:
            yield self
        finally:
            self.cleanup()
