# -*- coding: utf-8 -*-
"""
TakibiEsasi Büro Senkronizasyon Modülü

Bu modül, birden fazla bilgisayar arasında veri senkronizasyonu sağlar.
Raspberry Pi üzerinde çalışan bir sync server ile iletişim kurar.

Güvenlik Katmanları:
1. firm_id: Büro kimliği (yanlış ağa bağlanmayı önler)
2. device_id: Cihaz kimliği (whitelist kontrolü)
3. firm_key: AES-256 şifreleme anahtarı

Çakışma Çözümü: Last-Write-Wins (updated_at timestamp'ına göre)
"""

from .models import (
    SyncStatus,
    SyncConfig,
    SyncChange,
    SyncConflict,
    SyncResult,
    SYNCED_TABLES,
)
from .sync_manager import SyncManager
from .encryption_service import EncryptionService, RecoveryCodeManager
from .sync_client import SyncClient, FirmMismatchError, DeviceNotApprovedError
from .migration import SyncMigration, run_migration, recreate_triggers, diagnose_sync

__all__ = [
    # Models
    'SyncStatus',
    'SyncConfig',
    'SyncChange',
    'SyncConflict',
    'SyncResult',
    'SYNCED_TABLES',
    # Core
    'SyncManager',
    'EncryptionService',
    'RecoveryCodeManager',
    'SyncClient',
    # Errors
    'FirmMismatchError',
    'DeviceNotApprovedError',
    # Migration
    'SyncMigration',
    'run_migration',
    'recreate_triggers',
    'diagnose_sync',
]

__version__ = '1.0.0'
