# -*- coding: utf-8 -*-
"""
Senkronizasyon Veri Birleştirici

Sunucudan gelen değişiklikleri yerel veritabanına uygular.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from sync.outbox import SYNCABLE_TABLES, generate_uuid

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
    Sunucudan gelen değişiklikleri yerel veritabanına uygula.

    Args:
        changes: Değişiklik listesi
            Her biri: {'table': str, 'op': str, 'uuid': str, 'data': dict}

    Returns:
        İstatistikler: {'inserted': int, 'updated': int, 'deleted': int, 'errors': int}
    """
    stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 0}

    if not changes:
        return stats

    conn = _get_connection()
    try:
        cur = conn.cursor()

        for change in changes:
            try:
                table_name = change.get('table')
                operation = change.get('op')
                record_uuid = change.get('uuid')
                data = change.get('data', {})

                if table_name not in SYNCABLE_TABLES:
                    logger.warning(f"Bilinmeyen tablo: {table_name}")
                    stats['errors'] += 1
                    continue

                if operation == 'insert':
                    _insert_record(cur, table_name, record_uuid, data)
                    stats['inserted'] += 1

                elif operation == 'update':
                    updated = _update_record(cur, table_name, record_uuid, data)
                    if updated:
                        stats['updated'] += 1
                    else:
                        # Kayıt yoksa insert yap
                        _insert_record(cur, table_name, record_uuid, data)
                        stats['inserted'] += 1

                elif operation == 'upsert':
                    # Upsert: varsa güncelle, yoksa ekle
                    updated = _update_record(cur, table_name, record_uuid, data)
                    if updated:
                        stats['updated'] += 1
                    else:
                        _insert_record(cur, table_name, record_uuid, data)
                        stats['inserted'] += 1

                elif operation == 'delete':
                    _delete_record(cur, table_name, record_uuid)
                    stats['deleted'] += 1

                else:
                    logger.warning(f"Bilinmeyen operasyon: {operation}")
                    stats['errors'] += 1

            except Exception as e:
                logger.error(f"Değişiklik uygulanırken hata: {change}, {e}")
                stats['errors'] += 1

        conn.commit()

    except sqlite3.Error as e:
        logger.exception(f"Veritabanı hatası: {e}")
        conn.rollback()
    finally:
        conn.close()

    return stats


def _insert_record(
    cur: sqlite3.Cursor,
    table_name: str,
    record_uuid: str,
    data: Dict[str, Any]
) -> bool:
    """Yeni kayıt ekle."""
    table_info = SYNCABLE_TABLES[table_name]
    uuid_col = table_info.get('uuid_column', 'uuid')
    columns = table_info['columns']

    # Önce UUID'nin zaten var olup olmadığını kontrol et
    cur.execute(f"SELECT 1 FROM {table_name} WHERE {uuid_col} = ?", (record_uuid,))
    if cur.fetchone():
        # Zaten var - update yap
        return _update_record(cur, table_name, record_uuid, data)

    # Kolon ve değer listesi oluştur
    insert_cols = [uuid_col]
    insert_vals = [record_uuid]

    for col in columns:
        if col in data:
            insert_cols.append(col)
            insert_vals.append(data[col])

    # Timestamp kolonları ekle
    if 'created_at' not in insert_cols:
        insert_cols.append('created_at')
        insert_vals.append(datetime.now().isoformat())
    if 'updated_at' not in insert_cols:
        insert_cols.append('updated_at')
        insert_vals.append(datetime.now().isoformat())

    placeholders = ', '.join(['?'] * len(insert_vals))
    col_list = ', '.join(insert_cols)

    try:
        cur.execute(
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
            insert_vals
        )
        return True
    except sqlite3.IntegrityError as e:
        # Foreign key veya unique constraint hatası
        logger.warning(f"Insert hatası ({table_name}): {e}")
        return False


def _update_record(
    cur: sqlite3.Cursor,
    table_name: str,
    record_uuid: str,
    data: Dict[str, Any]
) -> bool:
    """Mevcut kaydı güncelle."""
    table_info = SYNCABLE_TABLES[table_name]
    uuid_col = table_info.get('uuid_column', 'uuid')
    columns = table_info['columns']

    # Güncellenecek kolonları hazırla
    update_parts = []
    update_vals = []

    for col in columns:
        if col in data:
            update_parts.append(f"{col} = ?")
            update_vals.append(data[col])

    if not update_parts:
        return False

    # updated_at ekle
    update_parts.append("updated_at = ?")
    update_vals.append(datetime.now().isoformat())

    # UUID'yi WHERE için ekle
    update_vals.append(record_uuid)

    set_clause = ', '.join(update_parts)
    cur.execute(
        f"UPDATE {table_name} SET {set_clause} WHERE {uuid_col} = ?",
        update_vals
    )

    return cur.rowcount > 0


def _delete_record(
    cur: sqlite3.Cursor,
    table_name: str,
    record_uuid: str
) -> bool:
    """Kaydı sil (soft delete)."""
    table_info = SYNCABLE_TABLES[table_name]
    uuid_col = table_info.get('uuid_column', 'uuid')

    # Soft delete: is_deleted = 1
    cur.execute(f"""
        UPDATE {table_name}
        SET is_deleted = 1, updated_at = ?
        WHERE {uuid_col} = ?
    """, (datetime.now().isoformat(), record_uuid))

    return cur.rowcount > 0


def get_local_revision(table_name: str, record_uuid: str) -> int:
    """Yerel kaydın revision numarasını al."""
    if table_name not in SYNCABLE_TABLES:
        return 0

    conn = _get_connection()
    try:
        cur = conn.cursor()
        uuid_col = SYNCABLE_TABLES[table_name].get('uuid_column', 'uuid')

        cur.execute(f"SELECT revision FROM {table_name} WHERE {uuid_col} = ?", (record_uuid,))
        row = cur.fetchone()

        return row[0] if row and row[0] else 0

    except sqlite3.Error as e:
        logger.error(f"Revision alınırken hata: {e}")
        return 0
    finally:
        conn.close()


def conflict_check(
    table_name: str,
    record_uuid: str,
    incoming_revision: int,
    incoming_updated_at: str
) -> str:
    """
    Çakışma kontrolü yap.

    Returns:
        'accept' - Gelen veriyi kabul et
        'reject' - Gelen veriyi reddet
        'merge'  - Birleştirme gerekli (şimdilik kullanılmıyor)
    """
    if table_name not in SYNCABLE_TABLES:
        return 'reject'

    conn = _get_connection()
    try:
        cur = conn.cursor()
        uuid_col = SYNCABLE_TABLES[table_name].get('uuid_column', 'uuid')

        cur.execute(f"""
            SELECT revision, updated_at FROM {table_name}
            WHERE {uuid_col} = ?
        """, (record_uuid,))
        row = cur.fetchone()

        if not row:
            # Kayıt yok, kabul et
            return 'accept'

        local_revision = row[0] or 0
        local_updated_at = row[1] or ''

        # Last-write-wins: Daha yüksek revision veya daha yeni tarih kazanır
        if incoming_revision > local_revision:
            return 'accept'

        if incoming_revision < local_revision:
            return 'reject'

        # Revision eşit - tarihe bak
        if incoming_updated_at > local_updated_at:
            return 'accept'

        return 'reject'

    except sqlite3.Error as e:
        logger.error(f"Conflict check hatası: {e}")
        return 'reject'
    finally:
        conn.close()


def get_all_records_for_initial_sync(table_name: str) -> List[Dict[str, Any]]:
    """
    İlk senkronizasyon için tüm kayıtları al.

    Yerel veritabanındaki tüm kayıtları sunucuya göndermek için kullanılır.
    """
    if table_name not in SYNCABLE_TABLES:
        return []

    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        table_info = SYNCABLE_TABLES[table_name]
        uuid_col = table_info.get('uuid_column', 'uuid')
        columns = table_info['columns']

        col_list = ', '.join([uuid_col] + columns)
        cur.execute(f"SELECT {col_list} FROM {table_name} WHERE is_deleted = 0 OR is_deleted IS NULL")

        records = []
        for row in cur.fetchall():
            record = dict(row)
            # UUID'yi ayır
            record_uuid = record.pop(uuid_col, None) or record.pop('uuid', None)
            if record_uuid:
                records.append({
                    'table': table_name,
                    'op': 'insert',
                    'uuid': record_uuid,
                    'data': record
                })

        return records

    except sqlite3.Error as e:
        logger.error(f"Initial sync verisi alınırken hata: {e}")
        return []
    finally:
        conn.close()


def prepare_initial_sync_payload() -> List[Dict[str, Any]]:
    """
    İlk senkronizasyon için tüm veritabanını hazırla.

    Returns:
        Tüm tablolardaki kayıtların listesi
    """
    all_records = []

    for table_name in SYNCABLE_TABLES.keys():
        try:
            records = get_all_records_for_initial_sync(table_name)
            all_records.extend(records)
            logger.info(f"Initial sync: {table_name} - {len(records)} kayıt")
        except Exception as e:
            logger.error(f"Initial sync hazırlanırken hata ({table_name}): {e}")

    return all_records
