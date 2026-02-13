# -*- coding: utf-8 -*-
"""
Sync Outbox - Değişiklik Takibi

Her INSERT/UPDATE/DELETE işlemi outbox'a kaydedilir.
Sync sırasında bu değişiklikler sunucuya gönderilir.
"""

import json
import logging
import uuid
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Senkronize edilecek tablolar ve kolonları
SYNCABLE_TABLES = {
    'dosyalar': {
        'uuid_column': 'uuid',
        'columns': [
            'buro_takip_no', 'dosya_esas_no', 'muvekkil_adi', 'muvekkil_rolu',
            'karsi_taraf', 'dosya_konusu', 'mahkeme_adi', 'dava_acilis_tarihi',
            'durusma_tarihi', 'dava_durumu', 'is_tarihi', 'aciklama',
            'tekrar_dava_durumu_2', 'is_tarihi_2', 'aciklama_2', 'is_archived'
        ]
    },
    'finans': {
        'uuid_column': 'uuid',
        'fk_column': 'dosya_uuid',
        'columns': [
            'dosya_uuid', 'sozlesme_ucreti', 'sozlesme_yuzdesi',
            'sozlesme_ucreti_cents', 'tahsil_hedef_cents', 'tahsil_edilen_cents',
            'masraf_toplam_cents', 'masraf_tahsil_cents', 'notlar', 'yuzde_is_sonu'
        ]
    },
    'taksitler': {
        'uuid_column': 'uuid',
        'fk_column': 'finans_uuid',
        'columns': [
            'finans_uuid', 'vade_tarihi', 'tutar_cents', 'durum',
            'odeme_tarihi', 'aciklama'
        ]
    },
    'odeme_kayitlari': {
        'uuid_column': 'uuid',
        'fk_column': 'finans_uuid',
        'columns': [
            'finans_uuid', 'tarih', 'tutar_cents', 'yontem',
            'aciklama', 'taksit_uuid'
        ]
    },
    'masraflar': {
        'uuid_column': 'uuid',
        'fk_column': 'finans_uuid',
        'columns': [
            'finans_uuid', 'kalem', 'tutar_cents', 'tarih',
            'tahsil_durumu', 'tahsil_tarihi', 'aciklama'
        ]
    },
    'tebligatlar': {
        'uuid_column': 'uuid',
        'columns': [
            'dosya_no', 'kurum', 'geldigi_tarih', 'teblig_tarihi',
            'is_son_gunu', 'icerik'
        ]
    },
    'arabuluculuk': {
        'uuid_column': 'uuid',
        'columns': [
            'davaci', 'davali', 'arb_adi', 'arb_tel',
            'toplanti_tarihi', 'toplanti_saati', 'konu'
        ]
    },
    'gorevler': {
        'uuid_column': 'uuid',
        'columns': [
            'tarih', 'konu', 'aciklama', 'atanan_kullanicilar',
            'kaynak_turu', 'olusturan_kullanici', 'olusturma_zamani',
            'tamamlandi', 'tamamlanma_zamani', 'dosya_uuid', 'gorev_turu'
        ]
    },
    'statuses': {
        'uuid_column': 'uuid',
        'columns': ['ad', 'color_hex', 'owner']
    },
    'muvekkil_kasasi': {
        'uuid_column': 'uuid',
        'fk_column': 'dosya_uuid',
        'columns': ['dosya_uuid', 'tarih', 'tutar_kurus', 'islem_turu', 'aciklama']
    },
    'finans_harici': {
        'uuid_column': 'uuid',
        'columns': [
            'harici_bn', 'harici_muvekkil', 'harici_esas_no',
            'sabit_ucret_cents', 'yuzde_orani', 'tahsil_edilen_cents',
            'masraf_toplam_cents', 'masraf_tahsil_cents', 'tahsil_hedef_cents',
            'yuzde_is_sonu', 'notlar'
        ]
    },
    'dosya_atamalar': {
        'uuid_column': 'uuid',
        'columns': ['dosya_uuid', 'user_uuid']
    },
    'attachments': {
        'uuid_column': 'uuid',
        'fk_column': 'dosya_uuid',
        'columns': [
            'dosya_uuid', 'original_name', 'stored_path', 'mime',
            'size_bytes', 'checksum', 'added_at'
        ]
    },
    'custom_tabs': {
        'uuid_column': 'uuid',
        'columns': ['name']
    },
    'custom_tabs_dosyalar': {
        'uuid_column': 'uuid',
        'columns': ['custom_tab_uuid', 'dosya_uuid']
    },
    'ayarlar': {
        'uuid_column': 'uuid',
        'columns': ['key', 'value']
    },
}


def _get_connection():
    """Veritabanı bağlantısı al."""
    try:
        from app.db import get_connection
        return get_connection()
    except:
        from db import get_connection
        return get_connection()


def generate_uuid() -> str:
    """Yeni UUID oluştur."""
    return str(uuid.uuid4())


def ensure_outbox_table():
    """sync_outbox tablosunu oluştur."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                record_uuid TEXT NOT NULL,
                data TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 0,
                synced_at TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_outbox_synced ON sync_outbox(synced)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_outbox_table ON sync_outbox(table_name)")
        conn.commit()
    finally:
        conn.close()


def record_change(
    table_name: str,
    operation: str,
    record_uuid: str,
    data: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Değişikliği outbox'a kaydet.

    Args:
        table_name: Tablo adı
        operation: İşlem türü (insert/update/delete)
        record_uuid: Kaydın UUID'si
        data: Kayıt verileri
        conn: Opsiyonel veritabanı bağlantısı

    Returns:
        Outbox kayıt ID'si
    """
    ensure_outbox_table()

    owns_conn = conn is None
    if owns_conn:
        conn = _get_connection()

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sync_outbox (
                table_name, operation, record_uuid, data, created_at, synced
            ) VALUES (?, ?, ?, ?, ?, 0)
        """, (
            table_name,
            operation,
            record_uuid,
            json.dumps(data, ensure_ascii=False, default=str),
            datetime.now().isoformat()
        ))

        if owns_conn:
            conn.commit()

        return cur.lastrowid

    except sqlite3.Error as e:
        logger.error(f"Outbox kaydı oluşturulurken hata: {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def get_pending_changes() -> List[Dict[str, Any]]:
    """Gönderilmemiş değişiklikleri al."""
    ensure_outbox_table()

    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, table_name, operation, record_uuid, data, created_at
            FROM sync_outbox
            WHERE synced = 0
            ORDER BY id ASC
        """)

        changes = []
        for row in cur.fetchall():
            try:
                data = json.loads(row['data']) if row['data'] else {}
            except json.JSONDecodeError:
                data = {}

            changes.append({
                'id': row['id'],
                'table': row['table_name'],
                'op': row['operation'],
                'uuid': row['record_uuid'],
                'data': data,
                'created_at': row['created_at']
            })

        return changes

    except sqlite3.Error as e:
        logger.error(f"Outbox okunurken hata: {e}")
        return []
    finally:
        conn.close()


def mark_changes_synced(change_ids: List[int]) -> bool:
    """Değişiklikleri senkronize edildi olarak işaretle."""
    if not change_ids:
        return True

    conn = _get_connection()
    try:
        cur = conn.cursor()
        placeholders = ','.join('?' * len(change_ids))
        cur.execute(f"""
            UPDATE sync_outbox
            SET synced = 1, synced_at = ?
            WHERE id IN ({placeholders})
        """, [datetime.now().isoformat()] + list(change_ids))
        conn.commit()
        return True

    except sqlite3.Error as e:
        logger.error(f"Outbox güncellenirken hata: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def clear_synced_changes(older_than_days: int = 7) -> int:
    """Eski senkronize edilmiş kayıtları temizle."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM sync_outbox
            WHERE synced = 1
            AND synced_at < datetime('now', ? || ' days')
        """, (f"-{older_than_days}",))
        deleted = cur.rowcount
        conn.commit()
        return deleted

    except sqlite3.Error as e:
        logger.error(f"Outbox temizlenirken hata: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_outbox_stats() -> Dict[str, int]:
    """Outbox istatistiklerini al."""
    ensure_outbox_table()

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sync_outbox WHERE synced = 0")
        pending = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sync_outbox WHERE synced = 1")
        synced = cur.fetchone()[0]

        return {
            'pending': pending,
            'synced': synced,
            'total': pending + synced
        }

    except sqlite3.Error as e:
        logger.error(f"Outbox stats alınırken hata: {e}")
        return {'pending': 0, 'synced': 0, 'total': 0}
    finally:
        conn.close()


def get_record_data(
    table_name: str,
    record_uuid: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Kayıt verilerini al."""
    if table_name not in SYNCABLE_TABLES:
        return None

    owns_conn = conn is None
    if owns_conn:
        conn = _get_connection()

    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        uuid_col = SYNCABLE_TABLES[table_name].get('uuid_column', 'uuid')
        columns = SYNCABLE_TABLES[table_name]['columns']

        col_list = ', '.join(columns)
        cur.execute(f"SELECT {col_list} FROM {table_name} WHERE {uuid_col} = ?", (record_uuid,))
        row = cur.fetchone()

        if row:
            return dict(row)
        return None

    except sqlite3.Error as e:
        logger.error(f"Kayıt verisi alınırken hata: {e}")
        return None
    finally:
        if owns_conn:
            conn.close()


# =============================================================================
# WRAPPER FONKSİYONLAR - Kolay kullanım için
# =============================================================================

def sync_record_insert(table_name: str, record_uuid: str, data: Dict[str, Any], conn=None):
    """Insert işlemini outbox'a kaydet."""
    if table_name in SYNCABLE_TABLES:
        record_change(table_name, 'insert', record_uuid, data, conn)


def sync_record_update(table_name: str, record_uuid: str, data: Dict[str, Any], conn=None):
    """Update işlemini outbox'a kaydet."""
    if table_name in SYNCABLE_TABLES:
        record_change(table_name, 'update', record_uuid, data, conn)


def sync_record_delete(table_name: str, record_uuid: str, conn=None):
    """Delete işlemini outbox'a kaydet."""
    if table_name in SYNCABLE_TABLES:
        record_change(table_name, 'delete', record_uuid, {}, conn)
