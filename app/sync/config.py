# -*- coding: utf-8 -*-
"""
Sync Yapılandırması

Basit ve temiz sync config yönetimi.
SQLite'ta sync_config tablosunda saklanır.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Sync yapılandırması."""

    # Sunucu bilgileri
    api_url: str = ""

    # Kimlik bilgileri
    device_id: str = ""
    auth_token: str = ""
    user_uuid: str = ""
    firm_id: str = ""
    firm_name: str = ""
    username: str = ""
    role: str = ""

    # Sync durumu
    last_sync_revision: int = 0
    last_sync_time: str = ""

    # Ayarlar
    auto_sync_enabled: bool = True
    sync_interval_seconds: int = 30

    @property
    def is_configured(self) -> bool:
        """Sync yapılandırılmış mı?"""
        return bool(self.api_url and self.auth_token and self.firm_id)

    def to_dict(self) -> Dict[str, Any]:
        """Config'i dict'e çevir."""
        return {
            'api_url': self.api_url,
            'device_id': self.device_id,
            'auth_token': self.auth_token,
            'user_uuid': self.user_uuid,
            'firm_id': self.firm_id,
            'firm_name': self.firm_name,
            'username': self.username,
            'role': self.role,
            'last_sync_revision': self.last_sync_revision,
            'last_sync_time': self.last_sync_time,
            'auto_sync_enabled': self.auto_sync_enabled,
            'sync_interval_seconds': self.sync_interval_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncConfig':
        """Dict'ten config oluştur."""
        return cls(
            api_url=data.get('api_url', ''),
            device_id=data.get('device_id', ''),
            auth_token=data.get('auth_token', ''),
            user_uuid=data.get('user_uuid', ''),
            firm_id=data.get('firm_id', ''),
            firm_name=data.get('firm_name', ''),
            username=data.get('username', ''),
            role=data.get('role', ''),
            last_sync_revision=data.get('last_sync_revision', 0),
            last_sync_time=data.get('last_sync_time', ''),
            auto_sync_enabled=data.get('auto_sync_enabled', True),
            sync_interval_seconds=data.get('sync_interval_seconds', 30),
        )


def _get_connection():
    """Veritabanı bağlantısı al."""
    try:
        from app.db import get_connection
        return get_connection()
    except:
        from db import get_connection
        return get_connection()


def ensure_config_table():
    """sync_config tablosunu oluştur."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_sync_config() -> SyncConfig:
    """Sync config'i yükle."""
    ensure_config_table()

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM sync_config")
        rows = cur.fetchall()

        data = {}
        for key, value in rows:
            try:
                data[key] = json.loads(value)
            except:
                data[key] = value

        # Device ID yoksa oluştur
        if not data.get('device_id'):
            data['device_id'] = str(uuid.uuid4())
            save_config_value('device_id', data['device_id'])

        return SyncConfig.from_dict(data)
    finally:
        conn.close()


def save_sync_config(config: SyncConfig):
    """Sync config'i kaydet."""
    ensure_config_table()

    conn = _get_connection()
    try:
        cur = conn.cursor()
        for key, value in config.to_dict().items():
            json_value = json.dumps(value) if not isinstance(value, str) else json.dumps(value)
            cur.execute("""
                INSERT OR REPLACE INTO sync_config (key, value)
                VALUES (?, ?)
            """, (key, json_value))
        conn.commit()
    finally:
        conn.close()


def save_config_value(key: str, value: Any):
    """Tek bir config değeri kaydet."""
    ensure_config_table()

    conn = _get_connection()
    try:
        cur = conn.cursor()
        json_value = json.dumps(value)
        cur.execute("""
            INSERT OR REPLACE INTO sync_config (key, value)
            VALUES (?, ?)
        """, (key, json_value))
        conn.commit()
    finally:
        conn.close()


def get_config_value(key: str, default: Any = None) -> Any:
    """Tek bir config değeri al."""
    ensure_config_table()

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM sync_config WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except:
                return row[0]
        return default
    finally:
        conn.close()


def clear_sync_config():
    """Sync config'i temizle (logout için)."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # Device ID hariç her şeyi sil
        cur.execute("DELETE FROM sync_config WHERE key != 'device_id'")
        conn.commit()
    finally:
        conn.close()
