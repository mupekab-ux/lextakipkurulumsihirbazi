#!/usr/bin/env python3
"""
Makine ID Tanilama Scripti (V2)
Bu script, makine ID'nin nasil olusturuldugunu gosterir.
V1 ve V2 algoritmalarini karsilastirir.
"""

import subprocess
import platform
import hashlib
import uuid
import sys
import os
import json

# =============================================================================
# V2 BILESENLERI (YENI - STABIL)
# =============================================================================

def _get_motherboard_uuid() -> str:
    """Anakart UUID'sini alir - EN STABIL bilesen."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            uuid_val = result.stdout.strip()
            invalid_uuids = [
                "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
                "00000000-0000-0000-0000-000000000000",
                ""
            ]
            if uuid_val and uuid_val not in invalid_uuids:
                return uuid_val
    except Exception as e:
        print(f"  ! Motherboard UUID alinamadi: {e}")
    return ""


def _get_baseboard_serial() -> str:
    """Anakart seri numarasini alir."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_BaseBoard).SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            serial = result.stdout.strip()
            invalid_serials = ["To Be Filled By O.E.M.", "Default string", ""]
            if serial and serial not in invalid_serials:
                return serial
    except Exception as e:
        print(f"  ! Baseboard serial alinamadi: {e}")
    return ""


def _get_cpu_id() -> str:
    """CPU kimligini alir."""
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
        print(f"  ! CPU ID alinamadi: {e}")
    return "UNKNOWN_CPU"


def _get_windows_product_id() -> str:
    """Windows urun kimligini alir."""
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
        print(f"  ! Windows urun kimligi alinamadi: {e}")
    return ""


# =============================================================================
# V1 BILESENLERI (ESKI - SORUNLU)
# =============================================================================

def _get_disk_serial_v1() -> str:
    """Birincil disk seri numarasini alir (SORUNLU - disk sirasi degisebilir)."""
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
        print(f"  ! Disk seri numarasi alinamadi: {e}")
    return "UNKNOWN_DISK"


def _get_mac_address_v1() -> str:
    """MAC adresini alir (SORUNLU - rastgele deger donebilir)."""
    try:
        mac = uuid.getnode()
        # 8. bit 1 ise rastgele uretilmis demektir
        is_random = (mac >> 40) & 1
        mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        if is_random:
            return f"{mac_str} (RASTGELE!)"
        return mac_str
    except Exception as e:
        print(f"  ! MAC adresi alinamadi: {e}")
        return "UNKNOWN_MAC"


def generate_machine_id_v2() -> str:
    """V2 Machine ID - Stabil bilesenleri kullanir."""
    components = []

    mb_uuid = _get_motherboard_uuid()
    if mb_uuid:
        components.append(mb_uuid)

    bb_serial = _get_baseboard_serial()
    if bb_serial:
        components.append(bb_serial)

    cpu_id = _get_cpu_id()
    if cpu_id and cpu_id != "UNKNOWN_CPU":
        components.append(cpu_id)

    win_id = _get_windows_product_id()
    if win_id:
        components.append(win_id)

    if not components:
        components.append(platform.node())

    combined = "|".join(c for c in components if c)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def generate_machine_id_v1() -> str:
    """V1 Machine ID - Eski algoritma (sorunlu bilesenleri icerir)."""
    mac = _get_mac_address_v1()
    if " " in mac:  # "(RASTGELE!)" kismini cikar
        mac = mac.split(" ")[0]
    components = [
        _get_cpu_id(),
        _get_disk_serial_v1(),
        mac,
        _get_windows_product_id(),
        platform.node(),
    ]
    combined = "|".join(c for c in components if c)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def main():
    print("=" * 70)
    print("TakibiEsasi - Makine ID Tanilama (V2)")
    print("=" * 70)
    print()

    print("V2 BILESENLERI (STABIL - DEGISMEZ):")
    print("-" * 70)

    mb_uuid = _get_motherboard_uuid()
    bb_serial = _get_baseboard_serial()
    cpu_id = _get_cpu_id()
    win_id = _get_windows_product_id()

    print(f"1. Motherboard UUID:    {mb_uuid or '(alinamadi)'}")
    print(f"2. Baseboard Serial:    {bb_serial or '(alinamadi)'}")
    print(f"3. CPU ID:              {cpu_id}")
    print(f"4. Windows Product ID:  {win_id or '(alinamadi)'}")
    print(f"5. Bilgisayar Adi:      {platform.node()}")
    print()

    print("V1 BILESENLERI (ESKI - SORUNLU):")
    print("-" * 70)

    disk_serial = _get_disk_serial_v1()
    mac_address = _get_mac_address_v1()

    print(f"* Disk Serial:          {disk_serial} (Sorunlu: disk sirasi degisebilir)")
    print(f"* MAC Address:          {mac_address} (Sorunlu: rastgele olabilir)")
    print()

    # ID'leri hesapla
    machine_id_v2 = generate_machine_id_v2()
    machine_id_v1 = generate_machine_id_v1()

    short_v2 = machine_id_v2[:16].upper()
    short_v1 = machine_id_v1[:16].upper()
    formatted_v2 = f"{short_v2[:4]}-{short_v2[4:8]}-{short_v2[8:12]}-{short_v2[12:16]}"
    formatted_v1 = f"{short_v1[:4]}-{short_v1[4:8]}-{short_v1[8:12]}-{short_v1[12:16]}"

    print("HESAPLANAN MAKINE ID'LERI:")
    print("-" * 70)
    print(f"V2 (YENI - STABIL):")
    print(f"  Tam:   {machine_id_v2}")
    print(f"  Kisa:  {formatted_v2}")
    print()
    print(f"V1 (ESKI - SORUNLU):")
    print(f"  Tam:   {machine_id_v1}")
    print(f"  Kisa:  {formatted_v1}")
    print()

    if machine_id_v1 != machine_id_v2:
        print("! NOT: V1 ve V2 ID'leri FARKLI. Bu beklenen bir durumdur.")
        print("       V1 ile kaydedilmis lisanslar otomatik olarak V2'ye migrate edilir.")
    print()

    # Lisans dosyasini kontrol et
    print("LISANS DOSYASI KONTROLU:")
    print("-" * 70)

    try:
        from pathlib import Path

        if platform.system() == "Windows":
            possible_dirs = [
                Path(os.environ.get("APPDATA", "")) / "TakibiEsasi",
                Path(os.environ.get("LOCALAPPDATA", "")) / "TakibiEsasi",
            ]
        else:
            possible_dirs = [
                Path.home() / ".config" / "takibiesasi",
            ]

        license_found = False
        for config_dir in possible_dirs:
            license_file = config_dir / ".takibiesasi_license"
            if license_file.exists():
                license_found = True
                print(f"Lisans dosyasi: {license_file}")

                # Dosyayi oku ve coz
                with open(license_file, 'r', encoding='utf-8') as f:
                    encoded = f.read().strip()

                # Decode (basit obfuscation)
                unshuffled = encoded[::-1]
                json_str = bytes.fromhex(unshuffled).decode('utf-8')
                license_data = json.loads(json_str)

                stored_machine_id = license_data.get("machine_id", "YOK")
                license_key = license_data.get("license_key", "YOK")

                print(f"Lisans anahtari: {license_key[:10]}...{license_key[-4:] if len(license_key) > 14 else license_key}")
                print(f"Kayitli Machine ID: {stored_machine_id}")
                print()

                # Eslestirme kontrolu
                if stored_machine_id == machine_id_v2:
                    print("[OK] V2 ID ESLESTI - Lisans gecerli")
                elif stored_machine_id == machine_id_v1:
                    print("[OK] V1 ID ESLESTI - Lisans gecerli (V2'ye migrate edilecek)")
                else:
                    print("[HATA] Machine ID ESLESMEDI!")
                    print()
                    print("Karsilastirma:")
                    print(f"  Kayitli: {stored_machine_id}")
                    print(f"  V2:      {machine_id_v2}")
                    print(f"  V1:      {machine_id_v1}")
                    print()
                    print("COZUM: Admin panelinden lisansi bu makine ID ile guncelleyin")
                    print(f"       veya lisansi transfer edin.")
                break

        if not license_found:
            print("Lisans dosyasi bulunamadi - Henuz aktive edilmemis.")

    except Exception as e:
        print(f"Lisans dosyasi okunamadi: {e}")

    print("-" * 70)
    print()

    # Tutarlilik testi
    print("TUTARLILIK TESTI (V2 - 5 kez):")
    print("-" * 70)
    ids = []
    for i in range(5):
        mid = generate_machine_id_v2()
        ids.append(mid)
        print(f"  Deneme {i+1}: {mid[:32]}...")

    if len(set(ids)) == 1:
        print()
        print("[OK] V2 Machine ID TUTARLI - Her seferinde ayni deger uretiliyor")
    else:
        print()
        print("[HATA] V2 Machine ID TUTARSIZ - Farkli degerler uretiliyor!")

    print()

    # Onbellek bilgisi
    print("ONBELLEK BILGISI:")
    print("-" * 70)
    cache_found = False
    for config_dir in possible_dirs:
        cache_file = config_dir / ".takibiesasi_machine_id"
        if cache_file.exists():
            cache_found = True
            print(f"Onbellek dosyasi: {cache_file}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"  Onbelleklenmis ID: {cache_data.get('machine_id', 'YOK')[:32]}...")
                print(f"  Versiyon: {cache_data.get('version', 'YOK')}")
                print(f"  Olusturulma: {cache_data.get('created_at', 'YOK')}")
            except Exception as e:
                print(f"  Onbellek okunamadi: {e}")
            break

    if not cache_found:
        print("Onbellek dosyasi bulunamadi (ilk calistirmada olusturulacak)")

    print("-" * 70)
    print()
    input("Cikmak icin Enter'a basin...")


if __name__ == "__main__":
    main()
