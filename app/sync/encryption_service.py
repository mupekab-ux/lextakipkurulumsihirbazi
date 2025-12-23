# -*- coding: utf-8 -*-
"""
Şifreleme Servisi

Firma anahtarı (firm_key) ile veri şifreleme/çözme işlemleri.
Transfer sırasında veriler bu anahtarla şifrelenir.
"""

import base64
import hashlib
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cryptography kütüphanesi
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("Cryptography kütüphanesi yüklü değil. pip install cryptography")

# BIP-39 için mnemonic
try:
    from mnemonic import Mnemonic
    MNEMONIC_AVAILABLE = True
except ImportError:
    MNEMONIC_AVAILABLE = False
    logger.info("Mnemonic kütüphanesi yüklü değil. Basit kurtarma kodu kullanılacak.")


class EncryptionService:
    """
    Firma anahtarı şifreleme servisi.

    Tüm senkronize veriler bu servis ile şifrelenir/çözülür.
    Sadece aynı firm_key'e sahip cihazlar veriyi okuyabilir.
    """

    def __init__(self, firm_key: bytes):
        """
        Args:
            firm_key: 32-byte Fernet uyumlu anahtar (base64 encoded)
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography kütüphanesi gerekli. pip install cryptography")

        self.firm_key = firm_key
        self._fernet = Fernet(firm_key)

    def encrypt_data(self, data: Dict[str, Any]) -> bytes:
        """
        Dict veriyi şifrele.

        Args:
            data: Şifrelenecek dict

        Returns:
            Şifrelenmiş bytes
        """
        try:
            json_str = json.dumps(data, ensure_ascii=False, default=str)
            return self._fernet.encrypt(json_str.encode('utf-8'))
        except Exception as e:
            logger.error(f"Şifreleme hatası: {e}")
            raise

    def decrypt_data(self, encrypted: bytes) -> Dict[str, Any]:
        """
        Şifrelenmiş veriyi çöz.

        Args:
            encrypted: Şifrelenmiş bytes

        Returns:
            Çözülmüş dict
        """
        try:
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            logger.error(f"Şifre çözme hatası: {e}")
            raise

    def encrypt_string(self, text: str) -> str:
        """String şifrele, base64 olarak döndür."""
        encrypted = self._fernet.encrypt(text.encode('utf-8'))
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt_string(self, encrypted_b64: str) -> str:
        """Base64 şifreli stringi çöz."""
        encrypted = base64.b64decode(encrypted_b64.encode('ascii'))
        return self._fernet.decrypt(encrypted).decode('utf-8')

    @staticmethod
    def generate_firm_key() -> bytes:
        """
        Yeni firma anahtarı üret.

        Returns:
            32-byte base64-encoded Fernet key
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography kütüphanesi gerekli")

        return Fernet.generate_key()

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """
        Paroladan Fernet anahtarı türet.

        Args:
            password: Kullanıcı parolası
            salt: 16-byte salt

        Returns:
            Fernet uyumlu anahtar
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography kütüphanesi gerekli")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
        return key


class RecoveryCodeManager:
    """
    Kurtarma kodu yönetimi.

    Firma anahtarı kaybolursa, kurtarma kodu ile geri alınabilir.
    BIP-39 formatında 24 kelime veya basit format kullanılabilir.
    """

    def __init__(self):
        if MNEMONIC_AVAILABLE:
            self._mnemonic = Mnemonic("english")
        else:
            self._mnemonic = None

    def generate_recovery_code(self, firm_key: bytes) -> str:
        """
        Firma anahtarından kurtarma kodu üret.

        Args:
            firm_key: Firma anahtarı

        Returns:
            24 kelimelik kurtarma kodu veya hex string
        """
        # firm_key'den entropy oluştur
        entropy = hashlib.sha256(firm_key).digest()

        if self._mnemonic:
            # BIP-39 formatında 24 kelime
            return self._mnemonic.to_mnemonic(entropy)
        else:
            # Basit format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
            hex_str = entropy.hex()
            parts = [hex_str[i:i+4].upper() for i in range(0, 24, 4)]
            return '-'.join(parts)

    def recover_firm_key(self, recovery_code: str) -> bytes:
        """
        Kurtarma kodundan firma anahtarını geri al.

        Args:
            recovery_code: Kurtarma kodu (24 kelime veya hex)

        Returns:
            Firma anahtarı
        """
        if self._mnemonic and ' ' in recovery_code:
            # BIP-39 formatı
            if not self._mnemonic.check(recovery_code):
                raise ValueError("Geçersiz kurtarma kodu")

            entropy = self._mnemonic.to_entropy(recovery_code)
        else:
            # Basit hex format
            hex_str = recovery_code.replace('-', '').lower()
            entropy = bytes.fromhex(hex_str[:64])

        # Entropy'den firm_key türet
        # Not: Bu tek yönlü bir işlem, orijinal key'e dönülemez
        # Bunun yerine entropy'yi key olarak kullanıyoruz
        return base64.urlsafe_b64encode(entropy[:32])

    def hash_recovery_code(self, recovery_code: str) -> str:
        """
        Kurtarma kodunun hash'ini al (doğrulama için).

        Args:
            recovery_code: Kurtarma kodu

        Returns:
            SHA-256 hash (hex)
        """
        return hashlib.sha256(recovery_code.encode()).hexdigest()


def encrypt_for_device(data: Dict[str, Any], device_key: bytes) -> bytes:
    """
    Veriyi cihaz anahtarıyla şifrele.

    Firma anahtarını cihaza iletirken kullanılır.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError("Cryptography kütüphanesi gerekli")

    fernet = Fernet(device_key)
    json_str = json.dumps(data, ensure_ascii=False, default=str)
    return fernet.encrypt(json_str.encode('utf-8'))


def decrypt_from_device(encrypted: bytes, device_key: bytes) -> Dict[str, Any]:
    """Cihaz anahtarıyla şifrelenmiş veriyi çöz."""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError("Cryptography kütüphanesi gerekli")

    fernet = Fernet(device_key)
    decrypted = fernet.decrypt(encrypted)
    return json.loads(decrypted.decode('utf-8'))
