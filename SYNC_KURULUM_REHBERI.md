# LexTakip Online Senkronizasyon Kurulum Rehberi

Bu rehber, LexTakip uygulamasına çoklu kullanıcı senkronizasyon özelliği eklemek için gerekli tüm adımları içerir.

---

## 1. MİMARİ ÖZET

```
┌─────────────────┐         ┌─────────────────┐
│  Bilgisayar A   │         │  Bilgisayar B   │
│  (SQLite)       │         │  (SQLite)       │
│  + sync_outbox  │         │  + sync_outbox  │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │      HTTP/JSON API        │
         └───────────┬───────────────┘
                     │
              ┌──────┴──────┐
              │ Raspberry Pi │
              │ (PostgreSQL) │
              │ FastAPI      │
              └──────────────┘
```

**Temel Prensipler:**
- **Offline-first:** Uygulama internetsiz tamamen çalışır
- **UUID-tabanlı:** Her kayıt benzersiz UUID ile tanımlanır
- **Outbox pattern:** Değişiklikler önce lokale, sonra sunucuya
- **Last-write-wins:** Çakışmalarda son yazan kazanır
- **Revision numaraları:** Artımlı senkronizasyon için

---

## 2. RASPBERRY PI SUNUCU KURULUMU

### 2.1 Sistem Hazırlığı

```bash
# Sistemi güncelle
sudo apt update && sudo apt upgrade -y

# PostgreSQL kur
sudo apt install -y postgresql postgresql-contrib

# Python araçları
sudo apt install -y python3-pip python3-venv
```

### 2.2 PostgreSQL Veritabanı

```bash
sudo -u postgres psql
```

```sql
CREATE USER lextakip WITH PASSWORD 'LexTakip2024!';
CREATE DATABASE lextakip_db OWNER lextakip;
GRANT ALL PRIVILEGES ON DATABASE lextakip_db TO lextakip;
\q
```

### 2.3 Sunucu Klasörü

```bash
mkdir -p ~/lextakip-server
cd ~/lextakip-server
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary python-jose[cryptography] bcrypt python-multipart pydantic pydantic-settings
```

### 2.4 Sunucu Dosyaları

#### .env
```bash
cat > ~/lextakip-server/.env << 'EOF'
DATABASE_URL=postgresql://lextakip:LexTakip2024!@localhost/lextakip_db
SECRET_KEY=lextakip-gizli-anahtar-2024-cok-guvenli-32kar
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF
```

#### config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://lextakip:LexTakip2024!@localhost/lextakip_db"
    SECRET_KEY: str = "lextakip-gizli-anahtar-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"

settings = Settings()
```

#### database.py
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

#### models.py
```python
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class BaseMixin:
    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    firm_id = Column(String(36), nullable=False, index=True)
    revision = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Firm(Base):
    __tablename__ = "firms"
    uuid = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class User(Base, BaseMixin):
    __tablename__ = "users"
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    active = Column(Boolean, default=True)

class Dosya(Base, BaseMixin):
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
    __tablename__ = "taksitler"
    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    vade_tarihi = Column(String(50))
    tutar_cents = Column(Integer, default=0)
    durum = Column(String(50))
    odeme_tarihi = Column(String(50))
    aciklama = Column(Text)

class OdemeKaydi(Base, BaseMixin):
    __tablename__ = "odeme_kayitlari"
    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    tarih = Column(String(50))
    tutar_cents = Column(Integer, default=0)
    yontem = Column(String(100))
    aciklama = Column(Text)
    taksit_uuid = Column(String(36))

class Masraf(Base, BaseMixin):
    __tablename__ = "masraflar"
    finans_uuid = Column(String(36), ForeignKey("finans.uuid"))
    kalem = Column(String(255))
    tutar_cents = Column(Integer, default=0)
    tarih = Column(String(50))
    tahsil_durumu = Column(String(50))
    tahsil_tarihi = Column(String(50))
    aciklama = Column(Text)

class MuvekkilKasasi(Base, BaseMixin):
    __tablename__ = "muvekkil_kasasi"
    dosya_uuid = Column(String(36), ForeignKey("dosyalar.uuid"))
    tarih = Column(String(50))
    tutar_kurus = Column(Integer, default=0)
    islem_turu = Column(String(100))
    aciklama = Column(Text)

class Tebligat(Base, BaseMixin):
    __tablename__ = "tebligatlar"
    dosya_no = Column(String(100))
    kurum = Column(String(255))
    geldigi_tarih = Column(String(50))
    teblig_tarihi = Column(String(50))
    is_son_gunu = Column(String(50))
    icerik = Column(Text)

class Arabuluculuk(Base, BaseMixin):
    __tablename__ = "arabuluculuk"
    davaci = Column(String(255))
    davali = Column(String(255))
    arb_adi = Column(String(255))
    arb_tel = Column(String(50))
    toplanti_tarihi = Column(String(50))
    toplanti_saati = Column(String(50))
    konu = Column(Text)

class Gorev(Base, BaseMixin):
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
    __tablename__ = "global_revisions"
    firm_id = Column(String(36), primary_key=True)
    current_revision = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Senkronize edilecek tüm tablolar
SYNCABLE_TABLES = {
    'dosyalar': Dosya, 'finans': Finans, 'taksitler': Taksit,
    'odeme_kayitlari': OdemeKaydi, 'masraflar': Masraf, 'muvekkil_kasasi': MuvekkilKasasi,
    'tebligatlar': Tebligat, 'arabuluculuk': Arabuluculuk, 'gorevler': Gorev, 'users': User
}
```

#### schemas.py
```python
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user_uuid: Optional[str] = None
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None
    role: Optional[str] = None

class SyncRequest(BaseModel):
    device_id: str
    last_sync_revision: int = 0
    changes: List[Dict[str, Any]] = []

class SyncResponse(BaseModel):
    success: bool
    message: str
    new_revision: int = 0
    changes: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

class SetupRequest(BaseModel):
    firm_name: str
    admin_username: str
    admin_password: str

class SetupResponse(BaseModel):
    success: bool
    message: str
    firm_id: Optional[str] = None
```

#### auth.py
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from config import settings
from database import get_db
from models import User

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
    if not user_uuid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")
    user = db.query(User).filter(User.uuid == user_uuid, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")
    return user
```

#### sync_handler.py
```python
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Tuple
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
    rev = db.query(GlobalRevision).filter(GlobalRevision.firm_id == firm_id).first()
    if not rev:
        rev = GlobalRevision(firm_id=firm_id, current_revision=0)
        db.add(rev)
    rev.current_revision += 1
    db.flush()
    return rev.current_revision

def process_incoming_changes(db: Session, firm_id: str, changes: List[Dict]) -> Tuple[int, List[Dict]]:
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

            if op == 'insert':
                existing = db.query(Model).filter(Model.uuid == record_uuid).first()
                if existing:
                    for key, value in converted_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.revision = new_rev
                else:
                    record = Model(uuid=record_uuid, firm_id=firm_id, revision=new_rev, **converted_data)
                    db.add(record)

            elif op == 'update':
                record = db.query(Model).filter(Model.uuid == record_uuid, Model.firm_id == firm_id).first()
                if record:
                    for key, value in converted_data.items():
                        if hasattr(record, key):
                            setattr(record, key, value)
                    record.revision = new_rev
                else:
                    record = Model(uuid=record_uuid, firm_id=firm_id, revision=new_rev, **converted_data)
                    db.add(record)

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
            db.rollback()

    return processed, errors

def get_outgoing_changes(db: Session, firm_id: str, since_revision: int) -> List[Dict]:
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
                    if isinstance(value, bool):
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
    processed, errors = process_incoming_changes(db, firm_id, incoming)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {'success': False, 'message': f'Commit hatası: {str(e)}', 'new_revision': since_revision, 'changes': [], 'errors': errors}
    outgoing = get_outgoing_changes(db, firm_id, since_revision)
    rev = db.query(GlobalRevision).filter(GlobalRevision.firm_id == firm_id).first()
    current_rev = rev.current_revision if rev else 0
    return {'success': True, 'message': f'{processed} değişiklik işlendi', 'new_revision': current_rev, 'changes': outgoing, 'errors': errors}
```

#### main.py
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import engine, get_db, Base
from models import User, Firm, GlobalRevision
from schemas import LoginRequest, LoginResponse, SyncRequest, SyncResponse, SetupRequest, SetupResponse
from auth import verify_password, get_password_hash, create_access_token, get_current_user
from sync_handler import perform_sync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LexTakip Sync Server", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/public/token")
def public_token():
    return {"status": "ok", "message": "Sunucu bağlantısı başarılı"}

@app.post("/api/setup", response_model=SetupResponse)
def initial_setup(request: SetupRequest, db: Session = Depends(get_db)):
    if db.query(Firm).first():
        raise HTTPException(status_code=400, detail="Sistem zaten kurulmuş")
    firm = Firm(name=request.firm_name)
    db.add(firm)
    db.flush()
    admin = User(firm_id=firm.uuid, username=request.admin_username, password_hash=get_password_hash(request.admin_password), role="admin", active=True)
    db.add(admin)
    db.add(GlobalRevision(firm_id=firm.uuid, current_revision=0))
    db.commit()
    return SetupResponse(success=True, message="Kurulum tamamlandı", firm_id=firm.uuid)

@app.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username, User.is_deleted == False, User.active == True).first()
    if not user or not verify_password(request.password, user.password_hash):
        return LoginResponse(success=False, message="Kullanıcı adı veya şifre hatalı")
    firm = db.query(Firm).filter(Firm.uuid == user.firm_id).first()
    token = create_access_token(data={"sub": user.uuid, "firm_id": user.firm_id})
    return LoginResponse(success=True, message="Giriş başarılı", token=token, user_uuid=user.uuid, firm_id=user.firm_id, firm_name=firm.name if firm else "", role=user.role)

@app.post("/api/sync", response_model=SyncResponse)
def sync(request: SyncRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = perform_sync(db=db, firm_id=user.firm_id, incoming=request.changes, since_revision=request.last_sync_revision)
        return SyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2.5 Systemd Servisi

```bash
sudo tee /etc/systemd/system/lextakip.service << 'EOF'
[Unit]
Description=LexTakip Sync Server
After=network.target postgresql.service

[Service]
User=lextakip
WorkingDirectory=/home/lextakip/lextakip-server
Environment="PATH=/home/lextakip/lextakip-server/venv/bin"
ExecStart=/home/lextakip/lextakip-server/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable lextakip
sudo systemctl start lextakip
```

### 2.6 İlk Kurulum Testi

```bash
# Sunucu sağlık kontrolü
curl http://localhost:8000/api/health

# İlk kurulum (büro ve admin oluştur)
curl -X POST http://localhost:8000/api/setup \
  -H "Content-Type: application/json" \
  -d '{"firm_name":"Hukuk Bürosu","admin_username":"admin","admin_password":"Admin123!"}'
```

---

## 3. İSTEMCİ (MASAÜSTÜ) DEĞİŞİKLİKLERİ

### 3.1 Klasör Yapısı

```
app/
├── sync/
│   ├── __init__.py
│   ├── config.py      # Sync yapılandırması
│   ├── client.py      # HTTP istemcisi
│   ├── outbox.py      # Değişiklik takibi
│   ├── merger.py      # Gelen veri birleştirici
│   └── db_wrapper.py  # Sync-tracked DB işlemleri
├── ui_sync_dialog.py  # Sync ayarları UI
└── ... (mevcut dosyalar)
```

### 3.2 db.py'ye Eklenmesi Gereken Tablolar

`initialize_database()` fonksiyonuna ekle:

```python
# Sync outbox tablosu
cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        operation TEXT NOT NULL,
        record_uuid TEXT NOT NULL,
        data TEXT,
        created_at TEXT NOT NULL,
        synced INTEGER NOT NULL DEFAULT 0,
        synced_at TEXT
    )
""")
```

### 3.3 Tüm Tablolara UUID Kolonu Ekleme

`initialize_database()` içinde çağrılacak fonksiyon:

```python
def _ensure_uuid_columns(cur: sqlite3.Cursor) -> None:
    """Tüm senkronize edilecek tablolara UUID kolonları ekle."""
    import uuid

    TABLES = [
        'dosyalar', 'finans', 'taksitler', 'odeme_kayitlari', 'masraflar',
        'muvekkil_kasasi', 'tebligatlar', 'arabuluculuk', 'gorevler'
    ]

    for table_name in TABLES:
        try:
            # Kolon var mı kontrol et
            cur.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cur.fetchall()]

            if 'uuid' not in columns:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN uuid TEXT")

            # Mevcut kayıtlara UUID ata
            cur.execute(f"SELECT id FROM {table_name} WHERE uuid IS NULL OR uuid = ''")
            for row in cur.fetchall():
                new_uuid = str(uuid.uuid4())
                cur.execute(f"UPDATE {table_name} SET uuid = ? WHERE id = ?", (new_uuid, row[0]))
        except Exception as e:
            print(f"UUID ekleme hatası ({table_name}): {e}")
```

### 3.4 models.py Değişiklikleri

Dosyanın başına ekle:

```python
import uuid

def _generate_uuid() -> str:
    return str(uuid.uuid4())

def _record_sync_change(conn, table_name: str, operation: str, record_uuid: str, data: dict) -> None:
    """Değişikliği sync_outbox'a kaydet."""
    import json
    from datetime import datetime
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sync_outbox (table_name, operation, record_uuid, data, created_at, synced)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (table_name, operation, record_uuid, json.dumps(data, ensure_ascii=False, default=str), datetime.now().isoformat()))
    except Exception as e:
        print(f"Sync outbox kaydı oluşturulamadı: {e}")
```

**add_dosya fonksiyonunu güncelle:**

```python
def add_dosya(data: Dict[str, Any]) -> int:
    # ... mevcut tarih kontrolleri ...

    # UUID oluştur
    dosya_uuid = _generate_uuid()
    data["uuid"] = dosya_uuid

    conn = get_connection()
    try:
        cur = conn.cursor()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = list(data.values())
        cur.execute(f"INSERT INTO dosyalar ({columns}) VALUES ({placeholders})", values)
        dosya_id = cur.lastrowid

        # Finans kaydı için de UUID
        finans_uuid = _generate_uuid()
        cur.execute("INSERT OR IGNORE INTO finans (dosya_id, uuid) VALUES (?, ?)", (dosya_id, finans_uuid))

        # Sync outbox'a kaydet
        sync_data = {k: v for k, v in data.items() if k != 'uuid'}
        _record_sync_change(conn, 'dosyalar', 'insert', dosya_uuid, sync_data)

        conn.commit()
        return dosya_id
    except sqlite3.Error as exc:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**update_dosya fonksiyonunu güncelle:**

```python
def update_dosya(dosya_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    # ... mevcut tarih kontrolleri ...

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Mevcut UUID'yi al
        cur.execute("SELECT uuid FROM dosyalar WHERE id = ?", (dosya_id,))
        row = cur.fetchone()
        dosya_uuid = row[0] if row and row[0] else _generate_uuid()

        if not row or not row[0]:
            data["uuid"] = dosya_uuid

        columns = ", ".join(f"{key} = ?" for key in data.keys())
        values = list(data.values()) + [dosya_id]
        cur.execute(f"UPDATE dosyalar SET {columns} WHERE id = ?", values)

        # Sync outbox'a kaydet
        sync_data = {k: v for k, v in data.items() if k != 'uuid'}
        _record_sync_change(conn, 'dosyalar', 'update', dosya_uuid, sync_data)

        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### 3.5 Sync Modülü Dosyaları

Bu dosyaları `app/sync/` klasörüne koy - mevcut repodaki dosyaları kopyalayabilirsin:
- `__init__.py`
- `config.py`
- `client.py`
- `outbox.py`
- `merger.py`
- `db_wrapper.py`

### 3.6 UI Entegrasyonu

**ui_main.py'ye ekle:**

1. Import ekle:
```python
try:
    from app.ui_sync_dialog import SyncDialog
    from app.sync.config import get_sync_config
    from app.sync.client import perform_full_sync
except:
    from ui_sync_dialog import SyncDialog
    from sync.config import get_sync_config
    from sync.client import perform_full_sync
```

2. `_setup_main_ui` metodunun sonunda çağır:
```python
self._setup_sync_ui()
```

3. Sync UI metodlarını ekle (mevcut repodaki `ui_main.py` satır 4951-5056 arası)

---

## 4. İLK SENKRONİZASYON

Mevcut verileri sunucuya aktarmak için `initial_sync.py` scriptini kullan (repoda mevcut).

```bash
python initial_sync.py
```

---

## 5. ÖNEMLİ NOKTALAR

1. **Sunucu IP'si:** Raspberry Pi'nin IP adresini sync ayarlarına gir
2. **Port:** Varsayılan 8000
3. **Foreign Key Dönüşümü:** `dosya_id` → `dosya_uuid`, `finans_id` → `finans_uuid`
4. **Upsert Desteği:** Merger'da `upsert` operasyonunu desteklemeyi unutma
5. **Boolean Dönüşümü:** PostgreSQL boolean bekler, string '0'/'1' değil

---

## 6. TEST ADIMLARI

1. Sunucu sağlık kontrolü: `http://PI_IP:8000/api/health`
2. İlk kurulum: `/api/setup` endpoint
3. Giriş testi: `/api/login` endpoint
4. İlk sync: `initial_sync.py` çalıştır
5. Uygulama içi sync: "Senkronize Et" butonu
6. İki bilgisayar testi: Birinde ekle, diğerinde sync yap

---

## 7. SORUN GİDERME

**Sunucu logları:**
```bash
sudo journalctl -u lextakip -f
```

**Outbox kontrolü:**
```python
import sqlite3
c = sqlite3.connect('data.db')
print(c.execute('SELECT * FROM sync_outbox ORDER BY id DESC LIMIT 5').fetchall())
```

**Revision sıfırlama:**
```python
import json
with open('sync_config.json', 'r') as f:
    d = json.load(f)
d['last_sync_revision'] = 0
with open('sync_config.json', 'w') as f:
    json.dump(d, f)
```
