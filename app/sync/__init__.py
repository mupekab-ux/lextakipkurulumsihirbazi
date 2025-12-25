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
from .migration import (
    SyncMigration,
    run_migration,
    recreate_triggers,
    diagnose_sync,
    UUIDFKMigration,
    run_uuid_fk_migration,
    check_uuid_fk_status,
    UUID_FK_RELATIONS,
)
from .sync_service import (
    SyncService,
    SyncStatus as ServiceSyncStatus,
    get_sync_service,
    init_sync_service,
    stop_sync_service
)

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
    # Background Service
    'SyncService',
    'ServiceSyncStatus',
    'get_sync_service',
    'init_sync_service',
    'stop_sync_service',
    # Errors
    'FirmMismatchError',
    'DeviceNotApprovedError',
    # Migration
    'SyncMigration',
    'run_migration',
    'recreate_triggers',
    'diagnose_sync',
    # UUID FK Migration
    'UUIDFKMigration',
    'run_uuid_fk_migration',
    'check_uuid_fk_status',
    'UUID_FK_RELATIONS',
]

__version__ = '2.0.0'
