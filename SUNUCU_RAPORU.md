# LexTakip Senkronizasyon Sunucusu - Teknik Rapor

## 1. Genel Bakış

### 1.1 Amaç
LexTakip masaüstü uygulaması için çoklu cihaz senkronizasyonu sağlayan bir REST API sunucusu. Birden fazla bilgisayarda çalışan LexTakip uygulamalarının verilerini merkezi bir sunucu üzerinden senkronize eder.

### 1.2 Mimari Yaklaşım
- **Offline-First**: Uygulama tamamen çevrimdışı çalışır, sunucu yalnızca senkronizasyon içindir
- **HTTP REST API**: JSON formatında veri alışverişi
- **Last-Write-Wins (LWW)**: Çakışma çözümlemesi için en son yazanın kazandığı strateji
- **UUID Tabanlı**: Cihazlar arası benzersizlik için UUID primary key
- **Revision Tracking**: Artımlı senkronizasyon için revizyon numaraları

### 1.3 Teknoloji Stack
- **Sunucu**: Raspberry Pi 5 (veya herhangi bir Linux sunucu)
- **Framework**: FastAPI (Python)
- **Veritabanı**: PostgreSQL
- **Kimlik Doğrulama**: JWT Token + bcrypt
- **Çalışma Modu**: systemd servisi olarak arka planda

---

## 2. Veritabanı Yapısı

### 2.1 Temel Tablolar
Sunucu veritabanı, istemcideki SQLite tablolarının PostgreSQL karşılıklarını içerir. Her tablo aşağıdaki ortak alanları içerir:

```sql
-- Her tabloda bulunan ortak alanlar (BaseMixin)
uuid VARCHAR(36) PRIMARY KEY,      -- Benzersiz tanımlayıcı
firm_id VARCHAR(36) NOT NULL,      -- Firma/kiracı kimliği (multi-tenant)
revision INTEGER DEFAULT 1,        -- Senkronizasyon revizyon numarası
is_deleted BOOLEAN DEFAULT FALSE,  -- Soft delete bayrağı
created_at TIMESTAMP,              -- Oluşturulma tarihi
updated_at TIMESTAMP               -- Güncellenme tarihi
```

### 2.2 Tablolar Listesi

| Tablo | Açıklama |
|-------|----------|
| `users` | Kullanıcı hesapları (sunucu kimlik doğrulama) |
| `dosyalar` | Hukuki dosyalar (ana tablo) |
| `muvekkillers` | Müvekkil bilgileri |
| `karsi_taraflar` | Karşı taraf bilgileri |
| `avukatlar` | Avukat bilgileri |
| `tür_bilgileri` | Dosya türü bilgileri |
| `durusmalar` | Duruşma kayıtları |
| `belgeler` | Belge kayıtları |
| `finans` | Finansal işlemler |
| `bildirimler` | Bildirim kayıtları |
| `dosya_kullanici` | Dosya-kullanıcı ilişkisi |
| `dosya_sekme` | Dosya-sekme ilişkisi |
| `sekmeler` | Sekme tanımları |
| `app_users` | Uygulama kullanıcıları |

### 2.3 İlişki Yönetimi
Sunucuda foreign key'ler UUID üzerinden yapılır:

```
dosyalar.muvekkil_uuid → muvekkillers.uuid
dosyalar.karsi_taraf_uuid → karsi_taraflar.uuid
dosyalar.avukat_uuid → avukatlar.uuid
durusmalar.dosya_uuid → dosyalar.uuid
belgeler.dosya_uuid → dosyalar.uuid
finans.dosya_uuid → dosyalar.uuid
```

---

## 3. API Endpoints

### 3.1 Endpoint Listesi

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| GET | `/api/health` | Sunucu sağlık kontrolü | Hayır |
| POST | `/api/setup` | İlk firma ve kullanıcı oluşturma | Hayır |
| POST | `/api/login` | Kullanıcı girişi, JWT token alma | Hayır |
| POST | `/api/sync` | Senkronizasyon işlemi | Evet |

### 3.2 Health Check
```http
GET /api/health

Response:
{
    "status": "healthy",
    "database": "connected",
    "timestamp": "2024-01-15T10:30:00"
}
```

### 3.3 Setup (İlk Kurulum)
İlk firma ve admin kullanıcısını oluşturur. Sadece bir kez çalışır.

```http
POST /api/setup
Content-Type: application/json

Request:
{
    "firm_name": "Örnek Hukuk Bürosu",
    "admin_email": "admin@firma.com",
    "admin_password": "GüçlüŞifre123!"
}

Response:
{
    "message": "Firma ve admin kullanıcısı oluşturuldu",
    "firm_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
}
```

### 3.4 Login
JWT token alır.

```http
POST /api/login
Content-Type: application/json

Request:
{
    "email": "admin@firma.com",
    "password": "GüçlüŞifre123!"
}

Response:
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "firm_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
}
```

### 3.5 Sync (Senkronizasyon)
Ana senkronizasyon endpoint'i. İki yönlü veri alışverişi yapar.

```http
POST /api/sync
Authorization: Bearer <jwt_token>
Content-Type: application/json

Request:
{
    "last_sync_revision": 0,
    "changes": [
        {
            "table_name": "dosyalar",
            "operation": "insert",
            "record_uuid": "a1b2c3d4-...",
            "data": {
                "esas_no": "2024/123",
                "mahkeme": "İstanbul 1. Asliye Hukuk",
                ...
            }
        },
        {
            "table_name": "muvekkillers",
            "operation": "update",
            "record_uuid": "e5f6g7h8-...",
            "data": {
                "ad": "Ahmet",
                "soyad": "Yılmaz",
                ...
            }
        }
    ]
}

Response:
{
    "status": "success",
    "current_revision": 42,
    "changes_accepted": 2,
    "server_changes": [
        {
            "table_name": "dosyalar",
            "operation": "upsert",
            "record_uuid": "x9y8z7w6-...",
            "data": {...}
        }
    ]
}
```

---

## 4. Senkronizasyon Akışı

### 4.1 Genel Akış Diyagramı

```
┌─────────────────┐                    ┌─────────────────┐
│  İstemci (PC1)  │                    │     Sunucu      │
│    (SQLite)     │                    │  (PostgreSQL)   │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  1. POST /api/login                  │
         │ ──────────────────────────────────► │
         │                                      │
         │  ◄─────────────────────────────────  │
         │     JWT Token                        │
         │                                      │
         │  2. POST /api/sync                   │
         │     - last_sync_revision: 0          │
         │     - changes: [yerel değişiklikler] │
         │ ──────────────────────────────────► │
         │                                      │
         │     Sunucu:                          │
         │     a) Gelen değişiklikleri uygula   │
         │     b) Revizyon numaralarını güncelle│
         │     c) Yeni değişiklikleri topla     │
         │                                      │
         │  ◄─────────────────────────────────  │
         │     - current_revision: 42           │
         │     - server_changes: [...]          │
         │                                      │
         │  3. İstemci sunucu değişikliklerini  │
         │     yerel veritabanına uygular       │
         │                                      │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Revizyon Sistemi

Her kayıt değiştiğinde `revision` numarası artar. Sunucu global bir revizyon sayacı tutar.

```
Başlangıç:
- Sunucu global_revision: 0
- Kayıt A revision: 0
- Kayıt B revision: 0

İstemci 1 Kayıt A'yı günceller:
- Sunucu global_revision: 1
- Kayıt A revision: 1

İstemci 2 Kayıt B'yi günceller:
- Sunucu global_revision: 2
- Kayıt B revision: 2

İstemci 1 sync yapar (last_sync_revision: 1):
- Sunucu revision > 1 olan kayıtları döner (Kayıt B)
```

### 4.3 Çakışma Çözümlemesi (Last-Write-Wins)

```python
def resolve_conflict(server_record, incoming_record):
    # updated_at damgasına göre karar ver
    if incoming_record['updated_at'] > server_record['updated_at']:
        # İstemci kazanır, sunucu kaydını güncelle
        return incoming_record
    else:
        # Sunucu kazanır, değişikliği reddet
        return server_record
```

### 4.4 Soft Delete

Kayıtlar fiziksel olarak silinmez, `is_deleted=True` olarak işaretlenir:

```python
# Silme işlemi
{
    "table_name": "dosyalar",
    "operation": "update",
    "record_uuid": "abc-123",
    "data": {
        "is_deleted": True,
        "updated_at": "2024-01-15T10:30:00"
    }
}
```

---

## 5. Sunucu Dosya Yapısı

```
~/lextakip-server/
├── .env                 # Ortam değişkenleri
├── venv/                # Python sanal ortamı
├── config.py            # Yapılandırma sınıfı
├── database.py          # Veritabanı bağlantısı
├── models.py            # SQLAlchemy modelleri
├── schemas.py           # Pydantic şemaları
├── auth.py              # JWT kimlik doğrulama
├── sync_handler.py      # Senkronizasyon mantığı
└── main.py              # FastAPI uygulaması
```

---

## 6. Dosya İçerikleri ve Açıklamaları

### 6.1 .env (Ortam Değişkenleri)
```bash
DATABASE_URL=postgresql://lextakip_user:SIFRE@localhost:5432/lextakip_db
SECRET_KEY=cok-gizli-bir-anahtar-en-az-32-karakter
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### 6.2 config.py (Yapılandırma)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 saat

    class Config:
        env_file = ".env"

settings = Settings()
```

**Açıklama**: Pydantic kullanarak ortam değişkenlerini tip güvenli şekilde yükler.

### 6.3 database.py (Veritabanı Bağlantısı)
```python
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
```

**Açıklama**: SQLAlchemy engine ve session yönetimi. FastAPI dependency injection ile kullanılır.

### 6.4 models.py (Veritabanı Modelleri)

```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.sql import func
from database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class BaseMixin:
    """Tüm tablolarda ortak alanlar"""
    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False, index=True)
    revision = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class User(Base):
    """Sunucu kimlik doğrulama kullanıcıları"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Dosya(BaseMixin, Base):
    """Hukuki dosyalar"""
    __tablename__ = "dosyalar"

    esas_no = Column(String(100))
    mahkeme = Column(String(255))
    dava_turu = Column(String(100))
    muvekkil_uuid = Column(String(36), ForeignKey('muvekkillers.uuid'))
    karsi_taraf_uuid = Column(String(36), ForeignKey('karsi_taraflar.uuid'))
    avukat_uuid = Column(String(36), ForeignKey('avukatlar.uuid'))
    # ... diğer alanlar

class Muvekkil(BaseMixin, Base):
    """Müvekkiller"""
    __tablename__ = "muvekkillers"

    ad = Column(String(100))
    soyad = Column(String(100))
    tc_kimlik = Column(String(11))
    telefon = Column(String(20))
    email = Column(String(255))
    adres = Column(Text)

class KarsiTaraf(BaseMixin, Base):
    """Karşı taraflar"""
    __tablename__ = "karsi_taraflar"

    ad = Column(String(100))
    soyad = Column(String(100))
    tc_kimlik = Column(String(11))
    # ... diğer alanlar

class Avukat(BaseMixin, Base):
    """Avukatlar"""
    __tablename__ = "avukatlar"

    ad = Column(String(100))
    soyad = Column(String(100))
    baro_sicil = Column(String(50))
    # ... diğer alanlar

class Durusma(BaseMixin, Base):
    """Duruşmalar"""
    __tablename__ = "durusmalar"

    dosya_uuid = Column(String(36), ForeignKey('dosyalar.uuid'))
    tarih = Column(DateTime)
    saat = Column(String(10))
    aciklama = Column(Text)
    sonuc = Column(Text)

class Belge(BaseMixin, Base):
    """Belgeler"""
    __tablename__ = "belgeler"

    dosya_uuid = Column(String(36), ForeignKey('dosyalar.uuid'))
    belge_adi = Column(String(255))
    belge_yolu = Column(Text)
    belge_turu = Column(String(100))

class Finans(BaseMixin, Base):
    """Finansal işlemler"""
    __tablename__ = "finans"

    dosya_uuid = Column(String(36), ForeignKey('dosyalar.uuid'))
    islem_turu = Column(String(50))  # gelir/gider
    tutar = Column(Float)
    aciklama = Column(Text)
    tarih = Column(DateTime)

class Bildirim(BaseMixin, Base):
    """Bildirimler"""
    __tablename__ = "bildirimler"

    baslik = Column(String(255))
    mesaj = Column(Text)
    tip = Column(String(50))
    okundu = Column(Boolean, default=False)
    ilgili_dosya_uuid = Column(String(36))

class DosyaKullanici(Base):
    """Dosya-Kullanıcı ilişkisi"""
    __tablename__ = "dosya_kullanici"

    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False)
    dosya_uuid = Column(String(36), ForeignKey('dosyalar.uuid'))
    kullanici_uuid = Column(String(36), ForeignKey('app_users.uuid'))
    revision = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)

class DosyaSekme(Base):
    """Dosya-Sekme ilişkisi"""
    __tablename__ = "dosya_sekme"

    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False)
    dosya_uuid = Column(String(36), ForeignKey('dosyalar.uuid'))
    sekme_uuid = Column(String(36), ForeignKey('sekmeler.uuid'))
    revision = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)

class Sekme(BaseMixin, Base):
    """Sekmeler (kategoriler)"""
    __tablename__ = "sekmeler"

    ad = Column(String(100))
    renk = Column(String(20))
    sira = Column(Integer)

class AppUser(BaseMixin, Base):
    """Uygulama kullanıcıları"""
    __tablename__ = "app_users"

    kullanici_adi = Column(String(100))
    email = Column(String(255))
    rol = Column(String(50))
```

**Açıklama**:
- `BaseMixin` sınıfı tüm tablolara ortak alanları ekler
- Her tablonun `firm_id` alanı multi-tenant yapıyı destekler
- Foreign key'ler `_uuid` suffix'i ile tanımlanır

### 6.5 schemas.py (Pydantic Şemaları)

```python
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# Kimlik doğrulama şemaları
class SetupRequest(BaseModel):
    firm_name: str
    admin_email: str
    admin_password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    firm_id: str
    user_id: str

# Senkronizasyon şemaları
class SyncChange(BaseModel):
    table_name: str
    operation: str  # insert, update, delete, upsert
    record_uuid: str
    data: dict

class SyncRequest(BaseModel):
    last_sync_revision: int = 0
    changes: List[SyncChange] = []

class SyncResponse(BaseModel):
    status: str
    current_revision: int
    changes_accepted: int
    server_changes: List[SyncChange]
```

**Açıklama**: API istek/cevap formatlarını tanımlar. Pydantic otomatik doğrulama sağlar.

### 6.6 auth.py (Kimlik Doğrulama)

```python
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from config import settings
from database import get_db
from models import User

security = HTTPBearer()

def hash_password(password: str) -> str:
    """Şifreyi bcrypt ile hashle"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifreyi doğrula"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT token oluştur"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """JWT token'dan kullanıcıyı al"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
```

**Önemli Not**: Python 3.13'te passlib/bcrypt uyumsuzluğu var. Bu yüzden passlib yerine doğrudan bcrypt kullanılıyor.

### 6.7 sync_handler.py (Senkronizasyon Mantığı)

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import List, Dict, Any
import models

# Tablo adı -> Model eşlemesi
TABLE_MODEL_MAP = {
    'dosyalar': models.Dosya,
    'muvekkillers': models.Muvekkil,
    'karsi_taraflar': models.KarsiTaraf,
    'avukatlar': models.Avukat,
    'durusmalar': models.Durusma,
    'belgeler': models.Belge,
    'finans': models.Finans,
    'bildirimler': models.Bildirim,
    'dosya_kullanici': models.DosyaKullanici,
    'dosya_sekme': models.DosyaSekme,
    'sekmeler': models.Sekme,
    'app_users': models.AppUser,
}

# Boolean alanları (SQLite'dan '0'/'1' string olarak gelebilir)
BOOLEAN_FIELDS = ['is_deleted', 'okundu', 'tamamlandi', 'is_active']

def convert_value(key: str, value: Any) -> Any:
    """Değeri uygun tipe dönüştür"""
    if key in BOOLEAN_FIELDS:
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)
    return value

def get_current_revision(db: Session, firm_id: str) -> int:
    """Firma için mevcut maksimum revizyonu al"""
    max_rev = 0
    for table_name, model in TABLE_MODEL_MAP.items():
        result = db.query(model).filter(
            model.firm_id == firm_id
        ).order_by(model.revision.desc()).first()
        if result and result.revision > max_rev:
            max_rev = result.revision
    return max_rev

def apply_client_changes(
    db: Session,
    firm_id: str,
    changes: List[Dict],
    current_revision: int
) -> int:
    """İstemciden gelen değişiklikleri uygula"""
    applied = 0
    new_revision = current_revision

    for change in changes:
        table_name = change['table_name']
        operation = change['operation']
        record_uuid = change['record_uuid']
        data = change['data']

        if table_name not in TABLE_MODEL_MAP:
            continue

        model = TABLE_MODEL_MAP[table_name]

        # Veriyi dönüştür
        converted_data = {k: convert_value(k, v) for k, v in data.items()}
        converted_data['firm_id'] = firm_id

        # Mevcut kaydı bul
        existing = db.query(model).filter(model.uuid == record_uuid).first()

        if operation in ('insert', 'upsert'):
            if existing:
                # Güncelle (Last-Write-Wins)
                incoming_updated = data.get('updated_at', '')
                existing_updated = str(existing.updated_at) if existing.updated_at else ''

                if incoming_updated >= existing_updated:
                    for key, value in converted_data.items():
                        if hasattr(existing, key) and key != 'uuid':
                            setattr(existing, key, value)
                    new_revision += 1
                    existing.revision = new_revision
                    applied += 1
            else:
                # Yeni kayıt ekle
                new_revision += 1
                converted_data['uuid'] = record_uuid
                converted_data['revision'] = new_revision
                new_record = model(**converted_data)
                db.add(new_record)
                applied += 1

        elif operation == 'update':
            if existing:
                incoming_updated = data.get('updated_at', '')
                existing_updated = str(existing.updated_at) if existing.updated_at else ''

                if incoming_updated >= existing_updated:
                    for key, value in converted_data.items():
                        if hasattr(existing, key) and key != 'uuid':
                            setattr(existing, key, value)
                    new_revision += 1
                    existing.revision = new_revision
                    applied += 1

        elif operation == 'delete':
            if existing:
                existing.is_deleted = True
                new_revision += 1
                existing.revision = new_revision
                applied += 1

    db.commit()
    return applied

def get_server_changes(
    db: Session,
    firm_id: str,
    since_revision: int
) -> List[Dict]:
    """Belirtilen revizyondan sonraki değişiklikleri al"""
    changes = []

    for table_name, model in TABLE_MODEL_MAP.items():
        records = db.query(model).filter(
            model.firm_id == firm_id,
            model.revision > since_revision
        ).all()

        for record in records:
            # Model'i dict'e çevir
            data = {}
            for column in model.__table__.columns:
                value = getattr(record, column.name)
                if value is not None:
                    if isinstance(value, datetime):
                        data[column.name] = value.isoformat()
                    else:
                        data[column.name] = value

            changes.append({
                'table_name': table_name,
                'operation': 'upsert',
                'record_uuid': record.uuid,
                'data': data
            })

    return changes
```

**Açıklama**:
- `convert_value()`: SQLite'dan gelen string boolean'ları ('0', '1') PostgreSQL boolean'a çevirir
- `apply_client_changes()`: İstemci değişikliklerini sunucuya uygular, LWW stratejisi kullanır
- `get_server_changes()`: Belirli revizyondan sonraki tüm değişiklikleri döner

### 6.8 main.py (FastAPI Uygulaması)

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from config import settings
from database import engine, get_db, Base
from models import User
from schemas import SetupRequest, LoginRequest, TokenResponse, SyncRequest, SyncResponse
from auth import hash_password, verify_password, create_access_token, get_current_user
from sync_handler import apply_client_changes, get_server_changes, get_current_revision

# Tabloları oluştur
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LexTakip Sync Server",
    description="LexTakip masaüstü uygulaması için senkronizasyon sunucusu",
    version="1.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    """Sunucu sağlık kontrolü"""
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/setup")
async def setup(request: SetupRequest, db: Session = Depends(get_db)):
    """İlk kurulum - firma ve admin oluştur"""
    # Zaten kullanıcı var mı kontrol et
    existing = db.query(User).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kurulum zaten yapılmış"
        )

    # Firma ID oluştur
    firm_id = str(uuid.uuid4())

    # Admin kullanıcısı oluştur
    user = User(
        id=str(uuid.uuid4()),
        firm_id=firm_id,
        email=request.admin_email,
        hashed_password=hash_password(request.admin_password),
        is_active=True
    )
    db.add(user)
    db.commit()

    return {
        "message": "Firma ve admin kullanıcısı oluşturuldu",
        "firm_id": firm_id,
        "user_id": user.id
    }

@app.post("/api/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Kullanıcı girişi"""
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz e-posta veya şifre"
        )

    access_token = create_access_token(
        data={"sub": user.id, "firm_id": user.firm_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        firm_id=user.firm_id,
        user_id=user.id
    )

@app.post("/api/sync", response_model=SyncResponse)
async def sync(
    request: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Senkronizasyon endpoint'i"""
    firm_id = current_user.firm_id

    # Mevcut revizyonu al
    current_revision = get_current_revision(db, firm_id)

    # İstemci değişikliklerini uygula
    changes_accepted = 0
    if request.changes:
        changes_accepted = apply_client_changes(
            db, firm_id,
            [c.dict() for c in request.changes],
            current_revision
        )
        # Yeni revizyonu al
        current_revision = get_current_revision(db, firm_id)

    # Sunucu değişikliklerini al
    server_changes = get_server_changes(db, firm_id, request.last_sync_revision)

    return SyncResponse(
        status="success",
        current_revision=current_revision,
        changes_accepted=changes_accepted,
        server_changes=[
            SyncChange(**c) for c in server_changes
        ]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 7. İstemci Tarafı Entegrasyonu

### 7.1 Gerekli Modüller

İstemci tarafında şu modüller gereklidir:

```
app/sync/
├── __init__.py       # Modül başlatma
├── config.py         # Sunucu yapılandırması
├── client.py         # HTTP istemcisi
├── outbox.py         # Yerel değişiklik kuyruğu
├── merger.py         # Sunucu değişikliklerini uygulama
└── db_wrapper.py     # Veritabanı yardımcıları
```

### 7.2 Sync Outbox Tablosu

İstemci veritabanına eklenmesi gereken tablo:

```sql
CREATE TABLE IF NOT EXISTS sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    record_uuid TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    synced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### 7.3 Değişiklik Takibi

Her CRUD işleminde sync_outbox'a kayıt eklenmeli:

```python
def add_dosya(conn, dosya_data):
    # UUID oluştur
    dosya_uuid = str(uuid.uuid4())
    dosya_data['uuid'] = dosya_uuid

    # Normal ekleme işlemi
    cur = conn.cursor()
    cur.execute("INSERT INTO dosyalar (...) VALUES (...)", ...)

    # Sync outbox'a kaydet
    cur.execute("""
        INSERT INTO sync_outbox (table_name, operation, record_uuid, data, created_at, synced)
        VALUES (?, ?, ?, ?, ?, 0)
    """, ('dosyalar', 'insert', dosya_uuid, json.dumps(dosya_data), datetime.now().isoformat()))

    conn.commit()
```

### 7.4 Senkronizasyon İstemcisi

```python
import requests
from typing import Optional, Dict, List

class SyncClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self.token: Optional[str] = None
        self.firm_id: Optional[str] = None

    def login(self, email: str, password: str) -> bool:
        """Sunucuya giriş yap"""
        response = requests.post(
            f"{self.server_url}/api/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data['access_token']
            self.firm_id = data['firm_id']
            return True
        return False

    def sync(self, last_revision: int, changes: List[Dict]) -> Dict:
        """Senkronizasyon yap"""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(
            f"{self.server_url}/api/sync",
            headers=headers,
            json={
                "last_sync_revision": last_revision,
                "changes": changes
            }
        )
        return response.json()
```

---

## 8. Kurulum Adımları Özeti

### 8.1 Sunucu Kurulumu

1. **PostgreSQL Kurulumu**
```bash
sudo apt update && sudo apt install postgresql postgresql-contrib
sudo -u postgres createuser -P lextakip_user
sudo -u postgres createdb -O lextakip_user lextakip_db
```

2. **Python Ortamı**
```bash
mkdir ~/lextakip-server && cd ~/lextakip-server
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose bcrypt pydantic-settings
```

3. **Dosyaları Oluştur** (6. bölümdeki tüm dosyalar)

4. **Systemd Servisi**
```bash
sudo nano /etc/systemd/system/lextakip-server.service
```

```ini
[Unit]
Description=LexTakip Sync Server
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/lextakip-server
Environment=PATH=/home/pi/lextakip-server/venv/bin
ExecStart=/home/pi/lextakip-server/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable lextakip-server
sudo systemctl start lextakip-server
```

### 8.2 İstemci Entegrasyonu

1. `app/sync/` klasörünü oluştur
2. Sync tablolarını veritabanına ekle
3. CRUD fonksiyonlarına sync tracking ekle
4. UI'da sync butonları ve ayarlar ekle

---

## 9. Sorun Giderme

### 9.1 Yaygın Hatalar

| Hata | Sebep | Çözüm |
|------|-------|-------|
| `bcrypt.__about__` | Python 3.13 uyumsuzluğu | passlib yerine bcrypt kullan |
| `Not a boolean value: '0'` | SQLite string boolean | convert_value() fonksiyonu |
| `invalid keyword argument 'dosya_id'` | FK eşleştirme hatası | dosya_id → dosya_uuid dönüşümü |
| `422 Unprocessable Entity` | Şema doğrulama hatası | İstek formatını kontrol et |
| `401 Unauthorized` | Token süresi dolmuş | Yeniden login ol |

### 9.2 Log Kontrolü
```bash
# Sunucu logları
sudo journalctl -u lextakip-server -f

# PostgreSQL logları
sudo tail -f /var/log/postgresql/postgresql-*-main.log
```

### 9.3 Manuel Test
```bash
# Health check
curl http://sunucu-ip:8000/api/health

# Login test
curl -X POST http://sunucu-ip:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@firma.com","password":"sifre"}'
```

---

## 10. Güvenlik Notları

1. **SECRET_KEY**: En az 32 karakter, rastgele oluşturulmuş
2. **HTTPS**: Production'da mutlaka SSL/TLS kullanın
3. **Firewall**: Sadece gerekli portları açın (8000)
4. **Şifre Politikası**: Güçlü şifre zorunluluğu
5. **Token Süresi**: İhtiyaca göre ayarlayın (varsayılan 24 saat)

---

## 11. Performans Önerileri

1. **İndeksler**: firm_id ve revision alanlarına indeks
2. **Batch Sync**: Çok sayıda değişikliği grupla
3. **Sıkıştırma**: Büyük veri transferlerinde gzip
4. **Connection Pool**: SQLAlchemy pool ayarları
5. **Async**: Yoğun trafikte async endpoint'ler

---

**Rapor Tarihi**: 2024-01-15
**Versiyon**: 1.0.0
**Hazırlayan**: LexTakip Geliştirme Ekibi
