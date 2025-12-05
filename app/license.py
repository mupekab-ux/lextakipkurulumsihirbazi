# -*- coding: utf-8 -*-
"""
LexTakip Lisans Sistemi

Bu modül, uygulamanın lisans doğrulama ve makine kimliği
oluşturma işlemlerini yönetir.

Güvenlik Katmanları:
1. Makine ID (donanım parmak izi)
2. Online aktivasyon (ilk kurulum)
3. Yerel lisans dosyası (sonraki açılışlar)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Lisans dosyası konumu
LICENSE_FILE_NAME = ".lextakip_license"


def _get_license_dir() -> Path:
    """Lisans dosyasının saklanacağı dizini döndürür."""
    if platform.system() == "Windows":
        # Windows: %APPDATA%/LexTakip
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            license_dir = Path(app_data) / "LexTakip"
        else:
            license_dir = Path.home() / "LexTakip"
    else:
        # Linux/Mac: ~/.config/lextakip
        license_dir = Path.home() / ".config" / "lextakip"

    license_dir.mkdir(parents=True, exist_ok=True)
    return license_dir


def _get_license_file_path() -> Path:
    """Lisans dosyasının tam yolunu döndürür."""
    return _get_license_dir() / LICENSE_FILE_NAME


# =============================================================================
# MAKINA ID OLUŞTURMA
# =============================================================================

def _get_cpu_id() -> str:
    """CPU kimliğini alır (Windows için WMIC, Linux için /proc/cpuinfo)."""
    try:
        if platform.system() == "Windows":
            # Windows: WMIC ile CPU ID
            result = subprocess.run(
                ["wmic", "cpu", "get", "processorid"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                return lines[1].strip()
        else:
            # Linux: /proc/cpuinfo'dan model name veya Serial
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "Serial" in line or "model name" in line:
                        return line.split(":")[1].strip()
    except Exception as e:
        logger.warning(f"CPU ID alınamadı: {e}")

    return "UNKNOWN_CPU"


def _get_disk_serial() -> str:
    """Birincil disk seri numarasını alır."""
    try:
        if platform.system() == "Windows":
            # Windows: WMIC ile disk seri numarası
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "serialnumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                serial = line.strip()
                if serial and serial != "SerialNumber":
                    return serial
        else:
            # Linux: lsblk veya /sys/block/*/serial
            result = subprocess.run(
                ["lsblk", "-ndo", "SERIAL"],
                capture_output=True,
                text=True,
                timeout=10
            )
            serial = result.stdout.strip().split('\n')[0]
            if serial:
                return serial
    except Exception as e:
        logger.warning(f"Disk seri numarası alınamadı: {e}")

    return "UNKNOWN_DISK"


def _get_mac_address() -> str:
    """Birincil ağ adaptörünün MAC adresini alır."""
    try:
        mac = uuid.getnode()
        # uuid.getnode() 48-bit integer döndürür
        mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        return mac_str
    except Exception as e:
        logger.warning(f"MAC adresi alınamadı: {e}")
        return "UNKNOWN_MAC"


def _get_windows_product_id() -> str:
    """Windows ürün kimliğini alır (ek güvenlik katmanı)."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "os", "get", "serialnumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                return lines[1].strip()
    except Exception as e:
        logger.warning(f"Windows ürün kimliği alınamadı: {e}")

    return ""


def generate_machine_id() -> str:
    """
    Benzersiz makine kimliği oluşturur.

    Kombinasyon:
    - CPU ID
    - Disk Seri Numarası
    - MAC Adresi
    - Windows Ürün Kimliği (varsa)

    Returns:
        SHA-256 hash olarak makine kimliği (64 karakter hex)
    """
    components = [
        _get_cpu_id(),
        _get_disk_serial(),
        _get_mac_address(),
        _get_windows_product_id(),
        platform.node(),  # Bilgisayar adı
    ]

    # Boş olmayan bileşenleri birleştir
    combined = "|".join(c for c in components if c)

    # SHA-256 hash oluştur
    machine_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    logger.debug(f"Makine ID oluşturuldu: {machine_id[:16]}...")
    return machine_id


def get_short_machine_id() -> str:
    """
    Kullanıcıya gösterilecek kısa makine kimliği.

    Format: XXXX-XXXX-XXXX-XXXX (16 karakter)
    """
    full_id = generate_machine_id()
    short_id = full_id[:16].upper()
    return f"{short_id[:4]}-{short_id[4:8]}-{short_id[8:12]}-{short_id[12:16]}"


# =============================================================================
# LİSANS DOSYASI YÖNETİMİ
# =============================================================================

def _encode_license_data(data: Dict[str, Any]) -> str:
    """Lisans verisini kodlar (basit obfuscation)."""
    json_str = json.dumps(data, ensure_ascii=False)
    # Base64 benzeri basit encoding
    encoded = json_str.encode('utf-8').hex()
    # Ters çevir ve karıştır
    shuffled = encoded[::-1]
    return shuffled


def _decode_license_data(encoded: str) -> Optional[Dict[str, Any]]:
    """Kodlanmış lisans verisini çözer."""
    try:
        # Karıştırmayı geri al
        unshuffled = encoded[::-1]
        # Hex'ten byte'a
        json_str = bytes.fromhex(unshuffled).decode('utf-8')
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Lisans verisi çözülemedi: {e}")
        return None


def save_license(license_key: str, activation_date: str, machine_id: str,
                 customer_name: str = "", customer_email: str = "") -> bool:
    """
    Lisans bilgilerini yerel dosyaya kaydeder.

    Args:
        license_key: Aktivasyon anahtarı
        activation_date: Aktivasyon tarihi (ISO format)
        machine_id: Makine kimliği
        customer_name: Müşteri adı
        customer_email: Müşteri e-postası

    Returns:
        Başarılı ise True
    """
    try:
        license_data = {
            "license_key": license_key,
            "activation_date": activation_date,
            "machine_id": machine_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "version": "1.0",
            "last_check": datetime.utcnow().isoformat()
        }

        encoded = _encode_license_data(license_data)
        license_file = _get_license_file_path()

        with open(license_file, 'w', encoding='utf-8') as f:
            f.write(encoded)

        # Dosyayı gizli yap (Windows)
        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["attrib", "+H", str(license_file)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass

        logger.info("Lisans dosyası kaydedildi")
        return True

    except Exception as e:
        logger.error(f"Lisans dosyası kaydedilemedi: {e}")
        return False


def load_license() -> Optional[Dict[str, Any]]:
    """
    Yerel lisans dosyasını okur.

    Returns:
        Lisans verisi sözlüğü veya None
    """
    try:
        license_file = _get_license_file_path()

        if not license_file.exists():
            logger.info("Lisans dosyası bulunamadı")
            return None

        with open(license_file, 'r', encoding='utf-8') as f:
            encoded = f.read().strip()

        if not encoded:
            return None

        return _decode_license_data(encoded)

    except Exception as e:
        logger.error(f"Lisans dosyası okunamadı: {e}")
        return None


def delete_license() -> bool:
    """Lisans dosyasını siler (deaktivasyon için)."""
    try:
        license_file = _get_license_file_path()
        if license_file.exists():
            license_file.unlink()
            logger.info("Lisans dosyası silindi")
        return True
    except Exception as e:
        logger.error(f"Lisans dosyası silinemedi: {e}")
        return False


# =============================================================================
# LİSANS DOĞRULAMA
# =============================================================================

def verify_local_license() -> Tuple[bool, str]:
    """
    Yerel lisans dosyasını doğrular.

    Returns:
        (geçerli_mi, mesaj) tuple'ı
    """
    license_data = load_license()

    if license_data is None:
        return False, "Lisans bulunamadı. Lütfen ürünü aktive edin."

    # Makine ID kontrolü
    current_machine_id = generate_machine_id()
    stored_machine_id = license_data.get("machine_id", "")

    if current_machine_id != stored_machine_id:
        return False, "Bu lisans farklı bir bilgisayar için aktive edilmiş."

    # Lisans anahtarı kontrolü
    license_key = license_data.get("license_key", "")
    if not license_key:
        return False, "Geçersiz lisans anahtarı."

    return True, "Lisans geçerli."


def is_activated() -> bool:
    """Uygulama aktive edilmiş mi kontrol eder."""
    valid, _ = verify_local_license()
    return valid


def get_license_info() -> Optional[Dict[str, Any]]:
    """Mevcut lisans bilgilerini döndürür."""
    if not is_activated():
        return None
    return load_license()


# =============================================================================
# ONLINE AKTİVASYON (Sunucu kurulduktan sonra etkinleştirilecek)
# =============================================================================

# API endpoint'leri (sunucu kurulduktan sonra güncellenecek)
API_BASE_URL = "https://api.lextakip.com"  # Placeholder

async def activate_online(license_key: str) -> Tuple[bool, str]:
    """
    Online lisans aktivasyonu yapar.

    NOT: Bu fonksiyon sunucu kurulduktan sonra implement edilecek.
    Şimdilik offline aktivasyon için placeholder.

    Args:
        license_key: Müşterinin satın aldığı lisans anahtarı

    Returns:
        (başarılı_mı, mesaj) tuple'ı
    """
    # TODO: Sunucu kurulduktan sonra implement edilecek
    # Şimdilik test modu - her anahtar kabul edilir

    machine_id = generate_machine_id()
    activation_date = datetime.utcnow().isoformat()

    # Lisansı kaydet
    success = save_license(
        license_key=license_key,
        activation_date=activation_date,
        machine_id=machine_id,
        customer_name="Test Kullanıcı",
        customer_email=""
    )

    if success:
        return True, "Lisans başarıyla aktive edildi."
    else:
        return False, "Lisans kaydedilemedi."


def activate_offline(license_key: str) -> Tuple[bool, str]:
    """
    Offline lisans aktivasyonu (test modu).

    Sunucu kurulana kadar bu fonksiyon kullanılacak.
    """
    # Basit format kontrolü: XXXX-XXXX-XXXX-XXXX
    parts = license_key.strip().split('-')
    if len(parts) != 4 or not all(len(p) == 4 for p in parts):
        return False, "Geçersiz lisans formatı. Format: XXXX-XXXX-XXXX-XXXX"

    machine_id = generate_machine_id()
    activation_date = datetime.utcnow().isoformat()

    success = save_license(
        license_key=license_key,
        activation_date=activation_date,
        machine_id=machine_id
    )

    if success:
        return True, "Lisans başarıyla aktive edildi."
    else:
        return False, "Lisans kaydedilemedi. Lütfen tekrar deneyin."


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def get_system_info() -> Dict[str, str]:
    """Sistem bilgilerini döndürür (destek için)."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "machine_id_short": get_short_machine_id(),
    }


def format_license_for_display(license_data: Optional[Dict[str, Any]]) -> str:
    """Lisans bilgilerini kullanıcıya gösterilecek formatta döndürür."""
    if not license_data:
        return "Aktive edilmemiş"

    key = license_data.get("license_key", "")
    date = license_data.get("activation_date", "")

    if date:
        try:
            dt = datetime.fromisoformat(date)
            date = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass

    return f"Lisans: {key}\nAktivasyon: {date}"
