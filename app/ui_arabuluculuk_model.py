# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt6.QtGui import QBrush, QColor

try:  # pragma: no cover - runtime import guard
    from app.utils import iso_to_tr
except ModuleNotFoundError:  # pragma: no cover
    from utils import iso_to_tr

COL_TAMAMLANDI = 0
COL_SIRA = 1
COL_DAVACI = 2
COL_DAVALI = 3
COL_ARB_ADI = 4
COL_ARB_TEL = 5
COL_TOPLANTI_TARIHI = 6
COL_TOPLANTI_SAATI = 7
COL_KONU = 8

HEADERS = [
    "✓",
    "Sıra",
    "Davacı",
    "Davalı",
    "Arb. adı",
    "Arb tel no",
    "Toplantı tarihi",
    "Toplantı saati",
    "Konu",
]

COLOR_TODAY = QColor("#F8D7DA")
COLOR_PLUS1 = QColor("#FFF3CD")
COLOR_PLUS23 = QColor("#FFE5B4")
COLOR_PLUS46 = QColor("#D6EAF8")
FG_BLACK = QBrush(QColor("#000000"))


class ArabuluculukTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: List[Dict[str, Any]] = []

    # -- Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: D401
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: D401
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(HEADERS):
                return HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        row = index.row()
        column = index.column()
        if not (0 <= row < len(self._records)):
            return QVariant()
        record = self._records[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if column == COL_TAMAMLANDI:
                return "✓" if record.get("tamamlandi") else ""
            if column == COL_SIRA:
                return row + 1
            if column == COL_DAVACI:
                return record.get("davaci", "") or ""
            if column == COL_DAVALI:
                return record.get("davali", "") or ""
            if column == COL_ARB_ADI:
                return record.get("arb_adi", "") or ""
            if column == COL_ARB_TEL:
                return record.get("arb_tel", "") or ""
            if column == COL_TOPLANTI_TARIHI:
                return self._format_date(record.get("toplanti_tarihi"))
            if column == COL_TOPLANTI_SAATI:
                return record.get("toplanti_saati", "") or ""
            if column == COL_KONU:
                return record.get("konu", "") or ""
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if column == COL_TAMAMLANDI:
                return Qt.AlignmentFlag.AlignCenter
        elif role == Qt.ItemDataRole.BackgroundRole and column == COL_TOPLANTI_TARIHI:
            # Tamamlanmamış olanlar için renk göster
            if not record.get("tamamlandi"):
                color = self._compute_background(record.get("toplanti_tarihi"))
                if color is not None:
                    return QBrush(color)
        elif role == Qt.ItemDataRole.ForegroundRole and column == COL_TOPLANTI_TARIHI:
            if not record.get("tamamlandi"):
                color = self._compute_background(record.get("toplanti_tarihi"))
                if color is not None:
                    return FG_BLACK
        elif role == Qt.ItemDataRole.UserRole:
            if column == COL_SIRA:
                return record.get("id")
            if column == COL_TAMAMLANDI:
                return record.get("tamamlandi", 0)
            return record
        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # -- Public helpers -----------------------------------------------------
    def set_records(self, records: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # -- Internal helpers ---------------------------------------------------
    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return ""
        try:
            return iso_to_tr(str(value))
        except Exception:
            return str(value)

    @staticmethod
    def _compute_background(value: Any) -> Optional[QColor]:
        if not value:
            return None
        try:
            meeting_date = date.fromisoformat(str(value))
        except ValueError:
            return None
        delta = (meeting_date - date.today()).days
        if delta == 0:
            return COLOR_TODAY
        if delta == 1:
            return COLOR_PLUS1
        if delta in (2, 3):
            return COLOR_PLUS23
        if 4 <= delta <= 6:
            return COLOR_PLUS46
        return None
