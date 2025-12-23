# -*- coding: utf-8 -*-
"""
Inbox Processor

Sunucudan gelen değişiklikleri alıp lokal veritabanına uygular.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .models import SyncChange, SyncOperation, SyncConflict, SYNCED_TABLES
from .encryption_service import EncryptionService
from .sync_client import SyncClient

logger = logging.getLogger(__name__)


class InboxProcessor:
    """
    Inbox işleyici.

    Sunucudan gelen değişiklikleri lokal veritabanına uygular.
    Çakışma durumunda ConflictHandler'ı kullanır.
    """

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

    def get_last_revision(self) -> int:
        """Son senkronize edilen revizyonu al"""
        conn = self._get_connection()
        try:
            result = conn.execute(
                "SELECT last_sync_revision FROM sync_metadata LIMIT 1"
            ).fetchone()
            return result['last_sync_revision'] if result else 0
        except sqlite3.OperationalError:
            # Tablo henüz yok
            return 0
        finally:
            conn.close()

    def fetch_and_process(self) -> Dict[str, Any]:
        """
        Sunucudan değişiklikleri çek ve uygula.

        Returns:
            {count, conflicts, last_revision}
        """
        result = {
            'count': 0,
            'conflicts': [],
            'last_revision': 0,
            'errors': [],
        }

        # Son revizyondan sonraki değişiklikleri al
        since_revision = self.get_last_revision()

        try:
            response = self.client.pull_changes(since_revision)
        except Exception as e:
            logger.error(f"Pull hatası: {e}")
            result['errors'].append(str(e))
            return result

        changes = response.get('changes', [])
        latest_revision = response.get('latest_revision', since_revision)

        if not changes:
            logger.info("Inbox: Yeni değişiklik yok")
            result['last_revision'] = latest_revision
            return result

        logger.info(f"Inbox: {len(changes)} değişiklik alındı")

        # Değişiklikleri inbox'a kaydet
        self._save_to_inbox(changes)

        # İşlenmemiş inbox kayıtlarını uygula
        process_result = self._process_inbox()

        result['count'] = process_result['count']
        result['conflicts'] = process_result['conflicts']
        result['last_revision'] = latest_revision

        # Son revizyonu güncelle
        self._update_last_revision(latest_revision)

        return result

    def _save_to_inbox(self, changes: List[Dict[str, Any]]):
        """Değişiklikleri inbox tablosuna kaydet"""
        conn = self._get_connection()
        try:
            for change in changes:
                # Şifreli veriyi çöz
                encrypted_hex = change.get('data_encrypted', '')
                if encrypted_hex:
                    encrypted_bytes = bytes.fromhex(encrypted_hex)
                    data = self.encryption.decrypt_data(encrypted_bytes)
                else:
                    data = change.get('data', {})

                conn.execute("""
                    INSERT OR REPLACE INTO sync_inbox
                    (uuid, table_name, operation, data_json, revision)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    change['uuid'],
                    change['table_name'],
                    change['operation'],
                    json.dumps(data, default=str),
                    change.get('revision', 0),
                ))

            conn.commit()
        finally:
            conn.close()

    def _process_inbox(self) -> Dict[str, Any]:
        """
        Inbox'taki değişiklikleri işle.

        Returns:
            {count, conflicts}
        """
        result = {'count': 0, 'conflicts': []}
        conn = self._get_connection()

        try:
            # İşlenmemiş kayıtları al (revizyon sırasına göre)
            rows = conn.execute("""
                SELECT id, uuid, table_name, operation, data_json, revision
                FROM sync_inbox
                WHERE processed = 0
                ORDER BY revision ASC
            """).fetchall()

            for row in rows:
                try:
                    conflict = self._apply_change(
                        conn,
                        row['uuid'],
                        row['table_name'],
                        row['operation'],
                        json.loads(row['data_json']),
                    )

                    if conflict:
                        result['conflicts'].append(conflict)
                    else:
                        result['count'] += 1

                    # İşlendi olarak işaretle
                    conn.execute("""
                        UPDATE sync_inbox
                        SET processed = 1, processed_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), row['id']))

                except Exception as e:
                    logger.error(f"Inbox işleme hatası ({row['uuid']}): {e}")

            conn.commit()

        finally:
            conn.close()

        return result

    def _apply_change(self, conn: sqlite3.Connection, uuid: str,
                      table_name: str, operation: str,
                      data: Dict[str, Any]) -> Optional[SyncConflict]:
        """
        Tek bir değişikliği uygula.

        Returns:
            Çakışma varsa SyncConflict, yoksa None
        """
        if table_name not in SYNCED_TABLES:
            logger.warning(f"Bilinmeyen tablo: {table_name}")
            return None

        # Mevcut kaydı kontrol et
        existing = conn.execute(
            f"SELECT * FROM {table_name} WHERE uuid = ?",
            (uuid,)
        ).fetchone()

        if operation == 'DELETE':
            if existing:
                # Soft delete uygula
                conn.execute(
                    f"UPDATE {table_name} SET is_deleted = 1, synced_at = ? WHERE uuid = ?",
                    (datetime.now().isoformat(), uuid)
                )
            return None

        if operation == 'INSERT':
            if existing:
                # Zaten var, UPDATE olarak işle
                return self._apply_update(conn, table_name, uuid, data, dict(existing))
            else:
                return self._apply_insert(conn, table_name, data)

        if operation == 'UPDATE':
            if existing:
                return self._apply_update(conn, table_name, uuid, data, dict(existing))
            else:
                # Kayıt yok, INSERT olarak işle
                return self._apply_insert(conn, table_name, data)

        return None

    def _apply_insert(self, conn: sqlite3.Connection, table_name: str,
                      data: Dict[str, Any]) -> Optional[SyncConflict]:
        """INSERT işlemi uygula"""
        # Kolon isimlerini ve değerlerini hazırla
        columns = []
        values = []

        for key, value in data.items():
            if key != 'id':  # id auto-increment
                columns.append(key)
                values.append(value)

        # synced_at ekle
        columns.append('synced_at')
        values.append(datetime.now().isoformat())

        placeholders = ','.join('?' * len(values))
        column_names = ','.join(columns)

        try:
            conn.execute(
                f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})",
                values
            )
        except sqlite3.IntegrityError as e:
            logger.warning(f"INSERT hatası ({table_name}): {e}")
            # Muhtemelen unique constraint, UPDATE dene
            if 'uuid' in data:
                self._apply_update(conn, table_name, data['uuid'], data, {})

        return None

    def _apply_update(self, conn: sqlite3.Connection, table_name: str,
                      uuid: str, remote_data: Dict[str, Any],
                      local_data: Dict[str, Any]) -> Optional[SyncConflict]:
        """UPDATE işlemi uygula, gerekirse çakışma döndür"""

        # Çakışma kontrolü (Last-Write-Wins)
        local_updated = local_data.get('updated_at')
        remote_updated = remote_data.get('updated_at')

        if local_updated and remote_updated:
            # Her ikisi de timestamp'a sahip
            local_ts = self._parse_timestamp(local_updated)
            remote_ts = self._parse_timestamp(remote_updated)

            if local_ts and remote_ts and local_ts > remote_ts:
                # Lokal daha yeni, çakışma var
                return SyncConflict(
                    record_uuid=uuid,
                    table_name=table_name,
                    local_data=local_data,
                    remote_data=remote_data,
                    local_updated_at=local_ts,
                    remote_updated_at=remote_ts,
                )

        # Remote'u uygula (Last-Write-Wins veya lokal yok)
        set_clauses = []
        values = []

        for key, value in remote_data.items():
            if key not in ('id', 'uuid'):  # id ve uuid değişmez
                set_clauses.append(f"{key} = ?")
                values.append(value)

        # synced_at güncelle
        set_clauses.append("synced_at = ?")
        values.append(datetime.now().isoformat())

        values.append(uuid)  # WHERE için

        conn.execute(
            f"UPDATE {table_name} SET {','.join(set_clauses)} WHERE uuid = ?",
            values
        )

        return None

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Timestamp parse et"""
        if isinstance(ts, datetime):
            return ts

        if not ts:
            return None

        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(ts), fmt)
            except ValueError:
                continue

        return None

    def _update_last_revision(self, revision: int):
        """Son revizyonu güncelle"""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE sync_metadata
                SET last_sync_revision = ?,
                    last_sync_at = ?
            """, (revision, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()

    def clear_processed(self, older_than_days: int = 7):
        """
        Eski işlenmiş kayıtları temizle.

        Args:
            older_than_days: Bu günden eski kayıtları sil
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM sync_inbox
                WHERE processed = 1
                  AND processed_at < datetime('now', ? || ' days')
            """, (f'-{older_than_days}',))
            conn.commit()
        finally:
            conn.close()
