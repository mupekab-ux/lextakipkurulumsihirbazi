# -*- coding: utf-8 -*-
"""
Outbox Processor

Lokal değişiklikleri sync_outbox tablosundan alıp sunucuya gönderir.
Transactional Outbox Pattern implementasyonu.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .models import SyncChange, SyncOperation, SyncConflict
from .encryption_service import EncryptionService
from .sync_client import SyncClient

logger = logging.getLogger(__name__)


class OutboxProcessor:
    """
    Outbox işleyici.

    Lokal değişiklikleri toplu halde sunucuya gönderir.
    Başarısız gönderimleri retry mekanizmasıyla tekrar dener.
    """

    MAX_BATCH_SIZE = 100  # Tek seferde gönderilecek maksimum değişiklik
    MAX_RETRY_COUNT = 5   # Maksimum deneme sayısı

    def __init__(self, db_path: str, client: SyncClient,
                 encryption: EncryptionService):
        """
        Args:
            db_path: SQLite veritabanı yolu
            client: SyncClient instance
            encryption: EncryptionService instance
        """
        self.db_path = db_path
        self.client = client
        self.encryption = encryption

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_pending_count(self) -> int:
        """Bekleyen değişiklik sayısını al"""
        conn = self._get_connection()
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM sync_outbox WHERE synced = 0 AND retry_count < ?",
                (self.MAX_RETRY_COUNT,)
            ).fetchone()
            return result[0] if result else 0
        finally:
            conn.close()

    def get_pending_changes(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Bekleyen değişiklikleri al.

        Args:
            limit: Maksimum kayıt sayısı

        Returns:
            Değişiklik listesi
        """
        limit = limit or self.MAX_BATCH_SIZE
        conn = self._get_connection()

        try:
            rows = conn.execute("""
                SELECT id, uuid, table_name, operation, data_json,
                       created_at, retry_count
                FROM sync_outbox
                WHERE synced = 0 AND retry_count < ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (self.MAX_RETRY_COUNT, limit)).fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    def process(self) -> Dict[str, Any]:
        """
        Bekleyen değişiklikleri işle ve sunucuya gönder.

        Returns:
            {count, conflicts, errors}
        """
        result = {
            'count': 0,
            'conflicts': [],
            'errors': [],
        }

        pending = self.get_pending_changes()
        if not pending:
            return result

        logger.info(f"Outbox: {len(pending)} değişiklik gönderilecek")

        # Değişiklikleri şifrele ve hazırla
        encrypted_changes = []
        outbox_ids = []

        for change in pending:
            try:
                # JSON veriyi parse et
                data = json.loads(change['data_json'])

                # Şifrele
                encrypted_data = self.encryption.encrypt_data(data)

                encrypted_changes.append({
                    'uuid': change['uuid'],
                    'table_name': change['table_name'],
                    'operation': change['operation'],
                    'data_encrypted': encrypted_data.hex(),  # bytes -> hex
                })
                outbox_ids.append(change['id'])

            except Exception as e:
                logger.error(f"Değişiklik hazırlama hatası: {e}")
                result['errors'].append(str(e))
                self._mark_error(change['id'], str(e))

        if not encrypted_changes:
            return result

        # Sunucuya gönder
        try:
            response = self.client.push_changes(encrypted_changes)

            if response.get('success'):
                # Başarılı olanları işaretle
                synced_count = response.get('synced_count', len(outbox_ids))
                result['count'] = synced_count

                self._mark_synced(outbox_ids)
                logger.info(f"Outbox: {synced_count} değişiklik gönderildi")

            # Çakışmaları işle
            conflicts = response.get('conflicts', [])
            for conflict_data in conflicts:
                conflict = SyncConflict(
                    record_uuid=conflict_data['uuid'],
                    table_name=conflict_data['table_name'],
                    local_data=conflict_data.get('local_data', {}),
                    remote_data=conflict_data.get('remote_data', {}),
                )
                result['conflicts'].append(conflict)

        except Exception as e:
            logger.error(f"Push hatası: {e}")
            result['errors'].append(str(e))

            # Retry count artır
            self._increment_retry(outbox_ids)

        return result

    def _mark_synced(self, outbox_ids: List[int]):
        """Değişiklikleri senkronize olarak işaretle"""
        if not outbox_ids:
            return

        conn = self._get_connection()
        try:
            placeholders = ','.join('?' * len(outbox_ids))
            conn.execute(f"""
                UPDATE sync_outbox
                SET synced = 1, synced_at = ?
                WHERE id IN ({placeholders})
            """, [datetime.now().isoformat()] + outbox_ids)
            conn.commit()
        finally:
            conn.close()

    def _mark_error(self, outbox_id: int, error_message: str):
        """Hata durumunu kaydet"""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE sync_outbox
                SET retry_count = retry_count + 1,
                    last_retry_at = ?,
                    error_message = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), error_message, outbox_id))
            conn.commit()
        finally:
            conn.close()

    def _increment_retry(self, outbox_ids: List[int]):
        """Retry sayısını artır"""
        if not outbox_ids:
            return

        conn = self._get_connection()
        try:
            placeholders = ','.join('?' * len(outbox_ids))
            conn.execute(f"""
                UPDATE sync_outbox
                SET retry_count = retry_count + 1,
                    last_retry_at = ?
                WHERE id IN ({placeholders})
            """, [datetime.now().isoformat()] + outbox_ids)
            conn.commit()
        finally:
            conn.close()

    def add_change(self, uuid: str, table_name: str,
                   operation: str, data: Dict[str, Any]):
        """
        Yeni değişiklik ekle.

        Args:
            uuid: Kayıt UUID'si
            table_name: Tablo adı
            operation: İşlem (INSERT, UPDATE, DELETE)
            data: Veri dict
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                VALUES (?, ?, ?, ?)
            """, (uuid, table_name, operation, json.dumps(data, default=str)))
            conn.commit()
        finally:
            conn.close()

    def clear_synced(self, older_than_days: int = 7):
        """
        Eski senkronize edilmiş kayıtları temizle.

        Args:
            older_than_days: Bu günden eski kayıtları sil
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM sync_outbox
                WHERE synced = 1
                  AND synced_at < datetime('now', ? || ' days')
            """, (f'-{older_than_days}',))
            conn.commit()
        finally:
            conn.close()

    def clear_failed(self):
        """Başarısız (max retry'a ulaşmış) kayıtları temizle"""
        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM sync_outbox
                WHERE synced = 0 AND retry_count >= ?
            """, (self.MAX_RETRY_COUNT,))
            conn.commit()
        finally:
            conn.close()
