# SYNC SİSTEMİ YENİDEN YAPILANDIRMA PLANI

## Mevcut Durum (SORUNLU)

### Sunucu Tarafı (sync_server/)
- 8 Python dosyası
- Karmaşık "künye" sistemi
- SyncRecord tablosu ile aşırı karmaşık yapı
- Verileri düzgün işleyemiyor

### Client Tarafı (app/sync/)
- **10 Python dosyası** (aşırı karmaşık!)
- encryption_service, conflict_handler, inbox_processor, outbox_processor...
- Sadece dosya durumları sync oluyor, diğer tablolar çalışmıyor

## Hedef Sistem (eski_server gibi basit)

### Sunucu: 6 dosya
```
sync_server/
├── main.py           # FastAPI endpoints
├── config.py         # Ayarlar
├── database.py       # PostgreSQL bağlantısı
├── models.py         # Tüm tablo modelleri
├── auth.py           # JWT authentication
└── sync_handler.py   # Sync işleme mantığı
```

### Client: 4 dosya
```
app/sync/
├── __init__.py       # Export'lar
├── config.py         # Sync yapılandırması
├── client.py         # HTTP client
└── outbox.py         # Değişiklik takibi
```

---

## SUNUCU MİMARİSİ (PostgreSQL)

### 1. Veritabanı Tabloları

```sql
-- Firmalar
CREATE TABLE firms (
    uuid UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB
);

-- Global Revision (HER FİRMA İÇİN TEK SAYAÇ)
CREATE TABLE global_revisions (
    firm_id UUID PRIMARY KEY REFERENCES firms(uuid),
    current_revision BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Kullanıcılar
CREATE TABLE users (
    uuid UUID PRIMARY KEY,
    firm_id UUID NOT NULL REFERENCES firms(uuid),
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'avukat',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    revision BIGINT DEFAULT 0,
    device_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(firm_id, username)
);

-- Dosyalar (ve diğer tüm tablolar aynı yapıda)
CREATE TABLE dosyalar (
    uuid UUID PRIMARY KEY,
    firm_id UUID NOT NULL REFERENCES firms(uuid),
    revision BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    device_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Tablo spesifik alanlar
    buro_takip_no INTEGER,
    dosya_esas_no VARCHAR(100),
    muvekkil_adi VARCHAR(255),
    -- ... diğer alanlar
);

-- Sync Logları
CREATE TABLE sync_logs (
    id SERIAL PRIMARY KEY,
    firm_id UUID NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    user_uuid UUID,
    sync_type VARCHAR(20),
    records_sent INTEGER DEFAULT 0,
    records_received INTEGER DEFAULT 0,
    last_revision BIGINT,
    status VARCHAR(20),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 2. Sync Protokolü (ÇOK BASİT)

**İstek:**
```json
POST /api/sync
Authorization: Bearer <jwt_token>

{
    "device_id": "abc123",
    "last_sync_revision": 150,
    "changes": [
        {
            "table": "dosyalar",
            "op": "insert",
            "uuid": "xxx-xxx",
            "data": {...}
        },
        {
            "table": "finans",
            "op": "update",
            "uuid": "yyy-yyy",
            "data": {...}
        }
    ]
}
```

**Yanıt:**
```json
{
    "success": true,
    "new_revision": 175,
    "changes": [
        {
            "table": "dosyalar",
            "op": "update",
            "uuid": "zzz-zzz",
            "data": {...},
            "revision": 160
        }
    ],
    "message": "Sync tamamlandı"
}
```

### 3. Sunucu Sync Mantığı

```python
def perform_sync(db, token_data, request):
    firm_id = token_data.firm_id
    device_id = request.device_id

    # 1. Gelen değişiklikleri işle
    for change in request.changes:
        new_rev = get_next_revision(db, firm_id)  # Atomik artırma

        if change.op == 'insert':
            # Yeni kayıt ekle, revision ata
            insert_record(table, change.uuid, change.data, new_rev)
        elif change.op == 'update':
            # Güncelle, revision ata
            update_record(table, change.uuid, change.data, new_rev)
        elif change.op == 'delete':
            # Soft delete, revision ata
            soft_delete(table, change.uuid, new_rev)

    # 2. İstemciye gönderilecek değişiklikleri al
    outgoing = []
    for table in SYNCABLE_TABLES:
        records = query(table).filter(
            firm_id == firm_id,
            revision > request.last_sync_revision
        ).all()
        outgoing.extend(records)

    # 3. Mevcut revision'ı döndür
    current_rev = get_current_revision(db, firm_id)

    return {
        "success": True,
        "new_revision": current_rev,
        "changes": outgoing
    }
```

---

## CLIENT MİMARİSİ

### 1. Outbox Tablosu (SQLite)

```sql
CREATE TABLE IF NOT EXISTS sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,  -- 'insert', 'update', 'delete'
    record_uuid TEXT NOT NULL,
    data TEXT,  -- JSON
    created_at TEXT,
    synced INTEGER DEFAULT 0,
    synced_at TEXT
);
```

### 2. Sync Config (SQLite)

```sql
CREATE TABLE IF NOT EXISTS sync_config (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Kayıtlar:
-- api_url: http://192.168.1.100:8787
-- device_id: xxx-xxx
-- auth_token: jwt_token
-- firm_id: xxx
-- last_sync_revision: 150
-- last_sync_time: 2024-01-01T12:00:00
```

### 3. Değişiklik Kaydetme (Her INSERT/UPDATE/DELETE'de)

```python
def sync_insert(table, uuid, data, conn):
    """Kayıt ekle ve outbox'a yaz."""
    # 1. Asıl insert
    conn.execute(f"INSERT INTO {table} ...")

    # 2. Outbox'a kaydet
    conn.execute("""
        INSERT INTO sync_outbox (table_name, operation, record_uuid, data, created_at)
        VALUES (?, 'insert', ?, ?, datetime('now'))
    """, (table, uuid, json.dumps(data)))

def sync_update(table, uuid, data, conn):
    """Kayıt güncelle ve outbox'a yaz."""
    conn.execute(f"UPDATE {table} SET ... WHERE uuid = ?")
    conn.execute("""
        INSERT INTO sync_outbox (table_name, operation, record_uuid, data, created_at)
        VALUES (?, 'update', ?, ?, datetime('now'))
    """, (table, uuid, json.dumps(data)))
```

### 4. Full Sync Akışı

```python
def perform_full_sync():
    client = SyncClient()

    # 1. Outbox'tan bekleyen değişiklikleri al
    pending = get_pending_changes()  # synced=0 olanlar

    # 2. Sunucuya gönder
    result = client.sync(pending)

    if result.success:
        # 3. Gelen değişiklikleri uygula
        apply_incoming_changes(result.incoming_changes)

        # 4. Gönderilenleri işaretle
        mark_changes_synced([c['id'] for c in pending])

        # 5. Revision güncelle
        save_config('last_sync_revision', result.new_revision)
```

---

## SYNC EDİLECEK TABLOLAR

| Tablo | Açıklama |
|-------|----------|
| `dosyalar` | Ana dosya/dava kayıtları |
| `finans` | Dosya finansları |
| `taksitler` | Taksit planları |
| `odeme_kayitlari` | Ödeme kayıtları |
| `masraflar` | Masraf kayıtları |
| `tebligatlar` | Tebligat kayıtları |
| `arabuluculuk` | Arabuluculuk kayıtları |
| `gorevler` | Görev/yapılacaklar |
| `statuses` | Dava durumları |
| `users` | Kullanıcılar |
| `permissions` | Yetkiler |
| `attachments` | Dosya ekleri (metadata) |
| `custom_tabs` | Özel sekmeler |
| `muvekkil_kasasi` | Müvekkil kasası |
| `finans_harici` | Harici finans |
| `ayarlar` | Uygulama ayarları |

---

## UYGULAMA ADIMLARI

### Adım 1: Sunucu Yeniden Yazımı
1. `eski_server/` dosyalarını `sync_server/` altına kopyala
2. `models.py` - Tüm tabloları PostgreSQL için tanımla
3. `sync_handler.py` - Basit sync mantığı
4. `main.py` - Sadece gerekli endpoint'ler:
   - `POST /api/setup` - İlk kurulum
   - `POST /api/login` - Giriş
   - `POST /api/sync` - Ana senkronizasyon
   - `GET /api/sync/status` - Durum

### Adım 2: Client Basitleştirme
1. `app/sync/` altındaki 10 dosyayı 4'e indir
2. Encryption kaldır (LAN'da gerek yok)
3. Conflict handler basitleştir (last-write-wins)
4. Outbox sistemi düzelt

### Adım 3: Veritabanı Entegrasyonu
1. Her kayıt işleminde `sync_outbox`'a yaz
2. Trigger veya wrapper fonksiyonlar kullan
3. Mevcut kodda `db.insert()` -> `sync_insert()` değiştir

### Adım 4: Test
1. İki cihazda test
2. Çakışma senaryoları test
3. Büyük veri seti test

---

## DOSYA DEĞİŞİKLİKLERİ

### Silinecek/Değiştirilecek Dosyalar

**Sunucu (sync_server/):**
```diff
- models.py          # Tamamen yeniden yazılacak
- main.py            # Tamamen yeniden yazılacak
- auth.py            # Basitleştirilecek
+ sync_handler.py    # Yeni eklenecek
```

**Client (app/sync/):**
```diff
- encryption_service.py    # SİL
- conflict_handler.py      # SİL (basit last-write-wins yeterli)
- inbox_processor.py       # SİL (merger.py ile birleşecek)
- outbox_processor.py      # SİL (outbox.py ile birleşecek)
- sync_service.py          # SİL
- models.py                # Basitleştirilecek
- migration.py             # Basitleştirilecek
- sync_manager.py          # Basitleştirilecek -> client.py
- sync_client.py           # -> client.py olacak
+ config.py                # Yeni
+ outbox.py                # Yeni (eski_server/sync/outbox.py'den)
+ merger.py                # Yeni (eski_server/sync/merger.py'den)
```

---

## ÖNCELİK SIRASI

1. **[YÜKSEK]** Sunucu yeniden yazımı (PostgreSQL + basit sync)
2. **[YÜKSEK]** Client basitleştirme
3. **[ORTA]** Tüm tabloların sync'e eklenmesi
4. **[DÜŞÜK]** Ek özellikler (attachment sync, etc.)

---

## ZAMAN TAHMİNİ

- Sunucu yeniden yazımı: ~2-3 saat
- Client basitleştirme: ~2-3 saat
- Entegrasyon ve test: ~1-2 saat
- **Toplam: ~5-8 saat**
