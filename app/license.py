# -*- coding: utf-8 -*-
"""
TakibiEsasi Lisans Sistemi

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Lisans dosyası konumu
LICENSE_FILE_NAME = ".takibiesasi_license"

# Sunucu tarafından açıkça reddedilen lisans durumunu takip eder
# Bu bayrak True olduğunda, demo sistemine düşülmemeli
_license_explicitly_rejected = False
_license_rejection_reason = ""


def _get_license_dir() -> Path:
    """Lisans dosyasının saklanacağı dizini döndürür."""
    possible_dirs = []

    if platform.system() == "Windows":
        # Windows: Birkaç alternatif konum dene
        app_data = os.environ.get("APPDATA", "")
        local_app_data = os.environ.get("LOCALAPPDATA", "")

        if app_data:
            possible_dirs.append(Path(app_data) / "TakibiEsasi")
        if local_app_data:
            possible_dirs.append(Path(local_app_data) / "TakibiEsasi")
        possible_dirs.append(Path.home() / "TakibiEsasi")
        possible_dirs.append(Path.home() / ".takibiesasi")
    else:
        # Linux/Mac: ~/.config/takibiesasi
        possible_dirs.append(Path.home() / ".config" / "takibiesasi")
        possible_dirs.append(Path.home() / ".takibiesasi")

    # İlk yazılabilir dizini bul
    for license_dir in possible_dirs:
        try:
            license_dir.mkdir(parents=True, exist_ok=True)
            # Yazma testi yap
            test_file = license_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            return license_dir
        except (PermissionError, OSError):
            continue

    # Hiçbiri çalışmazsa, uygulama dizinini kullan
    app_dir = Path(__file__).parent / ".license_data"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def _get_license_file_path() -> Path:
    """Lisans dosyasının tam yolunu döndürür."""
    return _get_license_dir() / LICENSE_FILE_NAME


# =============================================================================
# MAKINA ID OLUŞTURMA (V2 - Daha Stabil)
# =============================================================================

# Machine ID versiyon sabitleri
MACHINE_ID_VERSION = 2  # Yeni stabil versiyon
MACHINE_ID_FILE_NAME = ".takibiesasi_machine_id"  # Önbellek dosyası


def _get_motherboard_uuid() -> str:
    """
    Anakart UUID'sini alır - EN STABİL bileşen.
    BIOS'ta kayıtlı olduğu için hiçbir zaman değişmez.
    """
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            uuid_val = result.stdout.strip()
            # Bazı sistemlerde geçersiz UUID döner
            invalid_uuids = [
                "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
                "00000000-0000-0000-0000-000000000000",
                ""
            ]
            if uuid_val and uuid_val not in invalid_uuids:
                return uuid_val
        else:
            # Linux: /sys/class/dmi/id/product_uuid
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    return f.read().strip()
            except (FileNotFoundError, PermissionError):
                pass
    except Exception as e:
        logger.warning(f"Motherboard UUID alınamadı: {e}")

    return ""


def _get_baseboard_serial() -> str:
    """
    Anakart seri numarasını alır - çok stabil.
    Motherboard UUID yoksa yedek olarak kullanılır.
    """
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_BaseBoard).SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            serial = result.stdout.strip()
            # "To Be Filled By O.E.M." gibi geçersiz değerleri filtrele
            invalid_serials = ["To Be Filled By O.E.M.", "Default string", ""]
            if serial and serial not in invalid_serials:
                return serial
    except Exception as e:
        logger.warning(f"Baseboard serial alınamadı: {e}")

    return ""


def _get_cpu_id() -> str:
    """CPU kimliğini alır (Windows için PowerShell, Linux için /proc/cpuinfo)."""
    try:
        if platform.system() == "Windows":
            # Windows: PowerShell ile CPU ID
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            cpu_id = result.stdout.strip()
            if cpu_id:
                return cpu_id
        else:
            # Linux: /proc/cpuinfo'dan model name veya Serial
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "Serial" in line or "model name" in line:
                        return line.split(":")[1].strip()
    except Exception as e:
        logger.warning(f"CPU ID alınamadı: {e}")

    return "UNKNOWN_CPU"


def _get_windows_product_id() -> str:
    """Windows ürün kimliğini alır (ek güvenlik katmanı)."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -ClassName Win32_OperatingSystem).SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            serial = result.stdout.strip()
            if serial:
                return serial
    except Exception as e:
        logger.warning(f"Windows ürün kimliği alınamadı: {e}")

    return ""


def _get_machine_id_cache_path() -> Path:
    """Machine ID önbellek dosyasının yolunu döndürür."""
    return _get_license_dir() / MACHINE_ID_FILE_NAME


def _load_cached_machine_id() -> Optional[str]:
    """
    Önbelleklenmiş machine ID'yi yükle.
    İlk aktivasyonda oluşturulan ID'yi korur.
    """
    try:
        cache_path = _get_machine_id_cache_path()
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cached_id = data.get("machine_id")
                version = data.get("version", 1)
                if cached_id and version == MACHINE_ID_VERSION:
                    logger.debug("Önbelleklenmiş machine ID kullanılıyor")
                    return cached_id
    except Exception as e:
        logger.warning(f"Machine ID önbelleği okunamadı: {e}")
    return None


def _save_cached_machine_id(machine_id: str) -> bool:
    """Machine ID'yi önbelleğe kaydet."""
    try:
        cache_path = _get_machine_id_cache_path()
        data = {
            "machine_id": machine_id,
            "version": MACHINE_ID_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        logger.debug("Machine ID önbelleğe kaydedildi")
        return True
    except Exception as e:
        logger.warning(f"Machine ID önbelleğe kaydedilemedi: {e}")
        return False


def generate_machine_id() -> str:
    """
    Benzersiz makine kimliği oluşturur (V2 - Daha Stabil).

    STABİL BİLEŞENLER (değişmez):
    1. Motherboard UUID (BIOS'ta kayıtlı)
    2. Baseboard Serial (anakart seri no)
    3. CPU ID
    4. Windows Product ID

    NOT: MAC adresi ve Disk Serial KALDIRILDI çünkü:
    - uuid.getnode() rastgele değer döndürebilir
    - Disk sırası değişebilir (USB vs.)

    Returns:
        SHA-256 hash olarak makine kimliği (64 karakter hex)
    """
    # Önce önbellekten kontrol et (geriye uyumluluk)
    cached = _load_cached_machine_id()
    if cached:
        return cached

    # Stabil bileşenleri topla
    components = []

    # 1. Motherboard UUID - en güvenilir
    mb_uuid = _get_motherboard_uuid()
    if mb_uuid:
        components.append(mb_uuid)

    # 2. Baseboard Serial - yedek
    bb_serial = _get_baseboard_serial()
    if bb_serial:
        components.append(bb_serial)

    # 3. CPU ID
    cpu_id = _get_cpu_id()
    if cpu_id and cpu_id != "UNKNOWN_CPU":
        components.append(cpu_id)

    # 4. Windows Product ID
    win_id = _get_windows_product_id()
    if win_id:
        components.append(win_id)

    # 5. Bilgisayar adı (son çare olarak)
    if not components:
        components.append(platform.node())

    # Boş olmayan bileşenleri birleştir
    combined = "|".join(c for c in components if c)

    # SHA-256 hash oluştur
    machine_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    # Önbelleğe kaydet (ilk çalıştırmada)
    _save_cached_machine_id(machine_id)

    logger.debug(f"Makine ID oluşturuldu (V2): {machine_id[:16]}...")
    return machine_id


def generate_machine_id_v1() -> str:
    """
    ESKİ Machine ID algoritması (V1) - Geriye uyumluluk için.
    Mevcut lisansları doğrulamak için kullanılır.
    """
    def _get_disk_serial_v1() -> str:
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -First 1).SerialNumber"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                serial = result.stdout.strip()
                if serial:
                    return serial
        except Exception:
            pass
        return "UNKNOWN_DISK"

    def _get_mac_address_v1() -> str:
        try:
            mac = uuid.getnode()
            mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
            return mac_str
        except Exception:
            return "UNKNOWN_MAC"

    components = [
        _get_cpu_id(),
        _get_disk_serial_v1(),
        _get_mac_address_v1(),
        _get_windows_product_id(),
        platform.node(),
    ]

    combined = "|".join(c for c in components if c)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def get_short_machine_id() -> str:
    """
    Kullanıcıya gösterilecek kısa makine kimliği.

    Format: XXXX-XXXX-XXXX-XXXX (16 karakter)
    """
    full_id = generate_machine_id()
    short_id = full_id[:16].upper()
    return f"{short_id[:4]}-{short_id[4:8]}-{short_id[8:12]}-{short_id[12:16]}"


# =============================================================================
# OFFLINE TOKEN YÖNETİMİ
# =============================================================================

OFFLINE_TOKEN_FILE_NAME = ".takibiesasi_token"


def _get_token_file_path() -> Path:
    """Offline token dosyasının tam yolunu döndürür."""
    return _get_license_dir() / OFFLINE_TOKEN_FILE_NAME


def save_offline_token(token: str, expires_at: str) -> bool:
    """
    Offline token'ı yerel dosyaya kaydeder.

    Args:
        token: JWT token string
        expires_at: Token bitiş tarihi (ISO format)

    Returns:
        Başarılı ise True
    """
    try:
        token_data = {
            "token": token,
            "expires_at": expires_at,
            "saved_at": datetime.utcnow().isoformat()
        }

        encoded = _encode_license_data(token_data)
        token_file = _get_token_file_path()

        # Windows'ta önce hidden attribute'u kaldır (varsa)
        if platform.system() == "Windows" and token_file.exists():
            try:
                subprocess.run(
                    ["attrib", "-H", str(token_file)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass

        # Dosyayı yazmayı dene
        try:
            with open(token_file, 'w', encoding='utf-8') as f:
                f.write(encoded)
        except PermissionError:
            # Dosya kilitliyse silip tekrar dene
            try:
                token_file.unlink()
                with open(token_file, 'w', encoding='utf-8') as f:
                    f.write(encoded)
            except Exception as e2:
                logger.error(f"Token dosyası yazılamadı (retry): {e2}")
                return False

        # Dosyayı gizli yap (Windows)
        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["attrib", "+H", str(token_file)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass

        logger.info(f"Offline token kaydedildi, geçerlilik: {expires_at}")
        return True

    except Exception as e:
        logger.error(f"Offline token kaydedilemedi: {e}")
        return False


def load_offline_token() -> Optional[Dict[str, Any]]:
    """
    Yerel offline token dosyasını okur.

    Returns:
        Token verisi sözlüğü veya None
    """
    try:
        token_file = _get_token_file_path()

        if not token_file.exists():
            logger.debug("Offline token dosyası bulunamadı")
            return None

        with open(token_file, 'r', encoding='utf-8') as f:
            encoded = f.read().strip()

        if not encoded:
            return None

        return _decode_license_data(encoded)

    except Exception as e:
        logger.error(f"Offline token okunamadı: {e}")
        return None


def delete_offline_token() -> bool:
    """Offline token dosyasını siler."""
    try:
        token_file = _get_token_file_path()
        if token_file.exists():
            token_file.unlink()
            logger.info("Offline token silindi")
        return True
    except Exception as e:
        logger.error(f"Offline token silinemedi: {e}")
        return False


def is_offline_token_valid() -> Tuple[bool, str]:
    """
    Offline token'ın geçerli olup olmadığını kontrol eder.

    Returns:
        (geçerli_mi, mesaj) tuple'ı
    """
    token_data = load_offline_token()

    if not token_data:
        return False, "Offline token bulunamadı"

    expires_at_str = token_data.get("expires_at")
    if not expires_at_str:
        return False, "Token bitiş tarihi bulunamadı"

    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        # UTC zamanını karşılaştır
        if expires_at.tzinfo:
            now = datetime.now(expires_at.tzinfo)
        else:
            now = datetime.utcnow()

        if now > expires_at:
            return False, "Offline token süresi dolmuş"

        remaining_days = (expires_at - now).days
        return True, f"Offline token geçerli ({remaining_days} gün kaldı)"

    except Exception as e:
        logger.error(f"Token tarihi parse edilemedi: {e}")
        return False, "Token tarihi okunamadı"


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

        # Windows'ta önce hidden attribute'u kaldır (varsa)
        if platform.system() == "Windows" and license_file.exists():
            try:
                subprocess.run(
                    ["attrib", "-H", str(license_file)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass

        # Dosyayı yazmayı dene
        try:
            with open(license_file, 'w', encoding='utf-8') as f:
                f.write(encoded)
        except PermissionError:
            # Dosya kilitliyse silip tekrar dene
            try:
                license_file.unlink()
                with open(license_file, 'w', encoding='utf-8') as f:
                    f.write(encoded)
            except Exception as e2:
                logger.error(f"Lisans dosyası yazılamadı (retry): {e2}")
                return False

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
    Hem V1 hem V2 machine ID'leri destekler (geriye uyumluluk).

    Returns:
        (geçerli_mi, mesaj) tuple'ı
    """
    license_data = load_license()

    if license_data is None:
        return False, "Lisans bulunamadı. Lütfen ürünü aktive edin."

    stored_machine_id = license_data.get("machine_id", "")

    # Makine ID kontrolü - V2 ile dene
    current_machine_id_v2 = generate_machine_id()

    if current_machine_id_v2 == stored_machine_id:
        return _verify_license_key(license_data)

    # V2 eşleşmediyse V1 ile dene (geriye uyumluluk)
    current_machine_id_v1 = generate_machine_id_v1()

    if current_machine_id_v1 == stored_machine_id:
        # V1 eşleşti - lisansı V2'ye migrate et
        logger.info("V1 machine ID eşleşti, V2'ye migrate ediliyor...")
        license_data["machine_id"] = current_machine_id_v2
        save_license(
            license_key=license_data.get("license_key", ""),
            activation_date=license_data.get("activation_date", ""),
            machine_id=current_machine_id_v2,
            customer_name=license_data.get("customer_name", ""),
            customer_email=license_data.get("customer_email", "")
        )
        return _verify_license_key(license_data)

    return False, "Bu lisans farklı bir bilgisayar için aktive edilmiş."


def _verify_license_key(license_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Lisans anahtarını doğrular."""
    license_key = license_data.get("license_key", "")
    if not license_key:
        return False, "Geçersiz lisans anahtarı."
    return True, "Lisans geçerli."


def was_license_rejected() -> bool:
    """
    Son lisans kontrolünde sunucu tarafından açıkça reddedilip reddedilmediğini döndürür.
    Bu durumda demo sistemine düşülmemeli.
    """
    return _license_explicitly_rejected


def get_rejection_reason() -> str:
    """Lisans red nedenini döndürür."""
    return _license_rejection_reason


def _check_machine_id_match(stored_machine_id: str) -> Tuple[bool, str]:
    """
    Machine ID eşleşmesini kontrol et (V1 ve V2 destekli).

    Returns:
        (eşleşti_mi, kullanılacak_machine_id)
    """
    # V2 ile dene
    current_v2 = generate_machine_id()
    if current_v2 == stored_machine_id:
        return True, current_v2

    # V1 ile dene (geriye uyumluluk)
    current_v1 = generate_machine_id_v1()
    if current_v1 == stored_machine_id:
        return True, current_v2  # V2 döndür migration için

    return False, current_v2


def is_activated() -> bool:
    """
    Uygulama aktive edilmiş mi kontrol eder.

    Kontrol sırası:
    1. Önce sunucuya bağlanmayı dene (online doğrulama)
    2. Sunucu "geçersiz/devre dışı" derse False döndür
    3. Bağlantı hatası varsa offline token kontrol et
    4. Offline token geçerliyse True döndür
    5. Hiçbiri yoksa False döndür
    """
    global _license_explicitly_rejected, _license_rejection_reason

    # Her kontrolde bayrakları sıfırla
    _license_explicitly_rejected = False
    _license_rejection_reason = ""

    # Önce lokal lisans dosyası var mı kontrol et
    license_data = load_license()
    if not license_data:
        logger.info("Lisans dosyası bulunamadı")
        return False

    license_key = license_data.get("license_key", "")
    if not license_key:
        logger.info("Lisans anahtarı bulunamadı")
        return False

    # Makine ID kontrolü (V1 ve V2 destekli)
    stored_machine_id = license_data.get("machine_id", "")
    matched, current_machine_id = _check_machine_id_match(stored_machine_id)

    if not matched:
        logger.warning(
            f"Makine ID eşleşmiyor! "
            f"Yerel dosyadaki: {stored_machine_id[:16]}... vs "
            f"Mevcut V2: {current_machine_id[:16]}..."
        )
        return False

    # Eğer V1'den V2'ye migrate edilmesi gerekiyorsa
    if stored_machine_id != current_machine_id:
        logger.info("Machine ID V1'den V2'ye migrate ediliyor...")
        save_license(
            license_key=license_key,
            activation_date=license_data.get("activation_date", ""),
            machine_id=current_machine_id,
            customer_name=license_data.get("customer_name", ""),
            customer_email=license_data.get("customer_email", "")
        )

    # Online doğrulama dene
    try:
        import requests
        response = requests.post(
            f"{API_BASE_URL}/api/verify",
            json={
                "license_key": license_key,
                "machine_id": current_machine_id
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("valid"):
                # Lisans geçerli - yeni token'ı kaydet
                if data.get("offline_token"):
                    save_offline_token(
                        data["offline_token"],
                        data.get("token_expires_at", "")
                    )
                logger.info("Online doğrulama başarılı")
                return True
            else:
                # Sunucu lisansı reddetti (devre dışı, geçersiz vb.)
                error = data.get("error", "Lisans geçersiz")
                logger.warning(f"Sunucu lisansı reddetti: {error}")
                # Offline token'ı da sil çünkü lisans artık geçersiz
                delete_offline_token()
                # Açıkça reddedildi olarak işaretle - demo'ya düşülmemeli
                _license_explicitly_rejected = True
                _license_rejection_reason = error
                return False

    except requests.exceptions.ConnectionError:
        logger.info("Sunucuya bağlanılamadı, offline mod deneniyor")
    except requests.exceptions.Timeout:
        logger.info("Sunucu yanıt vermedi, offline mod deneniyor")
    except Exception as e:
        logger.warning(f"Online doğrulama hatası: {e}, offline mod deneniyor")

    # Sunucuya bağlanamadık - offline token kontrol et
    token_valid, token_msg = is_offline_token_valid()

    if token_valid:
        logger.info(f"Offline mod aktif: {token_msg}")
        return True

    # Offline token da geçersiz
    logger.warning(f"Offline token geçersiz: {token_msg}")
    return False


def is_activated_offline_only() -> bool:
    """
    Sadece offline kontrol yapar (sunucuya bağlanmaz).
    Hızlı kontrol gereken durumlar için kullanılır.
    """
    # Lokal lisans kontrolü
    valid, _ = verify_local_license()
    if not valid:
        return False

    # Offline token kontrolü
    token_valid, _ = is_offline_token_valid()
    return token_valid


def get_license_info() -> Optional[Dict[str, Any]]:
    """Mevcut lisans bilgilerini döndürür."""
    license_data = load_license()
    if not license_data:
        return None

    # Offline token durumunu da ekle
    token_valid, token_msg = is_offline_token_valid()
    license_data["offline_token_valid"] = token_valid
    license_data["offline_token_status"] = token_msg

    return license_data


# =============================================================================
# ONLINE AKTİVASYON
# =============================================================================

import requests

API_BASE_URL = "https://api.takibiesasi.com"


def activate_online(license_key: str) -> Tuple[bool, str]:
    """
    Online lisans aktivasyonu yapar.

    Args:
        license_key: Müşterinin satın aldığı lisans anahtarı

    Returns:
        (başarılı_mı, mesaj) tuple'ı
    """
    machine_id = generate_machine_id()

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/activate",
            json={
                "license_key": license_key,
                "machine_id": machine_id
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # Lisansı yerel dosyaya kaydet
                activation_date = datetime.utcnow().isoformat()
                save_license(
                    license_key=license_key,
                    activation_date=activation_date,
                    machine_id=machine_id
                )

                # Offline token'ı kaydet (30 gün geçerli)
                if data.get("offline_token"):
                    save_offline_token(
                        data["offline_token"],
                        data.get("token_expires_at", "")
                    )
                    logger.info("Offline token kaydedildi")

                return True, data.get("message", "Lisans başarıyla aktive edildi.")
            else:
                return False, data.get("error", data.get("message", "Aktivasyon başarısız."))

        elif response.status_code == 404:
            return False, "Lisans anahtarı bulunamadı."
        elif response.status_code == 403:
            detail = response.json().get("detail", "Lisans kullanılamaz.")
            return False, detail
        else:
            return False, f"Sunucu hatası: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin."
    except requests.exceptions.Timeout:
        return False, "Sunucu yanıt vermedi. Lütfen tekrar deneyin."
    except Exception as e:
        logger.error(f"Aktivasyon hatası: {e}")
        return False, f"Beklenmeyen hata: {str(e)}"


def verify_online() -> Tuple[bool, str]:
    """
    Lisansı online olarak doğrular.

    Returns:
        (geçerli_mi, mesaj) tuple'ı
    """
    license_data = load_license()
    if not license_data:
        return False, "Yerel lisans bulunamadı."

    license_key = license_data.get("license_key", "")
    machine_id = generate_machine_id()

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/verify",
            json={
                "license_key": license_key,
                "machine_id": machine_id
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("valid"):
                return True, data.get("message", "Lisans geçerli.")
            else:
                return False, data.get("message", "Lisans geçersiz.")
        else:
            return False, f"Sunucu hatası: {response.status_code}"

    except requests.exceptions.ConnectionError:
        # Offline mod - yerel lisansı kabul et
        logger.warning("Sunucuya bağlanılamadı, offline mod kullanılıyor")
        return verify_local_license()
    except Exception as e:
        logger.error(f"Doğrulama hatası: {e}")
        return verify_local_license()


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
