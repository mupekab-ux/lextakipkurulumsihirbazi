# BÜRO SENKRONİZASYON - DETAYLI İMPLEMENTASYON PLANI

## 1. GENEL MİMARİ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BÜRO SENKRONİZASYON MİMARİSİ                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                   │
│    │ Bilgisayar A │   │ Bilgisayar B │   │ Bilgisayar C │                   │
│    │              │   │              │   │              │                   │
│    │  TakibiEsasi │   │  TakibiEsasi │   │  TakibiEsasi │                   │
│    │   Desktop    │   │   Desktop    │   │   Desktop    │                   │
│    │              │   │              │   │              │                   │
│    │ SQLite+Fernet│   │ SQLite+Fernet│   │ SQLite+Fernet│                   │
│    │ (Lokal DB)   │   │ (Lokal DB)   │   │ (Lokal DB)   │                   │
│    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                   │
│           │                  │                  │                            │
│           │   HTTPS + JWT    │                  │                            │
│           │   (Yerel Ağ)     │                  │                            │
│           └──────────────────┼──────────────────┘                            │
│                              │                                               │
│                              ▼                                               │
│                    ┌─────────────────────┐                                   │
│                    │    Raspberry Pi     │                                   │
│                    │    192.168.1.126    │                                   │
│                    │                     │                                   │
│                    │  ┌───────────────┐  │                                   │
│                    │  │   FastAPI     │  │                                   │
│                    │  │  Sync Server  │  │                                   │
│                    │  └───────┬───────┘  │                                   │
│                    │          │          │                                   │
│                    │  ┌───────▼───────┐  │                                   │
│                    │  │  PostgreSQL   │  │                                   │
│                    │  │  (Ana DB)     │  │                                   │
│                    │  └───────────────┘  │                                   │
│                    │                     │                                   │
│                    └─────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. GÜVENLİK KATMANLARI

### 2.1 Firma Kimliği (firm_id)
```python
# Her büro kurulumunda benzersiz üretilir
firm_id = str(uuid.uuid4())  # Örnek: "f47ac10b-58cc-4372-a567-0e02b2c3d479"

# Bu değer:
# - Sunucuda: firms tablosunda saklanır
# - İstemcide: sync_metadata tablosunda saklanır
# - Her API isteğinde header olarak gönderilir
# - Yanlış büronun ağına bağlanmayı önler
```

### 2.2 Cihaz Kimliği (device_id)
```python
# Her cihaz için benzersiz
device_id = f"{platform.node()}-{uuid.uuid4().hex[:8]}"
# Örnek: "LAPTOP-MEHMET-a1b2c3d4"

# Bu değer:
# - Sunucuda: devices tablosunda whitelist olarak saklanır
# - Admin onayı olmadan cihaz sync yapamaz
# - Cihaz deaktif edilebilir
```

### 2.3 Firma Anahtarı (firm_key)
```python
# 256-bit AES anahtarı - büro kurulumunda üretilir
from cryptography.fernet import Fernet
firm_key = Fernet.generate_key()  # Örnek: b'gAAAAABh...'

# Bu anahtar:
# - Sunucuda: master_password ile şifreli saklanır
# - İstemcilere: ilk katılımda güvenli şekilde iletilir
# - Transfer sırasında: veri bu anahtarla şifrelenir
# - Kurtarma kodu: BIP-39 24 kelime formatında
```

### 2.4 JWT Token
```python
# Kullanıcı girişinde üretilir
token = jwt.encode({
    "user_id": user_id,
    "firm_id": firm_id,
    "device_id": device_id,
    "role": "avukat",
    "exp": datetime.utcnow() + timedelta(hours=1)
}, JWT_SECRET)

# Refresh token: 7 gün geçerli
```

---

## 3. VERİTABANI ŞEMASI

### 3.1 Sunucu (Raspberry Pi - PostgreSQL)

```sql
-- ============================================================
-- BÜRO YÖNETİMİ
-- ============================================================

-- Büro/Firma tablosu
CREATE TABLE firms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Şifreleme
    firm_key_encrypted BYTEA NOT NULL,  -- Master password ile şifreli
    recovery_code_hash VARCHAR(255),     -- Kurtarma kodu hash'i

    -- Ayarlar
    settings JSONB DEFAULT '{}',

    -- Durum
    is_active BOOLEAN DEFAULT TRUE,
    subscription_type VARCHAR(50) DEFAULT 'trial',  -- trial, basic, pro
    subscription_expires_at TIMESTAMP
);

-- Cihazlar tablosu
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,
    device_id VARCHAR(255) NOT NULL,
    device_name VARCHAR(255),
    device_info JSONB,  -- OS, platform, etc.

    -- Durum
    is_active BOOLEAN DEFAULT TRUE,
    is_approved BOOLEAN DEFAULT FALSE,  -- Admin onayı gerekli

    -- Senkronizasyon
    last_sync_at TIMESTAMP,
    last_sync_revision BIGINT DEFAULT 0,

    -- Zaman
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    deactivated_at TIMESTAMP,

    UNIQUE(firm_id, device_id)
);

-- Kullanıcılar tablosu (büro içi)
CREATE TABLE firm_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,

    -- Kimlik
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),

    -- Rol
    role VARCHAR(50) NOT NULL DEFAULT 'avukat',
    -- 'kurucu_avukat', 'avukat', 'stajyer', 'sekreter'

    -- Durum
    is_active BOOLEAN DEFAULT TRUE,

    -- Zaman
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    deactivated_at TIMESTAMP,

    UNIQUE(firm_id, username)
);

-- Kullanıcı-Cihaz ilişkisi
CREATE TABLE user_devices (
    user_id UUID REFERENCES firm_users(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_id)
);

-- Katılım kodları
CREATE TABLE join_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL UNIQUE,  -- BURO-XXXX-XXXX-XXXX

    -- Kısıtlamalar
    max_uses INTEGER DEFAULT 10,
    used_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,

    -- Kim oluşturdu
    created_by UUID REFERENCES firm_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- SENKRONİZASYON
-- ============================================================

-- Global revizyon sayacı
CREATE SEQUENCE sync_revision_seq;

-- Senkronize edilen veriler
CREATE TABLE sync_data (
    id UUID PRIMARY KEY,
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,

    -- Kaynak bilgisi
    table_name VARCHAR(100) NOT NULL,

    -- Veri (şifreli)
    data_encrypted BYTEA NOT NULL,

    -- Revizyon
    revision BIGINT NOT NULL DEFAULT nextval('sync_revision_seq'),

    -- Operasyon
    operation VARCHAR(10) NOT NULL,  -- INSERT, UPDATE, DELETE

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,

    -- Zaman
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_by_device UUID REFERENCES devices(id),

    -- İndeksler
    INDEX idx_sync_firm_revision (firm_id, revision),
    INDEX idx_sync_table (firm_id, table_name)
);

-- Çakışma logları
CREATE TABLE sync_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,
    record_uuid UUID NOT NULL,
    table_name VARCHAR(100) NOT NULL,

    -- Çakışan veriler
    local_data BYTEA,
    remote_data BYTEA,
    winning_data BYTEA,

    -- Çözüm
    resolution VARCHAR(50) NOT NULL,  -- 'last_write_wins', 'manual', 'merged'
    resolved_by UUID REFERENCES firm_users(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- VERİ TABLOLARI (Senkronize)
-- ============================================================

-- Not: Aşağıdaki tablolar sync_data içinde şifreli saklanır
-- Bu şema sadece referans içindir

-- dosyalar, finans, taksitler, odeme_kayitlari, masraflar,
-- muvekkil_kasasi, tebligatlar, arabuluculuk, gorevler, users
-- attachments (metadata), custom_tabs

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,
    user_id UUID REFERENCES firm_users(id),
    device_id UUID REFERENCES devices(id),

    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id UUID,

    details JSONB,
    ip_address VARCHAR(45),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 İstemci (SQLite - Eklentiler)

```sql
-- ============================================================
-- YENİ KOLONLAR (Mevcut tablolara eklenecek)
-- ============================================================

-- Tüm senkronize tablolara eklenecek kolonlar:
-- uuid VARCHAR(36)          -- Benzersiz global kimlik
-- firm_id VARCHAR(36)       -- Hangi büroya ait
-- revision INTEGER          -- Versiyon numarası
-- is_deleted INTEGER        -- Soft delete flag
-- synced_at DATETIME        -- Son senkronizasyon zamanı
-- created_by VARCHAR(36)    -- Kim oluşturdu (user uuid)
-- updated_by VARCHAR(36)    -- Kim güncelledi
-- created_at DATETIME       -- Oluşturulma zamanı
-- updated_at DATETIME       -- Güncellenme zamanı

-- ============================================================
-- YENİ TABLOLAR
-- ============================================================

-- Senkronizasyon metadata
CREATE TABLE sync_metadata (
    id INTEGER PRIMARY KEY,
    device_id VARCHAR(36) NOT NULL,
    firm_id VARCHAR(36),
    firm_key_encrypted BLOB,      -- Cihaz anahtarıyla şifreli

    last_sync_revision INTEGER DEFAULT 0,
    last_sync_at DATETIME,

    server_url TEXT,
    is_sync_enabled INTEGER DEFAULT 0
);

-- Bekleyen değişiklikler (Outbox Pattern)
CREATE TABLE sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,        -- INSERT, UPDATE, DELETE
    data_json TEXT NOT NULL,        -- Şifrelenmemiş JSON

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    last_retry_at DATETIME,

    synced INTEGER DEFAULT 0,
    synced_at DATETIME,
    error_message TEXT
);

-- Bekleyen indirilecekler (Inbox)
CREATE TABLE sync_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    data_json TEXT NOT NULL,
    revision INTEGER NOT NULL,

    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0,
    processed_at DATETIME
);

-- İndeksler
CREATE INDEX idx_outbox_pending ON sync_outbox(synced, created_at);
CREATE INDEX idx_inbox_pending ON sync_inbox(processed, revision);
```

---

## 4. RASPBERRY PI KURULUMU

### 4.1 Gereksinimler
```bash
# Raspberry Pi 4 (4GB RAM önerilen)
# Raspberry Pi OS (64-bit)
# SD Kart: 32GB+ (veya harici SSD)
```

### 4.2 Temel Kurulum Script'i
```bash
#!/bin/bash
# raspberry_setup.sh

set -e

echo "=== TakibiEsasi Sync Server Kurulumu ==="

# 1. Sistem Güncellemesi
echo "[1/8] Sistem güncelleniyor..."
sudo apt update && sudo apt upgrade -y

# 2. PostgreSQL Kurulumu
echo "[2/8] PostgreSQL kuruluyor..."
sudo apt install postgresql postgresql-contrib -y
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 3. Python & Dependencies
echo "[3/8] Python bağımlılıkları kuruluyor..."
sudo apt install python3-pip python3-venv -y

# 4. Proje Dizini
echo "[4/8] Proje dizini oluşturuluyor..."
sudo mkdir -p /opt/takibiesasi-sync
sudo chown $USER:$USER /opt/takibiesasi-sync
cd /opt/takibiesasi-sync

# 5. Virtual Environment
echo "[5/8] Python ortamı hazırlanıyor..."
python3 -m venv venv
source venv/bin/activate

# 6. Python Paketleri
echo "[6/8] Python paketleri yükleniyor..."
pip install fastapi uvicorn psycopg2-binary pyjwt bcrypt cryptography python-multipart

# 7. PostgreSQL Veritabanı
echo "[7/8] Veritabanı oluşturuluyor..."
sudo -u postgres psql << EOF
CREATE USER takibiesasi_sync WITH PASSWORD 'CHANGE_THIS_PASSWORD';
CREATE DATABASE takibiesasi_sync OWNER takibiesasi_sync;
GRANT ALL PRIVILEGES ON DATABASE takibiesasi_sync TO takibiesasi_sync;
EOF

# 8. Systemd Service
echo "[8/8] Servis oluşturuluyor..."
sudo tee /etc/systemd/system/takibiesasi-sync.service > /dev/null << EOF
[Unit]
Description=TakibiEsasi Sync Server
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/takibiesasi-sync
Environment="PATH=/opt/takibiesasi-sync/venv/bin"
ExecStart=/opt/takibiesasi-sync/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable takibiesasi-sync

echo "=== Kurulum Tamamlandı ==="
echo "Servis başlatmak için: sudo systemctl start takibiesasi-sync"
echo "Logları görmek için: journalctl -u takibiesasi-sync -f"
```

### 4.3 Güvenlik Ayarları
```bash
# Firewall (sadece yerel ağ)
sudo apt install ufw -y
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 8080
sudo ufw allow ssh
sudo ufw enable

# PostgreSQL sadece localhost
sudo nano /etc/postgresql/*/main/postgresql.conf
# listen_addresses = 'localhost'

# Fail2ban (SSH koruması)
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

### 4.4 SSL Sertifikası (Self-Signed)
```bash
# Yerel ağ için self-signed sertifika
sudo mkdir -p /opt/takibiesasi-sync/certs
cd /opt/takibiesasi-sync/certs

sudo openssl req -x509 -nodes -days 3650 \
    -newkey rsa:2048 \
    -keyout server.key \
    -out server.crt \
    -subj "/CN=takibiesasi-sync.local"

sudo chown $USER:$USER server.*
```

---

## 5. SYNC SERVER API (FastAPI)

### 5.1 Dosya Yapısı
```
/opt/takibiesasi-sync/
├── main.py                 # Ana FastAPI app
├── config.py               # Konfigürasyon
├── database.py             # PostgreSQL bağlantı
├── security.py             # JWT, şifreleme
├── models/
│   ├── __init__.py
│   ├── firm.py
│   ├── device.py
│   ├── user.py
│   └── sync.py
├── routes/
│   ├── __init__.py
│   ├── auth.py             # Kimlik doğrulama
│   ├── setup.py            # Büro kurulum
│   ├── sync.py             # Senkronizasyon
│   └── admin.py            # Yönetim
├── services/
│   ├── __init__.py
│   ├── sync_service.py
│   ├── encryption_service.py
│   └── conflict_resolver.py
└── certs/
    ├── server.crt
    └── server.key
```

### 5.2 Ana API Endpoint'leri

```python
# ============================================================
# BÜRO KURULUM
# ============================================================

POST /api/setup/init
# İlk büro kurulumu
# Request: { firm_name, admin_username, admin_password, admin_email }
# Response: { firm_id, recovery_code, join_code }

POST /api/setup/join
# Büroya katılım
# Request: { join_code, device_name, device_info }
# Response: { firm_id, device_id, requires_approval }

POST /api/setup/approve-device
# Cihaz onaylama (Admin)
# Request: { device_id }
# Response: { success, firm_key_encrypted }

# ============================================================
# KİMLİK DOĞRULAMA
# ============================================================

POST /api/auth/login
# Kullanıcı girişi
# Request: { username, password, device_id }
# Response: { access_token, refresh_token, user_info }

POST /api/auth/refresh
# Token yenileme
# Request: { refresh_token }
# Response: { access_token }

POST /api/auth/logout
# Çıkış
# Request: {}
# Response: { success }

# ============================================================
# SENKRONİZASYON
# ============================================================

POST /api/sync/push
# Değişiklikleri gönder
# Headers: Authorization, X-Firm-ID, X-Device-ID
# Request: { changes: [{ uuid, table, operation, data_encrypted }] }
# Response: { success, synced_count, conflicts: [] }

GET /api/sync/pull?since_revision={revision}
# Değişiklikleri al
# Headers: Authorization, X-Firm-ID, X-Device-ID
# Response: { changes: [...], latest_revision }

POST /api/sync/resolve-conflict
# Çakışma çöz
# Request: { record_uuid, resolution, winning_data }
# Response: { success }

GET /api/sync/status
# Senkronizasyon durumu
# Response: { is_connected, last_sync, pending_changes }

# ============================================================
# YÖNETİM
# ============================================================

GET /api/admin/devices
# Cihaz listesi
# Response: { devices: [...] }

POST /api/admin/devices/{device_id}/deactivate
# Cihaz deaktif et
# Response: { success }

GET /api/admin/users
# Kullanıcı listesi
# Response: { users: [...] }

POST /api/admin/users
# Kullanıcı ekle
# Request: { username, password, email, role }
# Response: { user_id }

POST /api/admin/users/{user_id}/deactivate
# Kullanıcı deaktif et
# Response: { success }

POST /api/admin/join-code/generate
# Yeni katılım kodu üret
# Response: { code, expires_at }

GET /api/admin/audit-log
# Denetim kaydı
# Response: { logs: [...] }
```

---

## 6. İSTEMCİ SYNC ENGINE

### 6.1 Dosya Yapısı (app/ içinde)
```
app/
├── sync/
│   ├── __init__.py
│   ├── sync_manager.py      # Ana senkronizasyon yöneticisi
│   ├── sync_client.py       # HTTP client
│   ├── outbox_processor.py  # Outbox işleme
│   ├── inbox_processor.py   # Inbox işleme
│   ├── conflict_handler.py  # Çakışma yönetimi
│   ├── encryption.py        # Firma anahtarı şifreleme
│   └── models.py            # Sync veri modelleri
```

### 6.2 SyncManager Sınıfı

```python
# sync/sync_manager.py

from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum
import threading
import time

class SyncStatus(Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    OFFLINE = "offline"
    NOT_CONFIGURED = "not_configured"

@dataclass
class SyncConfig:
    server_url: str
    firm_id: str
    device_id: str
    firm_key: bytes
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

class SyncManager:
    """Ana senkronizasyon yöneticisi"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.config: Optional[SyncConfig] = None
        self.status = SyncStatus.NOT_CONFIGURED
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sync_interval = 30  # saniye

        # Alt bileşenler
        self.client: Optional[SyncClient] = None
        self.outbox: Optional[OutboxProcessor] = None
        self.inbox: Optional[InboxProcessor] = None
        self.encryption: Optional[EncryptionService] = None

        # Callbacks
        self.on_status_change = None
        self.on_sync_complete = None
        self.on_conflict = None

    def initialize(self, config: SyncConfig):
        """Senkronizasyonu başlat"""
        self.config = config
        self.client = SyncClient(config)
        self.outbox = OutboxProcessor(self.db_path, self.client)
        self.inbox = InboxProcessor(self.db_path)
        self.encryption = EncryptionService(config.firm_key)
        self.status = SyncStatus.IDLE
        self._notify_status_change()

    def start_background_sync(self):
        """Arka plan senkronizasyonunu başlat"""
        if self._sync_thread and self._sync_thread.is_alive():
            return

        self._stop_event.clear()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()

    def stop_background_sync(self):
        """Arka plan senkronizasyonunu durdur"""
        self._stop_event.set()
        if self._sync_thread:
            self._sync_thread.join(timeout=5)

    def sync_now(self) -> Dict:
        """Hemen senkronize et"""
        if self.status == SyncStatus.SYNCING:
            return {"status": "already_syncing"}

        return self._perform_sync()

    def _sync_loop(self):
        """Arka plan sync döngüsü"""
        while not self._stop_event.is_set():
            try:
                self._perform_sync()
            except Exception as e:
                self.status = SyncStatus.ERROR
                self._notify_status_change()

            # Bekleme (interruptible)
            self._stop_event.wait(self._sync_interval)

    def _perform_sync(self) -> Dict:
        """Senkronizasyon işlemi"""
        self.status = SyncStatus.SYNCING
        self._notify_status_change()

        result = {"pushed": 0, "pulled": 0, "conflicts": []}

        try:
            # 1. Bağlantı kontrolü
            if not self.client.check_connection():
                self.status = SyncStatus.OFFLINE
                self._notify_status_change()
                return {"status": "offline"}

            # 2. Token yenile (gerekirse)
            self.client.refresh_token_if_needed()

            # 3. Push: Lokal değişiklikleri gönder
            push_result = self.outbox.process()
            result["pushed"] = push_result["count"]
            result["conflicts"].extend(push_result.get("conflicts", []))

            # 4. Pull: Uzak değişiklikleri al
            pull_result = self.inbox.fetch_and_process()
            result["pulled"] = pull_result["count"]

            # 5. Çakışmaları işle
            if result["conflicts"]:
                self._handle_conflicts(result["conflicts"])

            # 6. Son sync zamanını güncelle
            self._update_last_sync()

            self.status = SyncStatus.IDLE
            self._notify_status_change()

            if self.on_sync_complete:
                self.on_sync_complete(result)

            return result

        except Exception as e:
            self.status = SyncStatus.ERROR
            self._notify_status_change()
            raise

    def _handle_conflicts(self, conflicts: List):
        """Çakışmaları yönet (Last-Write-Wins)"""
        for conflict in conflicts:
            # Varsayılan: sunucu kazanır (daha yeni timestamp)
            # Gerekirse: UI'da göster
            if self.on_conflict:
                self.on_conflict(conflict)

    def _update_last_sync(self):
        """Son sync zamanını kaydet"""
        # sync_metadata tablosunu güncelle
        pass

    def _notify_status_change(self):
        """Durum değişikliğini bildir"""
        if self.on_status_change:
            self.on_status_change(self.status)

    # ============================================================
    # BÜRO YÖNETİMİ
    # ============================================================

    def setup_new_firm(self, server_url: str, firm_name: str,
                       admin_user: str, admin_pass: str) -> Dict:
        """Yeni büro kur"""
        # API çağrısı
        response = requests.post(f"{server_url}/api/setup/init", json={
            "firm_name": firm_name,
            "admin_username": admin_user,
            "admin_password": admin_pass
        })

        if response.ok:
            data = response.json()
            # Lokal yapılandırma
            self._save_firm_config(data)
            return data
        else:
            raise Exception(response.json().get("detail", "Kurulum başarısız"))

    def join_firm(self, server_url: str, join_code: str,
                  device_name: str) -> Dict:
        """Mevcut büroya katıl"""
        # Önce lokal veri kontrolü
        if self._has_existing_data():
            raise Exception("Bu cihazda başka büroya ait veri var. Önce temizleyin.")

        response = requests.post(f"{server_url}/api/setup/join", json={
            "join_code": join_code,
            "device_name": device_name,
            "device_info": self._get_device_info()
        })

        if response.ok:
            data = response.json()
            if data.get("requires_approval"):
                return {"status": "pending_approval", **data}
            else:
                self._save_firm_config(data)
                return {"status": "joined", **data}
        else:
            raise Exception(response.json().get("detail", "Katılım başarısız"))

    def leave_firm(self, keep_local_data: bool = False):
        """Bürodan ayrıl"""
        if not keep_local_data:
            self._clear_synced_data()

        self._clear_firm_config()
        self.status = SyncStatus.NOT_CONFIGURED
        self._notify_status_change()
```

### 6.3 Database Trigger'ları (SQLite)

```python
# db.py içinde - Outbox trigger'ları

def setup_sync_triggers(conn):
    """Senkronizasyon trigger'larını oluştur"""

    SYNCED_TABLES = [
        'dosyalar', 'finans', 'taksitler', 'odeme_kayitlari',
        'masraflar', 'muvekkil_kasasi', 'tebligatlar',
        'arabuluculuk', 'gorevler', 'users', 'attachments'
    ]

    for table in SYNCED_TABLES:
        # INSERT trigger
        conn.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {table}_sync_insert
            AFTER INSERT ON {table}
            FOR EACH ROW
            WHEN (SELECT is_sync_enabled FROM sync_metadata LIMIT 1) = 1
            BEGIN
                INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                VALUES (
                    NEW.uuid,
                    '{table}',
                    'INSERT',
                    json_object(
                        'uuid', NEW.uuid,
                        -- diğer alanlar dinamik olarak
                    )
                );
            END;
        """)

        # UPDATE trigger
        conn.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {table}_sync_update
            AFTER UPDATE ON {table}
            FOR EACH ROW
            WHEN (SELECT is_sync_enabled FROM sync_metadata LIMIT 1) = 1
            BEGIN
                INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                VALUES (
                    NEW.uuid,
                    '{table}',
                    'UPDATE',
                    json_object(...)
                );

                UPDATE {table} SET
                    revision = revision + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.id;
            END;
        """)

        # DELETE trigger (soft delete)
        conn.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {table}_sync_delete
            AFTER UPDATE OF is_deleted ON {table}
            FOR EACH ROW
            WHEN NEW.is_deleted = 1
              AND (SELECT is_sync_enabled FROM sync_metadata LIMIT 1) = 1
            BEGIN
                INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
                VALUES (
                    NEW.uuid,
                    '{table}',
                    'DELETE',
                    json_object('uuid', NEW.uuid)
                );
            END;
        """)
```

---

## 7. UI ENTEGRASYONU

### 7.1 Büro Kurulum Wizard'ı

```python
# ui_buro_setup_wizard.py

from PyQt6.QtWidgets import (QWizard, QWizardPage, QVBoxLayout,
                              QLineEdit, QLabel, QPushButton, QTextEdit)

class BuroSetupWizard(QWizard):
    """Büro kurulum sihirbazı"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Büro Kurulumu")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Sayfalar
        self.addPage(WelcomePage())
        self.addPage(ModeSelectPage())      # Yeni kur / Katıl
        self.addPage(ServerConfigPage())    # Sunucu adresi
        self.addPage(NewFirmPage())         # Yeni büro bilgileri
        self.addPage(JoinFirmPage())        # Katılım kodu
        self.addPage(RecoveryCodePage())    # Kurtarma kodu göster
        self.addPage(CompletePage())        # Tamamlandı

class ModeSelectPage(QWizardPage):
    """Mod seçimi: Yeni büro / Mevcut büroya katıl"""

    def __init__(self):
        super().__init__()
        self.setTitle("Kurulum Türü")
        self.setSubTitle("Ne yapmak istiyorsunuz?")

        layout = QVBoxLayout()

        self.btn_new = QPushButton("🏢 Yeni Büro Oluştur")
        self.btn_new.setStyleSheet("padding: 20px; font-size: 16px;")
        self.btn_new.clicked.connect(self.select_new)

        self.btn_join = QPushButton("🔗 Mevcut Büroya Katıl")
        self.btn_join.setStyleSheet("padding: 20px; font-size: 16px;")
        self.btn_join.clicked.connect(self.select_join)

        layout.addWidget(self.btn_new)
        layout.addWidget(self.btn_join)
        self.setLayout(layout)

        self.mode = None

    def select_new(self):
        self.mode = "new"
        self.wizard().next()

    def select_join(self):
        self.mode = "join"
        self.wizard().next()
```

### 7.2 Sync Durum Göstergesi

```python
# ui_sync_indicator.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer, pyqtSignal

class SyncIndicator(QWidget):
    """Senkronizasyon durumu göstergesi (status bar için)"""

    sync_requested = pyqtSignal()

    STATUS_ICONS = {
        "idle": "🟢",
        "syncing": "🔄",
        "error": "🔴",
        "offline": "⚫",
        "not_configured": "⚪"
    }

    STATUS_TEXTS = {
        "idle": "Senkronize",
        "syncing": "Senkronize ediliyor...",
        "error": "Senkronizasyon hatası",
        "offline": "Çevrimdışı",
        "not_configured": "Büro bağlantısı yok"
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.icon_label = QLabel("⚪")
        self.status_label = QLabel("Büro bağlantısı yok")
        self.sync_button = QPushButton("🔄")
        self.sync_button.setToolTip("Şimdi senkronize et")
        self.sync_button.clicked.connect(self.sync_requested.emit)
        self.sync_button.setVisible(False)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.sync_button)

        self.setLayout(layout)

    def set_status(self, status: str, detail: str = None):
        """Durumu güncelle"""
        self.icon_label.setText(self.STATUS_ICONS.get(status, "❓"))

        text = self.STATUS_TEXTS.get(status, status)
        if detail:
            text = f"{text} - {detail}"
        self.status_label.setText(text)

        # Sync butonu sadece idle/error/offline durumlarında
        self.sync_button.setVisible(status in ["idle", "error", "offline"])

    def set_last_sync(self, timestamp: str):
        """Son sync zamanını göster"""
        self.setToolTip(f"Son senkronizasyon: {timestamp}")
```

### 7.3 Ayarlar Paneline Büro Sekmesi

```python
# ui_settings_dialog.py içine eklenecek

class BuroSettingsTab(QWidget):
    """Büro ayarları sekmesi"""

    def __init__(self, sync_manager):
        super().__init__()
        self.sync_manager = sync_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Bağlantı Durumu
        status_group = QGroupBox("Bağlantı Durumu")
        status_layout = QFormLayout()

        self.lbl_firm_name = QLabel("-")
        self.lbl_device_id = QLabel("-")
        self.lbl_last_sync = QLabel("-")
        self.lbl_pending = QLabel("-")

        status_layout.addRow("Büro:", self.lbl_firm_name)
        status_layout.addRow("Cihaz ID:", self.lbl_device_id)
        status_layout.addRow("Son Senkronizasyon:", self.lbl_last_sync)
        status_layout.addRow("Bekleyen Değişiklik:", self.lbl_pending)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # İşlemler
        actions_group = QGroupBox("İşlemler")
        actions_layout = QVBoxLayout()

        self.btn_sync_now = QPushButton("🔄 Şimdi Senkronize Et")
        self.btn_sync_now.clicked.connect(self.sync_now)

        self.btn_view_conflicts = QPushButton("⚠️ Çakışmaları Görüntüle")
        self.btn_view_conflicts.clicked.connect(self.view_conflicts)

        self.btn_leave_firm = QPushButton("🚪 Bürodan Ayrıl")
        self.btn_leave_firm.setStyleSheet("background-color: #ff6b6b;")
        self.btn_leave_firm.clicked.connect(self.leave_firm)

        actions_layout.addWidget(self.btn_sync_now)
        actions_layout.addWidget(self.btn_view_conflicts)
        actions_layout.addWidget(self.btn_leave_firm)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # Admin İşlemleri (sadece admin için)
        self.admin_group = QGroupBox("Yönetici İşlemleri")
        admin_layout = QVBoxLayout()

        self.btn_manage_devices = QPushButton("💻 Cihazları Yönet")
        self.btn_manage_users = QPushButton("👥 Kullanıcıları Yönet")
        self.btn_generate_code = QPushButton("🔑 Katılım Kodu Oluştur")

        admin_layout.addWidget(self.btn_manage_devices)
        admin_layout.addWidget(self.btn_manage_users)
        admin_layout.addWidget(self.btn_generate_code)

        self.admin_group.setLayout(admin_layout)
        layout.addWidget(self.admin_group)

        layout.addStretch()
        self.setLayout(layout)
```

---

## 8. MİGRASYON PLANI

### 8.1 Veritabanı Migrasyon Script'i

```python
# migrations/add_sync_columns.py

def migrate_add_sync_columns(conn):
    """Mevcut tablolara sync kolonları ekle"""

    SYNCED_TABLES = [
        'dosyalar', 'finans', 'taksitler', 'odeme_kayitlari',
        'masraflar', 'muvekkil_kasasi', 'tebligatlar',
        'arabuluculuk', 'gorevler', 'users', 'attachments'
    ]

    for table in SYNCED_TABLES:
        # UUID kolonu
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN uuid VARCHAR(36)")
        except:
            pass  # Zaten var

        # Diğer kolonlar
        columns = [
            ("firm_id", "VARCHAR(36)"),
            ("revision", "INTEGER DEFAULT 1"),
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("synced_at", "DATETIME"),
            ("created_by", "VARCHAR(36)"),
            ("updated_by", "VARCHAR(36)"),
            ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]

        for col_name, col_type in columns:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except:
                pass

    # Mevcut kayıtlara UUID ata
    import uuid
    for table in SYNCED_TABLES:
        conn.execute(f"""
            UPDATE {table}
            SET uuid = lower(hex(randomblob(4)) || '-' ||
                            hex(randomblob(2)) || '-4' ||
                            substr(hex(randomblob(2)),2) || '-' ||
                            substr('89ab',abs(random()) % 4 + 1, 1) ||
                            substr(hex(randomblob(2)),2) || '-' ||
                            hex(randomblob(6)))
            WHERE uuid IS NULL
        """)

    conn.commit()


def migrate_create_sync_tables(conn):
    """Sync tablolarını oluştur"""

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            id INTEGER PRIMARY KEY,
            device_id VARCHAR(36) NOT NULL,
            firm_id VARCHAR(36),
            firm_key_encrypted BLOB,
            last_sync_revision INTEGER DEFAULT 0,
            last_sync_at DATETIME,
            server_url TEXT,
            is_sync_enabled INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid VARCHAR(36) NOT NULL,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            retry_count INTEGER DEFAULT 0,
            last_retry_at DATETIME,
            synced INTEGER DEFAULT 0,
            synced_at DATETIME,
            error_message TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid VARCHAR(36) NOT NULL,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            data_json TEXT NOT NULL,
            revision INTEGER NOT NULL,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0,
            processed_at DATETIME
        )
    """)

    # İndeksler
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_pending ON sync_outbox(synced, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inbox_pending ON sync_inbox(processed, revision)")

    conn.commit()
```

---

## 9. LAST-WRITE-WINS ÇAKIŞMA ÇÖZÜMÜ

```python
# sync/conflict_handler.py

from datetime import datetime
from typing import Dict, Optional

class ConflictResolver:
    """Last-Write-Wins çakışma çözücü"""

    def resolve(self, local_record: Dict, remote_record: Dict) -> Dict:
        """
        İki kayıt arasındaki çakışmayı çöz.
        Daha yeni updated_at değerine sahip olan kazanır.
        """

        local_time = self._parse_timestamp(local_record.get('updated_at'))
        remote_time = self._parse_timestamp(remote_record.get('updated_at'))

        if local_time and remote_time:
            if local_time > remote_time:
                return {
                    'winner': 'local',
                    'data': local_record,
                    'reason': f'Local daha yeni: {local_time} > {remote_time}'
                }
            else:
                return {
                    'winner': 'remote',
                    'data': remote_record,
                    'reason': f'Remote daha yeni: {remote_time} >= {local_time}'
                }

        # Timestamp yoksa remote kazanır (sunucu otoritesi)
        return {
            'winner': 'remote',
            'data': remote_record,
            'reason': 'Timestamp karşılaştırılamadı, sunucu otoritesi'
        }

    def _parse_timestamp(self, ts: Optional[str]) -> Optional[datetime]:
        """Timestamp parse et"""
        if not ts:
            return None

        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue

        return None

    def log_conflict(self, table: str, uuid: str,
                     local: Dict, remote: Dict, resolution: Dict):
        """Çakışmayı logla (audit için)"""
        # sync_conflicts tablosuna kaydet
        pass
```

---

## 10. İMPLEMENTASYON AŞAMALARI

### AŞAMA 1: Temel Altyapı (1-2 hafta)
- [ ] Raspberry Pi kurulumu
- [ ] PostgreSQL kurulumu
- [ ] FastAPI sync server temel yapısı
- [ ] Veritabanı şeması (sunucu)
- [ ] SSL sertifikası

### AŞAMA 2: Veritabanı Migrasyonu (1 hafta)
- [ ] SQLite tablolarına UUID ve sync kolonları ekle
- [ ] sync_metadata, sync_outbox, sync_inbox tabloları
- [ ] Migrasyon script'i
- [ ] Mevcut verilere UUID ata

### AŞAMA 3: Sync Engine - İstemci (2 hafta)
- [ ] SyncManager sınıfı
- [ ] SyncClient (HTTP)
- [ ] OutboxProcessor
- [ ] InboxProcessor
- [ ] EncryptionService (firm_key)
- [ ] Arka plan senkronizasyon thread'i

### AŞAMA 4: Sync Server API (2 hafta)
- [ ] /api/setup/* endpoint'leri
- [ ] /api/auth/* endpoint'leri
- [ ] /api/sync/* endpoint'leri
- [ ] /api/admin/* endpoint'leri
- [ ] JWT authentication
- [ ] Firm/Device/User modelleri

### AŞAMA 5: UI Entegrasyonu (1-2 hafta)
- [ ] Büro Kurulum Wizard'ı
- [ ] Büroya Katıl dialog'u
- [ ] Sync durum göstergesi (status bar)
- [ ] Ayarlar > Büro sekmesi
- [ ] Cihaz yönetimi dialog'u
- [ ] Kullanıcı yönetimi dialog'u

### AŞAMA 6: Güvenlik & Test (1 hafta)
- [ ] 3 katmanlı güvenlik kontrolü
- [ ] Yanlış ağ bağlantısı testi
- [ ] Büro değişikliği testi
- [ ] Çoklu cihaz senkronizasyon testi
- [ ] Çakışma çözümü testi

### AŞAMA 7: Polish & Dokümantasyon (1 hafta)
- [ ] Hata yönetimi ve kullanıcı mesajları
- [ ] Logging
- [ ] Kullanıcı dokümantasyonu
- [ ] Admin dokümantasyonu

---

## 11. YANLIŞ AĞA BAĞLANMA KORUMASI

```python
# sync/security.py

class FirmValidator:
    """Firma kimlik doğrulama"""

    @staticmethod
    def validate_connection(local_firm_id: str, server_firm_id: str) -> bool:
        """
        Bağlantı öncesi firm_id kontrolü.
        Yanlış ağa bağlanmayı önler.
        """
        if local_firm_id != server_firm_id:
            raise FirmMismatchError(
                f"Bu sunucu farklı bir büroya ait!\n\n"
                f"Sizin büro ID: {local_firm_id[:8]}...\n"
                f"Sunucu büro ID: {server_firm_id[:8]}...\n\n"
                f"Lütfen doğru ağa bağlandığınızdan emin olun."
            )
        return True

class DeviceValidator:
    """Cihaz doğrulama"""

    @staticmethod
    def validate_device(device_id: str, approved_devices: list) -> bool:
        """Cihaz whitelist kontrolü"""
        if device_id not in approved_devices:
            raise DeviceNotApprovedError(
                "Bu cihaz henüz onaylanmamış.\n"
                "Yöneticinizden onay isteyin."
            )
        return True


class SyncClient:
    """Güvenli sync client"""

    def connect(self):
        """Sunucuya bağlan ve doğrula"""

        # 1. Sunucu bilgisini al
        response = self._get("/api/sync/info")
        server_info = response.json()

        # 2. Firm ID kontrolü
        FirmValidator.validate_connection(
            self.config.firm_id,
            server_info['firm_id']
        )

        # 3. Device kontrolü
        if not server_info.get('device_approved'):
            raise DeviceNotApprovedError("Cihaz onayı gerekli")

        # 4. Token doğrulama
        self._validate_token()

        return True
```

---

## 12. BÜRO DEĞİŞİKLİĞİ AKIŞI

```python
# sync/firm_manager.py

class FirmManager:
    """Büro değişikliği yönetimi"""

    def leave_firm(self, backup_data: bool = True) -> Dict:
        """
        Mevcut bürodan ayrıl.

        Args:
            backup_data: Ayrılmadan önce yedeğe al
        """

        # 1. Onay al
        confirm = self._show_confirmation(
            "Bürodan Ayrıl",
            "Bu işlem geri alınamaz.\n\n"
            "Seçenekler:\n"
            "• Verileri yedekle ve sil\n"
            "• Sadece bağlantıyı kes (veriler kalır ama senkronize olmaz)\n"
        )

        if not confirm:
            return {"status": "cancelled"}

        # 2. Yedekleme
        if backup_data:
            backup_path = self._create_backup()

        # 3. Sunucuya bildir
        try:
            self.client.post("/api/device/leave", {
                "device_id": self.config.device_id,
                "reason": "user_requested"
            })
        except:
            pass  # Çevrimdışıysa bile devam et

        # 4. Lokal temizlik
        self._clear_sync_config()
        self._clear_firm_key()

        # 5. Opsiyonel: Tüm senkronize veriyi sil
        if confirm == "delete_all":
            self._delete_synced_data()

        return {
            "status": "left",
            "backup_path": backup_path if backup_data else None
        }

    def join_new_firm(self, server_url: str, join_code: str) -> Dict:
        """
        Yeni büroya katıl.
        """

        # 1. Mevcut veri kontrolü
        if self._has_synced_data():
            choice = self._show_choice(
                "Mevcut Veri Tespit Edildi",
                "Bu bilgisayarda başka büroya ait veri var.\n\n"
                "Ne yapmak istersiniz?",
                [
                    ("Yedekle ve Temizle", "backup_clear"),
                    ("Sadece Temizle", "clear"),
                    ("İptal", "cancel")
                ]
            )

            if choice == "cancel":
                return {"status": "cancelled"}

            if choice == "backup_clear":
                self._create_backup()

            self._delete_synced_data()

        # 2. Katılım isteği
        response = self.client.post(f"{server_url}/api/setup/join", {
            "join_code": join_code,
            "device_name": platform.node(),
            "device_info": self._get_device_info()
        })

        if not response.ok:
            raise JoinError(response.json().get("detail", "Katılım başarısız"))

        data = response.json()

        # 3. Onay bekleniyor mu?
        if data.get("requires_approval"):
            self._save_pending_join(data)
            return {
                "status": "pending_approval",
                "message": "Cihazınız yönetici onayı bekliyor."
            }

        # 4. Yapılandırmayı kaydet
        self._save_firm_config(data)

        # 5. İlk senkronizasyon
        self.sync_manager.sync_now()

        return {
            "status": "joined",
            "firm_name": data["firm_name"]
        }
```

---

## 13. KURTARMA KODU SİSTEMİ

```python
# sync/recovery.py

import hashlib
from mnemonic import Mnemonic

class RecoveryCodeManager:
    """BIP-39 tabanlı kurtarma kodu yönetimi"""

    def __init__(self):
        self.mnemonic = Mnemonic("english")

    def generate_recovery_code(self, firm_key: bytes) -> str:
        """
        Firma anahtarından 24 kelimelik kurtarma kodu üret.
        """
        # firm_key'i entropy olarak kullan
        entropy = hashlib.sha256(firm_key).digest()

        # 24 kelime (256-bit entropy)
        words = self.mnemonic.to_mnemonic(entropy)

        return words  # "apple banana cherry dragon ..."

    def recover_firm_key(self, recovery_words: str) -> bytes:
        """
        Kurtarma kodundan firma anahtarını geri elde et.
        """
        if not self.mnemonic.check(recovery_words):
            raise InvalidRecoveryCodeError("Geçersiz kurtarma kodu")

        # Kelimelerden entropy'e
        entropy = self.mnemonic.to_entropy(recovery_words)

        # Entropy'den firm_key'e (aynı işlemi tersine)
        firm_key = hashlib.sha256(entropy).digest()

        return firm_key

    def hash_recovery_code(self, recovery_words: str) -> str:
        """
        Kurtarma kodunun hash'ini al (doğrulama için).
        Sunucuda saklanır.
        """
        return hashlib.sha256(recovery_words.encode()).hexdigest()
```

---

## 14. NOTLAR VE KARARLAR

### Onaylanan Kararlar:
1. ✅ Şifreleme: Firma Anahtarlı (Strateji C)
2. ✅ Sunucu: Raspberry Pi (yerel ağ)
3. ✅ Çakışma Çözümü: Last-Write-Wins
4. ✅ Güvenlik: 3 Katmanlı (firm_id + device_id + firm_key)

### Bekleyen Kararlar:
- [ ] Raspberry Pi şifresi hatırlandığında kuruluma başlanacak

### Riskler:
1. Raspberry Pi arızası → Yedekleme stratejisi gerekli
2. Ağ kesintisi → Offline çalışma zaten mevcut
3. Firma anahtarı kaybı → Kurtarma kodu sistemi

---

## 15. SONRAKI ADIMLAR

1. **Raspberry Pi erişimi sağla**
   - SSH şifresi hatırla veya reset et
   - IP: 192.168.1.126

2. **Raspberry Pi kurulum script'ini çalıştır**

3. **PostgreSQL veritabanını oluştur**

4. **FastAPI sync server'ı deploy et**

5. **İstemci tarafı implementasyona başla**

---

*Bu doküman, implementasyon sürecinde güncellenecektir.*
