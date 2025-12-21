# -*- coding: utf-8 -*-
"""
TakibiEsasi Veritabanı Şifreleme Modülü

SQLCipher kullanarak veritabanını AES-256 ile şifreler.
Anahtar, makine ID + uygulama secret kombinasyonundan türetilir.
"""

import hashlib
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Uygulama secret (bu değer değiştirilmemeli, değişirse eski veriler açılamaz)
APP_SECRET = "TakibiEsasi-DB-Secret-2024-v1"

# SQLCipher kullanılabilir mi?
SQLCIPHER_AVAILABLE = False
sqlcipher = None

try:
    import sqlcipher3 as sqlcipher
    SQLCIPHER_AVAILABLE = True
    logger.info("SQLCipher kullanılabilir (sqlcipher3)")
except ImportError:
    try:
        import pysqlcipher3.dbapi2 as sqlcipher
        SQLCIPHER_AVAILABLE = True
        logger.info("SQLCipher kullanılabilir (pysqlcipher3)")
    except ImportError:
        logger.warning("SQLCipher bulunamadı, veritabanı şifrelenmeyecek")


def get_machine_id() -> str:
    """Makine kimliğini al (license.py'den)."""
    try:
        try:
            from app.license import generate_machine_id
        except ImportError:
            from license import generate_machine_id
        return generate_machine_id()
    except Exception as e:
        logger.warning(f"Makine ID alınamadı: {e}")
        # Fallback: basit bir ID oluştur
        import platform
        import uuid
        fallback = f"{platform.node()}-{uuid.getnode()}"
        return hashlib.sha256(fallback.encode()).hexdigest()


def derive_db_key() -> str:
    """
    Veritabanı şifreleme anahtarını türet.

    Kombinasyon:
    - Makine ID (donanım parmak izi)
    - Uygulama secret

    Returns:
        64 karakterlik hex string (256-bit anahtar)
    """
    machine_id = get_machine_id()
    combined = f"{APP_SECRET}:{machine_id}"

    # PBKDF2 benzeri çoklu hash (basit ama etkili)
    key = combined.encode('utf-8')
    for _ in range(10000):
        key = hashlib.sha256(key).digest()

    return key.hex()


def is_encrypted_db(db_path: str) -> bool:
    """
    Veritabanının şifreli olup olmadığını kontrol et.

    SQLite dosyaları "SQLite format 3" header'ı ile başlar.
    Şifreli dosyalar bu header'a sahip değildir.
    """
    try:
        with open(db_path, 'rb') as f:
            header = f.read(16)

        # SQLite magic bytes
        if header.startswith(b'SQLite format 3'):
            return False

        # Dosya var ama SQLite header yok = şifreli
        return len(header) > 0
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"Veritabanı header kontrol hatası: {e}")
        return False


def get_encrypted_connection(db_path: str, key: Optional[str] = None):
    """
    Şifreli veritabanı bağlantısı al.

    Args:
        db_path: Veritabanı dosya yolu
        key: Şifreleme anahtarı (None ise otomatik türetilir)

    Returns:
        sqlite3.Connection veya sqlcipher.Connection
    """
    if key is None:
        key = derive_db_key()

    if SQLCIPHER_AVAILABLE and sqlcipher is not None:
        conn = sqlcipher.connect(db_path)
        conn.execute(f"PRAGMA key = '{key}'")
        # SQLCipher ayarları
        conn.execute("PRAGMA cipher_page_size = 4096")
        conn.execute("PRAGMA kdf_iter = 256000")
        conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA256")
        conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA256")
        return conn
    else:
        # SQLCipher yok, normal sqlite3 kullan
        logger.warning("SQLCipher bulunamadı, şifresiz bağlantı kullanılıyor")
        return sqlite3.connect(db_path)


def migrate_to_encrypted(src_path: str, dst_path: str, key: Optional[str] = None) -> bool:
    """
    Şifresiz veritabanını şifreli versiyona migrate et.

    Args:
        src_path: Kaynak (şifresiz) veritabanı
        dst_path: Hedef (şifreli) veritabanı
        key: Şifreleme anahtarı

    Returns:
        Başarılı ise True
    """
    if not SQLCIPHER_AVAILABLE:
        logger.error("SQLCipher yüklü değil, migration yapılamaz")
        return False

    if key is None:
        key = derive_db_key()

    try:
        # Kaynak veritabanını aç (şifresiz)
        src_conn = sqlite3.connect(src_path)

        # Hedef veritabanını oluştur (şifreli)
        dst_conn = sqlcipher.connect(dst_path)
        dst_conn.execute(f"PRAGMA key = '{key}'")
        dst_conn.execute("PRAGMA cipher_page_size = 4096")
        dst_conn.execute("PRAGMA kdf_iter = 256000")

        # Tüm tabloları kopyala
        src_conn.backup(dst_conn)

        src_conn.close()
        dst_conn.close()

        logger.info(f"Veritabanı başarıyla şifrelendi: {dst_path}")
        return True

    except Exception as e:
        logger.error(f"Migration hatası: {e}")
        return False


def migrate_from_encrypted(src_path: str, dst_path: str, key: Optional[str] = None) -> bool:
    """
    Şifreli veritabanını şifresiz versiyona dönüştür (debug/export için).

    Args:
        src_path: Kaynak (şifreli) veritabanı
        dst_path: Hedef (şifresiz) veritabanı
        key: Şifreleme anahtarı

    Returns:
        Başarılı ise True
    """
    if not SQLCIPHER_AVAILABLE:
        logger.error("SQLCipher yüklü değil")
        return False

    if key is None:
        key = derive_db_key()

    try:
        # Kaynak veritabanını aç (şifreli)
        src_conn = sqlcipher.connect(src_path)
        src_conn.execute(f"PRAGMA key = '{key}'")

        # Hedef veritabanını oluştur (şifresiz)
        dst_conn = sqlite3.connect(dst_path)

        # Tüm tabloları kopyala
        src_conn.backup(dst_conn)

        src_conn.close()
        dst_conn.close()

        logger.info(f"Veritabanı başarıyla şifre çözüldü: {dst_path}")
        return True

    except Exception as e:
        logger.error(f"Decrypt hatası: {e}")
        return False


def ensure_encrypted_db(db_path: str) -> Tuple[bool, str]:
    """
    Veritabanının şifreli olduğundan emin ol.

    Eğer şifresiz ise, şifreli versiyona migrate et.

    Args:
        db_path: Veritabanı dosya yolu

    Returns:
        (başarılı, mesaj) tuple'ı
    """
    if not SQLCIPHER_AVAILABLE:
        return False, "SQLCipher yüklü değil. pip install sqlcipher3-binary"

    if not os.path.exists(db_path):
        # Veritabanı yok, yeni oluşturulacak (şifreli olarak)
        return True, "Yeni şifreli veritabanı oluşturulacak"

    if is_encrypted_db(db_path):
        # Zaten şifreli
        return True, "Veritabanı zaten şifreli"

    # Şifresiz - migrate et
    backup_path = db_path + ".unencrypted.backup"
    temp_path = db_path + ".encrypted.tmp"

    try:
        # Orijinali yedekle
        shutil.copy2(db_path, backup_path)

        # Şifreli versiyonu oluştur
        if migrate_to_encrypted(db_path, temp_path):
            # Başarılı - eski dosyayı sil, yenisini taşı
            os.remove(db_path)
            shutil.move(temp_path, db_path)
            logger.info(f"Veritabanı şifrelendi. Yedek: {backup_path}")
            return True, f"Veritabanı başarıyla şifrelendi. Yedek: {backup_path}"
        else:
            # Başarısız - temp dosyayı sil
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False, "Şifreleme başarısız"

    except Exception as e:
        logger.error(f"ensure_encrypted_db hatası: {e}")
        return False, f"Hata: {e}"


def verify_db_access(db_path: str) -> Tuple[bool, str]:
    """
    Veritabanına erişimi doğrula.

    Returns:
        (erişilebilir, mesaj) tuple'ı
    """
    try:
        if not os.path.exists(db_path):
            return True, "Veritabanı henüz oluşturulmamış"

        key = derive_db_key()

        if SQLCIPHER_AVAILABLE and is_encrypted_db(db_path):
            conn = get_encrypted_connection(db_path, key)
            # Basit bir sorgu çalıştır
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return True, "Şifreli veritabanı erişimi başarılı"
        else:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return True, "Veritabanı erişimi başarılı"

    except Exception as e:
        logger.error(f"Veritabanı erişim hatası: {e}")
        return False, f"Erişim hatası: {e}"


# Test fonksiyonu
if __name__ == "__main__":
    print("=" * 50)
    print("TakibiEsasi Veritabanı Şifreleme Testi")
    print("=" * 50)
    print()

    print(f"SQLCipher Durumu: {'Aktif' if SQLCIPHER_AVAILABLE else 'Yüklü Değil'}")
    print()

    key = derive_db_key()
    print(f"Türetilen Anahtar: {key[:32]}...")
    print()

    # Test veritabanı
    test_db = "test_encrypted.db"

    if SQLCIPHER_AVAILABLE:
        print("Şifreli test veritabanı oluşturuluyor...")
        conn = get_encrypted_connection(test_db, key)
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO test (data) VALUES ('Gizli veri!')")
        conn.commit()
        conn.close()
        print(f"Oluşturuldu: {test_db}")

        print("\nŞifreli veritabanı okunuyor...")
        conn = get_encrypted_connection(test_db, key)
        result = conn.execute("SELECT * FROM test").fetchone()
        print(f"Okunan veri: {result}")
        conn.close()

        # Temizle
        os.remove(test_db)
        print("\nTest dosyası silindi.")
    else:
        print("SQLCipher yüklü değil. Yüklemek için:")
        print("  pip install sqlcipher3-binary")
