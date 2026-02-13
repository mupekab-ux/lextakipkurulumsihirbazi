# -*- coding: utf-8 -*-
"""
Senkronizasyon Yapılandırması

Sunucu bağlantı bilgileri ve sync ayarlarını yönetir.
"""

import json
import os
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# Yapılandırma dosyası yolu
CONFIG_DIR = Path.home() / "Documents" / "LexTakip"
CONFIG_FILE = CONFIG_DIR / "sync_config.json"


@dataclass
class SyncConfig:
    """Senkronizasyon yapılandırması."""

    # Sunucu bilgileri
    server_url: str = ""  # Örn: "http://192.168.1.100:8787"
    auth_token: str = ""

    # Kullanıcı bilgileri
    user_uuid: str = ""
    firm_id: str = ""
    firm_name: str = ""
    username: str = ""
    role: str = ""

    # Cihaz tanımlayıcı (her cihaz için benzersiz)
    device_id: str = ""

    # Son sync bilgileri
    last_sync_revision: int = 0
    last_sync_time: str = ""

    # Ayarlar
    auto_sync_enabled: bool = False
    auto_sync_interval_minutes: int = 5
    sync_on_startup: bool = True

    def __post_init__(self):
        """Cihaz ID yoksa oluştur."""
        if not self.device_id:
            self.device_id = str(uuid.uuid4())

    @property
    def is_configured(self) -> bool:
        """Sunucu yapılandırılmış mı?"""
        return bool(self.server_url and self.auth_token and self.firm_id)

    @property
    def api_url(self) -> str:
        """API base URL."""
        return self.server_url.rstrip('/') if self.server_url else ""

    def to_dict(self) -> dict:
        """Dict'e çevir."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SyncConfig':
        """Dict'ten oluştur."""
        # Sadece bilinen alanları al
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def get_sync_config() -> SyncConfig:
    """Kayıtlı sync yapılandırmasını yükle."""
    if not CONFIG_FILE.exists():
        return SyncConfig()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return SyncConfig.from_dict(data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Sync config yüklenirken hata: {e}")
        return SyncConfig()


def save_sync_config(config: SyncConfig) -> bool:
    """Sync yapılandırmasını kaydet."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Sync config kaydedilirken hata: {e}")
        return False


def clear_sync_config() -> bool:
    """Sync yapılandırmasını temizle (çıkış için)."""
    try:
        if CONFIG_FILE.exists():
            # Token'ı temizle ama diğer ayarları koru
            config = get_sync_config()
            config.auth_token = ""
            config.user_uuid = ""
            config.username = ""
            config.role = ""
            save_sync_config(config)
        return True
    except IOError:
        return False
