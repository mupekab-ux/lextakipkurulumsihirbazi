# -*- coding: utf-8 -*-
"""
İlk Senkronizasyon Scripti

Mevcut tüm verileri sunucuya gönderir.
"""

import sqlite3
import uuid
import json
from urllib.request import Request, urlopen
import ssl

# Ayarlar
DB_PATH = r"C:\Users\İpek\Documents\LexTakip\data.db"
SERVER_URL = "http://192.168.1.126:8000"
USERNAME = "admin"
PASSWORD = "Admin123!"

# SSL ayarı
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# Senkronize edilecek tablolar ve kolonları
TABLES = {
    'dosyalar': ['buro_takip_no', 'dosya_esas_no', 'muvekkil_adi', 'muvekkil_rolu',
                 'karsi_taraf', 'dosya_konusu', 'mahkeme_adi', 'dava_acilis_tarihi',
                 'durusma_tarihi', 'dava_durumu', 'is_tarihi', 'aciklama', 'is_archived'],
    'finans': ['dosya_id', 'sozlesme_ucreti', 'sozlesme_yuzdesi', 'sozlesme_ucreti_cents',
               'tahsil_hedef_cents', 'tahsil_edilen_cents', 'masraf_toplam_cents',
               'masraf_tahsil_cents', 'notlar', 'yuzde_is_sonu'],
    'taksitler': ['finans_id', 'vade_tarihi', 'tutar_cents', 'durum', 'odeme_tarihi', 'aciklama'],
    'odeme_kayitlari': ['finans_id', 'tarih', 'tutar_cents', 'yontem', 'aciklama'],
    'masraflar': ['finans_id', 'kalem', 'tutar_cents', 'tarih', 'tahsil_durumu', 'tahsil_tarihi', 'aciklama'],
    'tebligatlar': ['dosya_no', 'kurum', 'geldigi_tarih', 'teblig_tarihi', 'is_son_gunu', 'icerik'],
    'arabuluculuk': ['davaci', 'davali', 'arb_adi', 'arb_tel', 'toplanti_tarihi', 'toplanti_saati', 'konu'],
    'gorevler': ['tarih', 'konu', 'aciklama', 'atanan_kullanicilar', 'kaynak_turu',
                 'olusturan_kullanici', 'olusturma_zamani', 'tamamlandi', 'tamamlanma_zamani'],
    'muvekkil_kasasi': ['dosya_id', 'tarih', 'tutar_kurus', 'islem_turu', 'aciklama'],
}

def generate_uuid():
    return str(uuid.uuid4())

def ensure_uuids(conn):
    """Tüm tablolardaki kayıtlara UUID ata."""
    cur = conn.cursor()

    for table in TABLES.keys():
        cur.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cur.fetchall()]

        if 'uuid' not in columns:
            print(f"  {table}: uuid kolonu ekleniyor...")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN uuid TEXT")

        cur.execute(f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = ''")
        rows = cur.fetchall()

        for row in rows:
            new_uuid = generate_uuid()
            cur.execute(f"UPDATE {table} SET uuid = ? WHERE id = ?", (new_uuid, row[0]))

        if rows:
            print(f"  {table}: {len(rows)} kayda UUID atandı")

    conn.commit()
    print("UUID ataması tamamlandı.\n")

def build_id_uuid_maps(conn):
    """ID -> UUID eşleme tablolarını oluştur."""
    cur = conn.cursor()
    maps = {}

    # dosyalar tablosu için
    cur.execute("SELECT id, uuid FROM dosyalar WHERE uuid IS NOT NULL")
    maps['dosyalar'] = {row[0]: row[1] for row in cur.fetchall()}

    # finans tablosu için
    cur.execute("SELECT id, uuid FROM finans WHERE uuid IS NOT NULL")
    maps['finans'] = {row[0]: row[1] for row in cur.fetchall()}

    return maps

def get_all_data(conn, id_maps):
    """Tüm verileri al."""
    cur = conn.cursor()
    all_changes = []

    for table, columns in TABLES.items():
        cur.execute(f"PRAGMA table_info({table})")
        existing_cols = [row[1] for row in cur.fetchall()]

        valid_cols = [c for c in columns if c in existing_cols]

        if 'uuid' not in existing_cols:
            print(f"  {table}: uuid kolonu yok, atlanıyor")
            continue

        col_list = ', '.join(['uuid'] + valid_cols)
        cur.execute(f"SELECT {col_list} FROM {table}")
        rows = cur.fetchall()

        for row in rows:
            if not row[0]:
                continue

            data = {}
            for i, col in enumerate(valid_cols):
                val = row[i + 1]

                # Foreign key dönüşümleri
                if col == 'dosya_id' and val is not None:
                    # dosya_id -> dosya_uuid
                    try:
                        dosya_uuid = id_maps['dosyalar'].get(int(val))
                        data['dosya_uuid'] = dosya_uuid
                    except:
                        data['dosya_uuid'] = None
                elif col == 'finans_id' and val is not None:
                    # finans_id -> finans_uuid
                    try:
                        finans_uuid = id_maps['finans'].get(int(val))
                        data['finans_uuid'] = finans_uuid
                    except:
                        data['finans_uuid'] = None
                else:
                    data[col] = str(val) if val is not None else None

            all_changes.append({
                'table': table,
                'op': 'insert',
                'uuid': row[0],
                'data': data
            })

        print(f"  {table}: {len(rows)} kayıt")

    return all_changes

def login():
    """Sunucuya giriş yap."""
    data = json.dumps({
        "username": USERNAME,
        "password": PASSWORD,
        "device_id": "initial-sync"
    }).encode('utf-8')

    req = Request(
        f"{SERVER_URL}/api/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urlopen(req, timeout=30, context=SSL_CTX) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('success'):
                return result.get('token')
            else:
                print(f"Giriş hatası: {result.get('message')}")
                return None
    except Exception as e:
        print(f"Bağlantı hatası: {e}")
        return None

def sync(token, changes):
    """Değişiklikleri gönder."""
    data = json.dumps({
        "device_id": "initial-sync",
        "last_sync_revision": 0,
        "changes": changes
    }, ensure_ascii=False).encode('utf-8')

    req = Request(
        f"{SERVER_URL}/api/sync",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )

    try:
        with urlopen(req, timeout=120, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Sync hatası: {e}")
        return None

def main():
    print("=" * 50)
    print("LexTakip İlk Senkronizasyon")
    print("=" * 50)

    print(f"\n1. Veritabanına bağlanılıyor: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        print("   Bağlantı başarılı!")
    except Exception as e:
        print(f"   HATA: {e}")
        return

    print("\n2. UUID'ler kontrol ediliyor...")
    ensure_uuids(conn)

    print("3. ID-UUID eşlemeleri oluşturuluyor...")
    id_maps = build_id_uuid_maps(conn)
    print(f"   Dosya: {len(id_maps['dosyalar'])}, Finans: {len(id_maps['finans'])}")

    print("\n4. Veriler okunuyor...")
    changes = get_all_data(conn, id_maps)
    print(f"\n   Toplam {len(changes)} kayıt bulundu.\n")

    if not changes:
        print("Gönderilecek veri yok!")
        return

    print("5. Sunucuya bağlanılıyor...")
    token = login()
    if not token:
        print("   Giriş başarısız!")
        return
    print("   Giriş başarılı!")

    print(f"\n6. {len(changes)} kayıt gönderiliyor...")
    result = sync(token, changes)

    if result:
        if result.get('success'):
            print(f"\n   BAŞARILI!")
            print(f"   Yeni revision: {result.get('new_revision')}")
            print(f"   Mesaj: {result.get('message')}")
            if result.get('errors'):
                print(f"   Hatalar ({len(result.get('errors'))}):")
                for err in result.get('errors')[:5]:
                    print(f"   - {err}")
                if len(result.get('errors')) > 5:
                    print(f"   ... ve {len(result.get('errors')) - 5} hata daha")
        else:
            print(f"\n   HATA: {result.get('message')}")
    else:
        print("   Sync başarısız!")

    conn.close()
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
