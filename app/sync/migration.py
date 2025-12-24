# -*- coding: utf-8 -*-
"""
Veritabanı Migration

Mevcut SQLite tablolarına sync kolonları ekler ve
trigger'ları oluşturur.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from typing import List, Tuple

from .models import SYNCED_TABLES, SYNC_COLUMNS

logger = logging.getLogger(__name__)


class SyncMigration:
    """
    Sync için veritabanı migration'ı.

    Yapılan işlemler:
    1. Mevcut tablolara sync kolonları ekle (uuid, firm_id, revision, etc.)
    2. Sync tablolarını oluştur (metadata, outbox, inbox)
    3. Mevcut kayıtlara UUID ata
    4. Trigger'ları oluştur (otomatik outbox kaydı)
    """

    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLite veritabanı yolu
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def run_all(self) -> Tuple[bool, str]:
        """
        Tüm migration'ları çalıştır.

        Returns:
            (başarılı, mesaj)
        """
        try:
            logger.info("Sync migration başlıyor...")

            # 1. Sync tablolarını oluştur
            self.create_sync_tables()
            logger.info("Sync tabloları oluşturuldu")

            # 2. Mevcut tablolara sync kolonları ekle
            self.add_sync_columns()
            logger.info("Sync kolonları eklendi")

            # 3. Mevcut kayıtlara UUID ata
            self.assign_uuids()
            logger.info("UUID'ler atandı")

            # 4. Trigger'ları oluştur
            self.create_triggers()
            logger.info("Trigger'lar oluşturuldu")

            logger.info("Sync migration tamamlandı")
            return True, "Migration başarıyla tamamlandı"

        except Exception as e:
            logger.error(f"Migration hatası: {e}")
            return False, f"Migration hatası: {e}"

    def create_sync_tables(self):
        """Sync tablolarını oluştur"""
        conn = self._get_connection()
        try:
            # sync_metadata - Cihaz ve büro bilgileri
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR(36) NOT NULL,
                    firm_id VARCHAR(36),
                    firm_key_encrypted BLOB,
                    last_sync_revision INTEGER DEFAULT 0,
                    last_sync_at DATETIME,
                    server_url TEXT,
                    is_sync_enabled INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # sync_outbox - Gönderilecek değişiklikler
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_retry_at DATETIME,
                    synced INTEGER DEFAULT 0,
                    synced_at DATETIME,
                    error_message TEXT
                )
            """)

            # sync_inbox - Alınan değişiklikler
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed INTEGER DEFAULT 0,
                    processed_at DATETIME
                )
            """)

            # sync_conflicts - Çakışma kayıtları
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_uuid VARCHAR(36) NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    local_data TEXT,
                    remote_data TEXT,
                    winning_data TEXT,
                    resolution VARCHAR(50),
                    resolved_by VARCHAR(36),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # İndeksler
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_pending "
                "ON sync_outbox(synced, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_inbox_pending "
                "ON sync_inbox(processed, revision)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conflicts_uuid "
                "ON sync_conflicts(record_uuid)"
            )

            conn.commit()
        finally:
            conn.close()

    def add_sync_columns(self):
        """Mevcut tablolara sync kolonları ekle"""
        conn = self._get_connection()
        try:
            for table in SYNCED_TABLES:
                # Tablo var mı kontrol et
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if not exists:
                    logger.info(f"Tablo bulunamadı, atlanıyor: {table}")
                    continue

                # Mevcut kolonları al
                existing_columns = set()
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    existing_columns.add(row[1])  # column name

                # Eksik kolonları ekle
                for col_name, col_type in SYNC_COLUMNS:
                    if col_name not in existing_columns:
                        try:
                            conn.execute(
                                f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                            )
                            logger.debug(f"{table}.{col_name} eklendi")
                        except sqlite3.OperationalError as e:
                            # Kolon zaten var olabilir
                            logger.debug(f"{table}.{col_name} eklenemedi: {e}")

                # created_at ve updated_at yoksa ekle (sync dışı ama gerekli)
                if 'created_at' not in existing_columns:
                    try:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                        )
                    except sqlite3.OperationalError:
                        pass

                if 'updated_at' not in existing_columns:
                    try:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                        )
                    except sqlite3.OperationalError:
                        pass

            conn.commit()
        finally:
            conn.close()

    def assign_uuids(self):
        """Mevcut kayıtlara UUID ata"""
        conn = self._get_connection()
        try:
            for table in SYNCED_TABLES:
                # Tablo var mı kontrol et
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if not exists:
                    continue

                # uuid kolonu var mı?
                has_uuid = False
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    if row[1] == 'uuid':
                        has_uuid = True
                        break

                if not has_uuid:
                    continue

                # UUID'si olmayan kayıtları al
                rows = conn.execute(
                    f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = ''"
                ).fetchall()

                # Her birine UUID ata
                for row in rows:
                    new_uuid = str(uuid.uuid4())
                    conn.execute(
                        f"UPDATE {table} SET uuid = ? WHERE id = ?",
                        (new_uuid, row[0])
                    )

                if rows:
                    logger.info(f"{table}: {len(rows)} kayda UUID atandı")

            conn.commit()
        finally:
            conn.close()

    def create_triggers(self):
        """
        Otomatik outbox kaydı için trigger'lar oluştur.

        Her INSERT, UPDATE, DELETE işleminde sync_outbox'a kayıt ekler.
        """
        conn = self._get_connection()
        try:
            for table in SYNCED_TABLES:
                # Tablo var mı kontrol et
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if not exists:
                    continue

                # Mevcut trigger'ları temizle
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_insert")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_update")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_delete")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_real_delete")

                # Kolon listesini al (JSON için)
                columns = []
                has_id_column = False
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    columns.append(row[1])
                    if row[1] == 'id':
                        has_id_column = True

                # Junction tablolar için (id kolonu olmayan) WHERE koşulu
                # rowid kullanıyoruz - SQLite'da her tablo için mevcuttur
                if has_id_column:
                    where_clause_new = "id = NEW.id"
                    where_clause_old = "id = OLD.id"
                    delete_json_new = "json_object('uuid', NEW.uuid, 'id', NEW.id)"
                    delete_json_old = "json_object('uuid', OLD.uuid, 'id', OLD.id)"
                else:
                    # Junction tablolar için rowid kullan
                    where_clause_new = "rowid = NEW.rowid"
                    where_clause_old = "rowid = OLD.rowid"
                    delete_json_new = "json_object('uuid', NEW.uuid)"
                    delete_json_old = "json_object('uuid', OLD.uuid)"

                # INSERT trigger
                # Not: uuid trigger içinde üretilecek
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_sync_insert
                    AFTER INSERT ON {table}
                    WHEN (SELECT COALESCE(is_sync_enabled, 0) FROM sync_metadata LIMIT 1) = 1
                    BEGIN
                        INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                        SELECT
                            COALESCE(NEW.uuid, lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
                            '{table}',
                            'INSERT',
                            json_object({self._build_json_object_args(columns, 'NEW')})
                        WHERE NEW.uuid IS NOT NULL OR 1=1;

                        UPDATE {table}
                        SET uuid = (SELECT uuid FROM sync_outbox ORDER BY id DESC LIMIT 1),
                            revision = COALESCE(revision, 0) + 1,
                            created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE {where_clause_new} AND NEW.uuid IS NULL;
                    END;
                """)

                # UPDATE trigger - Tüm güncellemeleri yakala (uuid varsa)
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_sync_update
                    AFTER UPDATE ON {table}
                    WHEN (SELECT COALESCE(is_sync_enabled, 0) FROM sync_metadata LIMIT 1) = 1
                      AND NEW.uuid IS NOT NULL
                      AND NEW.uuid != ''
                    BEGIN
                        INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                        VALUES (
                            NEW.uuid,
                            '{table}',
                            'UPDATE',
                            json_object({self._build_json_object_args(columns, 'NEW')})
                        );

                        UPDATE {table}
                        SET revision = COALESCE(revision, 0) + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE {where_clause_new};
                    END;
                """)

                # DELETE trigger (soft delete)
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_sync_delete
                    AFTER UPDATE OF is_deleted ON {table}
                    WHEN NEW.is_deleted = 1
                      AND (SELECT COALESCE(is_sync_enabled, 0) FROM sync_metadata LIMIT 1) = 1
                    BEGIN
                        INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                        VALUES (
                            NEW.uuid,
                            '{table}',
                            'DELETE',
                            {delete_json_new}
                        );
                    END;
                """)

                # REAL DELETE trigger - Gerçek silme işlemleri için
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_sync_real_delete
                    BEFORE DELETE ON {table}
                    WHEN (SELECT COALESCE(is_sync_enabled, 0) FROM sync_metadata LIMIT 1) = 1
                      AND OLD.uuid IS NOT NULL
                      AND OLD.uuid != ''
                    BEGIN
                        INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                        VALUES (
                            OLD.uuid,
                            '{table}',
                            'DELETE',
                            {delete_json_old}
                        );
                    END;
                """)

                logger.debug(f"{table} trigger'ları oluşturuldu")

            conn.commit()
        finally:
            conn.close()

    def _build_json_object_args(self, columns: List[str], prefix: str) -> str:
        """
        json_object() için argüman listesi oluştur.

        Args:
            columns: Kolon isimleri
            prefix: NEW veya OLD

        Returns:
            "'col1', NEW.col1, 'col2', NEW.col2, ..."
        """
        # Bazı kolonları hariç tut
        exclude = {'id'}  # id auto-increment, senkronize edilmez

        args = []
        for col in columns:
            if col not in exclude:
                args.append(f"'{col}', {prefix}.{col}")

        return ', '.join(args)

    def check_migration_status(self) -> dict:
        """
        Migration durumunu kontrol et.

        Returns:
            {
                'sync_tables_exist': bool,
                'columns_added': {table: [columns]},
                'uuids_assigned': {table: count},
                'triggers_created': [tables]
            }
        """
        result = {
            'sync_tables_exist': False,
            'columns_added': {},
            'uuids_assigned': {},
            'triggers_created': [],
        }

        conn = self._get_connection()
        try:
            # Sync tabloları var mı?
            sync_tables = ['sync_metadata', 'sync_outbox', 'sync_inbox', 'sync_conflicts']
            all_exist = True
            for table in sync_tables:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()
                if not exists:
                    all_exist = False
                    break
            result['sync_tables_exist'] = all_exist

            # Her tablo için kolon durumu
            for table in SYNCED_TABLES:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if not exists:
                    continue

                # Sync kolonları var mı?
                existing_columns = set()
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    existing_columns.add(row[1])

                sync_col_names = {col[0] for col in SYNC_COLUMNS}
                added = existing_columns & sync_col_names
                result['columns_added'][table] = list(added)

                # UUID'li kayıt sayısı
                try:
                    count = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE uuid IS NOT NULL AND uuid != ''"
                    ).fetchone()[0]
                    result['uuids_assigned'][table] = count
                except:
                    pass

                # Trigger'lar var mı?
                trigger = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND name=?",
                    (f"{table}_sync_insert",)
                ).fetchone()
                if trigger:
                    result['triggers_created'].append(table)

            return result
        finally:
            conn.close()

    def rollback(self):
        """
        Migration'ı geri al.

        DİKKAT: Bu işlem sync verilerini siler!
        """
        conn = self._get_connection()
        try:
            # Trigger'ları sil
            for table in SYNCED_TABLES:
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_insert")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_update")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_delete")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_real_delete")

            # Sync tablolarını sil
            conn.execute("DROP TABLE IF EXISTS sync_conflicts")
            conn.execute("DROP TABLE IF EXISTS sync_inbox")
            conn.execute("DROP TABLE IF EXISTS sync_outbox")
            conn.execute("DROP TABLE IF EXISTS sync_metadata")

            # Not: Kolonları silmek SQLite'da zor, bırakıyoruz

            conn.commit()
            logger.info("Migration geri alındı")

        finally:
            conn.close()


def run_migration(db_path: str) -> Tuple[bool, str]:
    """
    Migration'ı çalıştır.

    Args:
        db_path: Veritabanı yolu

    Returns:
        (başarılı, mesaj)
    """
    migration = SyncMigration(db_path)
    return migration.run_all()
