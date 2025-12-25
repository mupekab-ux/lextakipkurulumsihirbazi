# -*- coding: utf-8 -*-
"""
LexTakip Senkronizasyon Modülü - v2.0

Basit ve temiz senkronizasyon sistemi.
"""

from .config import (
    SyncConfig,
    get_sync_config,
    save_sync_config,
    save_config_value,
    get_config_value,
    clear_sync_config,
)

from .outbox import (
    SYNCABLE_TABLES,
    generate_uuid,
    record_change,
    get_pending_changes,
    mark_changes_synced,
    clear_synced_changes,
    get_outbox_stats,
    get_record_data,
    sync_record_insert,
    sync_record_update,
    sync_record_delete,
)

from .client import (
    SyncClient,
    SyncResult,
    LoginResult,
    perform_full_sync,
)

from .merger import (
    apply_incoming_changes,
    prepare_initial_sync_payload,
)

from .sync_manager import (
    SyncManager,
    SyncStatus,
    SyncState,
    get_sync_manager,
    init_sync_manager,
)

__all__ = [
    # Config
    'SyncConfig',
    'get_sync_config',
    'save_sync_config',
    'save_config_value',
    'get_config_value',
    'clear_sync_config',
    # Outbox
    'SYNCABLE_TABLES',
    'generate_uuid',
    'record_change',
    'get_pending_changes',
    'mark_changes_synced',
    'clear_synced_changes',
    'get_outbox_stats',
    'get_record_data',
    'sync_record_insert',
    'sync_record_update',
    'sync_record_delete',
    # Client
    'SyncClient',
    'SyncResult',
    'LoginResult',
    'perform_full_sync',
    # Merger
    'apply_incoming_changes',
    'prepare_initial_sync_payload',
    # Manager
    'SyncManager',
    'SyncStatus',
    'SyncState',
    'get_sync_manager',
    'init_sync_manager',
]

__version__ = '2.0.0'
