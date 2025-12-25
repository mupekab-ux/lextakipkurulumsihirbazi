# -*- coding: utf-8 -*-
"""
LexTakip Sunucu - FastAPI Ana Modülü

Raspberry Pi üzerinde çalışacak senkronizasyon sunucusu.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import engine, get_db, Base
from models import Firm, User, GlobalRevision, SYNCABLE_TABLES
from schemas import (
    LoginRequest, LoginResponse, SyncRequest, SyncResponse,
    HealthResponse, InitialSetupRequest, InitialSetupResponse,
    FirmResponse, ErrorResponse
)
from auth import (
    authenticate_user, create_access_token, get_current_user,
    hash_password, get_firm_by_code, TokenData
)
from sync_handler import perform_sync, get_current_revision

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
app = FastAPI(
    title="LexTakip Sunucu",
    description="Hukuk bürosu yönetim sistemi senkronizasyon sunucusu",
    version="1.0.0"
)

# CORS ayarları - LAN'dan erişim için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm origin'lere izin (LAN için)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# STARTUP / SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında tabloları oluştur."""
    logger.info("LexTakip Sunucu başlatılıyor...")
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları hazır.")


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatılırken temizlik."""
    logger.info("LexTakip Sunucu kapatılıyor...")


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/api/health", response_model=HealthResponse, tags=["Sistem"])
async def health_check(db: Session = Depends(get_db)):
    """Sunucu sağlık durumunu kontrol et."""
    try:
        # Veritabanı bağlantısını test et
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        database=db_status,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/public/token", tags=["Sistem"])
async def public_token():
    """Basit test endpoint'i - sunucuya erişilebilirliği kontrol için."""
    return {"status": "ok", "message": "LexTakip Sunucu çalışıyor"}


# =============================================================================
# İLK KURULUM
# =============================================================================

@app.post("/api/setup", response_model=InitialSetupResponse, tags=["Kurulum"])
async def initial_setup(request: InitialSetupRequest, db: Session = Depends(get_db)):
    """
    İlk kurulum - firma ve admin kullanıcı oluştur.

    Bu endpoint sadece hiç firma yokken çalışır.
    """
    # Mevcut firma var mı kontrol et
    existing_firm = db.query(Firm).first()
    if existing_firm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistem zaten kurulmuş. Yeni firma eklemek için admin paneli kullanın."
        )

    try:
        # Firma oluştur
        firm = Firm(
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
            firm_id=firm.uuid,
            username=request.admin_username,
            password_hash=hash_password(request.admin_password),
            role="admin",
            is_active=True,
            revision=1
        )
        db.add(admin_user)

        # Varsayılan durumları ekle
        _create_default_statuses(db, firm.uuid)

        db.commit()

        logger.info(f"Yeni firma oluşturuldu: {firm.name} ({firm.code})")

        return InitialSetupResponse(
            success=True,
            firm_id=firm.uuid,
            admin_user_uuid=admin_user.uuid,
            message="Kurulum tamamlandı!"
        )

    except Exception as e:
        db.rollback()
        logger.exception("Kurulum hatası")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kurulum sırasında hata oluştu: {str(e)}"
        )


def _create_default_statuses(db: Session, firm_id: str):
    """Varsayılan dava durumlarını oluştur."""
    from models import Status, generate_uuid

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
        ("SAVUNMA DİLEKÇESİ YAZILACAK", "FFD700", "SARI"),
        ("DELİLLER TOPLANACAK", "FFD700", "SARI"),
        ("TANIK LİSTESİ YAZILACAK", "FFD700", "SARI"),
        ("TALEPTE BULUNULACAK", "FFD700", "SARI"),
        ("ÖN İNCELEME DURUŞMASINA GİDİLECEK", "FFD700", "SARI"),
        ("İCRAYA KONULACAK", "FFD700", "SARI"),
        ("ÖDEME EMRİ GÖNDERİLECEK", "FFD700", "SARI"),
        ("İTİRAZ EDİLECEK", "FFD700", "SARI"),
        ("TAKİP TALEBİ", "FFD700", "SARI"),
        ("HACİZ TALEBİ", "FFD700", "SARI"),
        ("SATIŞ TALEBİ", "FFD700", "SARI"),
        ("CEZAEVİNE GİDİLECEK", "FFD700", "SARI"),
        ("HAKİMLE GÖRÜŞÜLECEK", "FFD700", "SARI"),
        ("MEMURLA GÖRÜŞÜLECEK", "FFD700", "SARI"),
        ("SUÇ DUYURUSU YAPILACAK", "FFD700", "SARI"),
        ("İFADE VERİLECEK", "FFD700", "SARI"),
        ("SAVCIYLA GÖRÜŞÜLECEK", "FFD700", "SARI"),
        ("GÖRÜŞME YAPILACAK", "FFD700", "SARI"),
        ("İSTİNAFA BAŞVURULACAK", "FFD700", "SARI"),
        ("TEMYİZE BAŞVURULACAK", "FFD700", "SARI"),
        ("AYM BAŞVURULACAK", "FFD700", "SARI"),
        ("SİGORTA CEVAP VERDİ", "FFD700", "SARI"),
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
        ("TAHKİMDE", "FF8C00", "TURUNCU"),
        ("PAYLAŞTIRMA", "FF8C00", "TURUNCU"),
        # GARIP_TURUNCU - Karşı tarafta
        ("CEVAP BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        ("CEVABA CEVAP BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        ("SAVUNMA DİLEKÇESİ BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        ("SİGORTAYA BAŞVURULDU", "CD853F", "GARIP_TURUNCU"),
        ("EKSPERTİZ BEKLENİYOR", "CD853F", "GARIP_TURUNCU"),
        # KIRMIZI - Kapandı
        ("DOSYA KAPANDI", "FF0000", "KIRMIZI"),
    ]

    for ad, color, owner in DEFAULT_STATUSES:
        status = Status(
            uuid=generate_uuid(),
            firm_id=firm_id,
            ad=ad,
            color_hex=color,
            owner=owner,
            revision=1
        )
        db.add(status)


# =============================================================================
# GİRİŞ
# =============================================================================

@app.post("/api/login", response_model=LoginResponse, tags=["Kimlik Doğrulama"])
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Kullanıcı girişi.

    Başarılı girişte JWT token döndürür.
    """
    # Önce firmayı bul - kullanıcı adının benzersiz olması için firma gerekli
    # Basit model: Tek firma varsayalım (çoklu firma için firma kodu gerekir)
    firm = db.query(Firm).filter(Firm.is_active == True).first()

    if not firm:
        return LoginResponse(
            success=False,
            message="Sistem henüz kurulmamış. Lütfen önce /api/setup ile kurulum yapın."
        )

    # Kullanıcıyı doğrula
    user = authenticate_user(db, request.username, request.password, firm.uuid)

    if not user:
        return LoginResponse(
            success=False,
            message="Kullanıcı adı veya parola hatalı."
        )

    # Token oluştur
    token = create_access_token(
        user_uuid=user.uuid,
        firm_id=firm.uuid,
        username=user.username,
        role=user.role,
        device_id=request.device_id
    )

    # Yetkileri al
    from models import Permission
    permissions_query = db.query(Permission).filter(
        Permission.firm_id == firm.uuid,
        Permission.role == user.role,
        Permission.is_deleted == False
    ).all()

    permissions = {p.action: p.allowed for p in permissions_query}

    # Admin için zorunlu yetkiler
    if user.role == "admin":
        permissions["can_hard_delete"] = True
        permissions["manage_users"] = True
        permissions["view_all_cases"] = True
        permissions["can_view_finance"] = True

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
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ana senkronizasyon endpoint'i.

    1. İstemciden gelen değişiklikleri al ve işle (push)
    2. İstemciye gönderilecek değişiklikleri hazırla (pull)
    3. Sonuçları döndür

    Token header'da gönderilmeli:
    Authorization: Bearer <token>
    """

    logger.info(f"Sync isteği: device={request.device_id}, last_rev={request.last_sync_revision}, changes={len(request.changes)}")

    response = perform_sync(db, token_data, request)

    logger.info(f"Sync tamamlandı: success={response.success}, new_rev={response.new_revision}, sent={len(response.changes)}")

    return response


@app.get("/api/sync/status", tags=["Senkronizasyon"])
async def sync_status(
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Senkronizasyon durumunu al."""

    current_rev = get_current_revision(db, token_data.firm_id)

    return {
        "firm_id": token_data.firm_id,
        "current_revision": current_rev,
        "timestamp": datetime.utcnow().isoformat()
    }


# =============================================================================
# KULLANICI YÖNETİMİ (Admin)
# =============================================================================

@app.get("/api/users", tags=["Kullanıcı Yönetimi"])
async def list_users(
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcıları listele (sadece admin)."""

    if token_data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    users = db.query(User).filter(
        User.firm_id == token_data.firm_id,
        User.is_deleted == False
    ).all()

    return [{
        "uuid": u.uuid,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None
    } for u in users]


@app.post("/api/users", tags=["Kullanıcı Yönetimi"])
async def create_user(
    username: str,
    password: str,
    role: str = "avukat",
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Yeni kullanıcı oluştur (sadece admin)."""

    if token_data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    # Kullanıcı adı kontrolü
    existing = db.query(User).filter(
        User.firm_id == token_data.firm_id,
        User.username == username,
        User.is_deleted == False
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten kullanılıyor"
        )

    from models import generate_uuid
    from sync_handler import get_next_revision

    user = User(
        uuid=generate_uuid(),
        firm_id=token_data.firm_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        revision=get_next_revision(db, token_data.firm_id)
    )
    db.add(user)
    db.commit()

    return {
        "success": True,
        "uuid": user.uuid,
        "message": f"Kullanıcı '{username}' oluşturuldu"
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
