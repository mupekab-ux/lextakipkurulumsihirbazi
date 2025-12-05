# -*- coding: utf-8 -*-
"""
TakibiEsasi Bilgisayar Transfer Modülü

Bu modül, kullanıcının verilerini bir bilgisayardan
diğerine taşımasını sağlar.

Transfer paketi (.teb) içeriği:
- data.db (veritabanı)
- license.json (lisans bilgileri)
- settings.json (uygulama ayarları)
"""

import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)

# Transfer dosyası uzantısı
TRANSFER_EXTENSION = ".teb"  # TakibiEsasi Backup


def get_docs_dir() -> Path:
    """TakibiEsasi belgeler dizinini döndürür."""
    return Path.home() / "Documents" / "TakibiEsasi"


def get_db_path() -> Path:
    """Veritabanı dosya yolunu döndürür."""
    return get_docs_dir() / "data.db"


def export_transfer_package(output_path: str) -> Tuple[bool, str]:
    """
    Transfer paketi oluşturur.

    Args:
        output_path: Çıktı dosyası yolu (.teb)

    Returns:
        (başarılı_mı, mesaj) tuple'ı
    """
    try:
        # Lisans bilgilerini al
        try:
            from app.license import load_license
        except ModuleNotFoundError:
            from license import load_license

        license_data = load_license()

        # Ayarları al
        settings = QSettings("MyCompany", "TakibiEsasi")
        settings_data = {}
        for key in settings.allKeys():
            settings_data[key] = settings.value(key)

        # Geçici dizin oluştur
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Veritabanını kopyala
            db_path = get_db_path()
            if db_path.exists():
                shutil.copy2(db_path, temp_path / "data.db")
            else:
                return False, "Veritabanı dosyası bulunamadı."

            # Lisans bilgilerini kaydet
            if license_data:
                with open(temp_path / "license.json", "w", encoding="utf-8") as f:
                    json.dump(license_data, f, ensure_ascii=False, indent=2)

            # Ayarları kaydet
            with open(temp_path / "settings.json", "w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=2)

            # Meta bilgileri kaydet
            meta = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "app_name": "TakibiEsasi"
            }
            with open(temp_path / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            # Vekalet dosyalarını kopyala (varsa)
            vekalet_dir = get_docs_dir() / "vekaletler"
            if vekalet_dir.exists():
                shutil.copytree(vekalet_dir, temp_path / "vekaletler")

            # ZIP dosyası oluştur
            if not output_path.endswith(TRANSFER_EXTENSION):
                output_path += TRANSFER_EXTENSION

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(temp_path)
                        zipf.write(file_path, arcname)

        # Dosya boyutunu hesapla
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB

        return True, f"Transfer paketi oluşturuldu.\nBoyut: {file_size:.2f} MB\nKonum: {output_path}"

    except Exception as e:
        logger.exception("Transfer paketi oluşturulamadı")
        return False, f"Hata: {str(e)}"


def import_transfer_package(package_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    Transfer paketini içe aktarır.

    Args:
        package_path: Transfer paketi dosya yolu (.teb)

    Returns:
        (başarılı_mı, mesaj, lisans_anahtarı) tuple'ı
    """
    try:
        if not os.path.exists(package_path):
            return False, "Dosya bulunamadı.", None

        if not package_path.endswith(TRANSFER_EXTENSION):
            return False, "Geçersiz dosya formatı. .teb dosyası seçin.", None

        # Geçici dizine çıkart
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with zipfile.ZipFile(package_path, 'r') as zipf:
                zipf.extractall(temp_path)

            # Meta kontrolü
            meta_file = temp_path / "meta.json"
            if not meta_file.exists():
                return False, "Geçersiz transfer paketi.", None

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            if meta.get("app_name") != "TakibiEsasi":
                return False, "Bu dosya TakibiEsasi transfer paketi değil.", None

            # Hedef dizini oluştur
            docs_dir = get_docs_dir()
            docs_dir.mkdir(parents=True, exist_ok=True)

            # Mevcut veritabanını yedekle
            db_path = get_db_path()
            if db_path.exists():
                backup_name = f"pre_import_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                backup_dir = docs_dir / "yedekler"
                backup_dir.mkdir(exist_ok=True)
                shutil.copy2(db_path, backup_dir / backup_name)

            # Veritabanını kopyala
            source_db = temp_path / "data.db"
            if source_db.exists():
                shutil.copy2(source_db, db_path)
            else:
                return False, "Transfer paketinde veritabanı bulunamadı.", None

            # Ayarları yükle
            settings_file = temp_path / "settings.json"
            if settings_file.exists():
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)

                settings = QSettings("MyCompany", "TakibiEsasi")
                for key, value in settings_data.items():
                    settings.setValue(key, value)

            # Vekalet dosyalarını kopyala
            vekalet_source = temp_path / "vekaletler"
            if vekalet_source.exists():
                vekalet_dest = docs_dir / "vekaletler"
                if vekalet_dest.exists():
                    shutil.rmtree(vekalet_dest)
                shutil.copytree(vekalet_source, vekalet_dest)

            # Lisans anahtarını al
            license_key = None
            license_file = temp_path / "license.json"
            if license_file.exists():
                with open(license_file, "r", encoding="utf-8") as f:
                    license_data = json.load(f)
                license_key = license_data.get("license_key")

        return True, "Veriler başarıyla içe aktarıldı.", license_key

    except zipfile.BadZipFile:
        return False, "Bozuk veya geçersiz dosya.", None
    except Exception as e:
        logger.exception("Transfer paketi içe aktarılamadı")
        return False, f"Hata: {str(e)}", None


def get_transfer_info(package_path: str) -> Optional[Dict[str, Any]]:
    """
    Transfer paketi hakkında bilgi döndürür.

    Args:
        package_path: Transfer paketi dosya yolu

    Returns:
        Paket bilgileri sözlüğü veya None
    """
    try:
        with zipfile.ZipFile(package_path, 'r') as zipf:
            with zipf.open("meta.json") as f:
                meta = json.load(f)

            # Dosya boyutu
            file_size = os.path.getsize(package_path) / (1024 * 1024)

            return {
                "version": meta.get("version"),
                "created_at": meta.get("created_at"),
                "file_size_mb": round(file_size, 2)
            }
    except Exception:
        return None
