# -*- coding: utf-8 -*-
"""
Sync Veri Modelleri

Senkronizasyon işlemlerinde kullanılan veri yapıları.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid


class SyncStatus(Enum):
    """Senkronizasyon durumları"""
    IDLE = "idle"                       # Boşta, senkronize
    SYNCING = "syncing"                 # Senkronizasyon devam ediyor
    ERROR = "error"                     # Hata oluştu
    OFFLINE = "offline"                 # Sunucuya ulaşılamıyor
    NOT_CONFIGURED = "not_configured"   # Büro bağlantısı yok
    PENDING_APPROVAL = "pending_approval"  # Cihaz onayı bekleniyor


class SyncOperation(Enum):
    """Senkronizasyon işlem türleri"""
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class SyncConfig:
    """Senkronizasyon yapılandırması"""
    server_url: str
    firm_id: str
    device_id: str
    firm_key: bytes
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    user_role: Optional[str] = None

    def is_valid(self) -> bool:
        """Yapılandırmanın geçerli olup olmadığını kontrol et"""
        return bool(
            self.server_url and
            self.firm_id and
            self.device_id and
            self.firm_key
        )


@dataclass
class SyncChange:
    """Tek bir senkronizasyon değişikliği"""
    uuid: str
    table_name: str
    operation: SyncOperation
    data: Dict[str, Any]
    revision: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    synced_by_device: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür"""
        return {
            'uuid': self.uuid,
            'table_name': self.table_name,
            'operation': self.operation.value,
            'data': self.data,
            'revision': self.revision,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'synced_by_device': self.synced_by_device,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SyncChange':
        """Dict'ten oluştur"""
        return cls(
            uuid=d['uuid'],
            table_name=d['table_name'],
            operation=SyncOperation(d['operation']),
            data=d['data'],
            revision=d.get('revision', 0),
            created_at=datetime.fromisoformat(d['created_at']) if d.get('created_at') else None,
            updated_at=datetime.fromisoformat(d['updated_at']) if d.get('updated_at') else None,
            synced_by_device=d.get('synced_by_device'),
        )


@dataclass
class SyncConflict:
    """Senkronizasyon çakışması"""
    record_uuid: str
    table_name: str
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    local_updated_at: Optional[datetime] = None
    remote_updated_at: Optional[datetime] = None
    resolution: Optional[str] = None  # 'local', 'remote', 'merged'
    winning_data: Optional[Dict[str, Any]] = None

    def resolve_last_write_wins(self) -> Dict[str, Any]:
        """Last-Write-Wins stratejisiyle çöz"""
        if self.local_updated_at and self.remote_updated_at:
            if self.local_updated_at > self.remote_updated_at:
                self.resolution = 'local'
                self.winning_data = self.local_data
            else:
                self.resolution = 'remote'
                self.winning_data = self.remote_data
        else:
            # Timestamp yoksa remote kazanır (sunucu otoritesi)
            self.resolution = 'remote'
            self.winning_data = self.remote_data

        return self.winning_data


@dataclass
class SyncResult:
    """Senkronizasyon sonucu"""
    success: bool
    pushed_count: int = 0
    pulled_count: int = 0
    conflicts: List[SyncConflict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    last_revision: int = 0
    sync_duration_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür"""
        return {
            'success': self.success,
            'pushed_count': self.pushed_count,
            'pulled_count': self.pulled_count,
            'conflicts_count': len(self.conflicts),
            'errors': self.errors,
            'last_revision': self.last_revision,
            'sync_duration_ms': self.sync_duration_ms,
        }


@dataclass
class DeviceInfo:
    """Cihaz bilgileri"""
    device_id: str
    device_name: str
    platform: str
    os_version: str
    app_version: str

    @classmethod
    def collect(cls) -> 'DeviceInfo':
        """Mevcut cihaz bilgilerini topla"""
        import platform
        import socket

        # Device ID oluştur
        node_name = platform.node()
        device_id = f"{node_name}-{uuid.uuid4().hex[:8]}"

        return cls(
            device_id=device_id,
            device_name=node_name,
            platform=platform.system(),
            os_version=platform.version(),
            app_version="1.0.0",  # TODO: version.txt'den oku
        )

    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür"""
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'platform': self.platform,
            'os_version': self.os_version,
            'app_version': self.app_version,
        }


@dataclass
class FirmInfo:
    """Büro bilgileri"""
    firm_id: str
    firm_name: str
    created_at: Optional[datetime] = None
    subscription_type: str = "trial"
    subscription_expires_at: Optional[datetime] = None


# Senkronize edilecek tablolar
SYNCED_TABLES = [
    # Ana tablolar
    'dosyalar',
    'finans',
    'odeme_plani',
    'taksitler',
    'odeme_kayitlari',
    'masraflar',
    'muvekkil_kasasi',
    'tebligatlar',
    'arabuluculuk',
    'gorevler',
    # Kullanıcı ve yetki
    'users',
    'permissions',
    'dosya_atamalar',
    # Ekler ve sekmeler
    'attachments',
    'custom_tabs',
    'custom_tabs_dosyalar',
    # Zaman çizelgeleri
    'dosya_timeline',
    'finans_timeline',
    # Durum tanımları
    'statuses',
]

# Sync kolonları (mevcut tablolara eklenecek)
SYNC_COLUMNS = [
    ('uuid', 'VARCHAR(36)'),
    ('firm_id', 'VARCHAR(36)'),
    ('revision', 'INTEGER DEFAULT 1'),
    ('is_deleted', 'INTEGER DEFAULT 0'),
    ('synced_at', 'DATETIME'),
    ('created_at', 'DATETIME'),
    ('updated_at', 'DATETIME'),
    ('created_by', 'VARCHAR(36)'),
    ('updated_by', 'VARCHAR(36)'),
]
