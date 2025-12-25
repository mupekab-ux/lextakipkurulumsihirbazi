# -*- coding: utf-8 -*-
"""
TakibiEsasi Sync Server

Künye tabanlı iki yönlü senkronizasyon sunucusu.
Raspberry Pi üzerinde çalışır.
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import secrets
import logging
import uuid as uuid_module

from config import settings
from database import engine, get_db
from models import (
    Base, Firm, User, Device, JoinCode, RefreshToken,
    SyncRecord, GlobalRevision, SyncLog, SYNCED_TABLES
)
from auth import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, verify_refresh_token,
    get_current_user, get_device_id_from_header, get_firm_id_from_header
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="TakibiEsasi Sync Server",
    version="2.0.0",
    description="Künye tabanlı iki yönlü senkronizasyon"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_str(val):
    """UUID'yi string'e dönüştür (JSON serileştirme için)"""
    if val is None:
        return None
    if isinstance(val, uuid_module.UUID):
        return str(val)
    return str(val)


# ============================================================
# SCHEMAS
# ============================================================

class InitFirmRequest(BaseModel):
    firm_name: str
    admin_username: str
    admin_password: str
    admin_email: str = ""
    device_name: str = ""
    device_id: str = ""


class InitFirmResponse(BaseModel):
    success: bool
    firm_id: str
    device_id: str
    recovery_code: str
    join_code: str
    firm_key: str


class JoinFirmRequest(BaseModel):
    join_code: str
    device_name: str
    device_info: Dict[str, Any] = {}


class JoinFirmResponse(BaseModel):
    success: bool
    firm_id: str
    device_id: str
    requires_approval: bool
    firm_key: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: str = ""


class LoginResponse(BaseModel):
    success: bool
    access_token: str
    refresh_token: str
    expires_in: int
    user_uuid: str
    firm_id: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class KunyeInfo(BaseModel):
    uuid: str
    table_name: str
    updated_at: str


class SyncRequest(BaseModel):
    kunyeler: List[KunyeInfo] = []
    changes: List[Dict[str, Any]] = []


class SyncChange(BaseModel):
    uuid: str
    table_name: str
    operation: str  # INSERT, UPDATE, DELETE
    data: Dict[str, Any]


class PushRequest(BaseModel):
    changes: List[Dict[str, Any]] = []


class SyncResponse(BaseModel):
    success: bool
    to_client: List[Dict[str, Any]] = []
    need_from_client: List[str] = []
    bn_changes: List[Dict[str, Any]] = []
    new_revision: int = 0
    message: str = ""


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    """Uygulama başlangıcında veritabanı kontrolü"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    required_tables = ['firms', 'users', 'devices', 'sync_records', 'global_revisions']
    missing = [t for t in required_tables if t not in existing_tables]

    if missing:
        logger.warning(f"Eksik tablolar: {missing}")
        logger.info("Migrasyon çalıştırılıyor...")
        try:
            from migrate import run_migration
            run_migration()
        except Exception as e:
            logger.error(f"Migrasyon hatası: {e}")
            # Eğer migrate modülü yoksa, direkt create_all dene
            try:
                Base.metadata.create_all(bind=engine)
            except Exception as e2:
                logger.error(f"Tablo oluşturma hatası: {e2}")
                raise

    logger.info("Sync Server başlatıldı")


# ============================================================
# HEALTH & INFO
# ============================================================

@app.get("/api/health")
def health_check():
    """Sunucu sağlık kontrolü"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/sync/info")
def get_server_info(
    db: Session = Depends(get_db),
    x_firm_id: str = Header(None)
):
    """Sunucu bilgileri"""
    firm = None
    if x_firm_id:
        firm = db.query(Firm).filter(Firm.id == x_firm_id).first()

    return {
        "version": "2.0.0",
        "firm_id": firm.uuid if firm else None,
        "firm_name": firm.name if firm else None,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================
# SETUP ENDPOINTS
# ============================================================

@app.post("/api/setup/init", response_model=InitFirmResponse)
def init_firm(request: InitFirmRequest, db: Session = Depends(get_db)):
    """
    Yeni büro oluştur (ilk kurulum).

    Bu endpoint sadece sunucu boşken çalışır.
    """
    # Zaten firma var mı?
    existing = db.query(Firm).first()
    if existing:
        raise HTTPException(status_code=400, detail="Sunucu zaten kurulmuş")

    # Firma oluştur
    firm_key = secrets.token_urlsafe(32)
    recovery_code = "-".join([secrets.token_hex(4).upper() for _ in range(4)])

    firm = Firm(
        name=request.firm_name,
        firm_key=firm_key
    )
    db.add(firm)
    db.flush()

    # Admin kullanıcı oluştur
    admin = User(
        firm_id=firm.uuid,
        username=request.admin_username,
        password_hash=get_password_hash(request.admin_password),
        email=request.admin_email,
        role="admin"
    )
    db.add(admin)

    # Cihaz kaydet
    device = Device(
        firm_id=firm.uuid,
        device_id=request.device_id or secrets.token_hex(16),
        device_name=request.device_name or "Ana Bilgisayar",
        is_approved=True,
        is_active=True
    )
    db.add(device)

    # Global revision başlat
    db.add(GlobalRevision(firm_id=firm.uuid, current_revision=0))

    # Katılım kodu oluştur
    join_code = f"BURO-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
    code = JoinCode(
        firm_id=firm.uuid,
        code=join_code,
        max_uses=100,
        expires_at=datetime.utcnow() + timedelta(days=365),
        created_by=admin.uuid
    )
    db.add(code)

    db.commit()

    logger.info(f"Yeni büro oluşturuldu: {firm.name} ({firm.uuid})")

    return InitFirmResponse(
        success=True,
        firm_id=firm.uuid,
        device_id=device.device_id,
        recovery_code=recovery_code,
        join_code=join_code,
        firm_key=firm_key
    )


@app.post("/api/setup/join", response_model=JoinFirmResponse)
def join_firm(
    request: JoinFirmRequest,
    db: Session = Depends(get_db),
    x_device_id: str = Header(None)
):
    """
    Mevcut büroya katıl.
    """
    # Katılım kodunu bul
    code = db.query(JoinCode).filter(
        JoinCode.code == request.join_code.upper(),
        JoinCode.expires_at > datetime.utcnow()
    ).first()

    if not code:
        raise HTTPException(status_code=404, detail="Geçersiz veya süresi dolmuş katılım kodu")

    if code.use_count >= code.max_uses:
        raise HTTPException(status_code=403, detail="Katılım kodu kullanım limitine ulaşmış")

    # Cihaz zaten kayıtlı mı?
    device_id = x_device_id or secrets.token_hex(16)
    existing_device = db.query(Device).filter(
        Device.firm_id == code.firm_id,
        Device.device_id == device_id
    ).first()

    if existing_device:
        # Cihaz zaten kayıtlı
        firm = db.query(Firm).filter(Firm.id == code.firm_id).first()
        return JoinFirmResponse(
            success=True,
            firm_id=code.firm_id,
            device_id=existing_device.uuid,
            requires_approval=not existing_device.is_approved,
            firm_key=firm.firm_key if existing_device.is_approved else None
        )

    # Yeni cihaz kaydet
    device = Device(
        firm_id=code.firm_id,
        device_id=device_id,
        device_name=request.device_name,
        device_info=request.device_info,
        is_approved=False,  # Onay bekleyecek
        is_active=True
    )
    db.add(device)

    # Kullanım sayısını artır
    code.use_count += 1

    db.commit()

    logger.info(f"Yeni cihaz katıldı: {device.device_name} ({device.device_id})")

    return JoinFirmResponse(
        success=True,
        firm_id=code.firm_id,
        device_id=device.uuid,
        requires_approval=True,
        firm_key=None
    )


@app.get("/api/setup/device/{device_id}/status")
def get_device_status(device_id: str, db: Session = Depends(get_db)):
    """Cihaz onay durumunu kontrol et"""
    device = db.query(Device).filter(
        (Device.device_id == device_id) | (Device.uuid == device_id)
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı")

    firm = db.query(Firm).filter(Firm.id == device.firm_id).first()

    return {
        "is_approved": device.is_approved,
        "is_active": device.is_active,
        "firm_id": device.firm_id,
        "firm_key": firm.firm_key if device.is_approved else None,
        "needs_login": device.is_approved  # Onaylandıysa login gerekli
    }


# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post("/api/auth/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    x_device_id: str = Header(None)
):
    """Kullanıcı girişi"""
    # Kullanıcıyı bul
    user = db.query(User).filter(
        User.username == request.username,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")

    device_id = request.device_id or x_device_id

    # Cihaz kontrolü
    if device_id:
        device = db.query(Device).filter(
            Device.firm_id == user.firm_id,
            Device.device_id == device_id
        ).first()

        if device:
            if not device.is_approved:
                raise HTTPException(
                    status_code=403,
                    detail="Bu cihaz henüz onaylanmamış",
                    headers={"X-Reason": "device_not_approved"}
                )
            if not device.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="Bu cihaz deaktif edilmiş"
                )
            # Son görülme zamanını güncelle
            device.last_seen_at = datetime.utcnow()

    # Token'lar oluştur
    access_token, expires_in = create_access_token(
        user_uuid=user.uuid,
        firm_id=user.firm_id,
        device_id=device_id
    )
    refresh_token = create_refresh_token(db, user.uuid, device_id)

    db.commit()

    return LoginResponse(
        success=True,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user_uuid=user.uuid,
        firm_id=user.firm_id,
        role=user.role
    )


@app.post("/api/auth/refresh")
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """Access token yenile"""
    refresh = verify_refresh_token(db, request.refresh_token)

    if not refresh:
        raise HTTPException(status_code=401, detail="Geçersiz refresh token")

    user = db.query(User).filter(User.uuid == refresh.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")

    access_token, expires_in = create_access_token(
        user_uuid=user.uuid,
        firm_id=user.firm_id,
        device_id=refresh.device_id
    )

    return {
        "access_token": access_token,
        "expires_in": expires_in
    }


@app.post("/api/auth/logout")
def logout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_device_id: str = Header(None)
):
    """Çıkış yap"""
    # Bu cihazdaki refresh token'ları iptal et
    if x_device_id:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.uuid,
            RefreshToken.device_id == x_device_id
        ).update({"revoked": True})
        db.commit()

    return {"success": True}


# ============================================================
# SYNC ENDPOINTS - KÜNYE SİSTEMİ
# ============================================================

def get_next_revision(db: Session, firm_id: str) -> int:
    """Sonraki revision numarasını al"""
    rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).with_for_update().first()

    if not rev:
        rev = GlobalRevision(firm_id=firm_id, current_revision=0)
        db.add(rev)

    rev.current_revision += 1
    db.flush()
    return rev.current_revision


def get_next_bn(db: Session, firm_id: str) -> int:
    """Sonraki büro takip numarasını al"""
    result = db.query(func.max(SyncRecord.buro_takip_no)).filter(
        SyncRecord.firm_id == firm_id,
        SyncRecord.table_name == 'dosyalar'
    ).scalar()

    return (result or 0) + 1


@app.post("/api/sync", response_model=SyncResponse)
def full_sync(
    request: SyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_device_id: str = Header(None)
):
    """
    Tam senkronizasyon - Künye tabanlı.

    1. Client künye listesini gönderir
    2. Server karşılaştırır
    3. Eksik/güncel olanları client'a gönderir
    4. Client'tan istenen verileri alır
    5. BN çakışmalarını çözer
    """
    firm_id = to_str(user.firm_id)
    to_client = []
    need_from_client = []
    bn_changes = []

    # 1. Önce gelen değişiklikleri işle
    for change in request.changes:
        result = process_incoming_change(db, firm_id, change, x_device_id)
        if result.get('bn_changed'):
            bn_changes.append(result)

    # 2. Client künye haritası oluştur
    client_kunyeler = {k.uuid: k for k in request.kunyeler}

    # 3. Sunucudaki tüm künyeleri al
    server_records = db.query(SyncRecord).filter(
        SyncRecord.firm_id == firm_id
    ).all()

    server_uuids = set()

    for record in server_records:
        record_uuid = to_str(record.uuid)
        server_uuids.add(record_uuid)

        if record_uuid not in client_kunyeler:
            # Client'ta yok → gönder
            to_client.append({
                'uuid': record_uuid,
                'table_name': record.table_name,
                'operation': 'DELETE' if record.is_deleted else 'INSERT',
                'data': record.data,
                'revision': record.revision
            })
        else:
            # İkisinde de var → timestamp karşılaştır
            client_kunye = client_kunyeler[record_uuid]
            try:
                client_time = datetime.fromisoformat(client_kunye.updated_at.replace('Z', '+00:00'))
            except:
                client_time = datetime.min

            server_time = record.updated_at

            if server_time > client_time:
                # Sunucu daha yeni → client'a gönder
                to_client.append({
                    'uuid': record_uuid,
                    'table_name': record.table_name,
                    'operation': 'UPDATE',
                    'data': record.data,
                    'revision': record.revision
                })
            elif client_time > server_time:
                # Client daha yeni → client'tan iste
                need_from_client.append(record_uuid)

    # 4. Client'ta olup sunucuda olmayan (yeni kayıtlar)
    for uuid in client_kunyeler:
        if uuid not in server_uuids:
            need_from_client.append(uuid)

    # Revision al
    rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).first()
    current_rev = rev.current_revision if rev else 0

    db.commit()

    # Log
    logger.info(
        f"Sync: {len(to_client)} to_client, "
        f"{len(need_from_client)} need_from_client, "
        f"{len(bn_changes)} bn_changes"
    )

    return SyncResponse(
        success=True,
        to_client=to_client,
        need_from_client=need_from_client,
        bn_changes=bn_changes,
        new_revision=current_rev,
        message=f"{len(request.changes)} değişiklik işlendi"
    )


def process_incoming_change(
    db: Session,
    firm_id: str,
    change: Dict[str, Any],
    device_id: str = None
) -> Dict[str, Any]:
    """
    Gelen değişikliği işle.

    BN çakışma kontrolü yapar.
    """
    uuid = change.get('uuid')
    table_name = change.get('table_name')
    operation = change.get('operation', 'INSERT')
    data = change.get('data', {})

    if not uuid or not table_name:
        return {'error': 'uuid ve table_name gerekli'}

    if table_name not in SYNCED_TABLES:
        return {'error': f'Bilinmeyen tablo: {table_name}'}

    # Timestamps
    created_at = data.get('created_at')
    updated_at = data.get('updated_at')

    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except:
            created_at = datetime.utcnow()
    else:
        created_at = created_at or datetime.utcnow()

    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        except:
            updated_at = datetime.utcnow()
    else:
        updated_at = updated_at or datetime.utcnow()

    result = {'uuid': uuid, 'status': 'ok'}

    # Mevcut kaydı kontrol et
    existing = db.query(SyncRecord).filter(
        SyncRecord.uuid == uuid,
        SyncRecord.firm_id == firm_id
    ).first()

    new_rev = get_next_revision(db, firm_id)

    # BN çakışma kontrolü (sadece dosyalar INSERT için)
    if table_name == 'dosyalar' and operation == 'INSERT' and not existing:
        requested_bn = data.get('buro_takip_no')

        if requested_bn:
            # Bu BN başka bir kayıtta var mı?
            bn_conflict = db.query(SyncRecord).filter(
                SyncRecord.firm_id == firm_id,
                SyncRecord.table_name == 'dosyalar',
                SyncRecord.buro_takip_no == requested_bn,
                SyncRecord.uuid != uuid,
                SyncRecord.is_deleted == False
            ).first()

            if bn_conflict:
                # Çakışma var! Zaman damgasına göre karar ver
                if created_at > bn_conflict.created_at:
                    # Bu kayıt daha yeni, yeni BN ver
                    new_bn = get_next_bn(db, firm_id)
                    old_bn = requested_bn
                    data['buro_takip_no'] = new_bn

                    result = {
                        'uuid': uuid,
                        'status': 'bn_reassigned',
                        'bn_changed': True,
                        'old_bn': old_bn,
                        'new_bn': new_bn,
                        'message': f'BN çakışması: {old_bn} → {new_bn}'
                    }

                    # Log
                    db.add(SyncLog(
                        firm_id=firm_id,
                        device_id=device_id,
                        action='bn_reassign',
                        record_uuid=uuid,
                        table_name=table_name,
                        details={'old_bn': old_bn, 'new_bn': new_bn}
                    ))

    # Kayıt işlemi
    if operation == 'DELETE':
        if existing:
            existing.is_deleted = True
            existing.revision = new_rev
            existing.updated_at = updated_at
            existing.updated_by_device = device_id

    elif existing:
        # UPDATE
        existing.data = data
        existing.revision = new_rev
        existing.updated_at = updated_at
        existing.updated_by_device = device_id
        if table_name == 'dosyalar':
            existing.buro_takip_no = data.get('buro_takip_no')

    else:
        # INSERT
        record = SyncRecord(
            uuid=uuid,
            firm_id=firm_id,
            table_name=table_name,
            data=data,
            buro_takip_no=data.get('buro_takip_no') if table_name == 'dosyalar' else None,
            revision=new_rev,
            is_deleted=False,
            created_at=created_at,
            updated_at=updated_at,
            created_by_device=device_id,
            updated_by_device=device_id
        )
        db.add(record)

    db.flush()
    return result


# ============================================================
# LEGACY SYNC ENDPOINTS (Uyumluluk için)
# ============================================================

@app.post("/api/sync/push")
def push_changes(
    request: PushRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_device_id: str = Header(None)
):
    """Değişiklikleri gönder (eski API uyumluluğu)"""
    results = []
    bn_changes = []
    firm_id = to_str(user.firm_id)

    for change in request.changes:
        result = process_incoming_change(db, firm_id, change, x_device_id)
        results.append(result)
        if result.get('bn_changed'):
            bn_changes.append(result)

    db.commit()

    return {
        'success': True,
        'synced_count': len(results),
        'bn_changes': bn_changes,
        'results': results
    }


@app.get("/api/sync/pull")
def pull_changes(
    since_revision: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Değişiklikleri çek (eski API uyumluluğu)"""
    firm_id = to_str(user.firm_id)
    records = db.query(SyncRecord).filter(
        SyncRecord.firm_id == firm_id,
        SyncRecord.revision > since_revision
    ).order_by(SyncRecord.revision).all()

    changes = []
    for record in records:
        changes.append({
            'uuid': to_str(record.uuid),
            'table_name': record.table_name,
            'operation': 'DELETE' if record.is_deleted else 'UPSERT',
            'data': record.data,
            'revision': record.revision
        })

    rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).first()

    return {
        'changes': changes,
        'latest_revision': rev.current_revision if rev else 0
    }


@app.get("/api/sync/status")
def get_sync_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Senkronizasyon durumu"""
    firm_id = to_str(user.firm_id)
    rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).first()

    record_count = db.query(func.count(SyncRecord.uuid)).filter(
        SyncRecord.firm_id == firm_id,
        SyncRecord.is_deleted == False
    ).scalar()

    return {
        'is_connected': True,
        'current_revision': rev.current_revision if rev else 0,
        'record_count': record_count,
        'last_sync': rev.updated_at.isoformat() if rev else None
    }


# ============================================================
# ADMIN ENDPOINTS
# ============================================================

@app.get("/api/admin/devices")
def get_devices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cihaz listesi"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    devices = db.query(Device).filter(
        Device.firm_id == user.firm_id
    ).all()

    return {
        'devices': [
            {
                'uuid': d.uuid,
                'device_id': d.device_id,
                'device_name': d.device_name,
                'is_approved': d.is_approved,
                'is_active': d.is_active,
                'last_seen_at': d.last_seen_at.isoformat() if d.last_seen_at else None,
                'created_at': d.created_at.isoformat()
            }
            for d in devices
        ]
    }


@app.post("/api/admin/devices/{device_id}/approve")
def approve_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cihazı onayla"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    device = db.query(Device).filter(
        (Device.uuid == device_id) | (Device.device_id == device_id),
        Device.firm_id == user.firm_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı")

    device.is_approved = True
    db.commit()

    firm = db.query(Firm).filter(Firm.id == user.firm_id).first()

    return {
        'success': True,
        'device_id': device.uuid,
        'firm_key': firm.firm_key
    }


@app.post("/api/admin/devices/{device_id}/deactivate")
def deactivate_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cihazı deaktif et"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    device = db.query(Device).filter(
        (Device.uuid == device_id) | (Device.device_id == device_id),
        Device.firm_id == user.firm_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı")

    device.is_active = False
    db.commit()

    return {'success': True}


@app.post("/api/admin/join-code/generate")
def generate_join_code(
    max_uses: int = 10,
    expires_hours: int = 24,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Yeni katılım kodu oluştur"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    code_str = f"BURO-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    code = JoinCode(
        firm_id=user.firm_id,
        code=code_str,
        max_uses=max_uses,
        expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
        created_by=user.uuid
    )
    db.add(code)
    db.commit()

    return {
        'code': code_str,
        'expires_at': code.expires_at.isoformat()
    }


@app.get("/api/admin/users")
def get_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcı listesi"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    users = db.query(User).filter(
        User.firm_id == user.firm_id
    ).all()

    return {
        'users': [
            {
                'uuid': u.uuid,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat()
            }
            for u in users
        ]
    }


@app.post("/api/admin/users")
def create_user(
    username: str,
    password: str,
    email: str = "",
    role: str = "user",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Yeni kullanıcı oluştur"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")

    # Kullanıcı adı kontrolü
    existing = db.query(User).filter(
        User.firm_id == user.firm_id,
        User.username == username
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanılıyor")

    new_user = User(
        firm_id=user.firm_id,
        username=username,
        password_hash=get_password_hash(password),
        email=email,
        role=role
    )
    db.add(new_user)
    db.commit()

    return {
        'success': True,
        'user_uuid': new_user.uuid
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
