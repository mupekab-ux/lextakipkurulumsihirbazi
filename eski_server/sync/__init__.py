# -*- coding: utf-8 -*-
"""
LexTakip Senkronizasyon Modülü

Bu modül, istemci ile sunucu arasındaki veri senkronizasyonunu yönetir.
"""

from sync.config import SyncConfig, get_sync_config, save_sync_config
from sync.client import SyncClient
from sync.outbox import (
    SYNCABLE_TABLES,
    record_change,
    get_pending_changes,
    mark_changes_synced,
    clear_synced_changes,
    ensure_uuid,
    generate_uuid,
    get_outbox_stats
)
from sync.merger import apply_incoming_changes, prepare_initial_sync_payload
from sync.db_wrapper import (
    sync_insert,
    sync_update,
    sync_delete,
    with_sync_tracking,
    # Kolaylık fonksiyonları
    sync_dosya_insert,
    sync_dosya_update,
    sync_finans_insert,
    sync_finans_update,
    sync_tebligat_insert,
    sync_tebligat_update,
    sync_gorev_insert,
    sync_gorev_update
)

__all__ = [
    # Config
    'SyncConfig',
    'get_sync_config',
    'save_sync_config',
    # Client
    'SyncClient',
    # Outbox
    'SYNCABLE_TABLES',
    'record_change',
    'get_pending_changes',
    'mark_changes_synced',
    'clear_synced_changes',
    'ensure_uuid',
    'generate_uuid',
    'get_outbox_stats',
    # Merger
    'apply_incoming_changes',
    'prepare_initial_sync_payload',
    # DB Wrapper
    'sync_insert',
    'sync_update',
    'sync_delete',
    'with_sync_tracking',
    'sync_dosya_insert',
    'sync_dosya_update',
    'sync_finans_insert',
    'sync_finans_update',
    'sync_tebligat_insert',
    'sync_tebligat_update',
    'sync_gorev_insert',
    'sync_gorev_update',
]
