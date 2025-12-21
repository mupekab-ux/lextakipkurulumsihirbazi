#!/usr/bin/env python3
"""
TakibiEsasi - Ekran Görüntüsü için Örnek Veri Oluşturucu
Bu script, uygulamanın profesyonel ekran görüntüleri için
gerçekçi Türk hukuk verisi oluşturur.
"""

import sqlite3
import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

# app klasörünü path'e ekle
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Veritabanı yolu
DB_PATH = SCRIPT_DIR / "data" / "takibiesasi.db"

# ============================================
# ÖRNEK VERİ HAVUZLARI
# ============================================

MUVEKKIL_ISIMLERI = [
    "Ahmet Yılmaz", "Mehmet Kaya", "Ayşe Demir", "Fatma Çelik", "Ali Şahin",
    "Mustafa Öztürk", "Zeynep Arslan", "Hüseyin Doğan", "Elif Koç", "İbrahim Aydın",
    "Hatice Yıldız", "Ömer Polat", "Emine Erdoğan", "Murat Can", "Hacer Korkmaz",
    "ABC İnşaat Ltd. Şti.", "XYZ Tekstil A.Ş.", "Güneş Otomotiv San. Tic. Ltd. Şti.",
    "Yıldız Gıda Pazarlama A.Ş.", "Ege Metal Sanayi Ltd. Şti.",
    "Anadolu Tarım Ürünleri A.Ş.", "İstanbul Lojistik Ltd. Şti.",
    "Marmara Mobilya San. Tic. A.Ş.", "Akdeniz Turizm Ltd. Şti."
]

KARSI_TARAF_ISIMLERI = [
    "Hasan Türk", "Hüsnü Aktaş", "Recep Güneş", "Necati Aslan", "Kadir Yalçın",
    "Süleyman Tekin", "Kemal Güler", "Orhan Özkan", "Turan Kılıç", "Cengiz Bulut",
    "Deniz Ticaret Ltd. Şti.", "Kuzey İnşaat A.Ş.", "Batı Tekstil San. Tic. Ltd. Şti.",
    "Doğu Gıda Pazarlama A.Ş.", "Güney Metal Sanayi Ltd. Şti.",
    "T.C. Sosyal Güvenlik Kurumu", "T.C. Maliye Bakanlığı", "Belediye Başkanlığı"
]

MAHKEMELER = [
    "İstanbul 1. Asliye Hukuk Mahkemesi",
    "İstanbul 2. Asliye Hukuk Mahkemesi",
    "İstanbul 3. Asliye Ticaret Mahkemesi",
    "İstanbul 5. İcra Hukuk Mahkemesi",
    "İstanbul 7. İş Mahkemesi",
    "İstanbul 12. Asliye Ceza Mahkemesi",
    "Ankara 1. Asliye Hukuk Mahkemesi",
    "Ankara 3. Ticaret Mahkemesi",
    "İzmir 2. Asliye Hukuk Mahkemesi",
    "Bursa 1. İcra Hukuk Mahkemesi",
    "Antalya 4. Asliye Hukuk Mahkemesi",
    "İstanbul Anadolu 6. Asliye Hukuk Mahkemesi",
    "İstanbul Anadolu 2. İcra Dairesi",
    "İstanbul 8. İcra Dairesi",
    "İstanbul 14. İcra Dairesi",
    "Kadıköy 3. İcra Dairesi",
    "Bakırköy 5. İcra Dairesi"
]

DOSYA_KONULARI = [
    "Alacak Davası", "İtirazın İptali", "Kira Alacağı", "Tahliye Davası",
    "İş Kazası Tazminatı", "Kıdem Tazminatı", "Boşanma Davası", "Velayet Davası",
    "Miras Taksimi", "Tapu İptali", "Trafik Kazası Tazminatı", "Haksız Fiil",
    "Sözleşmeden Kaynaklanan Alacak", "Çek İptali", "İflas Erteleme",
    "İcra Takibi", "Kambiyo Takibi", "Kira İcra Takibi", "Genel Haciz Yolu",
    "İlamlı İcra Takibi", "Rehnin Paraya Çevrilmesi"
]

# Sarı durumlar (ilk işlemler)
DAVA_DURUMLARI_SARI = [
    "Dava Açıldı", "Tensip Yapıldı", "Duruşma Bekleniyor", "Bilirkişiye Sevk Edildi",
    "Bilirkişi Raporu Bekleniyor", "İstinaf Başvurusu Yapıldı", "Temyiz Aşamasında",
    "Karar Bekleniyor", "Tebligat Bekleniyor", "Keşif Yapılacak"
]

# Turuncu durumlar (beklemede)
DAVA_DURUMLARI_TURUNCU = [
    "Beklemede", "Müvekkil Cevabı Bekleniyor", "Belge Bekleniyor",
    "Harç Yatırılacak", "Ödeme Bekleniyor"
]

# Yeşil durumlar (olumlu)
DAVA_DURUMLARI_YESIL = [
    "Dava Kazanıldı", "Anlaşma Sağlandı", "Tahsilat Yapıldı", "Dosya Kapandı"
]

# Kırmızı durumlar (olumsuz)
DAVA_DURUMLARI_KIRMIZI = [
    "Dava Kaybedildi", "Reddedildi", "Takipsizlik"
]

TEBLIGAT_KURUMLARI = [
    "İstanbul 8. İcra Dairesi", "İstanbul 14. İcra Dairesi",
    "Kadıköy 3. İcra Dairesi", "Bakırköy 5. İcra Dairesi",
    "Ankara 2. İcra Dairesi", "İstanbul 1. Asliye Hukuk Mahkemesi",
    "İstanbul Anadolu Adliyesi", "SGK İstanbul İl Müdürlüğü"
]

ARABULUCU_ISIMLERI = [
    "Av. Kemal Yıldırım", "Av. Serpil Acar", "Av. Osman Kara",
    "Av. Gülşen Demir", "Av. Burak Özdemir"
]

GOREV_KONULARI = [
    "Duruşmaya hazırlık", "Dilekçe hazırla", "Müvekkil ile görüşme",
    "Belge topla", "Bilirkişi raporunu incele", "İstinaf dilekçesi hazırla",
    "Harç yatır", "Dosya takibi", "Karşı taraf avukatı ile görüşme",
    "Tanık listesi hazırla", "Delil listesi hazırla", "Keşif için hazırlık"
]

ODEME_YONTEMLERI = ["Nakit", "Havale/EFT", "Kredi Kartı", "Çek"]

MASRAF_KALEMLERI = [
    "Harç", "Posta Masrafı", "Bilirkişi Ücreti", "Keşif Masrafı",
    "Yol Masrafı", "Fotokopi/Baskı", "Noter Masrafı", "Tercüme Ücreti"
]


def get_db_connection():
    """Veritabanı bağlantısı oluştur"""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables_manually(db_path):
    """Tabloları manuel olarak oluştur (app.db import edilemezse)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Dosyalar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dosyalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buro_takip_no INTEGER UNIQUE,
            dosya_esas_no TEXT,
            muvekkil_adi TEXT,
            muvekkil_rolu TEXT,
            karsi_taraf TEXT,
            dosya_konusu TEXT,
            mahkeme_adi TEXT,
            dava_acilis_tarihi DATE,
            durusma_tarihi DATE,
            dava_durumu TEXT,
            is_tarihi DATE,
            aciklama TEXT,
            tekrar_dava_durumu_2 TEXT,
            is_tarihi_2 DATE,
            aciklama_2 TEXT,
            is_archived INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Finans tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_id INTEGER UNIQUE,
            sozlesme_ucreti REAL,
            sozlesme_yuzdesi REAL,
            sozlesme_ucreti_cents INTEGER,
            tahsil_hedef_cents INTEGER NOT NULL DEFAULT 0,
            tahsil_edilen_cents INTEGER NOT NULL DEFAULT 0,
            masraf_toplam_cents INTEGER NOT NULL DEFAULT 0,
            masraf_tahsil_cents INTEGER NOT NULL DEFAULT 0,
            notlar TEXT,
            yuzde_is_sonu INTEGER NOT NULL DEFAULT 0,
            son_guncelleme DATETIME,
            FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
        )
    """)

    # Taksitler tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taksitler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finans_id INTEGER NOT NULL,
            sira INTEGER,
            tutar_cents INTEGER NOT NULL,
            vade_tarihi DATE,
            odendi INTEGER DEFAULT 0,
            odeme_tarihi DATE,
            FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE
        )
    """)

    # Masraflar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS masraflar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finans_id INTEGER NOT NULL,
            kalem TEXT NOT NULL,
            tutar_cents INTEGER NOT NULL,
            tarih DATE,
            odeme_kaynagi TEXT NOT NULL DEFAULT 'Büro',
            tahsil_durumu TEXT NOT NULL DEFAULT 'Bekliyor',
            tahsil_tarihi DATE,
            aciklama TEXT,
            FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE
        )
    """)

    # Tebligatlar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tebligatlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_no TEXT,
            kurum TEXT,
            tebligat_tarihi DATE,
            teslim_tarihi DATE,
            is_son_gunu DATE,
            icerik TEXT,
            notlar TEXT
        )
    """)

    # Arabuluculuk tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arabuluculuk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            davaci TEXT,
            davali TEXT,
            arabulucu TEXT,
            konu TEXT,
            toplanti_tarihi DATE,
            toplanti_saati TEXT,
            durum TEXT,
            notlar TEXT
        )
    """)

    # Görevler tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gorevler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            konu TEXT NOT NULL,
            aciklama TEXT,
            tamamlandi INTEGER DEFAULT 0,
            tamamlanma_tarihi DATETIME,
            dosya_id INTEGER,
            atanan_kullanici TEXT,
            kaynak TEXT DEFAULT 'manuel',
            FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE SET NULL
        )
    """)

    # Müvekkil kasası tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS muvekkil_kasasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            muvekkil_adi TEXT,
            islem_tipi TEXT,
            tutar_cents INTEGER,
            tarih DATE,
            aciklama TEXT
        )
    """)

    # Users tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT DEFAULT 'Kullanıcı',
            is_active INTEGER DEFAULT 1
        )
    """)

    # Statuses tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT UNIQUE,
            color_hex TEXT,
            sira INTEGER
        )
    """)

    # Custom tabs tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_tabs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Custom tabs - dosyalar ilişki tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_tabs_dosyalar (
            custom_tab_id INTEGER NOT NULL,
            dosya_id INTEGER NOT NULL,
            PRIMARY KEY (custom_tab_id, dosya_id),
            FOREIGN KEY (custom_tab_id) REFERENCES custom_tabs(id) ON DELETE CASCADE,
            FOREIGN KEY (dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
        )
    """)

    # Ayarlar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("  ✓ Tablolar manuel olarak oluşturuldu")


def random_date(start_year=2023, end_year=2025):
    """Rastgele tarih oluştur"""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")


def random_future_date(days_ahead_min=7, days_ahead_max=90):
    """Gelecekte rastgele tarih"""
    today = datetime.now()
    random_days = random.randint(days_ahead_min, days_ahead_max)
    return (today + timedelta(days=random_days)).strftime("%Y-%m-%d")


def random_past_date(days_ago_min=7, days_ago_max=180):
    """Geçmişte rastgele tarih"""
    today = datetime.now()
    random_days = random.randint(days_ago_min, days_ago_max)
    return (today - timedelta(days=random_days)).strftime("%Y-%m-%d")


def generate_esas_no(year=None):
    """Dosya esas numarası oluştur"""
    if year is None:
        year = random.choice([2023, 2024, 2025])
    num = random.randint(100, 9999)
    return f"{year}/{num} E."


def create_users(conn):
    """Kullanıcılar oluştur"""
    print("Kullanıcılar oluşturuluyor...")
    cursor = conn.cursor()

    users = [
        ("admin", "admin123", "Admin", 1),
        ("avukat1", "avukat123", "Yönetici Avukat", 1),
        ("stajyer", "stajyer123", "Kullanıcı", 1),
    ]

    for username, password, role, is_active in users:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?)
            """, (username, password, role, is_active))
        except:
            pass

    conn.commit()
    print(f"  ✓ {len(users)} kullanıcı oluşturuldu")


def create_statuses(conn):
    """Durum seçenekleri oluştur"""
    print("Durumlar oluşturuluyor...")
    cursor = conn.cursor()

    statuses = []
    # Sarı durumlar
    for s in DAVA_DURUMLARI_SARI:
        statuses.append((s, "#F59E0B"))  # Amber/Sarı
    # Turuncu durumlar
    for s in DAVA_DURUMLARI_TURUNCU:
        statuses.append((s, "#F97316"))  # Orange
    # Yeşil durumlar
    for s in DAVA_DURUMLARI_YESIL:
        statuses.append((s, "#22C55E"))  # Green
    # Kırmızı durumlar
    for s in DAVA_DURUMLARI_KIRMIZI:
        statuses.append((s, "#EF4444"))  # Red

    for ad, color in statuses:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO statuses (ad, color_hex)
                VALUES (?, ?)
            """, (ad, color))
        except:
            pass

    conn.commit()
    print(f"  ✓ {len(statuses)} durum oluşturuldu")


def create_custom_tabs(conn):
    """Özel sekmeler oluştur"""
    print("Özel sekmeler oluşturuluyor...")
    cursor = conn.cursor()

    tabs = ["Acil Dosyalar", "VIP Müvekkiller", "Tahsilat Bekleyen", "Bu Hafta Duruşma"]

    for tab_name in tabs:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO custom_tabs (name)
                VALUES (?)
            """, (tab_name,))
        except:
            pass

    conn.commit()
    print(f"  ✓ {len(tabs)} özel sekme oluşturuldu")


def create_dosyalar(conn, count=25):
    """Dosyalar oluştur"""
    print(f"{count} dosya oluşturuluyor...")
    cursor = conn.cursor()

    dosya_ids = []

    for i in range(1, count + 1):
        muvekkil = random.choice(MUVEKKIL_ISIMLERI)
        karsi_taraf = random.choice(KARSI_TARAF_ISIMLERI)
        mahkeme = random.choice(MAHKEMELER)
        konu = random.choice(DOSYA_KONULARI)

        # Durum seç - çoğunluk aktif durumda olsun
        all_statuses = DAVA_DURUMLARI_SARI + DAVA_DURUMLARI_TURUNCU
        if random.random() < 0.2:  # %20 kapanmış
            all_statuses = DAVA_DURUMLARI_YESIL + DAVA_DURUMLARI_KIRMIZI
        durum = random.choice(all_statuses)

        dava_tarihi = random_date(2023, 2024)
        durusma_tarihi = random_future_date(7, 60) if random.random() > 0.3 else None

        is_archived = 1 if durum in DAVA_DURUMLARI_KIRMIZI else 0

        cursor.execute("""
            INSERT INTO dosyalar (
                buro_takip_no, dosya_esas_no, muvekkil_adi, muvekkil_rolu,
                karsi_taraf, dosya_konusu, mahkeme_adi, dava_acilis_tarihi,
                durusma_tarihi, dava_durumu, is_archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            i, generate_esas_no(), muvekkil, random.choice(["Davacı", "Davalı"]),
            karsi_taraf, konu, mahkeme, dava_tarihi,
            durusma_tarihi, durum, is_archived
        ))

        dosya_ids.append(cursor.lastrowid)

    conn.commit()
    print(f"  ✓ {count} dosya oluşturuldu")
    return dosya_ids


def create_finans(conn, dosya_ids):
    """Finansal kayıtlar oluştur"""
    print("Finansal kayıtlar oluşturuluyor...")
    cursor = conn.cursor()

    for dosya_id in dosya_ids:
        # Her dosya için finans kaydı
        sozlesme_ucreti = random.choice([500000, 750000, 1000000, 1500000, 2000000, 3000000, 5000000])  # cents
        tahsil_hedef = random.choice([0, 5000000, 10000000, 25000000, 50000000, 100000000])
        tahsil_edilen = int(tahsil_hedef * random.uniform(0, 0.7)) if tahsil_hedef > 0 else 0

        cursor.execute("""
            INSERT OR IGNORE INTO finans (
                dosya_id, sozlesme_ucreti_cents, tahsil_hedef_cents, tahsil_edilen_cents
            ) VALUES (?, ?, ?, ?)
        """, (dosya_id, sozlesme_ucreti, tahsil_hedef, tahsil_edilen))

        finans_id = cursor.lastrowid

        # Taksitler oluştur (bazı dosyalar için)
        if random.random() > 0.4:
            taksit_sayisi = random.choice([3, 6, 9, 12])
            taksit_tutari = sozlesme_ucreti // taksit_sayisi

            for t in range(taksit_sayisi):
                vade = (datetime.now() + timedelta(days=30 * (t + 1))).strftime("%Y-%m-%d")
                odendi = 1 if t < taksit_sayisi // 2 else 0

                cursor.execute("""
                    INSERT INTO taksitler (finans_id, sira, tutar_cents, vade_tarihi, odendi)
                    VALUES (?, ?, ?, ?, ?)
                """, (finans_id, t + 1, taksit_tutari, vade, odendi))

        # Masraflar ekle
        masraf_sayisi = random.randint(0, 4)
        for _ in range(masraf_sayisi):
            kalem = random.choice(MASRAF_KALEMLERI)
            tutar = random.choice([5000, 10000, 15000, 25000, 50000, 75000, 100000])
            tahsil = random.choice(["Bekliyor", "Tahsil Edildi"])

            cursor.execute("""
                INSERT INTO masraflar (finans_id, kalem, tutar_cents, tarih, tahsil_durumu)
                VALUES (?, ?, ?, ?, ?)
            """, (finans_id, kalem, tutar, random_past_date(7, 90), tahsil))

    conn.commit()
    print(f"  ✓ {len(dosya_ids)} finansal kayıt oluşturuldu")


def create_tebligatlar(conn, count=15):
    """Tebligat kayıtları oluştur"""
    print("Tebligatlar oluşturuluyor...")
    cursor = conn.cursor()

    for _ in range(count):
        dosya_no = generate_esas_no()
        kurum = random.choice(TEBLIGAT_KURUMLARI)
        tebligat_tarihi = random_past_date(1, 30)
        teslim_tarihi = random_past_date(1, 14) if random.random() > 0.3 else None

        # Son gün hesapla (tebliğden 15 gün sonra gibi)
        if teslim_tarihi:
            teslim_dt = datetime.strptime(teslim_tarihi, "%Y-%m-%d")
            son_gun = (teslim_dt + timedelta(days=random.choice([7, 10, 15, 30]))).strftime("%Y-%m-%d")
        else:
            son_gun = random_future_date(7, 30)

        icerik = f"{kurum} tarafından gönderilen tebligat"

        cursor.execute("""
            INSERT INTO tebligatlar (dosya_no, kurum, tebligat_tarihi, teslim_tarihi, is_son_gunu, icerik)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dosya_no, kurum, tebligat_tarihi, teslim_tarihi, son_gun, icerik))

    conn.commit()
    print(f"  ✓ {count} tebligat oluşturuldu")


def create_arabuluculuk(conn, count=8):
    """Arabuluculuk kayıtları oluştur"""
    print("Arabuluculuk kayıtları oluşturuluyor...")
    cursor = conn.cursor()

    konular = [
        "İşçi-İşveren Uyuşmazlığı", "Kira Anlaşmazlığı", "Ticari Alacak",
        "Tüketici Uyuşmazlığı", "Aile Hukuku", "Ortaklık Anlaşmazlığı"
    ]

    for _ in range(count):
        davaci = random.choice(MUVEKKIL_ISIMLERI)
        davali = random.choice(KARSI_TARAF_ISIMLERI)
        arabulucu = random.choice(ARABULUCU_ISIMLERI)
        konu = random.choice(konular)

        cursor.execute("""
            INSERT INTO arabuluculuk (davaci, davali, arabulucu, konu, toplanti_tarihi, toplanti_saati)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (davaci, davali, arabulucu, konu, random_future_date(3, 45), f"{random.randint(9, 16)}:00"))

    conn.commit()
    print(f"  ✓ {count} arabuluculuk kaydı oluşturuldu")


def create_gorevler(conn, dosya_ids, count=20):
    """Görevler oluştur"""
    print("Görevler oluşturuluyor...")
    cursor = conn.cursor()

    for _ in range(count):
        konu = random.choice(GOREV_KONULARI)
        tarih = random_future_date(1, 30) if random.random() > 0.3 else random_past_date(1, 14)
        tamamlandi = 1 if random.random() < 0.3 else 0
        dosya_id = random.choice(dosya_ids) if random.random() > 0.2 else None

        cursor.execute("""
            INSERT INTO gorevler (tarih, konu, aciklama, tamamlandi, dosya_id)
            VALUES (?, ?, ?, ?, ?)
        """, (tarih, konu, f"{konu} için detaylı açıklama", tamamlandi, dosya_id))

    conn.commit()
    print(f"  ✓ {count} görev oluşturuldu")


def create_muvekkil_kasasi(conn, count=10):
    """Müvekkil kasası kayıtları oluştur"""
    print("Müvekkil kasası kayıtları oluşturuluyor...")
    cursor = conn.cursor()

    for _ in range(count):
        muvekkil = random.choice(MUVEKKIL_ISIMLERI)
        islem_tipi = random.choice(["Giriş", "Çıkış"])
        tutar = random.choice([100000, 250000, 500000, 1000000, 2500000])  # cents

        cursor.execute("""
            INSERT INTO muvekkil_kasasi (muvekkil_adi, islem_tipi, tutar_cents, tarih, aciklama)
            VALUES (?, ?, ?, ?, ?)
        """, (muvekkil, islem_tipi, tutar, random_past_date(1, 60), f"{islem_tipi} - {muvekkil}"))

    conn.commit()
    print(f"  ✓ {count} kasa hareketi oluşturuldu")


def assign_dosyalar_to_tabs(conn, dosya_ids):
    """Dosyaları özel sekmelere ata"""
    print("Dosyalar sekmelere atanıyor...")
    cursor = conn.cursor()

    # Sekme ID'lerini al
    cursor.execute("SELECT id FROM custom_tabs")
    tab_ids = [row[0] for row in cursor.fetchall()]

    if not tab_ids:
        return

    # Rastgele dosyaları rastgele sekmelere ata
    for dosya_id in random.sample(dosya_ids, min(len(dosya_ids), 15)):
        tab_id = random.choice(tab_ids)
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO custom_tabs_dosyalar (custom_tab_id, dosya_id)
                VALUES (?, ?)
            """, (tab_id, dosya_id))
        except:
            pass

    conn.commit()
    print("  ✓ Dosyalar sekmelere atandı")


def main():
    """Ana fonksiyon"""
    print("=" * 50)
    print("TakibiEsasi - Örnek Veri Oluşturucu")
    print("=" * 50)
    print()

    # Mevcut veritabanını yedekle
    if DB_PATH.exists():
        backup_path = DB_PATH.with_suffix(".db.backup")
        print(f"Mevcut veritabanı yedekleniyor: {backup_path}")
        import shutil
        shutil.copy(DB_PATH, backup_path)
        print()

    # Veritabanı klasörünü oluştur
    os.makedirs(DB_PATH.parent, exist_ok=True)

    # Önce tabloları oluştur (app/db.py'den init_db çağır)
    print("Veritabanı tabloları oluşturuluyor...")
    try:
        from app.db import init_db
        init_db(str(DB_PATH))
        print("  ✓ Tablolar oluşturuldu")
        print()
    except ImportError as e:
        print(f"  ⚠ app.db import edilemedi: {e}")
        print("  → Tabloları manuel oluşturmayı deniyorum...")
        create_tables_manually(DB_PATH)
        print()

    conn = get_db_connection()

    try:
        # Verileri oluştur
        create_users(conn)
        create_statuses(conn)
        create_custom_tabs(conn)
        dosya_ids = create_dosyalar(conn, count=25)
        create_finans(conn, dosya_ids)
        create_tebligatlar(conn, count=15)
        create_arabuluculuk(conn, count=8)
        create_gorevler(conn, dosya_ids, count=20)
        create_muvekkil_kasasi(conn, count=10)
        assign_dosyalar_to_tabs(conn, dosya_ids)

        print()
        print("=" * 50)
        print("✅ TÜM VERİLER BAŞARIYLA OLUŞTURULDU!")
        print("=" * 50)
        print()
        print(f"Veritabanı konumu: {DB_PATH}")
        print()
        print("Oluşturulan veriler:")
        print("  • 25 dosya (dava/icra)")
        print("  • 25 finansal kayıt (taksitler ve masraflar dahil)")
        print("  • 15 tebligat")
        print("  • 8 arabuluculuk kaydı")
        print("  • 20 görev")
        print("  • 10 müvekkil kasası hareketi")
        print("  • 4 özel sekme")
        print("  • 22+ durum seçeneği")
        print()

    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
