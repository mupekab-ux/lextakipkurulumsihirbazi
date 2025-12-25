# -*- coding: utf-8 -*-
"""
Arka Plan Senkronizasyon Servisi

Belirli aralıklarla otomatik senkronizasyon yapar.
Online/offline durumunu takip eder.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Senkronizasyon durumu"""
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    SYNCING = "syncing"
    ERROR = "error"


class SyncService:
    """
    Arka plan senkronizasyon servisi.

    Özellikler:
    - Belirli aralıklarla otomatik sync
    - Online/offline durumu takibi
    - Durum değişikliği callback'leri
    - Thread-safe
    """

    def __init__(
        self,
        sync_manager: 'SyncManager',
        interval: int = 30,
        on_status_change: Callable[[SyncStatus], None] = None,
        on_sync_complete: Callable[[Dict[str, Any]], None] = None,
        on_error: Callable[[Exception], None] = None
    ):
        """
        Args:
            sync_manager: SyncManager instance
            interval: Senkronizasyon aralığı (saniye)
            on_status_change: Durum değişikliği callback'i
            on_sync_complete: Sync tamamlandığında callback
            on_error: Hata callback'i
        """
        self.sync_manager = sync_manager
        self.interval = interval
        self.on_status_change = on_status_change
        self.on_sync_complete = on_sync_complete
        self.on_error = on_error

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._status = SyncStatus.OFFLINE
        self._last_sync: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

        # İstatistikler
        self._sync_count = 0
        self._error_count = 0

    @property
    def status(self) -> SyncStatus:
        """Mevcut durum"""
        return self._status

    @property
    def is_online(self) -> bool:
        """Online mı?"""
        return self._status in (SyncStatus.ONLINE, SyncStatus.SYNCING)

    @property
    def last_sync(self) -> Optional[datetime]:
        """Son senkronizasyon zamanı"""
        return self._last_sync

    @property
    def last_error(self) -> Optional[str]:
        """Son hata mesajı"""
        return self._last_error

    def _set_status(self, status: SyncStatus):
        """Durumu güncelle ve callback çağır"""
        if self._status != status:
            self._status = status
            if self.on_status_change:
                try:
                    self.on_status_change(status)
                except Exception as e:
                    logger.error(f"Status callback hatası: {e}")

    def start(self):
        """Servisi başlat"""
        if self._running:
            logger.warning("Sync servisi zaten çalışıyor")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.name = "SyncService"
        self._thread.start()
        logger.info(f"Sync servisi başlatıldı (interval={self.interval}s)")

    def stop(self):
        """Servisi durdur"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._set_status(SyncStatus.OFFLINE)
        logger.info("Sync servisi durduruldu")

    def sync_now(self) -> Dict[str, Any]:
        """
        Hemen senkronize et.

        Returns:
            Sync sonucu
        """
        return self._do_sync()

    def force_sync_all(self) -> Dict[str, Any]:
        """
        Tüm mevcut verileri zorla senkronize et.

        Mevcut verileri outbox'a ekler ve tam senkronizasyon yapar.

        Returns:
            {success, seeded, received, sent, errors}
        """
        with self._lock:
            self._set_status(SyncStatus.SYNCING)

            try:
                result = self.sync_manager.force_sync_all()

                if result.get('success'):
                    self._sync_count += 1
                    self._last_sync = datetime.now()
                    self._last_error = None
                    self._set_status(SyncStatus.ONLINE)
                else:
                    errors = result.get('errors', [])
                    self._last_error = errors[0] if errors else 'Bilinmeyen hata'
                    self._set_status(SyncStatus.ERROR)

                return result

            except Exception as e:
                self._error_count += 1
                self._last_error = str(e)
                self._set_status(SyncStatus.ERROR)
                logger.error(f"Force sync hatası: {e}")
                return {'success': False, 'errors': [str(e)]}

    def _run_loop(self):
        """Ana döngü"""
        while self._running:
            try:
                self._do_sync()
            except Exception as e:
                logger.error(f"Sync döngüsü hatası: {e}")
                self._error_count += 1
                self._last_error = str(e)
                self._set_status(SyncStatus.ERROR)

                if self.on_error:
                    try:
                        self.on_error(e)
                    except:
                        pass

            # Interval kadar bekle (erken çıkış kontrolü ile)
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)

    def _do_sync(self) -> Dict[str, Any]:
        """Senkronizasyon yap"""
        with self._lock:
            # Bağlantı kontrolü
            self._set_status(SyncStatus.CONNECTING)

            try:
                if not self.sync_manager.client:
                    self._set_status(SyncStatus.OFFLINE)
                    return {'success': False, 'error': 'Client yapılandırılmamış'}

                # Ping
                if not self.sync_manager.client.check_connection():
                    self._set_status(SyncStatus.OFFLINE)
                    return {'success': False, 'error': 'Sunucuya bağlanılamıyor'}

                self._set_status(SyncStatus.SYNCING)

                # Tam senkronizasyon
                result = self.sync_manager.full_sync()

                if result.get('success'):
                    self._sync_count += 1
                    self._last_sync = datetime.now()
                    self._last_error = None
                    self._set_status(SyncStatus.ONLINE)

                    if self.on_sync_complete:
                        try:
                            self.on_sync_complete(result)
                        except:
                            pass

                    logger.debug(
                        f"Sync tamamlandı: "
                        f"{result.get('received', 0)} alındı, "
                        f"{result.get('sent', 0)} gönderildi"
                    )
                else:
                    self._error_count += 1
                    self._last_error = result.get('error', 'Bilinmeyen hata')
                    self._set_status(SyncStatus.ERROR)

                return result

            except Exception as e:
                self._error_count += 1
                self._last_error = str(e)
                self._set_status(SyncStatus.ERROR)
                logger.error(f"Sync hatası: {e}")
                return {'success': False, 'error': str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """İstatistikleri döndür"""
        return {
            'status': self._status.value,
            'is_online': self.is_online,
            'last_sync': self._last_sync.isoformat() if self._last_sync else None,
            'last_error': self._last_error,
            'sync_count': self._sync_count,
            'error_count': self._error_count,
            'interval': self.interval
        }


# Global instance (lazy initialization)
_sync_service: Optional[SyncService] = None


def get_sync_service() -> Optional[SyncService]:
    """Global sync service instance'ı al"""
    return _sync_service


def init_sync_service(
    sync_manager: 'SyncManager',
    interval: int = 30,
    **callbacks
) -> SyncService:
    """
    Sync service'i başlat.

    Args:
        sync_manager: SyncManager instance
        interval: Sync aralığı (saniye)
        **callbacks: on_status_change, on_sync_complete, on_error

    Returns:
        SyncService instance
    """
    global _sync_service

    if _sync_service:
        _sync_service.stop()

    _sync_service = SyncService(
        sync_manager=sync_manager,
        interval=interval,
        **callbacks
    )
    _sync_service.start()

    return _sync_service


def stop_sync_service():
    """Sync service'i durdur"""
    global _sync_service

    if _sync_service:
        _sync_service.stop()
        _sync_service = None
