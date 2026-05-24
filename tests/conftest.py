from __future__ import annotations

import shutil
import re
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(request):
    base = Path(__file__).resolve().parent.parent / ".tmp" / "pytest-workspace-temp"
    base.mkdir(exist_ok=True)
    path = base / f"{_safe_name(request.node.name)}-{uuid.uuid4().hex}"
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "tmp"
