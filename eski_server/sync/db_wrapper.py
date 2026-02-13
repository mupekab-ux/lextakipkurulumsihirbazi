# -*- coding: utf-8 -*-
"""
Veritabanı İşlemleri Wrapper

Bu modül, veritabanı yazma işlemlerini wrap ederek
otomatik olarak sync_outbox'a kayıt yapar.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

from sync.outbox import SYNCABLE_TABLES, record_change, generate_uuid

logger = logging.getLogger(__name__)


def _get_connection():
    """Veritabanı bağlantısı al."""
    try:
        from app.db import get_connection
        return get_connection()
    except:
        from db import get_connection
        return get_connection()


def sync_insert(
    table_name: str,
    data: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Kayıt ekle ve outbox'a logla.

    Args:
        table_name: Tablo adı
        data: Eklenecek veri
        conn: Opsiyonel veritabanı bağlantısı

    Returns:
        Eklenen kaydın ID'si
    """
    if table_name not in SYNCABLE_TABLES:
        raise ValueError(f"Tablo senkronize edilemiyor: {table_name}")

    owns_conn = conn is None
    if owns_conn:
        conn = _get_connection()

    try:
        cur = conn.cursor()

        # UUID oluştur (yoksa)
        if 'uuid' not in data or not data['uuid']:
            data['uuid'] = generate_uuid()

        # Timestamp'ler
        now = datetime.now().isoformat()
        if 'created_at' not in data:
            data['created_at'] = now
        if 'updated_at' not in data:
            data['updated_at'] = now

        # Revision
        if 'revision' not in data:
            data['revision'] = 0

        # SQL oluştur
        columns = list(data.keys())
        placeholders = ', '.join(['?'] * len(columns))
        col_list = ', '.join(columns)
        values = [data[col] for col in columns]

        cur.execute(
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
            values
        )
        record_id = cur.lastrowid

        # Outbox'a kaydet
        record_change(
            table_name=table_name,
            operation='insert',
            record_uuid=data['uuid'],
            data=data,
            conn=conn
        )

        if owns_conn:
            conn.commit()

        return record_id

    except sqlite3.Error as e:
        logger.error(f"sync_insert hatası ({table_name}): {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def sync_update(
    table_name: str,
    record_id: int,
    data: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Kayıt güncelle ve outbox'a logla.

    Args:
        table_name: Tablo adı
        record_id: Güncellenecek kaydın ID'si
        data: Güncellenecek veriler
        conn: Opsiyonel veritabanı bağlantısı

    Returns:
        Güncelleme başarılı mı
    """
    if table_name not in SYNCABLE_TABLES:
        raise ValueError(f"Tablo senkronize edilemiyor: {table_name}")

    owns_conn = conn is None
    if owns_conn:
        conn = _get_connection()

    try:
        cur = conn.cursor()

        # Önce mevcut kaydı al (UUID için)
        cur.execute(f"SELECT uuid FROM {table_name} WHERE id = ?", (record_id,))
        row = cur.fetchone()
        if not row:
            return False

        record_uuid = row[0]

        # UUID yoksa oluştur
        if not record_uuid:
            record_uuid = generate_uuid()
            data['uuid'] = record_uuid

        # Timestamp güncelle
        data['updated_at'] = datetime.now().isoformat()

        # Revision artır
        cur.execute(f"SELECT revision FROM {table_name} WHERE id = ?", (record_id,))
        rev_row = cur.fetchone()
        current_revision = rev_row[0] if rev_row and rev_row[0] else 0
        data['revision'] = current_revision + 1

        # SQL oluştur
        set_parts = [f"{col} = ?" for col in data.keys()]
        set_clause = ', '.join(set_parts)
        values = list(data.values()) + [record_id]

        cur.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE id = ?",
            values
        )

        # Tam veriyi al (outbox için)
        table_info = SYNCABLE_TABLES[table_name]
        columns = table_info['columns']
        col_list = ', '.join(['uuid'] + columns)
        cur.execute(f"SELECT {col_list} FROM {table_name} WHERE id = ?", (record_id,))
        full_row = cur.fetchone()

        if full_row:
            full_data = {'uuid': full_row[0]}
            for i, col in enumerate(columns):
                full_data[col] = full_row[i + 1]

            # Outbox'a kaydet
            record_change(
                table_name=table_name,
                operation='update',
                record_uuid=record_uuid,
                data=full_data,
                conn=conn
            )

        if owns_conn:
            conn.commit()

        return True

    except sqlite3.Error as e:
        logger.error(f"sync_update hatası ({table_name}): {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def sync_delete(
    table_name: str,
    record_id: int,
    soft_delete: bool = True,
    conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Kayıt sil ve outbox'a logla.

    Args:
        table_name: Tablo adı
        record_id: Silinecek kaydın ID'si
        soft_delete: Soft delete mi hard delete mi
        conn: Opsiyonel veritabanı bağlantısı

    Returns:
        Silme başarılı mı
    """
    if table_name not in SYNCABLE_TABLES:
        raise ValueError(f"Tablo senkronize edilemiyor: {table_name}")

    owns_conn = conn is None
    if owns_conn:
        conn = _get_connection()

    try:
        cur = conn.cursor()

        # UUID'yi al
        cur.execute(f"SELECT uuid FROM {table_name} WHERE id = ?", (record_id,))
        row = cur.fetchone()
        if not row:
            return False

        record_uuid = row[0]
        if not record_uuid:
            # UUID yoksa oluştur ve kaydet
            record_uuid = generate_uuid()
            cur.execute(f"UPDATE {table_name} SET uuid = ? WHERE id = ?", (record_uuid, record_id))

        if soft_delete:
            # Soft delete
            cur.execute(
                f"UPDATE {table_name} SET is_deleted = 1, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), record_id)
            )
        else:
            # Hard delete
            cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))

        # Outbox'a kaydet
        record_change(
            table_name=table_name,
            operation='delete',
            record_uuid=record_uuid,
            data={'id': record_id},
            conn=conn
        )

        if owns_conn:
            conn.commit()

        return True

    except sqlite3.Error as e:
        logger.error(f"sync_delete hatası ({table_name}): {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def with_sync_tracking(table_name: str):
    """
    Decorator: Fonksiyonu sync tracking ile wrap et.

    Fonksiyon bir kayıt ID'si döndürmelidir.
    Insert için kullanılır.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Önce orijinal fonksiyonu çalıştır
            result = func(*args, **kwargs)

            # Eğer sonuç bir ID ise, outbox'a kaydet
            if isinstance(result, int) and result > 0:
                try:
                    conn = _get_connection()
                    cur = conn.cursor()

                    # UUID kontrolü
                    cur.execute(f"SELECT uuid FROM {table_name} WHERE id = ?", (result,))
                    row = cur.fetchone()

                    if row:
                        record_uuid = row[0]
                        if not record_uuid:
                            record_uuid = generate_uuid()
                            cur.execute(
                                f"UPDATE {table_name} SET uuid = ? WHERE id = ?",
                                (record_uuid, result)
                            )
                            conn.commit()

                        # Tam veriyi al
                        table_info = SYNCABLE_TABLES.get(table_name)
                        if table_info:
                            columns = table_info['columns']
                            col_list = ', '.join(['uuid'] + columns)
                            cur.execute(f"SELECT {col_list} FROM {table_name} WHERE id = ?", (result,))
                            full_row = cur.fetchone()

                            if full_row:
                                full_data = {'uuid': full_row[0]}
                                for i, col in enumerate(columns):
                                    full_data[col] = full_row[i + 1]

                                record_change(
                                    table_name=table_name,
                                    operation='insert',
                                    record_uuid=record_uuid,
                                    data=full_data,
                                    conn=conn
                                )
                                conn.commit()

                    conn.close()
                except Exception as e:
                    logger.error(f"Sync tracking hatası: {e}")

            return result
        return wrapper
    return decorator


# Kolaylık fonksiyonları - sık kullanılan tablolar için

def sync_dosya_insert(data: Dict[str, Any]) -> int:
    """Dosya ekle ve sync'e logla."""
    return sync_insert('dosyalar', data)


def sync_dosya_update(dosya_id: int, data: Dict[str, Any]) -> bool:
    """Dosya güncelle ve sync'e logla."""
    return sync_update('dosyalar', dosya_id, data)


def sync_finans_insert(data: Dict[str, Any]) -> int:
    """Finans ekle ve sync'e logla."""
    return sync_insert('finans', data)


def sync_finans_update(finans_id: int, data: Dict[str, Any]) -> bool:
    """Finans güncelle ve sync'e logla."""
    return sync_update('finans', finans_id, data)


def sync_tebligat_insert(data: Dict[str, Any]) -> int:
    """Tebligat ekle ve sync'e logla."""
    return sync_insert('tebligatlar', data)


def sync_tebligat_update(tebligat_id: int, data: Dict[str, Any]) -> bool:
    """Tebligat güncelle ve sync'e logla."""
    return sync_update('tebligatlar', tebligat_id, data)


def sync_gorev_insert(data: Dict[str, Any]) -> int:
    """Görev ekle ve sync'e logla."""
    return sync_insert('gorevler', data)


def sync_gorev_update(gorev_id: int, data: Dict[str, Any]) -> bool:
    """Görev güncelle ve sync'e logla."""
    return sync_update('gorevler', gorev_id, data)
