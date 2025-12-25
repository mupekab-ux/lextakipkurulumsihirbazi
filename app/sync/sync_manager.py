# -*- coding: utf-8 -*-
"""
Sync Manager - Ana Senkronizasyon Yöneticisi

Basit ve temiz sync yönetimi.
Eski karmaşık sistemin yerine geçer.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from .config import SyncConfig, get_sync_config, save_sync_config, save_config_value, clear_sync_config
from .client import SyncClient, SyncResult, LoginResult, perform_full_sync
from .outbox import get_pending_changes, get_outbox_stats, SYNCABLE_TABLES

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Senkronizasyon durumları"""
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    OFFLINE = "offline"
    NOT_CONFIGURED = "not_configured"


@dataclass
class SyncState:
    """Mevcut sync durumu"""
    status: SyncStatus
    last_sync_time: Optional[str] = None
    last_sync_revision: int = 0
    pending_changes: int = 0
    last_error: Optional[str] = None
    firm_name: Optional[str] = None
    username: Optional[str] = None


class SyncManager:
    """
    Ana senkronizasyon yöneticisi.

    Kullanım:
        manager = SyncManager()
        manager.configure("http://192.168.1.100:8787")
        result = manager.login("admin", "password")
        if result.success:
            manager.start_auto_sync()
    """

    def __init__(self, db_path: str = None):
        # db_path eski uyumluluk için - artık kullanılmıyor
        self.config = get_sync_config()
        self.client = SyncClient(self.config)
        self._status = SyncStatus.NOT_CONFIGURED if not self.config.is_configured else SyncStatus.IDLE
        self._last_error: Optional[str] = None
        self._sync_lock = threading.Lock()
        self._auto_sync_thread: Optional[threading.Thread] = None
        self._auto_sync_running = False
        self._on_sync_complete: Optional[Callable[[SyncResult], None]] = None
        self._on_status_change: Optional[Callable[[SyncStatus], None]] = None

    @property
    def status(self) -> SyncStatus:
        return self._status

    @status.setter
    def status(self, value: SyncStatus):
        old_status = self._status
        self._status = value
        if old_status != value and self._on_status_change:
            try:
                self._on_status_change(value)
            except Exception as e:
                logger.error(f"Status change callback hatası: {e}")

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    def get_state(self) -> SyncState:
        """Mevcut sync durumunu al."""
        stats = get_outbox_stats()
        return SyncState(
            status=self.status,
            last_sync_time=self.config.last_sync_time,
            last_sync_revision=self.config.last_sync_revision,
            pending_changes=stats['pending'],
            last_error=self._last_error,
            firm_name=self.config.firm_name,
            username=self.config.username
        )

    def configure(self, api_url: str):
        """Sunucu URL'ini yapılandır."""
        self.config.api_url = api_url
        save_config_value('api_url', api_url)
        self.client = SyncClient(self.config)

    def test_connection(self) -> tuple:
        """Sunucu bağlantısını test et."""
        if not self.config.api_url:
            return False, "Sunucu URL'i yapılandırılmamış"

        return self.client.test_connection()

    def login(self, username: str, password: str) -> LoginResult:
        """Sunucuya giriş yap."""
        if not self.config.api_url:
            return LoginResult(success=False, message="Sunucu URL'i yapılandırılmamış")

        result = self.client.login(username, password)

        if result.success:
            self.config = get_sync_config()  # Reload config
            self.client = SyncClient(self.config)
            self.status = SyncStatus.IDLE
            self._last_error = None
        else:
            self._last_error = result.message

        return result

    def logout(self):
        """Çıkış yap."""
        self.stop_auto_sync()
        self.client.logout()
        clear_sync_config()
        self.config = get_sync_config()
        self.client = SyncClient(self.config)
        self.status = SyncStatus.NOT_CONFIGURED

    def sync(self) -> SyncResult:
        """Manuel senkronizasyon yap."""
        if not self.config.is_configured:
            return SyncResult(
                success=False,
                message="Senkronizasyon yapılandırılmamış"
            )

        with self._sync_lock:
            self.status = SyncStatus.SYNCING

            try:
                result = perform_full_sync()

                if result.success:
                    self.config = get_sync_config()  # Reload
                    self.status = SyncStatus.IDLE
                    self._last_error = None
                else:
                    self.status = SyncStatus.ERROR
                    self._last_error = result.message

                # Callback
                if self._on_sync_complete:
                    try:
                        self._on_sync_complete(result)
                    except Exception as e:
                        logger.error(f"Sync complete callback hatası: {e}")

                return result

            except Exception as e:
                logger.exception("Sync hatası")
                self.status = SyncStatus.ERROR
                self._last_error = str(e)
                return SyncResult(success=False, message=str(e))

    def full_sync(self) -> SyncResult:
        """Tam senkronizasyon (sync ile aynı)."""
        return self.sync()

    def start_auto_sync(self, interval_seconds: int = 30):
        """Otomatik senkronizasyonu başlat."""
        if self._auto_sync_running:
            return

        self._auto_sync_running = True
        self.config.auto_sync_enabled = True
        self.config.sync_interval_seconds = interval_seconds
        save_sync_config(self.config)

        self._auto_sync_thread = threading.Thread(
            target=self._auto_sync_loop,
            daemon=True
        )
        self._auto_sync_thread.start()
        logger.info(f"Otomatik sync başlatıldı (interval: {interval_seconds}s)")

    def stop_auto_sync(self):
        """Otomatik senkronizasyonu durdur."""
        self._auto_sync_running = False
        self.config.auto_sync_enabled = False
        save_sync_config(self.config)
        logger.info("Otomatik sync durduruldu")

    def start_background_sync(self, interval: int = 30):
        """Arka plan sync'i başlat (eski API uyumluluğu)."""
        self.start_auto_sync(interval)

    def stop_background_sync(self):
        """Arka plan sync'i durdur (eski API uyumluluğu)."""
        self.stop_auto_sync()

    def _auto_sync_loop(self):
        """Otomatik sync döngüsü."""
        while self._auto_sync_running:
            try:
                if self.config.is_configured:
                    self.sync()
            except Exception as e:
                logger.error(f"Auto sync hatası: {e}")

            # Interval kadar bekle
            for _ in range(self.config.sync_interval_seconds):
                if not self._auto_sync_running:
                    break
                time.sleep(1)

    def set_on_sync_complete(self, callback: Callable[[SyncResult], None]):
        """Sync tamamlandığında çağrılacak callback'i ayarla."""
        self._on_sync_complete = callback

    def set_on_status_change(self, callback: Callable[[SyncStatus], None]):
        """Status değiştiğinde çağrılacak callback'i ayarla."""
        self._on_status_change = callback

    def reset_sync_state(self) -> Dict[str, Any]:
        """Sync durumunu sıfırla."""
        try:
            # Revision'ı sıfırla
            self.config.last_sync_revision = 0
            self.config.last_sync_time = ""
            save_sync_config(self.config)

            self._last_error = None
            self.status = SyncStatus.IDLE

            return {
                'success': True,
                'message': 'Sync durumu sıfırlandı'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }

    # =========================================================================
    # ESKİ API UYUMLULUĞU
    # =========================================================================

    def initialize(self, config=None):
        """Eski API uyumluluğu için."""
        pass

    def is_initialized(self) -> bool:
        """Eski API uyumluluğu için."""
        return self.is_configured

    def get_sync_status(self) -> SyncStatus:
        """Eski API uyumluluğu için."""
        return self.status

    def get_pending_count(self) -> int:
        """Bekleyen değişiklik sayısını al."""
        stats = get_outbox_stats()
        return stats['pending']


# Global instance
_sync_manager: Optional[SyncManager] = None


def get_sync_manager() -> SyncManager:
    """Global SyncManager instance'ını al."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager


def init_sync_manager(db_path: str = None) -> SyncManager:
    """SyncManager'ı başlat."""
    global _sync_manager
    _sync_manager = SyncManager(db_path)
    return _sync_manager
