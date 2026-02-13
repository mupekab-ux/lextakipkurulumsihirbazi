# -*- coding: utf-8 -*-
"""
LexTakip Sync Server - Basit ve Temiz

Raspberry Pi üzerinde çalışacak senkronizasyon sunucusu.
PostgreSQL ile tüm veriler gerçek tablolarda saklanır.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import settings
from database import engine, get_db
from models import Base, Firm, User, GlobalRevision, SYNCABLE_TABLES, Status, generate_uuid
from auth import (
    verify_password, get_password_hash,
    create_access_token, decode_token, get_current_user
)
from sync_handler import perform_sync, get_current_revision

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="LexTakip Sync Server",
    description="Hukuk bürosu senkronizasyon sunucusu",
    version="2.0.0"
)

# CORS - LAN erişimi için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# SCHEMAS
# =============================================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    timestamp: str


class SetupRequest(BaseModel):
    firm_name: str
    firm_code: str
    admin_username: str
    admin_password: str


class SetupResponse(BaseModel):
    success: bool
    firm_id: str = ""
    admin_uuid: str = ""
    message: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: str = ""


class LoginResponse(BaseModel):
    success: bool
    token: str = ""
    user_uuid: str = ""
    firm_id: str = ""
    firm_name: str = ""
    role: str = ""
    permissions: Dict[str, bool] = {}
    message: str = ""


class SyncRequest(BaseModel):
    device_id: str
    last_sync_revision: int = 0
    changes: List[Dict[str, Any]] = []


class SyncResponse(BaseModel):
    success: bool
    new_revision: int = 0
    changes: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    message: str = ""


# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında tabloları oluştur."""
    logger.info("LexTakip Sync Server başlatılıyor...")
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları hazır.")


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/api/health", response_model=HealthResponse, tags=["Sistem"])
async def health_check(db: Session = Depends(get_db)):
    """Sunucu sağlık durumunu kontrol et."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok",
        version="2.0.0",
        database=db_status,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/public/token", tags=["Sistem"])
async def public_token():
    """Basit test endpoint'i - sunucu erişilebilirlik kontrolü."""
    return {"status": "ok", "message": "LexTakip Sync Server çalışıyor"}


# =============================================================================
# İLK KURULUM
# =============================================================================

@app.post("/api/setup", response_model=SetupResponse, tags=["Kurulum"])
async def initial_setup(request: SetupRequest, db: Session = Depends(get_db)):
    """
    İlk kurulum - firma ve admin kullanıcı oluştur.
    Bu endpoint sadece hiç firma yokken çalışır.
    """
    # Mevcut firma var mı kontrol et
    existing_firm = db.query(Firm).first()
    if existing_firm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistem zaten kurulmuş."
        )

    try:
        # Firma oluştur
        firm = Firm(
            uuid=generate_uuid(),
            name=request.firm_name,
            code=request.firm_code.upper(),
            is_active=True
        )
        db.add(firm)
        db.flush()

        # Global revision başlat
        global_rev = GlobalRevision(
            firm_id=firm.uuid,
            current_revision=0
        )
        db.add(global_rev)

        # Admin kullanıcı oluştur
        admin_user = User(
            uuid=generate_uuid(),
            firm_id=firm.uuid,
            username=request.admin_username,
            password_hash=get_password_hash(request.admin_password),
            role="admin",
            is_active=True,
            revision=1
        )
        db.add(admin_user)

        # Varsayılan durumları ekle
        _create_default_statuses(db, firm.uuid)

        db.commit()

        logger.info(f"Yeni firma oluşturuldu: {firm.name} ({firm.code})")

        return SetupResponse(
            success=True,
            firm_id=firm.uuid,
            admin_uuid=admin_user.uuid,
            message="Kurulum tamamlandı!"
        )

    except Exception as e:
        db.rollback()
        logger.exception("Kurulum hatası")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kurulum hatası: {str(e)}"
        )


def _create_default_statuses(db: Session, firm_id: str):
    """Varsayılan dava durumlarını oluştur."""

    DEFAULT_STATUSES = [
        # SARI - Bizde
        ("BAŞVURU YAPILACAK", "FFD700", "SARI"),
        ("DAVA AÇILACAK", "FFD700", "SARI"),
        ("VEKALET SUNULACAK", "FFD700", "SARI"),
        ("DAVA DİLEKÇESİ VERİLECEK", "FFD700", "SARI"),
        ("CEVAP YAZILACAK", "FFD700", "SARI"),
        ("CEVABA CEVAP YAZILACAK", "FFD700", "SARI"),
        ("2. CEVAP VERİLECEK", "FFD700", "SARI"),
        ("BEYAN DİLEKÇESİ YAZILACAK", "FFD700", "SARI"),
        ("DELİLLER TOPLANACAK", "FFD700", "SARI"),
        ("İCRAYA KONULACAK", "FFD700", "SARI"),
        ("İTİRAZ EDİLECEK", "FFD700", "SARI"),
        ("SUÇ DUYURUSU YAPILACAK", "FFD700", "SARI"),
        ("İSTİNAFA BAŞVURULACAK", "FFD700", "SARI"),
        ("TEMYİZE BAŞVURULACAK", "FFD700", "SARI"),
        ("DEĞİŞİK İŞ", "FFD700", "SARI"),
        # TURUNCU - Mahkemede
        ("DURUŞMA BEKLENİYOR", "FF8C00", "TURUNCU"),
        ("GEREKÇELİ KARAR BEKLENİYOR", "FF8C00", "TURUNCU"),
        ("BİLİRKİŞİ RAPORU BEKLENİYOR", "FF8C00", "TURUNCU"),
        ("KEŞİF BEKLENİYOR", "FF8C00", "TURUNCU"),
        ("MÜZEKKERE BEKLENİYOR", "FF8C00", "TURUNCU"),
        ("KESİNLEŞME SÜRESİNDE", "FF8C00", "TURUNCU"),
        ("TEBLİĞ AŞAMASINDA", "FF8C00", "TURUNCU"),
        ("TEMYİZ EDİLDİ", "FF8C00", "TURUNCU"),
        ("İSTİNAF EDİLDİ", "FF8C00", "TURUNCU"),
        # GARIP_TURUNCU - Karşı tarafta
        ("CEVAP BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        ("CEVABA CEVAP BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        ("SİGORTAYA BAŞVURULDU", "CD853F", "GARIP_TURUNCU"),
        # KIRMIZI - Kapandı
        ("DOSYA KAPANDI", "FF0000", "KIRMIZI"),
    ]

    for ad, color, owner in DEFAULT_STATUSES:
        status_obj = Status(
            uuid=generate_uuid(),
            firm_id=firm_id,
            ad=ad,
            color_hex=color,
            owner=owner,
            revision=1
        )
        db.add(status_obj)


# =============================================================================
# GİRİŞ
# =============================================================================

@app.post("/api/login", response_model=LoginResponse, tags=["Kimlik Doğrulama"])
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Kullanıcı girişi.
    Başarılı girişte JWT token döndürür.
    """
    # Aktif firmayı bul
    firm = db.query(Firm).filter(Firm.is_active == True).first()

    if not firm:
        return LoginResponse(
            success=False,
            message="Sistem henüz kurulmamış. Lütfen /api/setup ile kurulum yapın."
        )

    # Kullanıcıyı doğrula
    user = db.query(User).filter(
        User.username == request.username,
        User.firm_id == firm.uuid,
        User.is_deleted == False,
        User.is_active == True
    ).first()

    if not user or not verify_password(request.password, user.password_hash):
        return LoginResponse(
            success=False,
            message="Kullanıcı adı veya parola hatalı."
        )

    # Token oluştur
    token, _ = create_access_token(
        user_uuid=user.uuid,
        firm_id=firm.uuid,
        device_id=request.device_id
    )

    # Yetkileri ayarla
    permissions = {}
    if user.role == "admin":
        permissions = {
            "can_hard_delete": True,
            "manage_users": True,
            "view_all_cases": True,
            "can_view_finance": True
        }

    return LoginResponse(
        success=True,
        token=token,
        user_uuid=user.uuid,
        firm_id=firm.uuid,
        firm_name=firm.name,
        role=user.role,
        permissions=permissions,
        message="Giriş başarılı!"
    )


# =============================================================================
# SENKRONİZASYON
# =============================================================================

@app.post("/api/sync", response_model=SyncResponse, tags=["Senkronizasyon"])
async def sync(
    request: SyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ana senkronizasyon endpoint'i.

    1. İstemciden gelen değişiklikleri al ve işle (push)
    2. İstemciye gönderilecek değişiklikleri hazırla (pull)
    3. Sonuçları döndür

    Authorization: Bearer <token>
    """

    logger.info(f"Sync isteği: user={user.username}, device={request.device_id}, last_rev={request.last_sync_revision}, changes={len(request.changes)}")

    result = perform_sync(
        db=db,
        firm_id=user.firm_id,
        user_uuid=user.uuid,
        device_id=request.device_id,
        last_sync_revision=request.last_sync_revision,
        changes=request.changes
    )

    return SyncResponse(
        success=result['success'],
        new_revision=result['new_revision'],
        changes=result['changes'],
        errors=result.get('errors', []),
        message=result.get('message', '')
    )


@app.get("/api/sync/status", tags=["Senkronizasyon"])
async def sync_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Senkronizasyon durumunu al."""

    current_rev = get_current_revision(db, user.firm_id)

    return {
        "firm_id": user.firm_id,
        "current_revision": current_rev,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/sync/reset", tags=["Senkronizasyon"])
async def sync_reset(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync durumunu sıfırla (geliştirme amaçlı)."""

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    # Sadece log'u temizle, veriyi silme
    logger.info(f"Sync reset: firm={user.firm_id}")

    return {
        "success": True,
        "message": "Sync durumu sıfırlandı"
    }


# =============================================================================
# KULLANICI YÖNETİMİ
# =============================================================================

@app.get("/api/users", tags=["Kullanıcı Yönetimi"])
async def list_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcıları listele (sadece admin)."""

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    users = db.query(User).filter(
        User.firm_id == user.firm_id,
        User.is_deleted == False
    ).all()

    return [{
        "uuid": u.uuid,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None
    } for u in users]


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "avukat"


@app.post("/api/users", tags=["Kullanıcı Yönetimi"])
async def create_user(
    request: CreateUserRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Yeni kullanıcı oluştur (sadece admin)."""

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    # Kullanıcı adı kontrolü
    existing = db.query(User).filter(
        User.firm_id == user.firm_id,
        User.username == request.username,
        User.is_deleted == False
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten kullanılıyor"
        )

    from sync_handler import get_next_revision

    new_user = User(
        uuid=generate_uuid(),
        firm_id=user.firm_id,
        username=request.username,
        password_hash=get_password_hash(request.password),
        role=request.role,
        is_active=True,
        revision=get_next_revision(db, user.firm_id)
    )
    db.add(new_user)
    db.commit()

    return {
        "success": True,
        "uuid": new_user.uuid,
        "message": f"Kullanıcı '{request.username}' oluşturuldu"
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
