# -*- coding: utf-8 -*-
"""
Ortak servis bağımlılıkları ve yardımcı fonksiyonlar.
Tüm servis modülleri bu modülü import eder.
"""

from typing import Any, Dict, Iterable, List, Optional, Set
import sqlite3
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import calendar

# Veritabanı bağlantısı
from db import get_connection, DB_PATH, timed_query

# Yardımcı fonksiyonlar
from utils import (
    hash_password,
    verify_password,
    iso_to_tr,
    tr_to_iso,
    normalize_hex,
    normalize_str,
    resolve_owner_label,
    get_status_text_color,
    format_tl,
)

logger = logging.getLogger(__name__)

# Sabitler
INSTALLMENT_OVERDUE_STATUS = "Gecikmiş"
AUTO_PAYMENT_NOTE = "Taksit ödemesi (otomatik)"
HARICI_AUTO_PAYMENT_NOTE = AUTO_PAYMENT_NOTE


def tl_to_cents(value) -> int:
    """TL değerini kuruşa çevir."""
    if value is None or value == "":
        return 0
    try:
        if isinstance(value, str):
            value = value.replace(",", ".").replace(" ", "").replace("₺", "")
        dec = Decimal(str(value))
        cents = int((dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return cents
    except (InvalidOperation, ValueError, TypeError):
        return 0


def cents_to_tl(value) -> float:
    """Kuruşu TL'ye çevir."""
    if value is None:
        return 0.0
    try:
        return int(value) / 100.0
    except (ValueError, TypeError):
        return 0.0


def safe_int(value: Any, default: int = 0) -> int:
    """Güvenli integer dönüşümü."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError, TypeError):
            return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Güvenli float dönüşümü."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, ValueError, TypeError):
            return default


def normalize_iso_date(value: Any) -> Optional[str]:
    """Tarihi ISO formatına normalize et."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    converted = tr_to_iso(text)
    return converted if converted else None


def normalize_hhmm(value: Any) -> Optional[str]:
    """Saat değerini HH:MM formatına normalize et."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) != 2:
        try:
            parsed = datetime.strptime(text, "%H%M")
        except ValueError:
            return None
        return f"{parsed.hour:02d}:{parsed.minute:02d}"
    try:
        hour, minute = (int(part) for part in parts)
    except ValueError:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return f"{hour:02d}:{minute:02d}"


def row_to_dict(row: sqlite3.Row | Dict[str, Any] | None) -> Dict[str, Any]:
    """sqlite3.Row veya dict'i dict'e çevir."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return dict(row)


def ensure_connection(conn: sqlite3.Connection | None) -> tuple[sqlite3.Connection, bool]:
    """Bağlantı yoksa yeni oluştur, var mı kontrol et."""
    if conn is None:
        return get_connection(), True
    return conn, False


__all__ = [
    # Typing
    "Any", "Dict", "Iterable", "List", "Optional", "Set",
    # Database
    "sqlite3", "get_connection", "DB_PATH", "timed_query",
    # Utils
    "logger", "datetime", "date", "timedelta", "Decimal", "ROUND_HALF_UP",
    "InvalidOperation", "calendar",
    "hash_password", "verify_password", "iso_to_tr", "tr_to_iso",
    "normalize_hex", "normalize_str", "resolve_owner_label",
    "get_status_text_color", "format_tl",
    # Constants
    "INSTALLMENT_OVERDUE_STATUS", "AUTO_PAYMENT_NOTE", "HARICI_AUTO_PAYMENT_NOTE",
    # Helper functions
    "tl_to_cents", "cents_to_tl", "safe_int", "safe_float",
    "normalize_iso_date", "normalize_hhmm", "row_to_dict", "ensure_connection",
]
