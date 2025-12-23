# BÜRO TÜRÜ - ÇOKLU KULLANICI SENKRONİZASYONU
# KAPSAMLI İMPLEMENTASYON PLANI

**Tarih:** 23 Aralık 2025
**Versiyon:** 1.0
**Durum:** Planlama Aşaması

---

## 1. PROJE ÖZETI

### 1.1 Hedef
Birden fazla bilgisayarda çalışan TakibiEsasi uygulamalarının verilerini Raspberry Pi üzerinden senkronize etmesi.

### 1.2 Temel Prensipler
- **Offline-First:** İnternet olmadan tam çalışma
- **UUID Tabanlı:** Her kayıt benzersiz UUID ile tanımlanır
- **Last-Write-Wins:** Çakışmalarda son yazan kazanır
- **3 Katmanlı Güvenlik:** firm_id + device_id + firm_key

### 1.3 Mimari Özet
```
┌─────────────────┐         ┌─────────────────┐
│  Bilgisayar A   │         │  Bilgisayar B   │
│  (SQLite)       │         │  (SQLite)       │
│  + sync_outbox  │         │  + sync_outbox  │
└────────┬────────┘         └────────┬────────┘
         │      HTTP/JSON + JWT      │
         └───────────┬───────────────┘
                     │
              ┌──────┴──────┐
              │ Raspberry Pi │
              │ (PostgreSQL) │
              │ FastAPI      │
              │ Yerel Ağ     │
              └──────────────┘
```

---

## 2. GÜVENLİK MİMARİSİ

### 2.1 Kimlik Doğrulama Katmanları

| Katman | Amaç | Nasıl Çalışır |
|--------|------|---------------|
| **firm_id** | Büro kimliği | UUID v4, kurulumda üretilir, değiştirilemez |
| **device_id** | Cihaz kimliği | Her cihaz için benzersiz, sunucuda whitelist |
| **firm_key** | Şifreleme anahtarı | 256-bit AES, sunucuda şifreli saklanır |
| **JWT token** | Oturum yönetimi | 1 saat geçerli, refresh token ile yenilenir |
| **user_permissions** | Yetkilendirme | Rol bazlı erişim kontrolü |

### 2.2 Yanlış Ağa Bağlanma Koruması
1. İstemci sync isteği gönderir: `{ firm_id: "X", device_id: "Y" }`
2. Sunucu kontrol eder:
   - firm_id eşleşmiyorsa → 403 FIRM_MISMATCH
   - device_id whitelist'te yoksa → 403 DEVICE_NOT_REGISTERED
   - JWT token geçersizse → 401 UNAUTHORIZED
3. Tüm kontroller geçerse → Sync başlar

### 2.3 Şifreleme Akışı
```
İLK KURULUM:
1. Admin büro kurar
2. Sunucu rastgele firm_key üretir (256-bit)
3. firm_key sunucuda master_key ile şifrelenir
4. Admin'e 24 kelimelik kurtarma kodu verilir

CİHAZ KATILIMI:
1. Kullanıcı katılım kodu girer
2. Sunucu device_id'yi kaydeder
3. Sunucu firm_key'i güvenli şekilde gönderir
4. İstemci firm_key'i lokal olarak saklar (keyring)
```

---

## 3. VERİTABANI DEĞİŞİKLİKLERİ

### 3.1 Yeni Kolonlar (Tüm Senkronize Tablolara)

```sql
-- Her senkronize tabloya eklenecek kolonlar
uuid VARCHAR(36) NOT NULL DEFAULT (lower(hex(randomblob(16)))),
firm_id VARCHAR(36),
revision INTEGER DEFAULT 1,
is_deleted INTEGER DEFAULT 0,
created_by VARCHAR(36),
updated_by VARCHAR(36),
synced_at DATETIME,
local_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### 3.2 Senkronize Edilecek Tablolar (10 Tablo)

| Tablo | Öncelik | Bağımlılık | Notlar |
|-------|---------|------------|--------|
| users | 1 | - | İlk senkronize edilmeli |
| dosyalar | 2 | - | Ana tablo |
| finans | 3 | dosyalar | dosya_id → dosya_uuid |
| taksitler | 4 | finans | finans_id → finans_uuid |
| odeme_kayitlari | 5 | finans, taksitler | FK'lar uuid'ye |
| masraflar | 6 | finans | finans_id → finans_uuid |
| muvekkil_kasasi | 7 | dosyalar | dosya_id → dosya_uuid |
| gorevler | 8 | dosyalar | dosya_id → dosya_uuid |
| tebligatlar | 9 | - | dosya_no TEXT kalabilir |
| arabuluculuk | 10 | - | Bağımsız |

### 3.3 Yeni Tablolar

```sql
-- Sync Outbox: Bekleyen değişiklikler
CREATE TABLE sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE')),
    data_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    synced INTEGER DEFAULT 0,
    synced_at DATETIME
);

-- Sync Metadata: Cihaz senkronizasyon durumu
CREATE TABLE sync_metadata (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    device_id VARCHAR(36) NOT NULL,
    device_name TEXT,
    firm_id VARCHAR(36),
    firm_name TEXT,
    last_sync_revision INTEGER DEFAULT 0,
    last_sync_at DATETIME,
    sync_enabled INTEGER DEFAULT 1,
    server_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sync Conflicts: Çakışma logları (opsiyonel, debug için)
CREATE TABLE sync_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL,
    table_name TEXT NOT NULL,
    local_data TEXT,
    remote_data TEXT,
    resolution TEXT,
    resolved_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 Migration Script Sırası

```
MIGRATION 001: sync_metadata tablosu oluştur
MIGRATION 002: sync_outbox tablosu oluştur
MIGRATION 003: users tablosuna uuid, firm_id, revision ekle
MIGRATION 004: dosyalar tablosuna uuid, firm_id, revision ekle
MIGRATION 005: finans tablosuna uuid, firm_id, revision, dosya_uuid ekle
MIGRATION 006: taksitler tablosuna uuid, firm_id, revision, finans_uuid ekle
MIGRATION 007: odeme_kayitlari tablosuna uuid, firm_id, revision ekle
MIGRATION 008: masraflar tablosuna uuid, firm_id, revision ekle
MIGRATION 009: muvekkil_kasasi tablosuna uuid, firm_id, revision ekle
MIGRATION 010: gorevler tablosuna uuid, firm_id, revision ekle
MIGRATION 011: tebligatlar tablosuna uuid, firm_id, revision ekle
MIGRATION 012: arabuluculuk tablosuna uuid, firm_id, revision ekle
MIGRATION 013: Mevcut kayıtlara UUID ata
MIGRATION 014: Outbox trigger'ları oluştur
MIGRATION 015: Index'leri oluştur
```

### 3.5 Outbox Trigger Örneği

```sql
-- dosyalar tablosu için trigger
CREATE TRIGGER tr_dosyalar_sync_insert
AFTER INSERT ON dosyalar
BEGIN
    INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
    VALUES (
        NEW.uuid,
        'dosyalar',
        'INSERT',
        json_object(
            'uuid', NEW.uuid,
            'buro_takip_no', NEW.buro_takip_no,
            'dosya_esas_no', NEW.dosya_esas_no,
            'muvekkil_adi', NEW.muvekkil_adi,
            -- ... diğer alanlar
            'revision', NEW.revision
        )
    );
END;

CREATE TRIGGER tr_dosyalar_sync_update
AFTER UPDATE ON dosyalar
WHEN OLD.revision = NEW.revision - 1
BEGIN
    INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
    VALUES (
        NEW.uuid,
        'dosyalar',
        'UPDATE',
        json_object(
            'uuid', NEW.uuid,
            -- ... tüm alanlar
            'revision', NEW.revision
        )
    );
END;

CREATE TRIGGER tr_dosyalar_sync_delete
AFTER UPDATE ON dosyalar
WHEN NEW.is_deleted = 1 AND OLD.is_deleted = 0
BEGIN
    INSERT INTO sync_outbox (uuid, table_name, operation, data_json)
    VALUES (
        NEW.uuid,
        'dosyalar',
        'DELETE',
        json_object('uuid', NEW.uuid, 'revision', NEW.revision)
    );
END;
```

---

## 4. RASPBERRY PI KURULUMU

### 4.1 Donanım Gereksinimleri
- Raspberry Pi 4 Model B (4GB RAM önerilen)
- 32GB+ microSD kart (veya SSD tercih edilir)
- Güç adaptörü (5V 3A USB-C)
- Ethernet kablosu (WiFi yerine önerilir)
- Kasa (opsiyonel ama önerilir)

### 4.2 İşletim Sistemi Kurulumu
```bash
# Raspberry Pi OS Lite (64-bit) önerilir
# Raspberry Pi Imager ile SD karta yazılır

# İlk boot sonrası:
sudo apt update && sudo apt upgrade -y
sudo raspi-config  # Hostname, timezone, SSH ayarları
```

### 4.3 PostgreSQL Kurulumu
```bash
# PostgreSQL kurulumu
sudo apt install postgresql postgresql-contrib -y

# PostgreSQL başlat
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Veritabanı ve kullanıcı oluştur
sudo -u postgres psql << EOF
CREATE USER takibiesasi WITH PASSWORD 'GÜÇLÜ_ŞİFRE_BURAYA';
CREATE DATABASE takibiesasi_sync OWNER takibiesasi;
GRANT ALL PRIVILEGES ON DATABASE takibiesasi_sync TO takibiesasi;
\q
EOF

# PostgreSQL'i yerel ağdan erişime aç
sudo nano /etc/postgresql/15/main/postgresql.conf
# listen_addresses = '*'

sudo nano /etc/postgresql/15/main/pg_hba.conf
# host    takibiesasi_sync    takibiesasi    192.168.0.0/16    scram-sha-256

sudo systemctl restart postgresql
```

### 4.4 Python Ortamı Kurulumu
```bash
# Python ve pip
sudo apt install python3 python3-pip python3-venv -y

# Uygulama dizini
sudo mkdir -p /opt/takibiesasi-sync
sudo chown $USER:$USER /opt/takibiesasi-sync
cd /opt/takibiesasi-sync

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Bağımlılıklar
pip install fastapi uvicorn[standard] asyncpg python-jose[cryptography] \
            passlib[bcrypt] python-multipart pydantic-settings \
            psycopg2-binary aiofiles
```

### 4.5 Sync Server Kurulumu
```bash
# Kod dizini
mkdir -p /opt/takibiesasi-sync/server
cd /opt/takibiesasi-sync/server

# .env dosyası
cat > .env << EOF
DATABASE_URL=postgresql://takibiesasi:GÜÇLÜ_ŞİFRE_BURAYA@localhost/takibiesasi_sync
JWT_SECRET=RASTGELE_64_KARAKTER_SECRET
MASTER_KEY=RASTGELE_64_KARAKTER_MASTER_KEY
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
DEBUG=false
EOF

# Systemd service
sudo tee /etc/systemd/system/takibiesasi-sync.service << EOF
[Unit]
Description=TakibiEsasi Sync Server
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/takibiesasi-sync/server
Environment=PATH=/opt/takibiesasi-sync/venv/bin
ExecStart=/opt/takibiesasi-sync/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable takibiesasi-sync
sudo systemctl start takibiesasi-sync
```

### 4.6 Firewall Ayarları
```bash
# UFW kurulumu
sudo apt install ufw -y
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8080/tcp  # Sync API
sudo ufw enable
```

### 4.7 Raspberry Pi IP'sini Sabitleme
```bash
# /etc/dhcpcd.conf düzenle
sudo nano /etc/dhcpcd.conf

# Ekle:
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

---

## 5. SYNC SERVER API (FastAPI)

### 5.1 Dosya Yapısı
```
/opt/takibiesasi-sync/server/
├── main.py              # FastAPI uygulaması
├── config.py            # Ayarlar
├── database.py          # PostgreSQL bağlantısı
├── models.py            # Pydantic modeller
├── auth.py              # JWT ve güvenlik
├── crypto.py            # Şifreleme fonksiyonları
├── routers/
│   ├── __init__.py
│   ├── setup.py         # Büro kurulum
│   ├── auth.py          # Giriş/çıkış
│   ├── sync.py          # Senkronizasyon
│   ├── devices.py       # Cihaz yönetimi
│   └── admin.py         # Admin işlemleri
├── services/
│   ├── __init__.py
│   ├── sync_service.py  # Sync iş mantığı
│   └── firm_service.py  # Firma işlemleri
└── .env                 # Ortam değişkenleri
```

### 5.2 PostgreSQL Şeması (Sunucu)

```sql
-- Firmalar
CREATE TABLE firms (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    firm_key_encrypted TEXT NOT NULL,  -- Master key ile şifreli
    recovery_hash TEXT NOT NULL,        -- Kurtarma kodu hash'i
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Cihazlar
CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    firm_id VARCHAR(36) REFERENCES firms(uuid) ON DELETE CASCADE,
    name VARCHAR(255),
    device_type VARCHAR(50),  -- desktop, laptop
    last_sync_at TIMESTAMP,
    last_ip VARCHAR(45),
    is_active BOOLEAN DEFAULT TRUE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registered_by VARCHAR(36)  -- user uuid
);

-- Kullanıcılar (Firma bazlı)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    firm_id VARCHAR(36) REFERENCES firms(uuid) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(firm_id, username)
);

-- Katılım Kodları
CREATE TABLE join_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    firm_id VARCHAR(36) REFERENCES firms(uuid) ON DELETE CASCADE,
    created_by VARCHAR(36),
    expires_at TIMESTAMP NOT NULL,
    max_uses INTEGER DEFAULT 10,
    used_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync Revisions (Global)
CREATE TABLE sync_revisions (
    id SERIAL PRIMARY KEY,
    firm_id VARCHAR(36) REFERENCES firms(uuid) ON DELETE CASCADE,
    current_revision BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync Data (Tüm tablolar için merkezi depo)
CREATE TABLE sync_data (
    id SERIAL PRIMARY KEY,
    firm_id VARCHAR(36) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_uuid VARCHAR(36) NOT NULL,
    revision BIGINT NOT NULL,
    operation VARCHAR(10) NOT NULL,  -- INSERT, UPDATE, DELETE
    data_json JSONB NOT NULL,
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(firm_id, table_name, record_uuid)
);

-- Sync History (Audit trail)
CREATE TABLE sync_history (
    id SERIAL PRIMARY KEY,
    firm_id VARCHAR(36) NOT NULL,
    device_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36),
    changes_pushed INTEGER DEFAULT 0,
    changes_pulled INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20),  -- success, partial, failed
    error_message TEXT
);

-- Indexler
CREATE INDEX idx_sync_data_firm_revision ON sync_data(firm_id, revision);
CREATE INDEX idx_sync_data_table_uuid ON sync_data(table_name, record_uuid);
CREATE INDEX idx_devices_firm ON devices(firm_id);
CREATE INDEX idx_users_firm ON users(firm_id);
```

### 5.3 API Endpoints

```
GENEL (Kimlik Doğrulama Gerektirmez)
────────────────────────────────────
GET  /api/health              Sunucu durumu
POST /api/setup               İlk büro kurulumu
POST /api/join                Büroya katılım
POST /api/auth/login          Kullanıcı girişi
POST /api/auth/refresh        Token yenileme

SYNC (JWT Gerekli)
────────────────────────────────────
POST /api/sync                Ana senkronizasyon endpoint'i
GET  /api/sync/status         Sync durumu
POST /api/sync/pull           Sadece çekme (debugging)
POST /api/sync/push           Sadece gönderme (debugging)

CİHAZ (JWT + Admin Gerekli)
────────────────────────────────────
GET  /api/devices             Kayıtlı cihazlar
POST /api/devices/register    Yeni cihaz kaydı
PUT  /api/devices/:id/toggle  Cihaz aktif/pasif
DELETE /api/devices/:id       Cihaz silme

KULLANICI (JWT + Admin Gerekli)
────────────────────────────────────
GET  /api/users               Kullanıcı listesi
POST /api/users               Yeni kullanıcı
PUT  /api/users/:id           Kullanıcı güncelle
DELETE /api/users/:id         Kullanıcı sil (soft delete)

ADMIN (JWT + Kurucu Avukat)
────────────────────────────────────
GET  /api/admin/stats         İstatistikler
POST /api/admin/join-code     Yeni katılım kodu
GET  /api/admin/sync-history  Sync geçmişi
POST /api/admin/force-sync    Zorla senkronizasyon
GET  /api/admin/backup        Veritabanı yedeği
POST /api/admin/restore       Yedekten geri yükle
```

### 5.4 Sync Request/Response Formatı

```json
// POST /api/sync
// Request
{
    "device_id": "abc-123-def",
    "firm_id": "firm-uuid-here",
    "last_sync_revision": 42,
    "changes": [
        {
            "table": "dosyalar",
            "operation": "INSERT",
            "uuid": "record-uuid-1",
            "revision": 43,
            "data": {
                "buro_takip_no": 1001,
                "dosya_esas_no": "2024/123",
                "muvekkil_adi": "Ahmet Yılmaz",
                ...
            }
        },
        {
            "table": "finans",
            "operation": "UPDATE",
            "uuid": "record-uuid-2",
            "revision": 44,
            "data": {...}
        }
    ]
}

// Response (Success)
{
    "success": true,
    "new_revision": 48,
    "server_changes": [
        {
            "table": "dosyalar",
            "operation": "UPDATE",
            "uuid": "record-uuid-5",
            "revision": 46,
            "data": {...}
        }
    ],
    "conflicts": [],
    "sync_timestamp": "2025-12-23T14:30:00Z"
}

// Response (Conflict - Last Write Wins uygulandı)
{
    "success": true,
    "new_revision": 48,
    "server_changes": [...],
    "conflicts": [
        {
            "table": "dosyalar",
            "uuid": "record-uuid-3",
            "resolution": "server_wins",
            "reason": "Server revision 45 > client revision 44"
        }
    ],
    "sync_timestamp": "2025-12-23T14:30:00Z"
}

// Response (Error)
{
    "success": false,
    "error": "FIRM_MISMATCH",
    "message": "Bu cihaz farklı bir büroya kayıtlı"
}
```

---

## 6. İSTEMCİ (MASAÜSTÜ UYGULAMA) DEĞİŞİKLİKLERİ

### 6.1 Yeni Dosyalar

```
app/
├── sync/
│   ├── __init__.py
│   ├── sync_manager.py      # Ana sync yöneticisi
│   ├── sync_client.py       # HTTP client
│   ├── sync_queue.py        # Outbox işleme
│   ├── conflict_resolver.py # Çakışma çözümü
│   ├── crypto_utils.py      # Şifreleme yardımcıları
│   └── models.py            # Sync veri modelleri
├── ui_sync_status.py        # Sync durumu widget'ı
├── ui_buro_setup_wizard.py  # Büro kurulum wizard'ı
├── ui_buro_join_dialog.py   # Büroya katılım dialog'u
└── ui_sync_settings.py      # Sync ayarları
```

### 6.2 SyncManager Sınıfı

```python
# app/sync/sync_manager.py

class SyncManager:
    """Ana senkronizasyon yöneticisi"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = SyncClient()
        self.queue = SyncQueue(db_path)
        self.is_syncing = False
        self.last_sync = None

    async def initialize(self) -> bool:
        """Sync sistemini başlat, metadata kontrol et"""
        pass

    async def sync(self) -> SyncResult:
        """Tam senkronizasyon yap"""
        # 1. Outbox'taki değişiklikleri topla
        # 2. Sunucuya gönder
        # 3. Sunucudan değişiklikleri al
        # 4. Lokal veritabanına uygula
        # 5. Outbox'u temizle
        pass

    async def push_only(self) -> int:
        """Sadece yerel değişiklikleri gönder"""
        pass

    async def pull_only(self) -> int:
        """Sadece sunucudan çek"""
        pass

    def is_configured(self) -> bool:
        """Büro yapılandırılmış mı?"""
        pass

    def get_pending_count(self) -> int:
        """Bekleyen değişiklik sayısı"""
        pass
```

### 6.3 UI Değişiklikleri

#### 6.3.1 Ana Pencereye Sync Durumu Ekleme
```
┌─────────────────────────────────────────────────────────────────┐
│ TakibiEsasi - Büro Modu                              [_][□][X] │
├─────────────────────────────────────────────────────────────────┤
│ Dosya | Düzen | Görünüm | Araçlar | Sync | Yardım              │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ [Dosyalar] [Görevler] [Finans] [Tebligatlar] [Arabuluculuk] │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ... mevcut içerik ...                                          │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ 🟢 Senkronize | Son sync: 14:30 | 3 bekleyen | [🔄 Şimdi Sync] │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.3.2 Büro Kurulum Wizard'ı
```
┌─────────────────────────────────────────────────────────────────┐
│  BÜRO KURULUMU - Adım 1/4                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Hoş geldiniz! Bu wizard ile büronuzu kuracaksınız.             │
│                                                                  │
│  Ne yapmak istiyorsunuz?                                        │
│                                                                  │
│  ○ Yeni büro oluştur (Admin)                                   │
│  ○ Mevcut büroya katıl                                          │
│                                                                  │
│                                                                  │
│                              [İptal]  [İleri →]                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.3.3 Sync Ayarları Paneli
```
┌─────────────────────────────────────────────────────────────────┐
│  SENKRONİZASYON AYARLARI                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Büro Bilgileri                                                  │
│  ─────────────────────────────────────                          │
│  Büro Adı:     Örnek Hukuk Bürosu                               │
│  Firma ID:     f47ac10b-58cc-4372-a567-...                      │
│  Bu Cihaz:     LAPTOP-MEHMET (aktif)                            │
│                                                                  │
│  Sunucu Ayarları                                                │
│  ─────────────────────────────────────                          │
│  Sunucu Adresi: [192.168.1.100:8080    ]                        │
│  Durum:         🟢 Bağlı                                        │
│                                                                  │
│  Otomatik Sync                                                   │
│  ─────────────────────────────────────                          │
│  ☑ Otomatik senkronizasyon aktif                               │
│  Sıklık: [Her 5 dakika ▼]                                       │
│                                                                  │
│  ─────────────────────────────────────                          │
│  [Bağlantıyı Test Et]  [Şimdi Sync]  [Bürodan Ayrıl]           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. KULLANICI SENARYOLARI

### 7.1 İlk Büro Kurulumu (Admin)

```
1. Admin uygulamayı açar
2. Dosya → Büro Kurulumu seçer
3. "Yeni büro oluştur" seçer
4. Sunucu bilgilerini girer (192.168.1.100:8080)
5. Büro adı ve admin bilgilerini girer
6. Sistem:
   - Sunucuya bağlanır
   - firm_id ve firm_key üretir
   - Admin kullanıcısını oluşturur
   - Kurtarma kodunu gösterir
7. Admin kurtarma kodunu kaydeder
8. Kurulum tamamlanır
9. Diğer cihazlar için katılım kodu üretilir
```

### 7.2 Büroya Katılım (Diğer Kullanıcılar)

```
1. Kullanıcı uygulamayı açar
2. "Büroya Katıl" seçer
3. Sunucu adresi ve katılım kodunu girer
4. Kullanıcı adı ve şifre belirler
5. Sistem:
   - Katılım kodunu doğrular
   - device_id oluşturur
   - Sunucuya kaydeder
   - firm_key'i alır
   - İlk senkronizasyonu başlatır
6. Tüm veriler indirilir
7. Kullanıcı çalışmaya başlar
```

### 7.3 Günlük Kullanım

```
1. Kullanıcı uygulamayı açar
2. Sistem otomatik login yapar
3. Arka planda sync başlar
4. Kullanıcı dosya ekler/düzenler
5. Değişiklikler outbox'a yazılır
6. 5 dakikada bir (veya manuel) sync çalışır
7. Değişiklikler sunucuya gönderilir
8. Diğer cihazların değişiklikleri alınır
9. Durum çubuğunda bilgi gösterilir
```

### 7.4 Kullanıcı Bürodan Ayrılır

```
1. Admin, kullanıcıyı "Pasif" yapar (mevcut UI)
2. Sunucu kullanıcıyı deaktif eder
3. Kullanıcının cihazı sync yapmaya çalışır
4. Sunucu 403 döner: "Hesabınız deaktif edildi"
5. Kullanıcıya mesaj gösterilir
6. Lokal veri kalır ama sync çalışmaz
7. Opsiyonel: Admin uzaktan silme komutu gönderir
```

### 7.5 Kullanıcı Yeni Büroya Geçer

```
1. Kullanıcı Ayarlar → Sync → "Bürodan Ayrıl" tıklar
2. Uyarı: "Lokal verileriniz silinecek"
3. Kullanıcı onaylar
4. Sistem:
   - Lokal sync tablolarını temizler
   - sync_metadata'yı sıfırlar
   - firm_key'i siler
5. "Büroya Katıl" wizard'ı açılır
6. Yeni büronun bilgileri girilir
7. Yeni büro verileri indirilir
```

### 7.6 Yanlış Ağa Bağlanma

```
1. Kullanıcı başka büronun WiFi'ına bağlanır
2. Sync çalışmaya çalışır
3. Sunucu firm_id kontrolü yapar
4. FIRM_MISMATCH hatası döner
5. Kullanıcıya mesaj:
   "Bağlandığınız sunucu farklı bir büroya ait.
    Kendi büro sunucunuza bağlı olduğunuzdan emin olun."
6. Veri transferi YAPILMAZ
7. Olay loglanır
```

---

## 8. ÇAKIŞMA ÇÖZÜMÜ (LAST-WRITE-WINS)

### 8.1 Çakışma Tespiti
```
Çakışma oluşur eğer:
- Aynı uuid'li kayıt
- Her iki tarafta da değişmiş
- Revision numaraları farklı

Örnek:
- Sunucu: revision=45, updated_at="14:30:00"
- İstemci: revision=44, updated_at="14:31:00"
```

### 8.2 Çözüm Algoritması
```python
def resolve_conflict(local_record, server_record):
    """Last-Write-Wins: Son yazan kazanır"""

    # Revision karşılaştır
    if server_record.revision > local_record.revision:
        # Sunucu kazanır
        return Resolution(
            winner="server",
            action="apply_server_data"
        )
    elif local_record.revision > server_record.revision:
        # İstemci kazanır
        return Resolution(
            winner="client",
            action="push_local_data"
        )
    else:
        # Aynı revision - timestamp'e bak
        if server_record.updated_at > local_record.updated_at:
            return Resolution(winner="server", action="apply_server_data")
        else:
            return Resolution(winner="client", action="push_local_data")
```

### 8.3 Çakışma Logu
```sql
INSERT INTO sync_conflicts (uuid, table_name, local_data, remote_data, resolution)
VALUES (
    'record-uuid',
    'dosyalar',
    '{"revision": 44, "muvekkil_adi": "Ahmet"}',
    '{"revision": 45, "muvekkil_adi": "Mehmet"}',
    'server_wins: revision 45 > 44'
);
```

---

## 9. TEST STRATEJİSİ

### 9.1 Unit Testler
```
tests/
├── test_sync_manager.py
├── test_sync_client.py
├── test_conflict_resolver.py
├── test_crypto_utils.py
├── test_outbox_queue.py
└── test_migration.py
```

### 9.2 Integration Testler
```
tests/integration/
├── test_full_sync_cycle.py
├── test_multi_device_sync.py
├── test_conflict_scenarios.py
├── test_offline_then_online.py
├── test_firm_mismatch.py
└── test_device_deactivation.py
```

### 9.3 Test Senaryoları

| Senaryo | Beklenen Sonuç |
|---------|----------------|
| 2 cihaz aynı anda farklı kayıt ekler | Her iki kayıt da sync olur |
| 2 cihaz aynı kaydı değiştirir | Last-write-wins, biri kazanır |
| Cihaz offline iken 10 değişiklik yapar | Online olunca hepsi sync olur |
| Yanlış firm_id ile bağlanma | 403 hatası, veri transferi yok |
| Deaktif kullanıcı sync dener | 403 hatası, mesaj gösterilir |
| Sunucu kapalıyken değişiklik yapılır | Outbox'ta birikir, sonra sync olur |
| Kurtarma kodu ile firm_key recovery | Başarılı recovery |

### 9.4 Stress Test
```
- 5 cihaz aynı anda sync
- 1000 kayıt aynı anda ekleme
- Sunucu restart sırasında sync
- Ağ kesintisi simülasyonu
```

---

## 10. DEPLOYMENT PLANI

### 10.1 Aşama 1: Altyapı (Hafta 1)
```
□ Raspberry Pi kurulumu
□ PostgreSQL kurulumu
□ Python ortamı kurulumu
□ Temel güvenlik ayarları
□ Sabit IP yapılandırması
```

### 10.2 Aşama 2: Sunucu Geliştirme (Hafta 2-3)
```
□ FastAPI proje yapısı
□ Veritabanı şeması
□ Auth sistemi (JWT)
□ Firma yönetimi API
□ Cihaz yönetimi API
□ Sync API
□ Unit testler
```

### 10.3 Aşama 3: İstemci Migration (Hafta 4-5)
```
□ Veritabanı migration scriptleri
□ UUID ekleme
□ Outbox trigger'ları
□ SyncManager sınıfı
□ SyncClient sınıfı
□ Unit testler
```

### 10.4 Aşama 4: UI Entegrasyonu (Hafta 6)
```
□ Büro Kurulum Wizard
□ Büroya Katıl Dialog
□ Sync Ayarları Panel
□ Durum çubuğu entegrasyonu
□ Hata mesajları
```

### 10.5 Aşama 5: Test & Debug (Hafta 7-8)
```
□ Integration testler
□ Multi-device testler
□ Conflict testleri
□ Stress testler
□ Bug fix
```

### 10.6 Aşama 6: Dokümantasyon & Release (Hafta 9)
```
□ Kullanıcı kılavuzu güncelleme
□ Admin kılavuzu
□ Troubleshooting rehberi
□ Release notes
□ Versiyon artışı (2.0.0)
```

---

## 11. RİSKLER VE ÖNLEMLERİ

| Risk | Olasılık | Etki | Önlem |
|------|----------|------|-------|
| Veri kaybı | Düşük | Yüksek | Günlük yedekleme, kurtarma kodu |
| Sync çakışması | Orta | Orta | Last-write-wins, conflict log |
| Ağ kesintisi | Yüksek | Düşük | Offline-first, outbox pattern |
| Sunucu arızası | Düşük | Yüksek | Otomatik yedekleme, SD kart yedeği |
| Güvenlik ihlali | Düşük | Yüksek | 3 katmanlı doğrulama, şifreleme |
| Performans | Orta | Orta | Batch sync, delta transfer |

---

## 12. SONRAKI ADIMLAR

1. **HEMEN:** Raspberry Pi IP'sini bul ve bağlantıyı test et
2. **Bu Hafta:** Sunucu altyapısını kur
3. **Sonraki Hafta:** Sync API'yi geliştir
4. **Paralel:** İstemci migration başlat

---

**Plan Durumu:** TAMAMLANDI
**Onay Bekliyor:** Kullanıcı onayı
**Tahmini Süre:** 8-9 hafta

---

*Bu plan TakibiEsasi Büro Türü senkronizasyon özelliğinin implementasyonunu kapsamaktadır.*
