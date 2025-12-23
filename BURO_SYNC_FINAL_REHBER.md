# BÜRO SENKRONİZASYON - FİNAL KURULUM REHBERİ

> **Karar:** Mevcut planlar + Güvenlik katmanları (Hibrit yaklaşım)

---

## 1. FİNAL MİMARİ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FİNAL MİMARİ                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                   │
│    │ Bilgisayar A │   │ Bilgisayar B │   │ Bilgisayar C │                   │
│    │   (SQLite)   │   │   (SQLite)   │   │   (SQLite)   │                   │
│    │              │   │              │   │              │                   │
│    │ device_id: A │   │ device_id: B │   │ device_id: C │                   │
│    │ firm_id: X   │   │ firm_id: X   │   │ firm_id: X   │                   │
│    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                   │
│           │                  │                  │                            │
│           └──────────────────┼──────────────────┘                            │
│                              │ HTTP/JSON                                     │
│                              ▼                                               │
│                    ┌─────────────────────┐                                   │
│                    │    Raspberry Pi 5   │                                   │
│                    │    192.168.1.xxx    │                                   │
│                    │                     │                                   │
│                    │  ┌───────────────┐  │                                   │
│                    │  │   FastAPI     │  │                                   │
│                    │  │  :8000 portu  │  │                                   │
│                    │  └───────┬───────┘  │                                   │
│                    │          │          │                                   │
│                    │  ┌───────▼───────┐  │                                   │
│                    │  │  PostgreSQL   │  │                                   │
│                    │  └───────────────┘  │                                   │
│                    └─────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Güvenlik Katmanları

| Katman | Amaç | Koruma |
|--------|------|--------|
| **firm_id** | Büro kimliği | Yanlış ağa bağlanmayı önler |
| **device_id** | Cihaz kimliği | Yetkisiz cihazı engeller |
| **JWT Token** | Oturum | Kullanıcı doğrulama |
| **Katılım Kodu** | Yeni cihaz | Kontrolsüz eklemeyi önler |

---

## 2. RASPBERRY PI SIFIRDAN KURULUM

### 2.1 Raspberry Pi Imager ile SD Kart Hazırlama

1. **Raspberry Pi Imager'ı aç**

2. **OS Seç:**
   - `Raspberry Pi OS (other)` → `Raspberry Pi OS Lite (64-bit)`
   - (Desktop gereksiz, sadece sunucu olacak)

3. **Storage Seç:**
   - SD kartını seç

4. **⚙️ Ayarlar (Dişli ikonu) - ÖNEMLİ:**

```
┌─────────────────────────────────────────────────────────┐
│  AYARLAR (Ctrl+Shift+X veya dişli ikonu)               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ☑ Set hostname: lextakip-server                       │
│                                                         │
│  ☑ Enable SSH                                          │
│    ● Use password authentication                        │
│                                                         │
│  ☑ Set username and password                           │
│    Username: lextakip                                   │
│    Password: LexTakip2024!  (veya kendi şifren)        │
│                                                         │
│  ☑ Configure wireless LAN (opsiyonel, kablo varsa gerek yok)
│    SSID: WiFi_Adi                                       │
│    Password: WiFi_Sifresi                               │
│    Wireless LAN country: TR                             │
│                                                         │
│  ☑ Set locale settings                                 │
│    Time zone: Europe/Istanbul                           │
│    Keyboard layout: tr                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

5. **WRITE** butonuna bas ve bekle

6. **SD kartı Pi'a tak, güç ver, 2-3 dakika bekle**

### 2.2 IP Adresini Bul

Yöntem 1 - Router'dan:
- Router admin paneline gir (genelde 192.168.1.1)
- Bağlı cihazlarda "lextakip-server" veya "raspberrypi" ara

Yöntem 2 - Windows'tan:
```cmd
# Ağdaki cihazları tara
arp -a

# veya ping at
ping lextakip-server.local
```

Yöntem 3 - Eğer ekran bağlayabilirsen:
```bash
hostname -I
```

### 2.3 SSH ile Bağlan

Windows PowerShell veya Terminal:
```bash
ssh lextakip@192.168.1.XXX
# Şifre: LexTakip2024! (veya belirlediğin)
```

### 2.4 Sistem Güncellemesi

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget
```

### 2.5 Statik IP Ayarla (Önemli!)

```bash
sudo nano /etc/dhcpcd.conf
```

Dosyanın sonuna ekle:
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

> **Not:** `192.168.1.100` yerine boş bir IP seç. Router'dan kontrol et.

Kaydet (Ctrl+O, Enter, Ctrl+X) ve yeniden başlat:
```bash
sudo reboot
```

Yeni IP ile tekrar bağlan:
```bash
ssh lextakip@192.168.1.100
```

---

## 3. SUNUCU YAZILIMI KURULUMU

### 3.1 PostgreSQL Kurulumu

```bash
# PostgreSQL kur
sudo apt install -y postgresql postgresql-contrib

# Servisi başlat
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Veritabanı ve kullanıcı oluştur
sudo -u postgres psql << 'EOF'
CREATE USER lextakip WITH PASSWORD 'LexTakip2024!';
CREATE DATABASE lextakip_db OWNER lextakip;
GRANT ALL PRIVILEGES ON DATABASE lextakip_db TO lextakip;
\q
EOF
```

### 3.2 Python Ortamı

```bash
# Python araçları
sudo apt install -y python3-pip python3-venv python3-dev libpq-dev

# Proje klasörü
mkdir -p ~/lextakip-server
cd ~/lextakip-server

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Paketler
pip install --upgrade pip
pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary python-jose[cryptography] bcrypt python-multipart pydantic pydantic-settings
```

### 3.3 Sunucu Dosyalarını Oluştur

#### .env
```bash
cat > ~/lextakip-server/.env << 'EOF'
DATABASE_URL=postgresql://lextakip:LexTakip2024!@localhost/lextakip_db
SECRET_KEY=lextakip-gizli-anahtar-2024-cok-guvenli-en-az-32-karakter
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF
```

#### config.py
```bash
cat > ~/lextakip-server/config.py << 'EOF'
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"

settings = Settings()
EOF
```

#### database.py
```bash
cat > ~/lextakip-server/database.py << 'EOF'
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF
```

#### models.py (Güvenlik Katmanlı)
```bash
cat > ~/lextakip-server/models.py << 'EOF'
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

# ============================================================
# GÜVENLİK TABLOLARI
# ============================================================

class Firm(Base):
    """Büro/Firma"""
    __tablename__ = "firms"

    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

class Device(Base):
    """Kayıtlı Cihazlar (Whitelist)"""
    __tablename__ = "devices"

    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), ForeignKey("firms.uuid"), nullable=False)
    device_id = Column(String(255), nullable=False)  # Benzersiz cihaz kimliği
    device_name = Column(String(255))  # "Mehmet'in Laptopu"

    is_approved = Column(Boolean, default=False)  # Admin onayı gerekli
    is_active = Column(Boolean, default=True)

    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    approved_at = Column(DateTime)

class JoinCode(Base):
    """Katılım Kodları"""
    __tablename__ = "join_codes"

    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), ForeignKey("firms.uuid"), nullable=False)
    code = Column(String(20), unique=True, nullable=False)  # BURO-XXXX-XXXX

    max_uses = Column(Integer, default=10)
    used_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

# ============================================================
# KULLANICI TABLOLARI
# ============================================================

class BaseMixin:
    """Tüm senkronize tablolar için ortak alanlar"""
    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False, index=True)
    revision = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class User(Base, BaseMixin):
    """Uygulama Kullanıcıları"""
    __tablename__ = "users"

    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    role = Column(String(50), default="avukat")  # kurucu_avukat, avukat, stajyer, sekreter
    active = Column(Boolean, default=True)

# ============================================================
# VERİ TABLOLARI
# ============================================================

class Dosya(Base, BaseMixin):
    """Hukuki Dosyalar"""
    __tablename__ = "dosyalar"

    buro_takip_no = Column(String(100))
    dosya_esas_no = Column(String(100))
    muvekkil_adi = Column(String(255))
    muvekkil_rolu = Column(String(100))
    karsi_taraf = Column(String(255))
    dosya_konusu = Column(Text)
    mahkeme_adi = Column(String(255))
    dava_acilis_tarihi = Column(String(50))
    durusma_tarihi = Column(String(50))
    dava_durumu = Column(String(100))
    is_tarihi = Column(String(50))
    aciklama = Column(Text)
    tekrar_dava_durumu_2 = Column(String(100))
    is_tarihi_2 = Column(String(50))
    aciklama_2 = Column(Text)
    is_archived = Column(Boolean, default=False)

class Finans(Base, BaseMixin):
    """Finansal Kayıtlar"""
    __tablename__ = "finans"

    dosya_uuid = Column(String(36), ForeignKey("dosyalar.uuid"))
    sozlesme_ucreti = Column(String(100))
    sozlesme_yuzdesi = Column(String(50))
    sozlesme_ucreti_cents = Column(Integer, default=0)
    tahsil_hedef_cents = Column(Integer, default=0)
    tahsil_edilen_cents = Column(Integer, default=0)
    masraf_toplam_cents = Column(Integer, default=0)
    masraf_tahsil_cents = Column(Integer, default=0)
    notlar = Column(Text)
    yuzde_is_sonu = Column(Boolean, default=False)

class Taksit(Base, BaseMixin):
    """Taksitler"""
    __tablename__ = "taksitler"

    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    vade_tarihi = Column(String(50))
    tutar_cents = Column(Integer, default=0)
    durum = Column(String(50))
    odeme_tarihi = Column(String(50))
    aciklama = Column(Text)

class OdemeKaydi(Base, BaseMixin):
    """Ödeme Kayıtları"""
    __tablename__ = "odeme_kayitlari"

    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    tarih = Column(String(50))
    tutar_cents = Column(Integer, default=0)
    yontem = Column(String(100))
    aciklama = Column(Text)
    taksit_uuid = Column(String(36))

class Masraf(Base, BaseMixin):
    """Masraflar"""
    __tablename__ = "masraflar"

    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    kalem = Column(String(255))
    tutar_cents = Column(Integer, default=0)
    tarih = Column(String(50))
    tahsil_durumu = Column(String(50))
    tahsil_tarihi = Column(String(50))
    aciklama = Column(Text)

class MuvekkilKasasi(Base, BaseMixin):
    """Müvekkil Kasası"""
    __tablename__ = "muvekkil_kasasi"

    dosya_uuid = Column(String(36), ForeignKey("dosyalar.uuid"))
    tarih = Column(String(50))
    tutar_kurus = Column(Integer, default=0)
    islem_turu = Column(String(100))
    aciklama = Column(Text)

class Tebligat(Base, BaseMixin):
    """Tebligatlar"""
    __tablename__ = "tebligatlar"

    dosya_no = Column(String(100))
    kurum = Column(String(255))
    geldigi_tarih = Column(String(50))
    teblig_tarihi = Column(String(50))
    is_son_gunu = Column(String(50))
    icerik = Column(Text)

class Arabuluculuk(Base, BaseMixin):
    """Arabuluculuk"""
    __tablename__ = "arabuluculuk"

    davaci = Column(String(255))
    davali = Column(String(255))
    arb_adi = Column(String(255))
    arb_tel = Column(String(50))
    toplanti_tarihi = Column(String(50))
    toplanti_saati = Column(String(50))
    konu = Column(Text)

class Gorev(Base, BaseMixin):
    """Görevler"""
    __tablename__ = "gorevler"

    tarih = Column(String(50))
    konu = Column(String(255))
    aciklama = Column(Text)
    atanan_kullanicilar = Column(Text)
    kaynak_turu = Column(String(50))
    olusturan_kullanici = Column(String(100))
    olusturma_zamani = Column(String(50))
    tamamlandi = Column(Boolean, default=False)
    tamamlanma_zamani = Column(String(50))
    dosya_uuid = Column(String(36))
    gorev_turu = Column(String(50))

class GlobalRevision(Base):
    """Global Revizyon Sayacı"""
    __tablename__ = "global_revisions"

    firm_id = Column(String(36), primary_key=True)
    current_revision = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Senkronize edilecek tablolar
SYNCABLE_TABLES = {
    'dosyalar': Dosya,
    'finans': Finans,
    'taksitler': Taksit,
    'odeme_kayitlari': OdemeKaydi,
    'masraflar': Masraf,
    'muvekkil_kasasi': MuvekkilKasasi,
    'tebligatlar': Tebligat,
    'arabuluculuk': Arabuluculuk,
    'gorevler': Gorev,
    'users': User
}
EOF
```

#### schemas.py
```bash
cat > ~/lextakip-server/schemas.py << 'EOF'
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime

# ============================================================
# KURULUM
# ============================================================

class SetupRequest(BaseModel):
    firm_name: str
    admin_username: str
    admin_password: str

class SetupResponse(BaseModel):
    success: bool
    message: str
    firm_id: Optional[str] = None
    join_code: Optional[str] = None

# ============================================================
# CİHAZ KATILIM
# ============================================================

class JoinRequest(BaseModel):
    join_code: str
    device_id: str
    device_name: str

class JoinResponse(BaseModel):
    success: bool
    message: str
    firm_id: Optional[str] = None
    requires_approval: bool = True

# ============================================================
# KİMLİK DOĞRULAMA
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: str
    firm_id: str  # Yanlış ağ koruması için

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user_uuid: Optional[str] = None
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None
    role: Optional[str] = None

# ============================================================
# SENKRONİZASYON
# ============================================================

class SyncRequest(BaseModel):
    device_id: str
    firm_id: str  # Yanlış ağ koruması için
    last_sync_revision: int = 0
    changes: List[Dict[str, Any]] = []

class SyncResponse(BaseModel):
    success: bool
    message: str
    new_revision: int = 0
    changes: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

# ============================================================
# YÖNETİM
# ============================================================

class DeviceApproveRequest(BaseModel):
    device_uuid: str

class GenerateJoinCodeRequest(BaseModel):
    max_uses: int = 10
    expires_days: int = 7
EOF
```

#### auth.py
```bash
cat > ~/lextakip-server/auth.py << 'EOF'
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from config import settings
from database import get_db
from models import User, Device

security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

    user_uuid = payload.get("sub")
    device_id = payload.get("device_id")
    firm_id = payload.get("firm_id")

    if not user_uuid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

    # Kullanıcı kontrolü
    user = db.query(User).filter(User.uuid == user_uuid, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

    # Cihaz kontrolü
    device = db.query(Device).filter(
        Device.device_id == device_id,
        Device.firm_id == firm_id,
        Device.is_approved == True,
        Device.is_active == True
    ).first()

    if not device:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cihaz onaylı değil")

    return user
EOF
```

#### sync_handler.py
```bash
cat > ~/lextakip-server/sync_handler.py << 'EOF'
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Tuple
from datetime import datetime
from models import SYNCABLE_TABLES, GlobalRevision
import logging

logger = logging.getLogger(__name__)

def convert_value(value, column_type):
    """Değeri doğru tipe dönüştür."""
    if value is None:
        return None
    type_name = str(column_type).upper()
    if 'BOOLEAN' in type_name:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'evet')
        return bool(value)
    if 'INTEGER' in type_name:
        if value == '' or value is None:
            return None
        try:
            return int(float(value))
        except:
            return None
    return value

def get_next_revision(db: Session, firm_id: str) -> int:
    """Yeni revizyon numarası al"""
    rev = db.query(GlobalRevision).filter(GlobalRevision.firm_id == firm_id).first()
    if not rev:
        rev = GlobalRevision(firm_id=firm_id, current_revision=0)
        db.add(rev)
    rev.current_revision += 1
    db.flush()
    return rev.current_revision

def process_incoming_changes(db: Session, firm_id: str, changes: List[Dict]) -> Tuple[int, List[Dict]]:
    """Gelen değişiklikleri işle"""
    errors = []
    processed = 0

    for change in changes:
        try:
            table_name = change.get('table')
            op = change.get('op')
            record_uuid = change.get('uuid')
            data = change.get('data', {})

            if table_name not in SYNCABLE_TABLES:
                errors.append({'uuid': record_uuid, 'error': f'Bilinmeyen tablo: {table_name}'})
                continue

            Model = SYNCABLE_TABLES[table_name]
            new_rev = get_next_revision(db, firm_id)

            # Veri tiplerini dönüştür
            converted_data = {}
            for key, value in data.items():
                if hasattr(Model, key):
                    column = getattr(Model, key).property.columns[0]
                    converted_data[key] = convert_value(value, column.type)
                else:
                    converted_data[key] = value

            if op in ('insert', 'upsert'):
                existing = db.query(Model).filter(Model.uuid == record_uuid).first()
                if existing:
                    # Güncelle (Last-Write-Wins)
                    for key, value in converted_data.items():
                        if hasattr(existing, key) and key not in ('uuid', 'firm_id'):
                            setattr(existing, key, value)
                    existing.revision = new_rev
                    existing.updated_at = datetime.utcnow()
                else:
                    # Yeni kayıt
                    record = Model(uuid=record_uuid, firm_id=firm_id, revision=new_rev, **converted_data)
                    db.add(record)

            elif op == 'update':
                record = db.query(Model).filter(Model.uuid == record_uuid, Model.firm_id == firm_id).first()
                if record:
                    for key, value in converted_data.items():
                        if hasattr(record, key) and key not in ('uuid', 'firm_id'):
                            setattr(record, key, value)
                    record.revision = new_rev
                    record.updated_at = datetime.utcnow()

            elif op == 'delete':
                record = db.query(Model).filter(Model.uuid == record_uuid, Model.firm_id == firm_id).first()
                if record:
                    record.is_deleted = True
                    record.revision = new_rev

            processed += 1
            db.flush()

        except Exception as e:
            logger.exception(f"Değişiklik işlenirken hata: {change}")
            errors.append({'uuid': change.get('uuid'), 'error': str(e)})

    return processed, errors

def get_outgoing_changes(db: Session, firm_id: str, since_revision: int) -> List[Dict]:
    """Belirtilen revizyondan sonraki değişiklikleri al"""
    changes = []

    for table_name, Model in SYNCABLE_TABLES.items():
        records = db.query(Model).filter(
            Model.firm_id == firm_id,
            Model.revision > since_revision
        ).all()

        for record in records:
            data = {}
            for column in record.__table__.columns:
                if column.name not in ('firm_id',):
                    value = getattr(record, column.name)
                    if isinstance(value, datetime):
                        data[column.name] = value.isoformat()
                    elif isinstance(value, bool):
                        data[column.name] = value
                    else:
                        data[column.name] = str(value) if value is not None else None

            changes.append({
                'table': table_name,
                'op': 'delete' if record.is_deleted else 'upsert',
                'uuid': record.uuid,
                'revision': record.revision,
                'data': data
            })

    return sorted(changes, key=lambda x: x['revision'])

def perform_sync(db: Session, firm_id: str, incoming: List[Dict], since_revision: int) -> Dict:
    """Tam senkronizasyon işlemi"""
    # Gelen değişiklikleri işle
    processed, errors = process_incoming_changes(db, firm_id, incoming)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {
            'success': False,
            'message': f'Commit hatası: {str(e)}',
            'new_revision': since_revision,
            'changes': [],
            'errors': errors
        }

    # Giden değişiklikleri al
    outgoing = get_outgoing_changes(db, firm_id, since_revision)

    # Mevcut revizyonu al
    rev = db.query(GlobalRevision).filter(GlobalRevision.firm_id == firm_id).first()
    current_rev = rev.current_revision if rev else 0

    return {
        'success': True,
        'message': f'{processed} değişiklik işlendi',
        'new_revision': current_rev,
        'changes': outgoing,
        'errors': errors
    }
EOF
```

#### main.py (Güvenlik Katmanlı)
```bash
cat > ~/lextakip-server/main.py << 'EOF'
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import string

from database import engine, get_db, Base
from models import Firm, Device, JoinCode, User, GlobalRevision
from schemas import (
    SetupRequest, SetupResponse,
    JoinRequest, JoinResponse,
    LoginRequest, LoginResponse,
    SyncRequest, SyncResponse,
    DeviceApproveRequest, GenerateJoinCodeRequest
)
from auth import verify_password, get_password_hash, create_access_token, get_current_user
from sync_handler import perform_sync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LexTakip Sync Server", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları oluşturuldu")

# ============================================================
# SAĞLIK KONTROLÜ
# ============================================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/info")
def server_info(db: Session = Depends(get_db)):
    """Sunucu bilgisi - Yanlış ağ kontrolü için"""
    firm = db.query(Firm).first()
    return {
        "status": "ok",
        "firm_id": firm.uuid if firm else None,
        "firm_name": firm.name if firm else None,
        "is_setup": firm is not None
    }

# ============================================================
# İLK KURULUM
# ============================================================

def generate_join_code() -> str:
    """BURO-XXXX-XXXX formatında kod üret"""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"BURO-{part1}-{part2}"

@app.post("/api/setup", response_model=SetupResponse)
def initial_setup(request: SetupRequest, db: Session = Depends(get_db)):
    """İlk büro kurulumu"""

    # Zaten kurulmuş mu?
    if db.query(Firm).first():
        raise HTTPException(status_code=400, detail="Sistem zaten kurulmuş")

    # Firma oluştur
    firm = Firm(name=request.firm_name)
    db.add(firm)
    db.flush()

    # Admin kullanıcısı oluştur
    admin = User(
        firm_id=firm.uuid,
        username=request.admin_username,
        password_hash=get_password_hash(request.admin_password),
        role="kurucu_avukat",
        active=True
    )
    db.add(admin)

    # İlk katılım kodu oluştur
    code = generate_join_code()
    join_code = JoinCode(
        firm_id=firm.uuid,
        code=code,
        expires_at=datetime.utcnow() + timedelta(days=30),
        max_uses=100
    )
    db.add(join_code)

    # Global revizyon başlat
    db.add(GlobalRevision(firm_id=firm.uuid, current_revision=0))

    db.commit()

    logger.info(f"Büro kuruldu: {firm.name} ({firm.uuid})")

    return SetupResponse(
        success=True,
        message="Büro başarıyla kuruldu",
        firm_id=firm.uuid,
        join_code=code
    )

# ============================================================
# CİHAZ KATILIM
# ============================================================

@app.post("/api/join", response_model=JoinResponse)
def join_firm(request: JoinRequest, db: Session = Depends(get_db)):
    """Büroya yeni cihaz ekle"""

    # Katılım kodunu kontrol et
    join_code = db.query(JoinCode).filter(
        JoinCode.code == request.join_code,
        JoinCode.is_active == True
    ).first()

    if not join_code:
        return JoinResponse(success=False, message="Geçersiz katılım kodu")

    if join_code.expires_at < datetime.utcnow():
        return JoinResponse(success=False, message="Katılım kodu süresi dolmuş")

    if join_code.used_count >= join_code.max_uses:
        return JoinResponse(success=False, message="Katılım kodu kullanım limiti dolmuş")

    # Cihaz zaten kayıtlı mı?
    existing = db.query(Device).filter(
        Device.device_id == request.device_id,
        Device.firm_id == join_code.firm_id
    ).first()

    if existing:
        if existing.is_approved:
            return JoinResponse(
                success=True,
                message="Cihaz zaten kayıtlı ve onaylı",
                firm_id=join_code.firm_id,
                requires_approval=False
            )
        else:
            return JoinResponse(
                success=True,
                message="Cihaz zaten kayıtlı, onay bekliyor",
                firm_id=join_code.firm_id,
                requires_approval=True
            )

    # Yeni cihaz ekle
    device = Device(
        firm_id=join_code.firm_id,
        device_id=request.device_id,
        device_name=request.device_name,
        is_approved=False  # Admin onayı gerekli
    )
    db.add(device)

    # Kullanım sayısını artır
    join_code.used_count += 1

    db.commit()

    logger.info(f"Yeni cihaz katıldı: {request.device_name} ({request.device_id})")

    return JoinResponse(
        success=True,
        message="Cihaz kaydedildi, yönetici onayı bekleniyor",
        firm_id=join_code.firm_id,
        requires_approval=True
    )

# ============================================================
# KİMLİK DOĞRULAMA
# ============================================================

@app.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Kullanıcı girişi"""

    # Firma kontrolü (Yanlış ağ koruması)
    firm = db.query(Firm).filter(Firm.uuid == request.firm_id).first()
    if not firm:
        return LoginResponse(
            success=False,
            message="FIRM_MISMATCH: Bu sunucu farklı bir büroya ait!"
        )

    # Cihaz kontrolü
    device = db.query(Device).filter(
        Device.device_id == request.device_id,
        Device.firm_id == request.firm_id
    ).first()

    if not device:
        return LoginResponse(success=False, message="Cihaz kayıtlı değil")

    if not device.is_approved:
        return LoginResponse(success=False, message="Cihaz henüz onaylanmadı")

    if not device.is_active:
        return LoginResponse(success=False, message="Cihaz deaktif edilmiş")

    # Kullanıcı kontrolü
    user = db.query(User).filter(
        User.username == request.username,
        User.firm_id == request.firm_id,
        User.is_deleted == False,
        User.active == True
    ).first()

    if not user or not verify_password(request.password, user.password_hash):
        return LoginResponse(success=False, message="Kullanıcı adı veya şifre hatalı")

    # Token oluştur
    token = create_access_token(data={
        "sub": user.uuid,
        "firm_id": user.firm_id,
        "device_id": request.device_id
    })

    # Son giriş zamanını güncelle
    device.last_sync_at = datetime.utcnow()
    db.commit()

    return LoginResponse(
        success=True,
        message="Giriş başarılı",
        token=token,
        user_uuid=user.uuid,
        firm_id=user.firm_id,
        firm_name=firm.name,
        role=user.role
    )

# ============================================================
# SENKRONİZASYON
# ============================================================

@app.post("/api/sync", response_model=SyncResponse)
def sync(request: SyncRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Senkronizasyon"""

    # Firma kontrolü (Yanlış ağ koruması)
    if request.firm_id != user.firm_id:
        return SyncResponse(
            success=False,
            message="FIRM_MISMATCH: Firma kimliği eşleşmiyor!"
        )

    # Cihaz kontrolü
    device = db.query(Device).filter(
        Device.device_id == request.device_id,
        Device.firm_id == user.firm_id,
        Device.is_active == True
    ).first()

    if not device:
        return SyncResponse(success=False, message="Cihaz bulunamadı veya deaktif")

    # Senkronizasyon yap
    try:
        result = perform_sync(
            db=db,
            firm_id=user.firm_id,
            incoming=request.changes,
            since_revision=request.last_sync_revision
        )

        # Son sync zamanını güncelle
        device.last_sync_at = datetime.utcnow()
        db.commit()

        return SyncResponse(**result)

    except Exception as e:
        logger.exception("Senkronizasyon hatası")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# YÖNETİM (Admin)
# ============================================================

@app.get("/api/admin/devices")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cihaz listesi"""
    if user.role not in ("kurucu_avukat", "admin"):
        raise HTTPException(status_code=403, detail="Yetki yok")

    devices = db.query(Device).filter(Device.firm_id == user.firm_id).all()
    return {
        "devices": [
            {
                "uuid": d.uuid,
                "device_id": d.device_id,
                "device_name": d.device_name,
                "is_approved": d.is_approved,
                "is_active": d.is_active,
                "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None
            }
            for d in devices
        ]
    }

@app.post("/api/admin/devices/approve")
def approve_device(request: DeviceApproveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cihaz onayla"""
    if user.role not in ("kurucu_avukat", "admin"):
        raise HTTPException(status_code=403, detail="Yetki yok")

    device = db.query(Device).filter(
        Device.uuid == request.device_uuid,
        Device.firm_id == user.firm_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı")

    device.is_approved = True
    device.approved_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "Cihaz onaylandı"}

@app.post("/api/admin/devices/{device_uuid}/deactivate")
def deactivate_device(device_uuid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cihaz deaktif et"""
    if user.role not in ("kurucu_avukat", "admin"):
        raise HTTPException(status_code=403, detail="Yetki yok")

    device = db.query(Device).filter(
        Device.uuid == device_uuid,
        Device.firm_id == user.firm_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı")

    device.is_active = False
    db.commit()

    return {"success": True, "message": "Cihaz deaktif edildi"}

@app.post("/api/admin/join-code/generate")
def generate_new_join_code(
    request: GenerateJoinCodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Yeni katılım kodu oluştur"""
    if user.role not in ("kurucu_avukat", "admin"):
        raise HTTPException(status_code=403, detail="Yetki yok")

    code = generate_join_code()
    join_code = JoinCode(
        firm_id=user.firm_id,
        code=code,
        max_uses=request.max_uses,
        expires_at=datetime.utcnow() + timedelta(days=request.expires_days)
    )
    db.add(join_code)
    db.commit()

    return {
        "success": True,
        "code": code,
        "expires_at": join_code.expires_at.isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
```

### 3.4 Systemd Servisi

```bash
# Servis dosyası oluştur
sudo tee /etc/systemd/system/lextakip.service << 'EOF'
[Unit]
Description=LexTakip Sync Server
After=network.target postgresql.service

[Service]
Type=simple
User=lextakip
WorkingDirectory=/home/lextakip/lextakip-server
Environment="PATH=/home/lextakip/lextakip-server/venv/bin"
ExecStart=/home/lextakip/lextakip-server/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Servisi aktifleştir ve başlat
sudo systemctl daemon-reload
sudo systemctl enable lextakip
sudo systemctl start lextakip

# Durumu kontrol et
sudo systemctl status lextakip
```

### 3.5 Firewall (Opsiyonel)

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow from 192.168.1.0/24 to any port 8000
sudo ufw enable
```

---

## 4. TEST

### 4.1 Sunucu Testi

```bash
# Sağlık kontrolü
curl http://192.168.1.100:8000/api/health

# Sunucu bilgisi
curl http://192.168.1.100:8000/api/info

# İlk kurulum
curl -X POST http://192.168.1.100:8000/api/setup \
  -H "Content-Type: application/json" \
  -d '{
    "firm_name": "Örnek Hukuk Bürosu",
    "admin_username": "admin",
    "admin_password": "Admin123!"
  }'
```

Başarılı yanıt:
```json
{
  "success": true,
  "message": "Büro başarıyla kuruldu",
  "firm_id": "abc-123-...",
  "join_code": "BURO-X7K9-M2P4"
}
```

### 4.2 Cihaz Katılım Testi

```bash
# Cihaz katılımı
curl -X POST http://192.168.1.100:8000/api/join \
  -H "Content-Type: application/json" \
  -d '{
    "join_code": "BURO-X7K9-M2P4",
    "device_id": "PC-MEHMET-001",
    "device_name": "Mehmet Laptop"
  }'
```

### 4.3 Log İzleme

```bash
# Canlı log
sudo journalctl -u lextakip -f

# Son 100 satır
sudo journalctl -u lextakip -n 100
```

---

## 5. İSTEMCİ DEĞİŞİKLİKLERİ (Özet)

Masaüstü uygulamasında yapılacak değişiklikler:

1. **Yeni tablolar:** `sync_outbox`, `sync_metadata`
2. **UUID kolonları:** Tüm tablolara `uuid` kolonu ekle
3. **Sync modülü:** `app/sync/` klasörü
4. **Login güncelleme:** `device_id` ve `firm_id` gönder
5. **UI:** Sync durumu göstergesi, ayarlar paneli

> Detaylar için: `SYNC_KURULUM_REHBERI.md`

---

## 6. GÜVENLİK ÖZETİ

| Tehdit | Koruma |
|--------|--------|
| Yanlış ağa bağlanma | `firm_id` kontrolü |
| Yetkisiz cihaz | Device whitelist + onay |
| Kontrolsüz cihaz ekleme | Katılım kodu sistemi |
| Eski çalışan erişimi | Cihaz deaktif etme |
| Brute force | JWT + bcrypt |

---

## 7. HIZLI BAŞLANGIÇ KONTROL LİSTESİ

- [ ] Raspberry Pi Imager ile SD kart hazırla
- [ ] Pi'ı ağa bağla, IP bul
- [ ] SSH ile bağlan
- [ ] PostgreSQL kur
- [ ] Python ortamı hazırla
- [ ] Sunucu dosyalarını oluştur
- [ ] Systemd servisi kur
- [ ] `/api/health` test et
- [ ] `/api/setup` ile büro oluştur
- [ ] Katılım kodunu not al
- [ ] İstemci değişikliklerini yap

---

*Son güncelleme: 2024*
