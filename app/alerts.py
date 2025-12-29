# -*- coding: utf-8 -*-
"""Helpers for scanning upcoming events and producing alert chips."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import sqlite3

try:  # pragma: no cover - runtime import guard
    from app.db import get_connection
except ModuleNotFoundError:  # pragma: no cover
    from db import get_connection


@dataclass(frozen=True)
class AlertChip:
    """Represents a single alert chip on the UI."""

    timeframe_key: str
    timeframe_label: str
    category_key: str
    category_label: str
    count: int
    start_date: date
    end_date: date

    def build_hint(self) -> str:
        """Return a textual hint that can be dropped into a search box."""

        prefix_map = {
            "hearing": "#hearing",
            "notice": "#notice",
            "payment": "#payment",
            "mediation": "#mediation",
        }
        prefix = prefix_map.get(self.category_key, "#date")
        start = self.start_date.isoformat()
        end = self.end_date.isoformat()
        return f"{prefix}:{start}..{end}"


class AlertsScanner:
    """Scans the database for upcoming events within given timeframes."""

    _TIMEFRAMES: Sequence[Tuple[str, str, Tuple[int, int]]] = (
        ("today", "Bugün", (0, 0)),
        ("tomorrow", "Yarın", (1, 1)),
        ("week", "7 Gün", (2, 7)),
    )

    _CATEGORY_ORDER: Sequence[str] = ("hearing", "notice", "payment", "mediation")

    _TIMEFRAME_ORDER: Sequence[str] = tuple(tf[0] for tf in _TIMEFRAMES)

    _CATEGORY_CONFIG: Dict[str, Dict[str, object]] = {
        "hearing": {
            "table": "dosyalar",
            "columns": ("durusma_tarihi", "duruşma_tarihi", "hearing_date"),
            "label": "Duruşma",
            "extra_where": "AND COALESCE(is_archived, 0) = 0",
        },
        "notice": {
            "table": "tebligatlar",
            "columns": (
                "is_son_gunu",
                "teblig_tarihi",
                "geldigi_tarih",
                "tebligat_tarihi",
            ),
            "label": "Tebligat",
        },
        "payment": {
            "tables": (
                {"table": "odeme_plani", "columns": ("vade_tarihi",)},
                {
                    "table": "taksitler",
                    "columns": ("vade_tarihi",),
                    "extra_where": "AND (odeme_tarihi IS NULL OR TRIM(odeme_tarihi) = '')",
                },
            ),
            "label": "Ödeme",
        },
        "mediation": {
            "table": "arabuluculuk",
            "columns": (
                "toplanti_tarihi",
                "toplantı_tarihi",
                "meeting_date",
            ),
            "label": "Arabuluculuk",
        },
    }

    def __init__(self) -> None:
        self._table_columns_cache: Dict[str, Tuple[str, ...]] = {}

    def scan(self, *, reference_date: Optional[date] = None) -> List[AlertChip]:
        """Return alert chips for upcoming events."""

        today = reference_date or date.today()
        chips: List[AlertChip] = []

        conn = get_connection()
        try:
            for timeframe_key, timeframe_label, offsets in self._TIMEFRAMES:
                start = today + timedelta(days=offsets[0])
                end = today + timedelta(days=offsets[1])
                if end < start:
                    continue
                for category_key in self._CATEGORY_ORDER:
                    config = self._CATEGORY_CONFIG.get(category_key)
                    if not config:
                        continue
                    count = self._count_for_category(conn, config, start, end)
                    if count <= 0:
                        continue
                    label = str(config.get("label", category_key.title()))
                    chips.append(
                        AlertChip(
                            timeframe_key=timeframe_key,
                            timeframe_label=timeframe_label,
                            category_key=category_key,
                            category_label=label,
                            count=int(count),
                            start_date=start,
                            end_date=end,
                        )
                    )
        finally:
            conn.close()

        chips.sort(key=self._chip_sort_key)
        return chips

    def _chip_sort_key(self, chip: AlertChip) -> Tuple[int, int, str]:
        timeframe_index = self._TIMEFRAME_ORDER.index(chip.timeframe_key)
        category_index = self._CATEGORY_ORDER.index(chip.category_key)
        return (timeframe_index, category_index, chip.category_label)

    def _count_for_category(
        self,
        conn: sqlite3.Connection,
        config: Dict[str, object],
        start: date,
        end: date,
    ) -> int:
        table_entry = config.get("table")
        if isinstance(table_entry, str):
            count = self._count_in_table(
                conn,
                table_entry,
                tuple(config.get("columns", ())),
                start,
                end,
                extra_where=str(config.get("extra_where", "")),
            )
            return count if count >= 0 else 0

        tables = config.get("tables")
        if isinstance(tables, Iterable):
            for entry in tables:
                if not isinstance(entry, dict):
                    continue
                table_name = entry.get("table")
                columns = tuple(entry.get("columns", ()))
                extra_where = str(entry.get("extra_where", ""))
                if not table_name:
                    continue
                count = self._count_in_table(
                    conn,
                    str(table_name),
                    columns,
                    start,
                    end,
                    extra_where=extra_where,
                )
                if count >= 0:
                    return count
        return 0

    def _count_in_table(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        columns: Sequence[str],
        start: date,
        end: date,
        *,
        extra_where: str = "",
    ) -> int:
        if not self._table_exists(conn, table_name):
            return -1
        column = self._first_existing_column(conn, table_name, columns)
        if column is None:
            return -1
        column_expr = f'"{column}"'
        table_expr = f'"{table_name}"'
        where_clauses = [f"{column_expr} IS NOT NULL", f"DATE({column_expr}) BETWEEN ? AND ?"]
        extra = extra_where.strip()
        available = self._get_columns(conn, table_name)
        if extra and "is_archived" in extra and "is_archived" not in available:
            extra = ""
        if extra and "odeme_tarihi" in extra and "odeme_tarihi" not in available:
            extra = ""
        if extra:
            if extra.upper().startswith("AND "):
                where_clauses.append(extra[4:])
            else:
                where_clauses.append(extra)
        where_sql = " AND ".join(where_clauses)
        query = f"SELECT COUNT(*) FROM {table_expr} WHERE {where_sql}"
        cur = conn.cursor()
        try:
            cur.execute(query, (start.isoformat(), end.isoformat()))
        except sqlite3.OperationalError:
            return -1
        row = cur.fetchone()
        if not row:
            return 0
        try:
            return int(row[0] or 0)
        except (TypeError, ValueError):
            return 0

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        )
        return cur.fetchone() is not None

    def _first_existing_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        columns: Sequence[str],
    ) -> Optional[str]:
        if not columns:
            return None
        available = self._get_columns(conn, table_name)
        for name in columns:
            if name in available:
                return name
        return None

    def _get_columns(self, conn: sqlite3.Connection, table_name: str) -> Tuple[str, ...]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        cur = conn.cursor()
        try:
            cur.execute(f'PRAGMA table_info("{table_name}")')
        except sqlite3.OperationalError:
            columns: Tuple[str, ...] = ()
        else:
            columns = tuple(row[1] for row in cur.fetchall())
        self._table_columns_cache[table_name] = columns
        return columns
