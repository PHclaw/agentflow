"""Tests for repository path helpers."""
import os
from pathlib import Path

import pytest

from app.core import paths


def test_repo_root_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    monkeypatch.setenv("AGENTFLOW_REPO_ROOT", str(repo))
    paths.repo_root.cache_clear()
    try:
        assert paths.repo_root() == repo.resolve()
        assert paths.skills_root() == repo / "skills"
        assert paths.generated_root() == repo / "static" / "generated"
        assert paths.uploads_root() == repo / "uploads"
    finally:
        paths.repo_root.cache_clear()
        monkeypatch.delenv("AGENTFLOW_REPO_ROOT", raising=False)
