"""Repository path resolution for local dev and Docker."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache
def repo_root() -> Path:
    """AgentFlow repo root (contains skills/, config/, static/)."""
    env = (os.environ.get("AGENTFLOW_REPO_ROOT") or "").strip()
    if env:
        return Path(env).resolve()

    # backend/app/core/paths.py -> parents[2] == backend/
    backend_dir = Path(__file__).resolve().parents[2]
    candidate = backend_dir.parent
    if (candidate / "skills").is_dir():
        return candidate

    # Docker: skills/config/static mounted under /repo
    docker_repo = Path("/repo")
    if docker_repo.is_dir():
        return docker_repo

    return candidate


def skills_root() -> Path:
    return repo_root() / "skills"


def static_root() -> Path:
    return repo_root() / "static"


def generated_root() -> Path:
    path = static_root() / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_root() -> Path:
    env = (os.environ.get("AGENTFLOW_UPLOADS_DIR") or "").strip()
    if env:
        path = Path(env).resolve()
    else:
        path = repo_root() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_catalog_path() -> Path:
    return repo_root() / "config" / "models.json"
