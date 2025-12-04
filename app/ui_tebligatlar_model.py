# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import List, Dict, Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt6.QtGui import QBrush, QColor

try:  # pragma: no cover - runtime import guard
    from app.utils import iso_to_tr
except ModuleNotFoundError:  # pragma: no cover
    from utils import iso_to_tr

COL_TAMAMLANDI = 0
COL_SIRA = 1
COL_DOSYA_NO = 2
COL_KURUM = 3
COL_GELDIGI_TARIH = 4
COL_TEBLIG_TARIHI = 5
COL_SON_GUN = 6
COL_ICERIK = 7

HEADERS = [
    "✓",
    "Sıra",
    "Dosya No",
    "Kurum",
    "Geldiği Tarih",
    "Tebliğ Tarihi",
    "İşin Son Günü",
    "İçerik",
]

TODAY_COLOR = QColor("#F8D7DA")
TOMORROW_COLOR = QColor("#FFF3CD")
SOON_COLOR = QColor("#FFE5B4")
NEXT_COLOR = QColor("#D6EAF8")

FG_SIYAH = QBrush(QColor("#000000"))


class TebligatlarTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: D401
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: D401
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(HEADERS):
                return HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        row = index.row()
        column = index.column()
        if not (0 <= row < len(self._rows)):
            return QVariant()
        record = self._rows[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if column == COL_TAMAMLANDI:
                return "✓" if record.get("tamamlandi") else ""
            if column == COL_SIRA:
                return row + 1
            if column == COL_DOSYA_NO:
                return record.get("dosya_no", "") or ""
            if column == COL_KURUM:
                return record.get("kurum", "") or ""
            if column == COL_GELDIGI_TARIH:
                return self._format_date(record.get("geldigi_tarih"))
            if column == COL_TEBLIG_TARIHI:
                return self._format_date(record.get("teblig_tarihi"))
            if column == COL_SON_GUN:
                return self._format_date(record.get("is_son_gunu"))
            if column == COL_ICERIK:
                return record.get("icerik", "") or ""
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if column == COL_TAMAMLANDI:
                return Qt.AlignmentFlag.AlignCenter
        elif role == Qt.ItemDataRole.BackgroundRole and column == COL_SON_GUN:
            # Tamamlanmamış olanlar için renk göster
            if not record.get("tamamlandi"):
                color = self._due_background(record.get("is_son_gunu"))
                if color is not None:
                    return QBrush(color)
        elif role == Qt.ItemDataRole.ForegroundRole and column == COL_SON_GUN:
            if not record.get("tamamlandi"):
                color = self._due_background(record.get("is_son_gunu"))
                if color is not None:
                    return FG_SIYAH
        elif role == Qt.ItemDataRole.UserRole:
            if column == COL_SIRA:
                return record.get("id")
            if column == COL_TAMAMLANDI:
                return record.get("tamamlandi", 0)
            if column in (COL_GELDIGI_TARIH, COL_TEBLIG_TARIHI, COL_SON_GUN):
                return record.get(self._column_key(column)) or ""
            return record.get(self._column_key(column)) or ""
        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def set_records(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def record_at(self, row: int) -> Dict[str, Any] | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return ""
        try:
            return iso_to_tr(str(value))
        except Exception:
            return str(value)

    @staticmethod
    def _column_key(column: int) -> str:
        mapping = {
            COL_DOSYA_NO: "dosya_no",
            COL_KURUM: "kurum",
            COL_GELDIGI_TARIH: "geldigi_tarih",
            COL_TEBLIG_TARIHI: "teblig_tarihi",
            COL_SON_GUN: "is_son_gunu",
            COL_ICERIK: "icerik",
        }
        return mapping.get(column, "")

    @staticmethod
    def _due_background(value: Any) -> QColor | None:
        if not value:
            return None
        try:
            due_date = date.fromisoformat(str(value))
        except ValueError:
            return None
        today = date.today()
        delta = (due_date - today).days
        if delta < 0:
            return None
        if delta == 0:
            return TODAY_COLOR
        if delta == 1:
            return TOMORROW_COLOR
        if 2 <= delta <= 3:
            return SOON_COLOR
        if 4 <= delta <= 6:
            return NEXT_COLOR
        return None
