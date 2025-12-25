# UUID Tabanlı FK Migration Planı

## Mevcut Durum Analizi

### Senkronize Edilen Tablolar (21 tablo)

```
SYNCED_TABLES = [
    'dosyalar', 'finans', 'odeme_plani', 'taksitler', 'odeme_kayitlari',
    'masraflar', 'muvekkil_kasasi', 'tebligatlar', 'arabuluculuk', 'gorevler',
    'users', 'permissions', 'dosya_atamalar', 'attachments', 'custom_tabs',
    'custom_tabs_dosyalar', 'dosya_timeline', 'finans_timeline', 'statuses'
]
```

### Mevcut FK İlişkileri (INTEGER Tabanlı)

```
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL 0 (Bağımsız - FK yok)                                         │
├─────────────────────────────────────────────────────────────────────┤
│  users          statuses          custom_tabs                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL 1 (Level 0'a bağlı)                                           │
├─────────────────────────────────────────────────────────────────────┤
│  dosyalar                    permissions                            │
│  (bağımsız)                  (user_id → users)                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL 2 (Level 1'e bağlı)                                           │
├─────────────────────────────────────────────────────────────────────┤
│  finans (dosya_id → dosyalar)                                       │
│  muvekkil_kasasi (dosya_id → dosyalar)                              │
│  tebligatlar (dosya_id → dosyalar)                                  │
│  arabuluculuk (dosya_id → dosyalar)                                 │
│  gorevler (dosya_id → dosyalar)                                     │
│  dosya_atamalar (dosya_id → dosyalar, user_id → users)              │
│  attachments (dosya_id → dosyalar)                                  │
│  custom_tabs_dosyalar (dosya_id → dosyalar, custom_tab_id → tabs)   │
│  dosya_timeline (dosya_id → dosyalar)                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL 3 (Level 2'ye bağlı)                                          │
├─────────────────────────────────────────────────────────────────────┤
│  odeme_plani (finans_id → finans)                                   │
│  taksitler (finans_id → finans)                                     │
│  masraflar (finans_id → finans)                                     │
│  finans_timeline (dosya_id → dosyalar)                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL 4 (Level 3'e bağlı)                                           │
├─────────────────────────────────────────────────────────────────────┤
│  odeme_kayitlari (finans_id → finans, taksit_id → taksitler)        │
└─────────────────────────────────────────────────────────────────────┘
```

### Sorunun Kök Nedeni

```
Makine A:                           Makine B:
┌────────────────┐                  ┌────────────────┐
│ dosyalar       │                  │ dosyalar       │
│ id=1, uuid=ABC │                  │ id=5, uuid=ABC │  ← Aynı kayıt, farklı ID!
└────────────────┘                  └────────────────┘
        │                                   │
        ▼                                   ▼
┌────────────────┐                  ┌────────────────┐
│ finans         │                  │ finans         │
│ dosya_id=1 ✓   │   ──SYNC──►     │ dosya_id=1 ✗   │  ← ID=1 yok, FK HATASI!
│ dosya_uuid=ABC │                  │ dosya_uuid=ABC │  ← UUID ile çalışır ✓
└────────────────┘                  └────────────────┘
```

---

## MİGRASYON PLANI

### AŞAMA 1: Veritabanı Şema Değişiklikleri

#### 1.1 Yeni UUID FK Kolonları Ekleme

Her FK ilişkisi için yeni bir `_uuid` kolonu eklenecek:

```sql
-- Level 2 tablolar
ALTER TABLE finans ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE muvekkil_kasasi ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE tebligatlar ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE arabuluculuk ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE gorevler ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE attachments ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE dosya_timeline ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE dosya_atamalar ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE dosya_atamalar ADD COLUMN user_uuid VARCHAR(36);
ALTER TABLE custom_tabs_dosyalar ADD COLUMN dosya_uuid VARCHAR(36);
ALTER TABLE custom_tabs_dosyalar ADD COLUMN custom_tab_uuid VARCHAR(36);
ALTER TABLE permissions ADD COLUMN user_uuid VARCHAR(36);

-- Level 3 tablolar
ALTER TABLE odeme_plani ADD COLUMN finans_uuid VARCHAR(36);
ALTER TABLE taksitler ADD COLUMN finans_uuid VARCHAR(36);
ALTER TABLE masraflar ADD COLUMN finans_uuid VARCHAR(36);
ALTER TABLE finans_timeline ADD COLUMN dosya_uuid VARCHAR(36);

-- Level 4 tablolar
ALTER TABLE odeme_kayitlari ADD COLUMN finans_uuid VARCHAR(36);
ALTER TABLE odeme_kayitlari ADD COLUMN taksit_uuid VARCHAR(36);
```

#### 1.2 UUID FK Değerlerini Doldurma

```sql
-- finans.dosya_uuid doldur
UPDATE finans
SET dosya_uuid = (SELECT uuid FROM dosyalar WHERE dosyalar.id = finans.dosya_id)
WHERE dosya_id IS NOT NULL;

-- odeme_plani.finans_uuid doldur
UPDATE odeme_plani
SET finans_uuid = (SELECT uuid FROM finans WHERE finans.id = odeme_plani.finans_id)
WHERE finans_id IS NOT NULL;

-- Diğer tablolar için benzer UPDATE'ler...
```

#### 1.3 İndeksler Ekleme

```sql
CREATE INDEX IF NOT EXISTS idx_finans_dosya_uuid ON finans(dosya_uuid);
CREATE INDEX IF NOT EXISTS idx_odeme_plani_finans_uuid ON odeme_plani(finans_uuid);
CREATE INDEX IF NOT EXISTS idx_taksitler_finans_uuid ON taksitler(finans_uuid);
-- ... diğer tablolar
```

---

### AŞAMA 2: Uygulama Kodu Değişiklikleri

#### 2.1 Değiştirilecek Dosyalar

| Dosya | Değişiklik Türü |
|-------|-----------------|
| `app/db.py` | INSERT/UPDATE sorgularında UUID FK kullanımı |
| `app/ui_main.py` | JOIN sorgularında UUID FK kullanımı |
| `app/ui_finance_dialog.py` | Finans kaydı oluştururken dosya_uuid kullanımı |
| `app/sync/sync_manager.py` | Sync sırasında UUID FK kullanımı |
| `app/sync/migration.py` | Migration scriptleri |

#### 2.2 Kod Değişiklik Örneği

**Önce (INTEGER FK):**
```python
# Finans kaydı oluştur
cursor.execute("""
    INSERT INTO finans (dosya_id, sozlesme_ucreti)
    VALUES (?, ?)
""", (dosya_id, ucret))
```

**Sonra (UUID FK):**
```python
# Önce dosyanın UUID'sini al
dosya_uuid = cursor.execute(
    "SELECT uuid FROM dosyalar WHERE id = ?", (dosya_id,)
).fetchone()[0]

# UUID ile kayıt oluştur
cursor.execute("""
    INSERT INTO finans (dosya_id, dosya_uuid, sozlesme_ucreti)
    VALUES (?, ?, ?)
""", (dosya_id, dosya_uuid, ucret))
```

#### 2.3 JOIN Sorguları Değişikliği

**Önce:**
```python
SELECT f.* FROM finans f
JOIN dosyalar d ON d.id = f.dosya_id
WHERE d.id = ?
```

**Sonra (Sync uyumlu):**
```python
SELECT f.* FROM finans f
JOIN dosyalar d ON d.uuid = f.dosya_uuid
WHERE d.uuid = ?
```

---

### AŞAMA 3: Sync Sistemi Değişiklikleri

#### 3.1 Sync Data Formatı

**Önce:**
```json
{
  "uuid": "abc-123",
  "table_name": "finans",
  "data": {
    "dosya_id": 1,
    "sozlesme_ucreti": 5000
  }
}
```

**Sonra:**
```json
{
  "uuid": "abc-123",
  "table_name": "finans",
  "data": {
    "dosya_uuid": "xyz-456",
    "sozlesme_ucreti": 5000
  }
}
```

#### 3.2 Sync Sıralaması (Önemli!)

Veri bütünlüğü için sıralama kritik:

```
1. users, statuses, custom_tabs (Level 0)
2. dosyalar, permissions (Level 1)
3. finans, attachments, dosya_atamalar, ... (Level 2)
4. odeme_plani, taksitler, masraflar (Level 3)
5. odeme_kayitlari (Level 4)
```

---

### AŞAMA 4: Sunucu Değişiklikleri

#### 4.1 sync_records Tablosu

Sunucuda `data` kolonunda INTEGER FK yerine UUID FK saklanacak.

#### 4.2 Büro Sıfırlama Endpoint'i

```python
@app.post("/api/admin/reset-sync")
def reset_sync_state(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Büronun sync durumunu sıfırla"""
    firm_id = user.firm_id

    # sync_records temizle
    db.query(SyncRecord).filter(SyncRecord.firm_id == firm_id).delete()

    # global_revision sıfırla
    db.query(GlobalRevision).filter(GlobalRevision.firm_id == firm_id).delete()

    db.commit()
    return {"success": True, "message": "Sync durumu sıfırlandı"}
```

---

### AŞAMA 5: Client Büro Sıfırlama

#### 5.1 Yeni Menü Seçenekleri

```
Büro Senkronizasyon Ayarları:
├── 🔧 Büro Kurulumu
├── 📤 Tüm Verileri Senkronize Et
├── 🔄 Sync Durumunu Sıfırla  ← YENİ
│   └── Lokal sync tablolarını temizler
│   └── Sunucudan tüm veriyi yeniden çeker
└── 🚪 Bürodan Ayrıl
```

#### 5.2 Sıfırlama Mantığı

```python
def reset_sync_state(self):
    """Sync durumunu sıfırla - tüm veriyi yeniden sync et"""
    conn = self._get_connection()
    try:
        # Lokal sync tablolarını temizle
        conn.execute("DELETE FROM sync_outbox")
        conn.execute("DELETE FROM sync_metadata WHERE id > 0")

        # Sunucuya sıfırlama isteği gönder
        self.client.reset_sync()

        # Tüm lokal verileri outbox'a ekle
        migration = SyncMigration(self.db_path)
        migration.seed_existing_data()

        # Full sync çalıştır
        self.full_sync()

        conn.commit()
    finally:
        conn.close()
```

---

## UYGULAMA SIRASI

```
┌─────────────────────────────────────────────────────────────────────┐
│ HAFTA 1: Veritabanı Hazırlığı                                       │
├─────────────────────────────────────────────────────────────────────┤
│ □ Migration script yaz (UUID FK kolonları ekle)                     │
│ □ UUID FK değerlerini doldur                                        │
│ □ İndeksler ekle                                                    │
│ □ Test: Mevcut veriler bozulmadı mı?                                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HAFTA 2: Kod Değişiklikleri                                         │
├─────────────────────────────────────────────────────────────────────┤
│ □ INSERT sorgularında UUID FK kullan                                │
│ □ JOIN sorgularında UUID FK kullan                                  │
│ □ Sync sisteminde UUID FK kullan                                    │
│ □ Test: Yeni kayıt ekleme çalışıyor mu?                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HAFTA 3: Sunucu ve Entegrasyon                                      │
├─────────────────────────────────────────────────────────────────────┤
│ □ Sunucu endpoint'lerini güncelle                                   │
│ □ Büro sıfırlama özelliği ekle                                      │
│ □ Yenile butonu ekle                                                │
│ □ Test: 2 bilgisayar arası tam sync testi                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## RİSKLER VE ÖNLEMLER

| Risk | Önlem |
|------|-------|
| Migration sırasında veri kaybı | Backup al, test ortamında dene |
| UUID NULL kalabilir | NOT NULL constraint SONRA ekle |
| Eski sorgular bozulabilir | Geçiş döneminde hem ID hem UUID destekle |
| Performans düşüşü | UUID kolonlarına index ekle |

---

## BAŞARI KRİTERLERİ

1. ✓ İki bilgisayar arası sync sorunsuz çalışıyor
2. ✓ Yeni dosya/kayıt ekleme FK hatası vermiyor
3. ✓ Büro sıfırlama sunucu verilerini silmeden çalışıyor
4. ✓ Sync süresi < 30 saniye (100 kayıt için)
5. ✓ Veri kaybı yok
