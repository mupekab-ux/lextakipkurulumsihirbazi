# -*- coding: utf-8 -*-
"""Compatibility shim that reuses the full harici finans diyaloğu."""
from __future__ import annotations

from typing import Any

try:  # pragma: no cover - runtime import guard
    from app.ui_finans_harici_dialog import FinansHariciDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_finans_harici_dialog import FinansHariciDialog  # type: ignore


class FinansHariciQuickDialog(FinansHariciDialog):
    """Open the full dialog but default to Sözleşme/Anlaşma sekmesi.

    NOTE: inherits the main dialog's auto-payment behavior for paid installments.
    """

    def __init__(self, parent=None, *, conn=None, harici_id: int | None = None, **kwargs: Any) -> None:
        super().__init__(parent, conn=conn, harici_id=harici_id)
        self.tab_widget.setCurrentIndex(0)

    def save_contract(self) -> None:  # NOTE: quick dialog auto-closes after save
        super().save_contract()
        self.accept()
