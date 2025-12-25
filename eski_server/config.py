# -*- coding: utf-8 -*-
"""
LexTakip Sunucu Yapılandırması
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Uygulama ayarları - environment variables'dan okunur."""

    # Veritabanı
    DATABASE_URL: str = "postgresql://lextakip:lextakip123@localhost:5432/lextakip"

    # JWT Ayarları
    SECRET_KEY: str = "lextakip-super-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30  # Token 30 gün geçerli

    # Sunucu Ayarları
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8787
    DEBUG: bool = True

    # Firma Ayarları
    DEFAULT_FIRM_NAME: str = "Ana Ofis"

    # Dosya Depolama
    UPLOAD_DIR: str = "/var/lib/lextakip/uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()


settings = get_settings()
