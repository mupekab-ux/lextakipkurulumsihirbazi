# -*- coding: utf-8 -*-
"""
Lisans sorunlarını düzelten script.
Tüm yerel lisans dosyalarını temizler ve yeniden aktivasyona hazırlar.
"""

import os
import platform
from pathlib import Path
import sqlite3

def get_license_dir() -> Path:
    """Lisans dosyalarının bulunduğu dizini döndürür."""
    if platform.system() == "Windows":
        app_data = os.environ.get("APPDATA", "")
        local_app_data = os.environ.get("LOCALAPPDATA", "")

        # Olası konumları kontrol et
        possible_dirs = []
        if app_data:
            possible_dirs.append(Path(app_data) / "TakibiEsasi")
        if local_app_data:
            possible_dirs.append(Path(local_app_data) / "TakibiEsasi")
        possible_dirs.append(Path.home() / "TakibiEsasi")
        possible_dirs.append(Path.home() / ".takibiesasi")

        for d in possible_dirs:
            if d.exists():
                return d

        # Varsayılan
        if local_app_data:
            return Path(local_app_data) / "TakibiEsasi"
        return Path.home() / "TakibiEsasi"
    else:
        return Path.home() / ".config" / "takibiesasi"

def get_database_path() -> Path:
    """Veritabanı dosyasının yolunu döndürür."""
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return Path(local_app_data) / "TakibiEsasi" / "data.db"
        return Path.home() / "TakibiEsasi" / "data.db"
    else:
        return Path.home() / ".takibiesasi" / "data.db"

def show_local_license_content():
    """Yerel lisans dosyasının içeriğini gösterir."""
    license_dir = get_license_dir()
    license_file = license_dir / ".takibiesasi_license"

    if not license_file.exists():
        print(f"[--] Lisans dosyası bulunamadı: {license_file}")
        return None

    try:
        with open(license_file, 'r', encoding='utf-8') as f:
            encoded = f.read().strip()

        # Decode (reverse hex)
        unshuffled = encoded[::-1]
        import json
        json_str = bytes.fromhex(unshuffled).decode('utf-8')
        data = json.loads(json_str)

        print(f"\n=== YEREL LİSANS DOSYASI ===")
        print(f"Dosya: {license_file}")
        print(f"Lisans Anahtarı: {data.get('license_key', 'YOK')}")
        print(f"Kayıtlı Makine ID: {data.get('machine_id', 'YOK')[:32]}...")
        print(f"Aktivasyon Tarihi: {data.get('activation_date', 'YOK')}")
        return data
    except Exception as e:
        print(f"[HATA] Lisans dosyası okunamadı: {e}")
        return None

def clear_local_license_files():
    """Yerel lisans ve token dosyalarını siler."""
    license_dir = get_license_dir()

    files_to_delete = [
        ".takibiesasi_license",
        ".takibiesasi_token"
    ]

    deleted = []
    for filename in files_to_delete:
        file_path = license_dir / filename
        if file_path.exists():
            try:
                file_path.unlink()
                deleted.append(str(file_path))
                print(f"[OK] Silindi: {file_path}")
            except Exception as e:
                print(f"[HATA] Silinemedi: {file_path} - {e}")
        else:
            print(f"[--] Bulunamadı: {file_path}")

    return deleted

def clear_demo_table():
    """demo_info tablosundaki lisans bilgilerini temizler."""
    db_path = get_database_path()

    if not db_path.exists():
        print(f"[--] Veritabanı bulunamadı: {db_path}")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # demo_info tablosundaki lisans bilgilerini temizle
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demo_info'")
        if cur.fetchone():
            cur.execute("UPDATE demo_info SET license_key = NULL, activated_at = NULL, machine_id = NULL")
            conn.commit()
            print(f"[OK] demo_info tablosu temizlendi")
        else:
            print(f"[--] demo_info tablosu bulunamadı")

        conn.close()
        return True
    except Exception as e:
        print(f"[HATA] Veritabanı hatası: {e}")
        return False

def show_current_machine_id():
    """Mevcut makine ID'sini gösterir."""
    try:
        # license.py'den generate_machine_id fonksiyonunu kullan
        import sys
        sys.path.insert(0, str(Path(__file__).parent / "app"))

        from license import generate_machine_id, get_short_machine_id

        full_id = generate_machine_id()
        short_id = get_short_machine_id()

        print(f"\n=== MEVCUT MAKİNE ID ===")
        print(f"Kısa ID: {short_id}")
        print(f"Tam ID:  {full_id}")

        return full_id
    except Exception as e:
        print(f"[HATA] Makine ID alınamadı: {e}")
        return None

def main():
    print("=" * 60)
    print("TakibiEsasi Lisans Sorun Giderici")
    print("=" * 60)
    print()

    # 1. Mevcut makine ID'sini göster
    machine_id = show_current_machine_id()
    print()

    # 2. Yerel lisans dosyasının içeriğini göster
    license_data = show_local_license_content()
    print()

    # 3. Karşılaştırma
    if license_data and machine_id:
        stored_id = license_data.get("machine_id", "")
        if stored_id == machine_id:
            print("[OK] Makine ID'leri EŞLEŞİYOR!")
        else:
            print("[!!] SORUN TESPİT EDİLDİ: Makine ID'leri FARKLI!")
            print(f"     Yerel dosyadaki: {stored_id[:32]}...")
            print(f"     Mevcut:          {machine_id[:32]}...")
        print()

    # 4. Yerel lisans dosyalarını sil
    print("=== YEREL DOSYALARI TEMİZLE ===")
    clear_local_license_files()
    print()

    # 3. Demo tablosunu temizle
    print("=== DEMO TABLOSUNU TEMİZLE ===")
    clear_demo_table()
    print()

    # 4. Sunucu talimatları
    print("=" * 60)
    print("SONRAKİ ADIMLAR:")
    print("=" * 60)
    print()
    print("1. Sunucuda PostgreSQL'e bağlan:")
    print("   PGPASSWORD='TakibiEsasi2024!' psql -U takibiesasi_user -d takibiesasi_db -h localhost")
    print()
    print("2. Machine ID'yi temizle:")
    print("   UPDATE licenses SET machine_id = NULL, activated_at = NULL;")
    print()
    print("3. Uygulamayı yeniden başlat ve lisansı aktive et.")
    print()

    if machine_id:
        print("4. Sunucudaki lisansı bu makine ID ile eşleştirmek için:")
        print(f"   UPDATE licenses SET machine_id = '{machine_id}' WHERE license_key = 'XXXX-XXXX-XXXX-XXXX';")
        print("   (XXXX-XXXX-XXXX-XXXX yerine lisans anahtarınızı yazın)")

    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
