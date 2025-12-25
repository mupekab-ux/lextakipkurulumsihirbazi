# -*- coding: utf-8 -*-
"""
Sync Server Configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://lextakip:LexTakip2024!@localhost/lextakip_sync"

    # JWT
    SECRET_KEY: str = "lextakip-sync-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 saat
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
