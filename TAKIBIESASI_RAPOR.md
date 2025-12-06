# TakibiEsasi - Kapsamlı Uygulama Raporu

**Tarih:** 6 Aralık 2025
**Versiyon:** 1.0.0
**Durum:** Aktif Geliştirme

---

## 1. GENEL BAKIŞ

### 1.1 Uygulama Tanımı

**TakibiEsasi**, Türk avukatlar ve hukuk büroları için geliştirilmiş profesyonel bir hukuki takip yazılımıdır. Masaüstü uygulaması olarak PyQt6 ve Python ile geliştirilmiş olup, dava takibi, icra takibi, finansal yönetim, tebligat takibi, arabuluculuk ve görev yönetimi gibi kapsamlı özellikler sunar.

### 1.2 Hedef Kitle

- Bireysel avukatlar
- Küçük ve orta ölçekli hukuk büroları
- Stajyer avukatlar
- Hukuk ofisi yöneticileri

### 1.3 Temel Değer Önerisi

- **Offline-First:** İnternet bağlantısı olmadan tam çalışabilme
- **Türkçe Arayüz:** Tamamen Türkçe, Türk hukuk sistemine uygun
- **Tek Uygulama:** Tüm hukuki süreçleri tek yerden yönetme
- **Güvenlik:** Şifreli veritabanı, rol tabanlı erişim kontrolü
- **Lisans Sistemi:** Makine bazlı lisanslama ile koruma

---

## 2. TEKNİK MİMARİ

### 2.1 Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| Masaüstü Uygulama | Python 3.12, PyQt6 |
| Veritabanı (Lokal) | SQLite3 (WAL mode) |
| Backend API | FastAPI (Python) |
| Veritabanı (Sunucu) | PostgreSQL |
| Kimlik Doğrulama | JWT Token + bcrypt |
| Web Sitesi | HTML5, CSS3, JavaScript |

### 2.2 Klasör Yapısı

```
lextakipkurulumsihirbazi/
├── app/                          # Masaüstü Uygulama
│   ├── main.py                  # Ana giriş noktası
│   ├── db.py                    # SQLite veritabanı katmanı
│   ├── models.py                # Veri modelleri
│   ├── license.py               # Lisans doğrulama
│   ├── ui_main.py               # Ana pencere (304KB)
│   ├── ui_edit_dialog.py        # Dosya düzenleme (88KB)
│   ├── ui_finance_dialog.py     # Finans yönetimi (76KB)
│   ├── ui_finans_harici_dialog.py # Harici finans (68KB)
│   ├── ui_settings_dialog.py    # Ayarlar (59KB)
│   ├── ui_tebligatlar_tab.py    # Tebligat takibi
│   ├── ui_arabuluculuk_tab.py   # Arabuluculuk
│   ├── ui_activation_dialog.py  # Lisans aktivasyonu
│   ├── ui_agreements_dialog.py  # Sözleşmeler
│   ├── ui_update_dialog.py      # Güncelleme
│   ├── ui_transfer_dialog.py    # Veri aktarımı
│   ├── services/                # İş mantığı servisleri
│   │   ├── dosya_service.py
│   │   ├── finans_service.py
│   │   ├── tebligat_service.py
│   │   ├── arabuluculuk_service.py
│   │   ├── export_service.py
│   │   └── user_service.py
│   └── themes/                  # 6 adet tema dosyası
├── server/                      # FastAPI Backend
│   ├── main.py                  # API sunucusu
│   ├── index.html               # Pazarlama sitesi
│   ├── admin.html               # Admin paneli
│   ├── download.html            # İndirme sayfası
│   └── favicon.svg              # Site ikonu
├── tests/                       # Birim testleri
└── assets/                      # Uygulama kaynakları
```

### 2.3 Veritabanı Şeması

#### Ana Tablolar

| Tablo | Açıklama | Kayıt Sayısı (Örnek) |
|-------|----------|---------------------|
| dosyalar | Dava/icra dosyaları | Ana tablo |
| finans | Dosya bazlı finansal kayıtlar | 1:1 dosyalar |
| taksitler | Ödeme taksitleri | N:1 finans |
| odeme_kayitlari | Ödeme geçmişi | N:1 finans |
| masraflar | Masraf kalemleri | N:1 finans |
| finans_harici | Dosya dışı finansal kayıtlar | Bağımsız |
| tebligatlar | Tebligat takibi | N:1 dosyalar |
| arabuluculuk | Arabuluculuk kayıtları | Bağımsız |
| gorevler | Görev/yapılacaklar | N:1 dosyalar |
| attachments | Dosya ekleri | N:1 dosyalar |
| users | Kullanıcı hesapları | Bağımsız |
| permissions | Rol izinleri | N:1 users |
| statuses | Durum tanımları | 50+ kayıt |
| custom_tabs | Özel sekmeler | Kullanıcı tanımlı |
| audit_log | Denetim kaydı | Otomatik |

#### Dosyalar Tablosu (Ana Tablo)

```sql
CREATE TABLE dosyalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buro_takip_no INTEGER UNIQUE,      -- Büro takip numarası
    dosya_esas_no TEXT,                -- Mahkeme esas no
    muvekkil_adi TEXT,                 -- Müvekkil adı
    muvekkil_rolu TEXT,                -- Davacı/Davalı/vs
    karsi_taraf TEXT,                  -- Karşı taraf
    dosya_konusu TEXT,                 -- Dava konusu
    mahkeme_adi TEXT,                  -- Mahkeme adı
    dava_acilis_tarihi TEXT,           -- Açılış tarihi
    durusma_tarihi TEXT,               -- Duruşma tarihi
    dava_durumu TEXT,                  -- Birincil durum
    is_tarihi TEXT,                    -- İş tarihi
    aciklama TEXT,                     -- Açıklama
    tekrar_dava_durumu_2 TEXT,         -- İkincil durum
    is_tarihi_2 TEXT,                  -- İkincil iş tarihi
    aciklama_2 TEXT,                   -- İkincil açıklama
    is_archived INTEGER DEFAULT 0,     -- Arşiv durumu
    created_at DATETIME,
    updated_at DATETIME
);
```

#### Finans Tablosu

```sql
CREATE TABLE finans (
    id INTEGER PRIMARY KEY,
    dosya_id INTEGER UNIQUE,
    sozlesme_ucreti_cents INTEGER,     -- Sabit ücret (kuruş)
    sozlesme_yuzdesi REAL,             -- Yüzde oranı
    tahsil_hedef_cents INTEGER,        -- Hedef tahsilat
    tahsil_edilen_cents INTEGER,       -- Tahsil edilen
    masraf_toplam_cents INTEGER,       -- Toplam masraf
    masraf_tahsil_cents INTEGER,       -- Tahsil edilen masraf
    yuzde_is_sonu INTEGER,             -- İş sonu yüzdesi
    notlar TEXT,
    FOREIGN KEY (dosya_id) REFERENCES dosyalar(id)
);
```

---

## 3. MEVCUT ÖZELLİKLER

### 3.1 Dava/Dosya Yönetimi

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Dosya Oluşturma | Yeni dava/icra dosyası açma | ✅ Tamamlandı |
| Dosya Düzenleme | Mevcut dosyayı güncelleme | ✅ Tamamlandı |
| Dosya Arama | Tüm alanlarda arama | ✅ Tamamlandı |
| Dosya Filtreleme | Durum, tarih, mahkeme bazlı | ✅ Tamamlandı |
| Dosya Arşivleme | Silmeden arşive taşıma | ✅ Tamamlandı |
| Dosya Silme | Kalıcı silme (izinli) | ✅ Tamamlandı |
| Özel Sekmeler | Kullanıcı tanımlı gruplar | ✅ Tamamlandı |
| Bağlı Dosyalar | Dosyalar arası ilişki | ✅ Tamamlandı |
| Dosya Ekleri | Belge/dosya ekleme | ✅ Tamamlandı |
| Durum Renklendirme | Kategoriye göre renk | ✅ Tamamlandı |
| İki Aşamalı Takip | Birincil ve ikincil durum | ✅ Tamamlandı |

#### Müvekkil Rolleri
- DVC (Davacı)
- DVL (Davalı)
- DAD (Davacı-Davalı)
- ALC (Alacaklı)
- BRC (Borçlu)
- SNK (Sanık)
- MGD (Mağdur)
- MÜD (Müdahil)
- ŞPH (Şüpheli)
- VEK (Vekil)

#### Durum Kategorileri (50+ Durum)
- **SARI (Sarı):** Beklemede, devam eden işler
- **TURUNCU (Turuncu):** Dikkat gerektiren durumlar
- **GARIP_TURUNCU (Kahverengi):** Özel durumlar
- **KIRMIZI (Kırmızı):** Acil/kritik durumlar

### 3.2 Finansal Yönetim

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Sözleşme Ücreti | Sabit ücret tanımlama | ✅ Tamamlandı |
| Yüzde Ücreti | Tahsilat yüzdesi | ✅ Tamamlandı |
| İş Sonu Yüzdesi | Ertelemeli yüzde | ✅ Tamamlandı |
| Taksit Planı | Otomatik taksit oluşturma | ✅ Tamamlandı |
| Ödeme Kayıtları | Ödeme takibi | ✅ Tamamlandı |
| Kısmi Ödeme | Taksitlere dağıtım | ✅ Tamamlandı |
| Masraf Takibi | Masraf kalemi ekleme | ✅ Tamamlandı |
| Masraf Tahsilatı | Tahsil durumu takibi | ✅ Tamamlandı |
| Harici Finans | Dosya dışı kayıtlar | ✅ Tamamlandı |
| Bakiye Hesaplama | Otomatik hesaplama | ✅ Tamamlandı |
| Finans Özeti | Tüm dosyaların özeti | ✅ Tamamlandı |

#### Ödeme Yöntemleri
- Nakit
- Havale/EFT
- Kredi Kartı
- Çek
- Senet
- Diğer

#### Taksit Periyotları
- Günlük
- Haftalık
- Aylık
- 2 Aylık
- 3 Aylık
- 6 Aylık
- Yıllık
- Özel

### 3.3 Tebligat Takibi

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Tebligat Ekleme | Yeni tebligat kaydı | ✅ Tamamlandı |
| Kurum Takibi | Gönderen kurum | ✅ Tamamlandı |
| Tarih Takibi | Geliş ve tebliğ tarihi | ✅ Tamamlandı |
| Son Gün Hesaplama | İş son günü | ✅ Tamamlandı |
| Otomatik Görev | Görev oluşturma | ✅ Tamamlandı |
| Tamamlama | İşlem tamamlama | ✅ Tamamlandı |
| Filtreleme | Tarih bazlı filtre | ✅ Tamamlandı |

### 3.4 Arabuluculuk Takibi

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Toplantı Kaydı | Arabuluculuk toplantısı | ✅ Tamamlandı |
| Taraf Bilgileri | Davacı/davalı | ✅ Tamamlandı |
| Arabulucu Bilgisi | Ad ve iletişim | ✅ Tamamlandı |
| Tarih/Saat | Toplantı zamanı | ✅ Tamamlandı |
| Otomatik Görev | Görev oluşturma | ✅ Tamamlandı |
| Tamamlama | Süreç tamamlama | ✅ Tamamlandı |

### 3.5 Görev Yönetimi

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Manuel Görev | Kullanıcı görevi | ✅ Tamamlandı |
| Otomatik Görev | Durum değişikliğinden | ✅ Tamamlandı |
| Tebligat Görevi | Tebligattan otomatik | ✅ Tamamlandı |
| Arabuluculuk Görevi | Arabuluculuktan otomatik | ✅ Tamamlandı |
| Takvim Görünümü | Aylık takvim | ✅ Tamamlandı |
| Görev Atama | Kullanıcıya atama | ✅ Tamamlandı |
| Tamamlama | Görev kapatma | ✅ Tamamlandı |
| Tarih Filtreleme | Bugün/Hafta/Ay | ✅ Tamamlandı |

#### Görev Türleri
- `MANUEL` - Kullanıcı tarafından oluşturulan
- `IS_TARIHI` - Birincil iş tarihinden
- `IS_TARIHI_2` - İkincil iş tarihinden
- `TEBLIGAT` - Tebligattan otomatik
- `ARABULUCULUK` - Arabuluculuktan otomatik

### 3.6 Kullanıcı Yönetimi

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Kullanıcı Ekleme | Yeni hesap | ✅ Tamamlandı |
| Rol Atama | 4 farklı rol | ✅ Tamamlandı |
| Şifre Yönetimi | bcrypt şifreleme | ✅ Tamamlandı |
| Hesap Durumu | Aktif/Pasif | ✅ Tamamlandı |
| Dosya Atama | Kullanıcıya dosya | ✅ Tamamlandı |
| İzin Yönetimi | Granüler izinler | ✅ Tamamlandı |

#### Roller ve İzinler

| Rol | Tüm Dosyalar | Kullanıcı Yönetimi | Finans | Kalıcı Silme | Yedekleme |
|-----|--------------|-------------------|--------|--------------|-----------|
| Kurucu Avukat (Admin) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Yönetici Avukat | ✅ | ❌ | ✅ | ❌ | ❌ |
| Avukat | ❌ (atanan) | ❌ | ❌ | ❌ | ❌ |
| Stajyer | ❌ (atanan) | ❌ | ❌ | ❌ | ❌ |

### 3.7 Raporlama ve Dışa Aktarım

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Excel Export | XLSX formatında | ✅ Tamamlandı |
| PDF Export | Raporlama | ✅ Tamamlandı |
| Word Export | DOCX formatında | ✅ Tamamlandı |
| CSV Export | Basit tablo | ✅ Tamamlandı |
| Seçici Export | Kolon/satır seçimi | ✅ Tamamlandı |
| Finans Raporu | Finansal özet | ✅ Tamamlandı |
| Dosya Listesi | Filtrelenmiş liste | ✅ Tamamlandı |

### 3.8 Sistem Özellikleri

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Otomatik Yedekleme | Başlangıçta yedek | ✅ Tamamlandı |
| Manuel Yedekleme | İstenildiğinde | ✅ Tamamlandı |
| Yedek Saklama | N adet yedek tutma | ✅ Tamamlandı |
| Şifreli Yedek | Şifreli export | ✅ Tamamlandı |
| 6 Tema | Açık/koyu temalar | ✅ Tamamlandı |
| Denetim Kaydı | Tüm işlem geçmişi | ✅ Tamamlandı |
| Lisans Sistemi | Makine bazlı | ✅ Tamamlandı |
| Güncelleme Kontrolü | Otomatik kontrol | ✅ Tamamlandı |

#### Temalar
1. Varsayılan (Açık)
2. Koyu
3. Mavi
4. Pastel
5. Koyu Gri
6. Koyu Mavi

### 3.9 Lisans ve Güvenlik

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Makine ID | CPU/MAC/UUID bazlı | ✅ Tamamlandı |
| Online Aktivasyon | API üzerinden | ✅ Tamamlandı |
| Lisans Transferi | Max 2 transfer | ✅ Tamamlandı |
| Lisans Doğrulama | Başlangıçta kontrol | ✅ Tamamlandı |
| Şifre Koruması | bcrypt hashing | ✅ Tamamlandı |
| Rol Bazlı Erişim | RBAC | ✅ Tamamlandı |

---

## 4. SUNUCU / API (BACKEND)

### 4.1 Sunucu Bilgileri

| Özellik | Değer |
|---------|-------|
| Sunucu | DigitalOcean VPS |
| IP Adresi | 165.22.79.15 |
| Framework | FastAPI |
| Veritabanı | PostgreSQL |
| Port | 8000 |
| Domain | takibiesasi.com |

### 4.2 API Endpoint'leri

#### Genel API'ler (Public)

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/activate` | POST | Lisans aktivasyonu |
| `/api/verify` | POST | Lisans doğrulama |
| `/api/transfer` | POST | Lisans transferi |
| `/api/check-update` | POST | Güncelleme kontrolü |
| `/api/releases/latest` | GET | Son sürüm bilgisi |
| `/api/site/settings` | GET | Site ayarları |
| `/api/site/pricing` | GET | Fiyatlandırma |
| `/api/site/features` | GET | Özellikler |
| `/api/site/testimonials` | GET | Müşteri yorumları |
| `/api/site/faq` | GET | SSS |
| `/api/contact` | POST | İletişim formu |

#### Admin API'leri (JWT Gerekli)

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/admin/login` | POST | Admin girişi |
| `/api/admin/stats` | GET | Dashboard istatistikleri |
| `/api/admin/licenses` | GET | Tüm lisanslar |
| `/api/admin/license/create` | POST | Yeni lisans |
| `/api/admin/license/toggle` | POST | Lisans aç/kapa |
| `/api/admin/releases` | GET | Sürüm listesi |
| `/api/admin/release/publish` | POST | Sürüm yayınla |
| `/api/admin/upload` | POST | Dosya yükle |
| `/api/admin/pricing/*` | CRUD | Fiyat yönetimi |
| `/api/admin/features/*` | CRUD | Özellik yönetimi |
| `/api/admin/testimonials/*` | CRUD | Yorum yönetimi |
| `/api/admin/faq/*` | CRUD | SSS yönetimi |
| `/api/admin/screenshots/*` | CRUD | Ekran görüntüleri |

### 4.3 Veritabanı Tabloları (PostgreSQL)

| Tablo | Açıklama |
|-------|----------|
| licenses | Lisans anahtarları |
| site_settings | Site ayarları |
| pricing_plans | Fiyat planları |
| testimonials | Müşteri yorumları |
| faq | SSS kayıtları |
| announcements | Duyurular |
| features | Özellik listesi |
| screenshots | Galeri görselleri |
| media | Medya dosyaları |
| contact_messages | İletişim mesajları |

---

## 5. WEB SİTESİ

### 5.1 Sayfalar

| Sayfa | URL | Açıklama |
|-------|-----|----------|
| Ana Sayfa | / | Pazarlama sitesi |
| İndir | /download | İndirme sayfası |
| Admin | /admin | Yönetim paneli |

### 5.2 Tasarım

- **Tema:** Koyu (#0A0A0F arka plan)
- **Vurgu Rengi:** Altın/Amber gradyan (#FBBF24 → #D97706)
- **Animasyonlar:** Floating orbs, sparkles, grid pattern
- **Responsive:** Tüm cihazlara uyumlu
- **Font:** Sora, DM Sans, Instrument Serif

### 5.3 İçerik Yönetimi (CMS)

Admin panelinden yönetilebilen içerikler:
- Özellikler listesi
- Fiyatlandırma planları
- Müşteri yorumları
- SSS
- Ekran görüntüleri
- Site ayarları
- Duyurular

---

## 6. PLANLANAN ÖZELLİKLER

### 6.1 Kısa Vadeli (1-3 Ay)

| Özellik | Öncelik | Durum |
|---------|---------|-------|
| Code Signing | Yüksek | Beklemede |
| SEO Optimizasyonu | Yüksek | Planlandı |
| Gerçek Ekran Görüntüleri | Yüksek | Planlandı |
| Google Search Console | Orta | Planlandı |
| E-posta Bildirimleri | Orta | Planlandı |

### 6.2 Orta Vadeli (3-6 Ay)

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Kullanıcı Kayıt Sistemi | Web üzerinden kayıt | Planlandı |
| Ödeme Entegrasyonu | iyzico/PayTR | Planlandı |
| Abonelik Sistemi | Aylık/yıllık planlar | Planlandı |
| Canlı Destek | Tawk.to entegrasyonu | Planlandı |
| Video Eğitimler | Kullanım kılavuzları | Planlandı |

### 6.3 Uzun Vadeli (6-12 Ay)

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Mobil Uygulama | iOS/Android | Planlandı |
| UYAP Entegrasyonu | Resmi API (varsa) | Araştırılıyor |
| Detaylı Raporlama | İstatistik modülü | Planlandı |
| Çoklu Dil Desteği | İngilizce | Planlandı |

---

## 7. BÜRO TÜRÜ - ÇOKLU KULLANICI SENKRONİZASYONU

### 7.1 Genel Bakış

Büro türü sürüm, birden fazla bilgisayarda çalışan TakibiEsasi uygulamalarının verilerini merkezi bir sunucu (Raspberry Pi veya VPS) üzerinden senkronize etmesini sağlayacak.

### 7.2 Mimari

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

### 7.3 Temel Prensipler

| Prensip | Açıklama |
|---------|----------|
| Offline-First | İnternet olmadan tam çalışma |
| UUID Tabanlı | Her kayıt benzersiz UUID ile |
| Outbox Pattern | Değişiklikler önce lokale, sonra sunucuya |
| Last-Write-Wins | Çakışmalarda son yazan kazanır |
| Revision Numaraları | Artımlı senkronizasyon |

### 7.4 Senkronizasyon Tabloları

```sql
-- Her senkronize tabloya eklenecek
uuid VARCHAR(36) PRIMARY KEY,
firm_id VARCHAR(36) NOT NULL,
revision INTEGER DEFAULT 1,
is_deleted BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP,
updated_at TIMESTAMP
```

### 7.5 Senkronize Edilecek Tablolar

- dosyalar
- finans
- taksitler
- odeme_kayitlari
- masraflar
- muvekkil_kasasi
- tebligatlar
- arabuluculuk
- gorevler
- users

### 7.6 Sync API Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/health` | GET | Sunucu durumu |
| `/api/setup` | POST | İlk kurulum |
| `/api/login` | POST | Giriş, token alma |
| `/api/sync` | POST | Senkronizasyon |

### 7.7 Sync Request/Response

```json
// Request
{
    "device_id": "abc-123",
    "last_sync_revision": 42,
    "changes": [
        {
            "table": "dosyalar",
            "op": "insert",
            "uuid": "xxx-yyy",
            "data": {...}
        }
    ]
}

// Response
{
    "success": true,
    "new_revision": 45,
    "changes": [...],
    "errors": []
}
```

### 7.8 Kurulum Gereksinimleri

**Sunucu (Raspberry Pi / VPS):**
- PostgreSQL
- Python 3.x + FastAPI
- Uvicorn
- Sabit IP veya DDNS

**İstemci Değişiklikleri:**
- Tüm tablolara UUID kolonu
- sync_outbox tablosu
- sync_metadata tablosu
- Sync UI dialog

---

## 8. SATIŞ VE PAZARLAMA STRATEJİSİ

### 8.1 Pazarlama Kanalları

| Kanal | Strateji | Durum |
|-------|----------|-------|
| SEO | Google optimizasyonu | Planlandı |
| Google Ads | Anahtar kelime reklamları | Planlandı |
| Sosyal Medya | LinkedIn, Twitter | Planlandı |
| Baro Dernekleri | İşbirliği | Planlandı |
| Referans Programı | Tavsiye sistemi | Planlandı |
| E-posta Pazarlama | Hukuk bürosu listeleri | Planlandı |

### 8.2 Fiyatlandırma Modeli (Taslak)

| Plan | Aylık | Yıllık | Özellikler |
|------|-------|--------|------------|
| Bireysel | ₺XXX | ₺XXX | 1 kullanıcı, temel özellikler |
| Profesyonel | ₺XXX | ₺XXX | 3 kullanıcı, tüm özellikler |
| Büro | ₺XXX | ₺XXX | Sınırsız kullanıcı, senkronizasyon |

### 8.3 Deneme Sürümü

- 14 gün ücretsiz deneme
- Tüm özelliklere erişim
- Kredi kartı gerektirmez
- Otomatik lisans aktivasyonu

---

## 9. FATURA VE ÖDEME SİSTEMİ

### 9.1 Ödeme Entegrasyonu Seçenekleri

| Platform | Özellikler | Komisyon |
|----------|------------|----------|
| iyzico | Türkiye'de yaygın, kolay entegrasyon | %2.79 + ₺0.25 |
| PayTR | Sanal POS, taksit | %2.49 + ₺0.30 |
| Stripe | Global, güçlü API | %2.9 + ₺0.30 |

### 9.2 Fatura Kesimi

| Yöntem | Açıklama |
|--------|----------|
| Şahıs Şirketi | Basit usul, gelir vergisi |
| Limited Şirket | Kurumlar vergisi, e-fatura zorunlu |
| E-Fatura Platformları | Paraşüt, Logo, Luca |

### 9.3 E-Fatura Entegrasyonu

- Ödeme sonrası otomatik fatura
- PDF fatura e-posta ile gönderim
- Fatura arşivleme
- Muhasebe entegrasyonu

---

## 10. İLETİŞİM VE DESTEK

### 10.1 İletişim Kanalları

| Kanal | Bilgi |
|-------|-------|
| E-posta | destek@takibiesasi.com |
| Web Sitesi | takibiesasi.com |
| Admin Panel | takibiesasi.com/admin |

### 10.2 Destek Planı

- E-posta destek (7/24)
- Bilgi bankası / SSS
- Video eğitimler
- Canlı destek (ileride)

---

## 11. TEKNİK METRİKLER

### 11.1 Kod İstatistikleri

| Dosya | Boyut | Satır (Tahmini) |
|-------|-------|-----------------|
| ui_main.py | 304 KB | ~9,000 |
| ui_edit_dialog.py | 88 KB | ~2,500 |
| ui_finance_dialog.py | 76 KB | ~2,200 |
| ui_finans_harici_dialog.py | 68 KB | ~2,000 |
| ui_settings_dialog.py | 59 KB | ~1,700 |
| db.py | ~150 KB | ~4,600 |
| models.py | ~150 KB | ~4,500 |
| server/main.py | ~50 KB | ~1,500 |
| **Toplam** | **~1 MB+** | **~30,000+** |

### 11.2 Veritabanı Performansı

- WAL mode aktif
- 200 MB cache
- Memory-mapped I/O (256 MB)
- Foreign key constraints
- Index optimizasyonu

---

## 12. SONUÇ

TakibiEsasi, Türk hukuk büroları için kapsamlı bir dava takip ve yönetim çözümüdür. Mevcut haliyle:

**Güçlü Yönler:**
- Tam Türkçe arayüz ve içerik
- Offline çalışabilme
- Kapsamlı finansal yönetim
- Rol tabanlı erişim kontrolü
- Çoklu tema desteği
- Profesyonel dışa aktarım

**Geliştirilecek Alanlar:**
- Çoklu kullanıcı senkronizasyonu (Büro türü)
- Mobil uygulama
- Ödeme entegrasyonu
- SEO ve pazarlama

**Öncelikli Hedefler:**
1. Ekran görüntülerini güncelleme
2. Code signing tamamlama
3. SEO optimizasyonu
4. Google Search Console kaydı
5. Satış stratejisi uygulama

---

**Rapor Sonu**

*Bu rapor TakibiEsasi uygulamasının mevcut durumunu, özelliklerini ve gelecek planlarını kapsamaktadır.*
