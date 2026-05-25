"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture()
def tmp_git_repo(tmp_path: Path):
    """A minimal git repo for testing worktree operations."""
    import git

    repo = git.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    return tmp_path, repo
