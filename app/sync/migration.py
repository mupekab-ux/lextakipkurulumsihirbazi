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

    def drop_all_sync_triggers(self):
        """
        Tüm sync trigger'larını sil.

        Bu metod, tutarsız durumları önlemek için migration başında çağrılır.
        Önceki başarısız migration'lardan kalan trigger'lar temizlenir.
        """
        conn = self._get_connection()
        try:
            for table in SYNCED_TABLES:
                # Her tablo için 4 trigger olabilir
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_insert")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_update")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_delete")
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_sync_real_delete")
            conn.commit()
            logger.debug("Tüm sync trigger'ları silindi")
        except Exception as e:
            logger.warning(f"Trigger temizleme hatası (önemsiz): {e}")
        finally:
            conn.close()

    def run_all(self) -> Tuple[bool, str]:
        """
        Tüm migration'ları çalıştır.

        Returns:
            (başarılı, mesaj)
        """
        try:
            logger.info("Sync migration başlıyor...")

            # 0. Önce mevcut sync trigger'larını temizle (tutarsız durumları önlemek için)
            self.drop_all_sync_triggers()
            logger.info("Mevcut sync trigger'ları temizlendi")

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

                # id kolonu var mı kontrol et
                has_id = False
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    if row[1] == 'id':
                        has_id = True
                        break

                # UUID'si olmayan kayıtları al
                if has_id:
                    # Normal tablolar için id kullan
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
                else:
                    # Junction tablolar için rowid kullan
                    rows = conn.execute(
                        f"SELECT rowid FROM {table} WHERE uuid IS NULL OR uuid = ''"
                    ).fetchall()

                    # Her birine UUID ata
                    for row in rows:
                        new_uuid = str(uuid.uuid4())
                        conn.execute(
                            f"UPDATE {table} SET uuid = ? WHERE rowid = ?",
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
                # Not: INSERT trigger'dan gelen uuid atamasını atla
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_sync_update
                    AFTER UPDATE ON {table}
                    WHEN (SELECT COALESCE(is_sync_enabled, 0) FROM sync_metadata LIMIT 1) = 1
                      AND NEW.uuid IS NOT NULL
                      AND NEW.uuid != ''
                      AND NOT (OLD.uuid IS NULL AND NEW.uuid IS NOT NULL)
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

    def seed_existing_data(self) -> int:
        """
        Mevcut verileri sync_outbox'a ekle (ilk senkronizasyon için).

        Trigger'lar sadece yeni işlemleri yakalar. Bu metod, trigger'lar
        oluşturulmadan önce var olan verileri outbox'a ekleyerek ilk
        senkronizasyonu mümkün kılar.

        Returns:
            Eklenen kayıt sayısı
        """
        import json

        conn = self._get_connection()
        total_seeded = 0

        try:
            for table in SYNCED_TABLES:
                # Tablo var mı kontrol et
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if not exists:
                    continue

                # Kolon listesini al
                columns = []
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    col_name = row[1]
                    if col_name != 'id':  # id hariç
                        columns.append(col_name)

                if 'uuid' not in columns:
                    continue

                # UUID'si olan ama outbox'ta olmayan kayıtları bul
                rows = conn.execute(f"""
                    SELECT * FROM {table}
                    WHERE uuid IS NOT NULL AND uuid != ''
                    AND uuid NOT IN (SELECT uuid FROM sync_outbox WHERE table_name = ?)
                    AND (is_deleted IS NULL OR is_deleted = 0)
                """, (table,)).fetchall()

                # Her kayıt için outbox'a INSERT ekle
                for row in rows:
                    row_dict = dict(row)
                    row_uuid = row_dict.get('uuid')

                    if not row_uuid:
                        continue

                    # id hariç tüm kolonları JSON'a çevir
                    data = {k: v for k, v in row_dict.items() if k != 'id'}

                    # Datetime'ları string'e çevir
                    for k, v in data.items():
                        if hasattr(v, 'isoformat'):
                            data[k] = v.isoformat()

                    conn.execute("""
                        INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                        VALUES (?, ?, 'INSERT', ?)
                    """, (row_uuid, table, json.dumps(data, ensure_ascii=False)))

                    total_seeded += 1

                if rows:
                    logger.info(f"{table}: {len(rows)} mevcut kayıt outbox'a eklendi")

            conn.commit()
            logger.info(f"Toplam {total_seeded} kayıt outbox'a eklendi (ilk senkronizasyon)")

        finally:
            conn.close()

        return total_seeded

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


    def diagnose_triggers(self) -> dict:
        """
        Trigger durumunu detaylı olarak analiz et.

        Returns:
            {
                'sync_enabled': bool,
                'metadata_row_count': int,
                'triggers': {table: [trigger_names]},
                'trigger_count': int,
                'outbox_pending': int,
                'outbox_total': int,
                'issues': [str]
            }
        """
        result = {
            'sync_enabled': False,
            'metadata_row_count': 0,
            'triggers': {},
            'trigger_count': 0,
            'outbox_pending': 0,
            'outbox_total': 0,
            'issues': [],
        }

        conn = self._get_connection()
        try:
            # sync_metadata durumu
            try:
                meta = conn.execute(
                    "SELECT COUNT(*), COALESCE(MAX(is_sync_enabled), 0) FROM sync_metadata"
                ).fetchone()
                result['metadata_row_count'] = meta[0]
                result['sync_enabled'] = bool(meta[1])

                if meta[0] == 0:
                    result['issues'].append("sync_metadata tablosunda kayıt yok!")
                elif not result['sync_enabled']:
                    result['issues'].append("is_sync_enabled = 0 - trigger'lar çalışmayacak!")
            except sqlite3.OperationalError:
                result['issues'].append("sync_metadata tablosu bulunamadı!")

            # Trigger'ları listele
            triggers = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'trigger'
                AND name LIKE '%_sync_%'
                ORDER BY name
            """).fetchall()

            result['trigger_count'] = len(triggers)

            for trigger in triggers:
                name = trigger[0]
                # Parse table name from trigger name (e.g., dosyalar_sync_insert -> dosyalar)
                parts = name.rsplit('_sync_', 1)
                if len(parts) == 2:
                    table = parts[0]
                    if table not in result['triggers']:
                        result['triggers'][table] = []
                    result['triggers'][table].append(name)

            # Beklenen trigger sayısını kontrol et
            expected_triggers = len(SYNCED_TABLES) * 4  # 4 trigger per table
            if result['trigger_count'] < expected_triggers:
                result['issues'].append(
                    f"Eksik trigger! Beklenen: {expected_triggers}, Mevcut: {result['trigger_count']}"
                )

            # Outbox durumu
            try:
                outbox = conn.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN synced = 0 THEN 1 ELSE 0 END) as pending
                    FROM sync_outbox
                """).fetchone()
                result['outbox_total'] = outbox[0] or 0
                result['outbox_pending'] = outbox[1] or 0
            except sqlite3.OperationalError:
                result['issues'].append("sync_outbox tablosu bulunamadı!")

            # Her synced table için trigger kontrolü
            for table in SYNCED_TABLES:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()

                if exists and table not in result['triggers']:
                    result['issues'].append(f"{table} tablosu var ama trigger'ı yok!")

            return result

        finally:
            conn.close()

    def test_trigger_manually(self, table_name: str = 'statuses') -> dict:
        """
        Trigger'ları test etmek için bir kayıt ekle ve sil.

        Args:
            table_name: Test edilecek tablo (varsayılan: statuses)

        Returns:
            {success, message, outbox_before, outbox_after}
        """
        if table_name not in SYNCED_TABLES:
            return {'success': False, 'message': f'{table_name} senkronize edilen tablolar listesinde değil'}

        conn = self._get_connection()
        try:
            # Önce outbox sayısını al
            before = conn.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0]

            # Test kaydı ekle (statuses için basit bir kayıt)
            if table_name == 'statuses':
                test_uuid = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO statuses (uuid, status_type, name, color_hex, display_order)
                    VALUES (?, 'test', 'TRIGGER_TEST', '#000000', 9999)
                """, (test_uuid,))
                conn.commit()

                # Sonra outbox sayısını al
                after = conn.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0]

                # Test kaydını sil
                conn.execute("DELETE FROM statuses WHERE uuid = ?", (test_uuid,))
                conn.commit()

                if after > before:
                    return {
                        'success': True,
                        'message': f'Trigger çalışıyor! Outbox: {before} -> {after}',
                        'outbox_before': before,
                        'outbox_after': after
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Trigger çalışmıyor! Outbox değişmedi: {before}',
                        'outbox_before': before,
                        'outbox_after': after
                    }
            else:
                return {'success': False, 'message': f'{table_name} için otomatik test desteklenmiyor'}

        except Exception as e:
            return {'success': False, 'message': f'Test hatası: {e}'}
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


def recreate_triggers(db_path: str) -> Tuple[bool, str]:
    """
    Sadece trigger'ları yeniden oluştur.

    Mevcut trigger'ları siler ve güncel kodu ile yeniden oluşturur.
    Migration tamamlanmış ancak trigger'lar düzgün çalışmıyorsa kullanılır.

    Args:
        db_path: Veritabanı yolu

    Returns:
        (başarılı, mesaj)
    """
    try:
        migration = SyncMigration(db_path)
        migration.drop_all_sync_triggers()
        migration.create_triggers()
        return True, "Trigger'lar yeniden oluşturuldu"
    except Exception as e:
        return False, f"Trigger yenileme hatası: {e}"


def diagnose_sync(db_path: str) -> dict:
    """
    Sync durumunu analiz et.

    Args:
        db_path: Veritabanı yolu

    Returns:
        Detaylı diagnostic bilgisi
    """
    migration = SyncMigration(db_path)
    return migration.diagnose_triggers()


# ============================================================
# UUID TABANLI FK MİGRASYONU
# ============================================================

# FK İlişkileri: (tablo, yeni_kolon, referans_tablo, mevcut_fk_kolon)
UUID_FK_RELATIONS = [
    # Level 2: dosyalar'a bağlı tablolar
    ('finans', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('muvekkil_kasasi', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('tebligatlar', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('arabuluculuk', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('gorevler', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('attachments', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('dosya_timeline', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('dosya_atamalar', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('custom_tabs_dosyalar', 'dosya_uuid', 'dosyalar', 'dosya_id'),
    ('finans_timeline', 'dosya_uuid', 'dosyalar', 'dosya_id'),

    # Level 2: users'a bağlı tablolar
    ('dosya_atamalar', 'user_uuid', 'users', 'user_id'),
    ('permissions', 'user_uuid', 'users', 'user_id'),

    # Level 2: custom_tabs'a bağlı tablolar
    ('custom_tabs_dosyalar', 'custom_tab_uuid', 'custom_tabs', 'custom_tab_id'),

    # Level 3: finans'a bağlı tablolar
    ('odeme_plani', 'finans_uuid', 'finans', 'finans_id'),
    ('taksitler', 'finans_uuid', 'finans', 'finans_id'),
    ('masraflar', 'finans_uuid', 'finans', 'finans_id'),
    ('odeme_kayitlari', 'finans_uuid', 'finans', 'finans_id'),

    # Level 4: taksitler'e bağlı tablolar
    ('odeme_kayitlari', 'taksit_uuid', 'taksitler', 'taksit_id'),
]


class UUIDFKMigration:
    """
    UUID tabanlı Foreign Key migration.

    INTEGER FK'ları UUID FK'lara dönüştürür:
    1. Yeni _uuid kolonları ekler
    2. Mevcut FK değerlerinden UUID'leri doldurur
    3. İndeksler oluşturur
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """Tablo var mı kontrol et"""
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        return result is not None

    def _column_exists(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        """Kolon var mı kontrol et"""
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]
        return column_name in columns

    def add_uuid_fk_columns(self) -> Tuple[int, List[str]]:
        """
        UUID FK kolonlarını ekle.

        Returns:
            (eklenen_kolon_sayısı, [mesajlar])
        """
        conn = self._get_connection()
        added = 0
        messages = []

        try:
            for table, uuid_col, ref_table, int_col in UUID_FK_RELATIONS:
                # Tablo var mı?
                if not self._table_exists(conn, table):
                    messages.append(f"⚠️ {table} tablosu bulunamadı, atlanıyor")
                    continue

                # Kolon zaten var mı?
                if self._column_exists(conn, table, uuid_col):
                    messages.append(f"✓ {table}.{uuid_col} zaten mevcut")
                    continue

                # Kolonu ekle
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {uuid_col} VARCHAR(36)")
                    added += 1
                    messages.append(f"✓ {table}.{uuid_col} eklendi")
                except Exception as e:
                    messages.append(f"✗ {table}.{uuid_col} eklenemedi: {e}")

            conn.commit()
            logger.info(f"UUID FK kolonları eklendi: {added} yeni kolon")

        finally:
            conn.close()

        return added, messages

    def populate_uuid_fk_values(self) -> Tuple[int, List[str]]:
        """
        UUID FK değerlerini mevcut INTEGER FK'lardan doldur.

        Returns:
            (güncellenen_kayıt_sayısı, [mesajlar])
        """
        conn = self._get_connection()
        updated = 0
        messages = []

        try:
            for table, uuid_col, ref_table, int_col in UUID_FK_RELATIONS:
                # Tablolar var mı?
                if not self._table_exists(conn, table):
                    continue
                if not self._table_exists(conn, ref_table):
                    messages.append(f"⚠️ {ref_table} tablosu bulunamadı")
                    continue

                # Kolonlar var mı?
                if not self._column_exists(conn, table, uuid_col):
                    messages.append(f"⚠️ {table}.{uuid_col} kolonu bulunamadı")
                    continue
                if not self._column_exists(conn, table, int_col):
                    messages.append(f"⚠️ {table}.{int_col} kolonu bulunamadı")
                    continue
                if not self._column_exists(conn, ref_table, 'uuid'):
                    messages.append(f"⚠️ {ref_table}.uuid kolonu bulunamadı")
                    continue

                # UUID FK değerlerini doldur
                try:
                    cursor = conn.execute(f"""
                        UPDATE {table}
                        SET {uuid_col} = (
                            SELECT uuid FROM {ref_table}
                            WHERE {ref_table}.id = {table}.{int_col}
                        )
                        WHERE {int_col} IS NOT NULL
                        AND ({uuid_col} IS NULL OR {uuid_col} = '')
                    """)
                    count = cursor.rowcount
                    if count > 0:
                        updated += count
                        messages.append(f"✓ {table}.{uuid_col}: {count} kayıt güncellendi")
                    else:
                        messages.append(f"○ {table}.{uuid_col}: güncelleme gerekmiyor")

                except Exception as e:
                    messages.append(f"✗ {table}.{uuid_col} doldurulamadı: {e}")

            conn.commit()
            logger.info(f"UUID FK değerleri dolduruldu: {updated} kayıt güncellendi")

        finally:
            conn.close()

        return updated, messages

    def create_uuid_fk_indexes(self) -> Tuple[int, List[str]]:
        """
        UUID FK kolonlarına index ekle.

        Returns:
            (oluşturulan_index_sayısı, [mesajlar])
        """
        conn = self._get_connection()
        created = 0
        messages = []

        try:
            for table, uuid_col, ref_table, int_col in UUID_FK_RELATIONS:
                if not self._table_exists(conn, table):
                    continue
                if not self._column_exists(conn, table, uuid_col):
                    continue

                index_name = f"idx_{table}_{uuid_col}"

                try:
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({uuid_col})")
                    created += 1
                    messages.append(f"✓ {index_name} oluşturuldu")
                except Exception as e:
                    messages.append(f"✗ {index_name} oluşturulamadı: {e}")

            conn.commit()
            logger.info(f"UUID FK indexleri oluşturuldu: {created} index")

        finally:
            conn.close()

        return created, messages

    def run_full_migration(self) -> dict:
        """
        Tam UUID FK migration'ı çalıştır.

        Returns:
            {success, columns_added, values_updated, indexes_created, messages}
        """
        logger.info("UUID FK migration başlatılıyor...")
        all_messages = []

        # Step 1: Kolonları ekle
        cols_added, msgs = self.add_uuid_fk_columns()
        all_messages.extend(msgs)
        all_messages.append(f"\n--- Kolonlar: {cols_added} eklendi ---\n")

        # Step 2: Değerleri doldur
        vals_updated, msgs = self.populate_uuid_fk_values()
        all_messages.extend(msgs)
        all_messages.append(f"\n--- Değerler: {vals_updated} güncellendi ---\n")

        # Step 3: İndexleri oluştur
        idxs_created, msgs = self.create_uuid_fk_indexes()
        all_messages.extend(msgs)
        all_messages.append(f"\n--- İndeksler: {idxs_created} oluşturuldu ---\n")

        logger.info(f"UUID FK migration tamamlandı: {cols_added} kolon, {vals_updated} değer, {idxs_created} index")

        return {
            'success': True,
            'columns_added': cols_added,
            'values_updated': vals_updated,
            'indexes_created': idxs_created,
            'messages': all_messages
        }

    def check_migration_status(self) -> dict:
        """
        Migration durumunu kontrol et.

        Returns:
            {complete, missing_columns, empty_values, details}
        """
        conn = self._get_connection()
        missing_columns = []
        empty_values = []
        details = []

        try:
            for table, uuid_col, ref_table, int_col in UUID_FK_RELATIONS:
                if not self._table_exists(conn, table):
                    continue

                # Kolon var mı?
                if not self._column_exists(conn, table, uuid_col):
                    missing_columns.append(f"{table}.{uuid_col}")
                    details.append(f"✗ {table}.{uuid_col} eksik")
                    continue

                # Boş değer var mı?
                if self._column_exists(conn, table, int_col):
                    empty_count = conn.execute(f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE {int_col} IS NOT NULL
                        AND ({uuid_col} IS NULL OR {uuid_col} = '')
                    """).fetchone()[0]

                    if empty_count > 0:
                        empty_values.append(f"{table}.{uuid_col}: {empty_count}")
                        details.append(f"⚠️ {table}.{uuid_col}: {empty_count} boş değer")
                    else:
                        details.append(f"✓ {table}.{uuid_col} tamam")

        finally:
            conn.close()

        return {
            'complete': len(missing_columns) == 0 and len(empty_values) == 0,
            'missing_columns': missing_columns,
            'empty_values': empty_values,
            'details': details
        }


def run_uuid_fk_migration(db_path: str) -> dict:
    """
    UUID FK migration'ı çalıştır.

    Args:
        db_path: Veritabanı yolu

    Returns:
        Migration sonucu
    """
    migration = UUIDFKMigration(db_path)
    return migration.run_full_migration()


def check_uuid_fk_status(db_path: str) -> dict:
    """
    UUID FK migration durumunu kontrol et.

    Args:
        db_path: Veritabanı yolu

    Returns:
        Durum bilgisi
    """
    migration = UUIDFKMigration(db_path)
    return migration.check_migration_status()
