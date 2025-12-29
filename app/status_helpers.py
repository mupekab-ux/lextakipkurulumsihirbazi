"""Shared helpers for dava durumu lists."""
from __future__ import annotations

from typing import List

try:  # pragma: no cover - runtime import guard
    from app.models import get_statuses
except ModuleNotFoundError:  # pragma: no cover
    from models import get_statuses  # type: ignore

_STATUS_NAMES: list[str] = []


def get_dava_durumu_list() -> List[str]:
    """Return the cached list of dava durumu names."""
    global _STATUS_NAMES
    if not _STATUS_NAMES:
        try:
            _STATUS_NAMES = [
                str(row.get("ad", "")).strip()
                for row in get_statuses()
                if str(row.get("ad", "")).strip()
            ]
        except Exception:
            _STATUS_NAMES = []
    return list(_STATUS_NAMES)
