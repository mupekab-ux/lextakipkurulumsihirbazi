# -*- coding: utf-8 -*-
"""
Sync Manager

Ana senkronizasyon yöneticisi.
Tüm sync bileşenlerini koordine eder.
"""

import json
import logging
import platform
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

from .models import (
    SyncStatus, SyncConfig, SyncResult, SyncConflict,
    DeviceInfo, SYNCED_TABLES, SYNC_COLUMNS
)
from .encryption_service import EncryptionService, RecoveryCodeManager
from .sync_client import SyncClient, FirmMismatchError, DeviceNotApprovedError
from .outbox_processor import OutboxProcessor
from .inbox_processor import InboxProcessor
from .conflict_handler import ConflictHandler

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Ana senkronizasyon yöneticisi.

    Kullanım:
        sync_manager = SyncManager(db_path)
        sync_manager.initialize(config)
        sync_manager.start_background_sync()
    """

    DEFAULT_SYNC_INTERVAL = 30  # saniye

    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLite veritabanı yolu
        """
        self.db_path = db_path
        self.config: Optional[SyncConfig] = None
        self.status = SyncStatus.NOT_CONFIGURED

        # Alt bileşenler
        self.client: Optional[SyncClient] = None
        self.encryption: Optional[EncryptionService] = None
        self.outbox: Optional[OutboxProcessor] = None
        self.inbox: Optional[InboxProcessor] = None
        self.conflict_handler: Optional[ConflictHandler] = None

        # Thread yönetimi
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sync_interval = self.DEFAULT_SYNC_INTERVAL
        self._lock = threading.Lock()

        # Callbacks
        self.on_status_change: Optional[Callable[[SyncStatus], None]] = None
        self.on_sync_complete: Optional[Callable[[SyncResult], None]] = None
        self.on_conflict: Optional[Callable[[SyncConflict], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================================
    # YAPILANDIRMA
    # ============================================================

    def initialize(self, config: SyncConfig) -> bool:
        """
        Senkronizasyonu başlat.

        Args:
            config: SyncConfig instance

        Returns:
            Başarılıysa True
        """
        if not config.is_valid():
            logger.error("Geçersiz sync yapılandırması")
            return False

        self.config = config

        # Alt bileşenleri oluştur
        self.encryption = EncryptionService(config.firm_key)
        self.client = SyncClient(config)
        self.outbox = OutboxProcessor(self.db_path, self.client, self.encryption)
        self.inbox = InboxProcessor(self.db_path, self.client, self.encryption)
        self.conflict_handler = ConflictHandler(self.db_path)

        # Tabloları hazırla
        self._ensure_sync_tables()

        self.status = SyncStatus.IDLE
        self._notify_status_change()

        logger.info("SyncManager başlatıldı")
        return True

    def load_config_from_db(self) -> bool:
        """
        Yapılandırmayı veritabanından yükle.

        Returns:
            Yapılandırma bulunduysa True
        """
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT device_id, firm_id, firm_key_encrypted,
                       server_url, is_sync_enabled
                FROM sync_metadata
                LIMIT 1
            """).fetchone()

            if not row or not row['is_sync_enabled']:
                return False

            # firm_key'i çöz (cihaz anahtarıyla şifreli)
            # TODO: Cihaz anahtarıyla decrypt
            firm_key = row['firm_key_encrypted']

            config = SyncConfig(
                server_url=row['server_url'],
                firm_id=row['firm_id'],
                device_id=row['device_id'],
                firm_key=firm_key,
            )

            return self.initialize(config)

        except sqlite3.OperationalError:
            # Tablo yok
            return False
        finally:
            conn.close()

    def save_config_to_db(self):
        """Yapılandırmayı veritabanına kaydet"""
        if not self.config:
            return

        conn = self._get_connection()
        try:
            # Önce mevcut kaydı sil
            conn.execute("DELETE FROM sync_metadata")

            conn.execute("""
                INSERT INTO sync_metadata
                (device_id, firm_id, firm_key_encrypted, server_url, is_sync_enabled)
                VALUES (?, ?, ?, ?, 1)
            """, (
                self.config.device_id,
                self.config.firm_id,
                self.config.firm_key,  # TODO: Cihaz anahtarıyla şifrele
                self.config.server_url,
            ))
            conn.commit()
        finally:
            conn.close()

    def clear_config(self):
        """Yapılandırmayı temizle"""
        conn = self._get_connection()
        try:
            conn.execute("UPDATE sync_metadata SET is_sync_enabled = 0")
            conn.commit()
        finally:
            conn.close()

        self.config = None
        self.status = SyncStatus.NOT_CONFIGURED
        self._notify_status_change()

    # ============================================================
    # ARKA PLAN SENKRONİZASYON
    # ============================================================

    def start_background_sync(self):
        """Arka plan senkronizasyonunu başlat"""
        if self._sync_thread and self._sync_thread.is_alive():
            logger.warning("Arka plan sync zaten çalışıyor")
            return

        if self.status == SyncStatus.NOT_CONFIGURED:
            logger.warning("Sync yapılandırılmamış, arka plan sync başlatılamaz")
            return

        self._stop_event.clear()
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            name="SyncThread",
            daemon=True
        )
        self._sync_thread.start()
        logger.info("Arka plan sync başlatıldı")

    def stop_background_sync(self):
        """Arka plan senkronizasyonunu durdur"""
        self._stop_event.set()
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
            self._sync_thread = None
        logger.info("Arka plan sync durduruldu")

    def set_sync_interval(self, seconds: int):
        """Sync aralığını ayarla"""
        self._sync_interval = max(10, seconds)  # Minimum 10 saniye

    def _sync_loop(self):
        """Arka plan sync döngüsü"""
        while not self._stop_event.is_set():
            try:
                self._perform_sync()
            except Exception as e:
                logger.error(f"Sync döngüsü hatası: {e}")
                self.status = SyncStatus.ERROR
                self._notify_status_change()

                if self.on_error:
                    self.on_error(str(e))

            # Interruptible bekleme
            self._stop_event.wait(self._sync_interval)

    # ============================================================
    # SENKRONİZASYON İŞLEMLERİ
    # ============================================================

    def sync_now(self) -> SyncResult:
        """
        Hemen senkronize et.

        Returns:
            SyncResult instance
        """
        with self._lock:
            return self._perform_sync()

    def _perform_sync(self) -> SyncResult:
        """Senkronizasyon işlemi"""
        start_time = time.time()
        result = SyncResult(success=False)

        if self.status == SyncStatus.NOT_CONFIGURED:
            result.errors.append("Sync yapılandırılmamış")
            return result

        if self.status == SyncStatus.SYNCING:
            result.errors.append("Sync zaten devam ediyor")
            return result

        self.status = SyncStatus.SYNCING
        self._notify_status_change()

        try:
            # 1. Bağlantı kontrolü
            if not self.client.check_connection():
                self.status = SyncStatus.OFFLINE
                self._notify_status_change()
                result.errors.append("Sunucuya bağlanılamadı")
                return result

            # 2. Firma doğrulaması
            try:
                self.client.validate_firm_connection()
            except FirmMismatchError as e:
                self.status = SyncStatus.ERROR
                self._notify_status_change()
                result.errors.append(str(e))
                return result

            # 3. Token yenile (gerekirse)
            if self.config.access_token:
                try:
                    self.client.refresh_token()
                except Exception:
                    pass  # Login gerekebilir

            # 4. Push: Lokal değişiklikleri gönder
            push_result = self.outbox.process()
            result.pushed_count = push_result['count']

            for conflict in push_result.get('conflicts', []):
                resolved = self.conflict_handler.resolve(conflict)
                result.conflicts.append(conflict)
                if self.on_conflict:
                    self.on_conflict(conflict)

            # 5. Pull: Uzak değişiklikleri al
            pull_result = self.inbox.fetch_and_process()
            result.pulled_count = pull_result['count']
            result.last_revision = pull_result['last_revision']

            for conflict in pull_result.get('conflicts', []):
                resolved = self.conflict_handler.resolve(conflict)
                result.conflicts.append(conflict)
                if self.on_conflict:
                    self.on_conflict(conflict)

            # 6. Başarılı
            result.success = True
            self.status = SyncStatus.IDLE
            self._notify_status_change()

            # 7. Son sync zamanını güncelle
            self._update_last_sync()

            logger.info(
                f"Sync tamamlandı: {result.pushed_count} push, "
                f"{result.pulled_count} pull, {len(result.conflicts)} çakışma"
            )

        except Exception as e:
            logger.error(f"Sync hatası: {e}")
            result.errors.append(str(e))
            self.status = SyncStatus.ERROR
            self._notify_status_change()

        result.sync_duration_ms = (time.time() - start_time) * 1000

        if self.on_sync_complete:
            self.on_sync_complete(result)

        return result

    def _update_last_sync(self):
        """Son sync zamanını güncelle"""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE sync_metadata
                SET last_sync_at = ?
            """, (datetime.now().isoformat(),))
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # BÜRO YÖNETİMİ
    # ============================================================

    def setup_new_firm(self, server_url: str, firm_name: str,
                       admin_username: str, admin_password: str,
                       admin_email: str = "") -> Dict[str, Any]:
        """
        Yeni büro kur.

        Args:
            server_url: Sync server URL
            firm_name: Büro adı
            admin_username: Yönetici kullanıcı adı
            admin_password: Yönetici şifresi
            admin_email: E-posta (opsiyonel)

        Returns:
            {firm_id, recovery_code, join_code}
        """
        # Geçici client oluştur
        device_info = DeviceInfo.collect()
        temp_config = SyncConfig(
            server_url=server_url,
            firm_id="",  # Henüz yok
            device_id=device_info.device_id,
            firm_key=b"",  # Henüz yok
        )

        client = SyncClient(temp_config)

        # Büro oluştur
        response = client.init_firm(
            firm_name=firm_name,
            admin_username=admin_username,
            admin_password=admin_password,
            admin_email=admin_email,
        )

        # Yapılandırmayı kaydet
        firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']

        self.config = SyncConfig(
            server_url=server_url,
            firm_id=response['firm_id'],
            device_id=device_info.device_id,
            firm_key=firm_key,
        )

        self.initialize(self.config)
        self.save_config_to_db()

        # Kurtarma kodu üret
        recovery_manager = RecoveryCodeManager()
        recovery_code = recovery_manager.generate_recovery_code(firm_key)

        return {
            'firm_id': response['firm_id'],
            'recovery_code': recovery_code,
            'join_code': response.get('join_code', ''),
        }

    def join_firm(self, server_url: str, join_code: str) -> Dict[str, Any]:
        """
        Mevcut büroya katıl.

        Args:
            server_url: Sync server URL
            join_code: Katılım kodu

        Returns:
            {status: 'joined'|'pending_approval', firm_name?, message?}
        """
        # Mevcut veri kontrolü
        if self._has_synced_data():
            raise ValueError(
                "Bu cihazda başka büroya ait veri var. "
                "Önce 'Bürodan Ayrıl' işlemi yapın."
            )

        # Geçici client oluştur
        device_info = DeviceInfo.collect()
        temp_config = SyncConfig(
            server_url=server_url,
            firm_id="",
            device_id=device_info.device_id,
            firm_key=b"",
        )

        client = SyncClient(temp_config)

        # Katılım isteği
        response = client.join_firm(
            join_code=join_code,
            device_name=device_info.device_name,
            device_info=device_info.to_dict(),
        )

        if response.get('requires_approval'):
            # Onay bekliyor
            self._save_pending_config(
                server_url=server_url,
                firm_id=response['firm_id'],
                device_id=device_info.device_id,
            )

            self.status = SyncStatus.PENDING_APPROVAL
            self._notify_status_change()

            return {
                'status': 'pending_approval',
                'message': 'Cihazınız yönetici onayı bekliyor.',
            }

        # Hemen katıldı
        firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']

        self.config = SyncConfig(
            server_url=server_url,
            firm_id=response['firm_id'],
            device_id=device_info.device_id,
            firm_key=firm_key,
        )

        self.initialize(self.config)
        self.save_config_to_db()

        return {
            'status': 'joined',
            'firm_name': response.get('firm_name', ''),
        }

    def check_approval_status(self) -> Dict[str, Any]:
        """
        Cihaz onay durumunu kontrol et.

        Returns:
            {is_approved, firm_key?}
        """
        if not self.client:
            raise ValueError("Client yapılandırılmamış")

        response = self.client.check_approval_status()

        if response.get('is_approved'):
            # Onaylandı, firm_key'i al
            firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']
            self.config.firm_key = firm_key
            self.initialize(self.config)
            self.save_config_to_db()

            self.status = SyncStatus.IDLE
            self._notify_status_change()

        return response

    def leave_firm(self, keep_local_data: bool = False) -> Dict[str, Any]:
        """
        Bürodan ayrıl.

        Args:
            keep_local_data: True ise veriler silinmez

        Returns:
            {status, backup_path?}
        """
        backup_path = None

        # Sunucuya bildir
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass

        # Veriyi temizle
        if not keep_local_data:
            backup_path = self._backup_and_clear_data()

        # Yapılandırmayı temizle
        self.clear_config()
        self.stop_background_sync()

        return {
            'status': 'left',
            'backup_path': backup_path,
        }

    # ============================================================
    # YARDIMCI METODLAR
    # ============================================================

    def _has_synced_data(self) -> bool:
        """Senkronize edilmiş veri var mı?"""
        conn = self._get_connection()
        try:
            result = conn.execute("""
                SELECT firm_id FROM sync_metadata
                WHERE firm_id IS NOT NULL AND firm_id != ''
                LIMIT 1
            """).fetchone()
            return result is not None
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    def _save_pending_config(self, server_url: str, firm_id: str, device_id: str):
        """Onay bekleyen yapılandırmayı kaydet"""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM sync_metadata")
            conn.execute("""
                INSERT INTO sync_metadata
                (device_id, firm_id, server_url, is_sync_enabled)
                VALUES (?, ?, ?, 0)
            """, (device_id, firm_id, server_url))
            conn.commit()
        finally:
            conn.close()

    def _backup_and_clear_data(self) -> str:
        """Veriyi yedekle ve temizle"""
        # TODO: Yedekleme implementasyonu
        backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

        # Sync tablolarını temizle
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM sync_outbox")
            conn.execute("DELETE FROM sync_inbox")

            # Senkronize verilerdeki firm bilgilerini temizle
            for table in SYNCED_TABLES:
                try:
                    conn.execute(f"UPDATE {table} SET firm_id = NULL, synced_at = NULL")
                except sqlite3.OperationalError:
                    pass

            conn.commit()
        finally:
            conn.close()

        return backup_path

    def _ensure_sync_tables(self):
        """Sync tablolarının var olduğundan emin ol"""
        conn = self._get_connection()
        try:
            # sync_metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR(36) NOT NULL,
                    firm_id VARCHAR(36),
                    firm_key_encrypted BLOB,
                    last_sync_revision INTEGER DEFAULT 0,
                    last_sync_at DATETIME,
                    server_url TEXT,
                    is_sync_enabled INTEGER DEFAULT 0
                )
            """)

            # sync_outbox
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

            # sync_inbox
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

            # sync_conflicts
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

            conn.commit()
        finally:
            conn.close()

    def _notify_status_change(self):
        """Durum değişikliğini bildir"""
        if self.on_status_change:
            self.on_status_change(self.status)

    # ============================================================
    # DURUM BİLGİSİ
    # ============================================================

    def get_status_info(self) -> Dict[str, Any]:
        """
        Detaylı durum bilgisi al.

        Returns:
            Durum dict
        """
        conn = self._get_connection()
        try:
            meta = conn.execute(
                "SELECT * FROM sync_metadata LIMIT 1"
            ).fetchone()

            pending_out = conn.execute(
                "SELECT COUNT(*) FROM sync_outbox WHERE synced = 0"
            ).fetchone()[0]

            pending_in = conn.execute(
                "SELECT COUNT(*) FROM sync_inbox WHERE processed = 0"
            ).fetchone()[0]

            return {
                'status': self.status.value,
                'is_configured': self.config is not None,
                'server_url': self.config.server_url if self.config else None,
                'firm_id': self.config.firm_id[:8] + '...' if self.config else None,
                'device_id': self.config.device_id if self.config else None,
                'last_sync_at': meta['last_sync_at'] if meta else None,
                'last_revision': meta['last_sync_revision'] if meta else 0,
                'pending_push': pending_out,
                'pending_pull': pending_in,
            }
        except sqlite3.OperationalError:
            return {
                'status': self.status.value,
                'is_configured': False,
            }
        finally:
            conn.close()

    def get_pending_changes_count(self) -> int:
        """Bekleyen değişiklik sayısını al"""
        if self.outbox:
            return self.outbox.get_pending_count()
        return 0
