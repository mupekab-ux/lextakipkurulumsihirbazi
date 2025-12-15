#!/usr/bin/env python3
"""
Makine ID Tanılama Scripti
Bu script, makine ID'nin nasıl oluşturulduğunu gösterir.
"""

import subprocess
import platform
import hashlib
import uuid
import sys

def _get_cpu_id() -> str:
    """CPU kimliğini alır."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            cpu_id = result.stdout.strip()
            if cpu_id:
                return cpu_id
    except Exception as e:
        print(f"  ⚠ CPU ID alınamadı: {e}")
    return "UNKNOWN_CPU"


def _get_disk_serial() -> str:
    """Birincil disk seri numarasını alır."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -First 1).SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            serial = result.stdout.strip()
            if serial:
                return serial
    except Exception as e:
        print(f"  ⚠ Disk seri numarası alınamadı: {e}")
    return "UNKNOWN_DISK"


def _get_mac_address() -> str:
    """MAC adresini alır."""
    try:
        mac = uuid.getnode()
        mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        return mac_str
    except Exception as e:
        print(f"  ⚠ MAC adresi alınamadı: {e}")
        return "UNKNOWN_MAC"


def _get_windows_product_id() -> str:
    """Windows ürün kimliğini alır."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_OperatingSystem).SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            serial = result.stdout.strip()
            if serial:
                return serial
    except Exception as e:
        print(f"  ⚠ Windows ürün kimliği alınamadı: {e}")
    return ""


def main():
    print("=" * 60)
    print("TakibiEsasi - Makine ID Tanılama")
    print("=" * 60)
    print()

    print("Bileşenler toplanıyor...\n")

    cpu_id = _get_cpu_id()
    disk_serial = _get_disk_serial()
    mac_address = _get_mac_address()
    windows_id = _get_windows_product_id()
    computer_name = platform.node()

    print("BİLEŞENLER:")
    print("-" * 60)
    print(f"1. CPU ID:           {cpu_id}")
    print(f"2. Disk Serial:      {disk_serial}")
    print(f"3. MAC Address:      {mac_address}")
    print(f"4. Windows ID:       {windows_id}")
    print(f"5. Computer Name:    {computer_name}")
    print("-" * 60)
    print()

    # Birleştir
    components = [cpu_id, disk_serial, mac_address, windows_id, computer_name]
    combined = "|".join(c for c in components if c)

    print(f"Birleştirilmiş String:")
    print(f"  {combined}")
    print()

    # Hash oluştur
    machine_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    short_id = machine_id[:16].upper()
    formatted_short = f"{short_id[:4]}-{short_id[4:8]}-{short_id[8:12]}-{short_id[12:16]}"

    print("SONUÇ:")
    print("-" * 60)
    print(f"Tam Makine ID (64 karakter):")
    print(f"  {machine_id}")
    print()
    print(f"Kısa Makine ID (kullanıcıya gösterilen):")
    print(f"  {formatted_short}")
    print("-" * 60)
    print()

    # Lisans dosyasını kontrol et
    print("LİSANS DOSYASI KONTROLÜ:")
    print("-" * 60)

    try:
        from pathlib import Path
        import json

        if platform.system() == "Windows":
            config_dir = Path.home() / "AppData" / "Local" / "TakibiEsasi"
        else:
            config_dir = Path.home() / ".config" / "takibiesasi"

        license_file = config_dir / ".takibiesasi_license"

        if license_file.exists():
            with open(license_file, 'r', encoding='utf-8') as f:
                license_data = json.load(f)

            stored_machine_id = license_data.get("machine_id", "YOK")
            license_key = license_data.get("license_key", "YOK")

            print(f"Lisans dosyası: {license_file}")
            print(f"Lisans anahtarı: {license_key[:10]}...{license_key[-4:] if len(license_key) > 14 else license_key}")
            print(f"Kayıtlı Makine ID: {stored_machine_id}")
            print()

            if stored_machine_id == machine_id:
                print("✅ EŞLEŞME: Mevcut makine ID, kayıtlı ID ile AYNI")
            else:
                print("❌ UYUMSUZLUK: Makine ID'ler FARKLI!")
                print()
                print("Karşılaştırma:")
                print(f"  Mevcut:  {machine_id}")
                print(f"  Kayıtlı: {stored_machine_id}")
                print()
                print("ÇÖZÜM: Admin panelinden lisansı bu makine ID ile güncelleyin")
                print(f"       veya lisansı transfer edin.")
        else:
            print(f"Lisans dosyası bulunamadı: {license_file}")
            print("Henüz aktive edilmemiş.")
    except Exception as e:
        print(f"Lisans dosyası okunamadı: {e}")

    print("-" * 60)
    print()

    # 3 kez çalıştırıp tutarlılık kontrolü
    print("TUTARLILIK TESTİ (3 kez):")
    print("-" * 60)
    ids = []
    for i in range(3):
        components = [
            _get_cpu_id(),
            _get_disk_serial(),
            _get_mac_address(),
            _get_windows_product_id(),
            platform.node()
        ]
        combined = "|".join(c for c in components if c)
        mid = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        ids.append(mid)
        print(f"  Deneme {i+1}: {mid[:32]}...")

    if len(set(ids)) == 1:
        print("\n✅ Makine ID TUTARLI - Her seferinde aynı değer üretiliyor")
    else:
        print("\n❌ Makine ID TUTARSIZ - Farklı değerler üretiliyor!")
        print("   Bu soruna neden olan bileşeni tespit etmek gerekiyor.")

    print()
    input("Çıkmak için Enter'a basın...")


if __name__ == "__main__":
    main()
