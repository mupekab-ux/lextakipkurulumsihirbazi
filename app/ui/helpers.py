# -*- coding: utf-8 -*-
"""
UI yardımcı fonksiyonları.

Bu modül, UI bileşenlerinde sıkça kullanılan yardımcı fonksiyonları içerir.
Şimdilik ui_main.py'deki fonksiyonlar yerinde kalıyor - aşamalı olarak buraya
taşınacak.
"""

from datetime import date, datetime
from typing import Any, Optional

from PyQt6.QtCore import QDate
from PyQt6.QtGui import QColor, QBrush

__all__ = [
    "coerce_to_qdate",
    "coerce_to_date",
    "date_sort_key",
    "int_sort_key",
    "normalize_text_value",
    "hex_to_qcolor",
]


def coerce_to_qdate(value: Any) -> Optional[QDate]:
    """Herhangi bir değeri QDate'e çevirir."""
    if isinstance(value, QDate):
        return value if value.isValid() else None
    if isinstance(value, datetime):
        return QDate(value.year, value.month, value.day)
    if isinstance(value, date):
        return QDate(value.year, value.month, value.day)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = QDate.fromString(text, "yyyy-MM-dd")
        if parsed.isValid():
            return parsed
        parsed = QDate.fromString(text, "dd.MM.yyyy")
        if parsed.isValid():
            return parsed
    return None


def coerce_to_date(value: Any) -> Optional[date]:
    """Herhangi bir değeri Python date nesnesine çevirir."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # ISO format: YYYY-MM-DD
        if len(text) >= 10:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                pass
        # TR format: DD.MM.YYYY
        try:
            return datetime.strptime(text[:10], "%d.%m.%Y").date()
        except ValueError:
            pass
    if isinstance(value, QDate) and value.isValid():
        return date(value.year(), value.month(), value.day())
    return None


def date_sort_key(value: Optional[date]) -> int:
    """Tarih sıralama anahtarı - None değerler en sona gider."""
    if value is None:
        return 0
    return value.year * 10000 + value.month * 100 + value.day


def int_sort_key(value: Any) -> int:
    """Integer sıralama anahtarı - geçersiz değerler 0 olur."""
    try:
        if value in (None, ""):
            return 0
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def normalize_text_value(value: Any) -> str:
    """Metin değerini normalize eder."""
    if value in (None, ""):
        return ""
    return str(value).strip()


def hex_to_qcolor(hex_code: str) -> QColor:
    """Hex renk kodunu QColor'a çevirir."""
    if not hex_code:
        return QColor()
    if not hex_code.startswith("#"):
        hex_code = f"#{hex_code}"
    return QColor(hex_code)
