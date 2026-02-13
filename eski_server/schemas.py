# -*- coding: utf-8 -*-
"""
Pydantic şemaları - API request/response modelleri
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# AUTH
# =============================================================================

class LoginRequest(BaseModel):
    """Giriş isteği."""
    username: str
    password: str
    device_id: str  # Cihaz tanımlayıcı


class LoginResponse(BaseModel):
    """Giriş yanıtı."""
    success: bool
    token: Optional[str] = None
    user_uuid: Optional[str] = None
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None
    message: Optional[str] = None


class TokenData(BaseModel):
    """JWT token içeriği."""
    user_uuid: str
    firm_id: str
    username: str
    role: str
    device_id: str
    exp: datetime


# =============================================================================
# SYNC
# =============================================================================

class SyncChange(BaseModel):
    """Tek bir değişiklik kaydı."""
    table: str
    op: Literal['insert', 'update', 'delete']
    uuid: str
    data: Dict[str, Any]
    revision: int = 0
    updated_at: Optional[str] = None


class SyncRequest(BaseModel):
    """Senkronizasyon isteği."""
    device_id: str
    last_sync_revision: int = 0
    changes: List[SyncChange] = []


class SyncResponse(BaseModel):
    """Senkronizasyon yanıtı."""
    success: bool
    new_revision: int
    changes: List[SyncChange] = []
    errors: List[Dict[str, Any]] = []
    message: Optional[str] = None


# =============================================================================
# FİRMA YÖNETİMİ
# =============================================================================

class FirmCreate(BaseModel):
    """Yeni firma oluşturma."""
    name: str
    code: str


class FirmResponse(BaseModel):
    """Firma bilgisi."""
    uuid: str
    name: str
    code: str
    is_active: bool


class InitialSetupRequest(BaseModel):
    """İlk kurulum - firma ve admin kullanıcı oluşturma."""
    firm_name: str
    firm_code: str
    admin_username: str
    admin_password: str


class InitialSetupResponse(BaseModel):
    """İlk kurulum yanıtı."""
    success: bool
    firm_id: Optional[str] = None
    admin_user_uuid: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# HEALTH CHECK
# =============================================================================

class HealthResponse(BaseModel):
    """Sunucu sağlık durumu."""
    status: str
    version: str
    database: str
    timestamp: str


# =============================================================================
# GENEL
# =============================================================================

class ErrorResponse(BaseModel):
    """Hata yanıtı."""
    success: bool = False
    error: str
    detail: Optional[str] = None
