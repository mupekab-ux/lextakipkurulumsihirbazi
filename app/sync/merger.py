# -*- coding: utf-8 -*-
"""
Sync Merger - Gelen Değişiklikleri Uygula

Sunucudan gelen değişiklikleri yerel veritabanına uygular.
Last-Write-Wins stratejisi kullanılır.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from .outbox import SYNCABLE_TABLES

logger = logging.getLogger(__name__)


def _get_connection():
    """Veritabanı bağlantısı al."""
    try:
        from app.db import get_connection
        return get_connection()
    except:
        from db import get_connection
        return get_connection()


def apply_incoming_changes(changes: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Sunucudan gelen değişiklikleri uygula.

    Args:
        changes: Değişiklik listesi

    Returns:
        {'inserted': X, 'updated': Y, 'deleted': Z, 'skipped': W}
    """
    stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'skipped': 0, 'errors': 0}

    if not changes:
        return stats

    conn = _get_connection()
    try:
        for change in changes:
            try:
                table_name = change.get('table')
                operation = change.get('op')
                record_uuid = change.get('uuid')
                data = change.get('data', {})

                if table_name not in SYNCABLE_TABLES:
                    logger.warning(f"Bilinmeyen tablo: {table_name}")
                    stats['skipped'] += 1
                    continue

                if operation == 'delete':
                    result = _apply_delete(conn, table_name, record_uuid)
                    if result:
                        stats['deleted'] += 1
                else:
                    result = _apply_upsert(conn, table_name, record_uuid, data)
                    if result == 'inserted':
                        stats['inserted'] += 1
                    elif result == 'updated':
                        stats['updated'] += 1
                    else:
                        stats['skipped'] += 1

            except Exception as e:
                logger.error(f"Değişiklik uygulanırken hata: {change} - {e}")
                stats['errors'] += 1
                continue

        conn.commit()

    except Exception as e:
        logger.exception("Değişiklikler uygulanırken genel hata")
        conn.rollback()
        raise
    finally:
        conn.close()

    return stats


def _apply_upsert(
    conn: sqlite3.Connection,
    table_name: str,
    record_uuid: str,
    data: Dict[str, Any]
) -> str:
    """
    Kayıt ekle veya güncelle.

    Returns:
        'inserted', 'updated', veya 'skipped'
    """
    table_config = SYNCABLE_TABLES[table_name]
    uuid_col = table_config.get('uuid_column', 'uuid')
    columns = table_config['columns']

    cur = conn.cursor()

    # Mevcut kaydı kontrol et
    cur.execute(f"SELECT {uuid_col} FROM {table_name} WHERE {uuid_col} = ?", (record_uuid,))
    existing = cur.fetchone()

    # Sadece geçerli kolonları kullan
    valid_data = {}
    for col in columns:
        if col in data:
            valid_data[col] = data[col]

    if existing:
        # UPDATE
        if not valid_data:
            return 'skipped'

        set_clause = ', '.join([f"{col} = ?" for col in valid_data.keys()])
        values = list(valid_data.values()) + [record_uuid]

        cur.execute(f"""
            UPDATE {table_name}
            SET {set_clause}
            WHERE {uuid_col} = ?
        """, values)

        return 'updated'
    else:
        # INSERT
        valid_data[uuid_col] = record_uuid

        col_names = ', '.join(valid_data.keys())
        placeholders = ', '.join(['?' for _ in valid_data])
        values = list(valid_data.values())

        try:
            cur.execute(f"""
                INSERT INTO {table_name} ({col_names})
                VALUES ({placeholders})
            """, values)
            return 'inserted'
        except sqlite3.IntegrityError as e:
            logger.warning(f"Insert integrity error (skipping): {e}")
            return 'skipped'


def _apply_delete(
    conn: sqlite3.Connection,
    table_name: str,
    record_uuid: str
) -> bool:
    """
    Kaydı sil (soft delete veya hard delete).

    Returns:
        True if deleted, False otherwise
    """
    table_config = SYNCABLE_TABLES[table_name]
    uuid_col = table_config.get('uuid_column', 'uuid')

    cur = conn.cursor()

    # Önce soft delete dene (is_deleted kolonu varsa)
    try:
        cur.execute(f"""
            UPDATE {table_name}
            SET is_deleted = 1
            WHERE {uuid_col} = ?
        """, (record_uuid,))

        if cur.rowcount > 0:
            return True
    except sqlite3.OperationalError:
        pass

    # Soft delete yoksa hard delete
    cur.execute(f"""
        DELETE FROM {table_name}
        WHERE {uuid_col} = ?
    """, (record_uuid,))

    return cur.rowcount > 0


def prepare_initial_sync_payload() -> List[Dict[str, Any]]:
    """
    İlk sync için tüm verileri hazırla.

    Returns:
        Tüm kayıtların listesi
    """
    conn = _get_connection()
    changes = []

    try:
        conn.row_factory = sqlite3.Row

        for table_name, table_config in SYNCABLE_TABLES.items():
            try:
                uuid_col = table_config.get('uuid_column', 'uuid')
                columns = table_config['columns']

                # UUID kolonunu da dahil et
                all_cols = [uuid_col] + columns
                col_list = ', '.join(all_cols)

                cur = conn.cursor()
                cur.execute(f"SELECT {col_list} FROM {table_name}")

                for row in cur.fetchall():
                    record_uuid = row[uuid_col]
                    if not record_uuid:
                        continue

                    data = {}
                    for col in columns:
                        if col in row.keys():
                            data[col] = row[col]

                    changes.append({
                        'table': table_name,
                        'op': 'insert',
                        'uuid': record_uuid,
                        'data': data
                    })

            except sqlite3.OperationalError as e:
                logger.warning(f"Tablo okunamadı: {table_name} - {e}")
                continue

    finally:
        conn.close()

    return changes
