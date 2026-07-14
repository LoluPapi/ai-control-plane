"""Data root resolution — env-overridable so the container image works."""

from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    override = os.environ.get("AICP_DATA_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data"
