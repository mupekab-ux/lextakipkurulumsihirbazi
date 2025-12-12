# -*- coding: utf-8 -*-
"""
TakibiEsasi Güncelleme Modülü

Bu modül, uygulama güncellemelerini kontrol eder ve
kullanıcıya güncelleme seçenekleri sunar.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Uygulama sürümü
APP_VERSION = "1.0.0"

# API URL
API_BASE_URL = "https://api.takibiesasi.com"


@dataclass
class UpdateInfo:
    """Güncelleme bilgisi."""
    has_update: bool
    current_version: str
    latest_version: str
    download_url: Optional[str]
    release_notes: Optional[str]
    is_critical: bool


def get_current_version() -> str:
    """Mevcut uygulama sürümünü döndürür."""
    # Önce version.txt dosyasını kontrol et
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller ile paketlenmiş
            app_dir = Path(sys.executable).parent
        else:
            # Geliştirme ortamı
            app_dir = Path(__file__).parent.parent

        version_file = app_dir / "version.txt"
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception as e:
        logger.warning(f"version.txt okunamadı: {e}")

    return APP_VERSION


def check_for_updates() -> Tuple[bool, Optional[UpdateInfo], Optional[str]]:
    """
    Güncelleme kontrolü yapar.

    Returns:
        (başarılı_mı, güncelleme_bilgisi, hata_mesajı)
    """
    current_version = get_current_version()

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/check-update",
            json={"current_version": current_version},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            update_info = UpdateInfo(
                has_update=data.get("has_update", False),
                current_version=data.get("current_version", current_version),
                latest_version=data.get("latest_version", current_version),
                download_url=data.get("download_url"),
                release_notes=data.get("release_notes"),
                is_critical=data.get("is_critical", False)
            )
            return True, update_info, None
        else:
            return False, None, f"Sunucu hatası: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, None, "Sunucuya bağlanılamadı"
    except requests.exceptions.Timeout:
        return False, None, "Bağlantı zaman aşımı"
    except Exception as e:
        logger.error(f"Güncelleme kontrolü hatası: {e}")
        return False, None, str(e)


def download_update(download_url: str, progress_callback=None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Güncellemeyi indirir.

    Args:
        download_url: İndirme URL'i
        progress_callback: İlerleme callback'i (percent, downloaded, total)

    Returns:
        (başarılı_mı, dosya_yolu, hata_mesajı)
    """
    if not download_url:
        return False, None, "İndirme bağlantısı bulunamadı"

    try:
        logger.info(f"İndirme başlıyor: {download_url}")

        # Geçici dizine indir
        temp_dir = tempfile.gettempdir()
        filename = download_url.split("/")[-1]

        # Dosya adı boşsa veya geçersizse
        if not filename or '.' not in filename:
            filename = "TakibiEsasi_Setup.exe"

        file_path = os.path.join(temp_dir, filename)

        response = requests.get(download_url, stream=True, timeout=300)

        # HTTP hata kodlarını kontrol et
        if response.status_code == 404:
            return False, None, "Güncelleme dosyası sunucuda bulunamadı (404)"
        elif response.status_code == 403:
            return False, None, "Güncelleme dosyasına erişim reddedildi (403)"
        elif response.status_code >= 400:
            return False, None, f"Sunucu hatası: HTTP {response.status_code}"

        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        if total_size == 0:
            return False, None, "Dosya boyutu alınamadı - bağlantı sorunu olabilir"

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        progress_callback(percent, downloaded, total_size)

        # Dosya boyutunu doğrula
        if os.path.getsize(file_path) < 1024:  # 1KB'den küçükse sorun var
            os.remove(file_path)
            return False, None, "İndirilen dosya çok küçük - bozuk olabilir"

        logger.info(f"İndirme tamamlandı: {file_path}")
        return True, file_path, None

    except requests.exceptions.ConnectionError:
        logger.error("Bağlantı hatası")
        return False, None, "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin."
    except requests.exceptions.Timeout:
        logger.error("Zaman aşımı")
        return False, None, "İndirme zaman aşımına uğradı. Lütfen tekrar deneyin."
    except requests.exceptions.RequestException as e:
        logger.error(f"İndirme hatası: {e}")
        return False, None, f"İndirme hatası: {str(e)}"
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        return False, None, f"Beklenmeyen hata: {str(e)}"


def install_update(installer_path: str) -> Tuple[bool, Optional[str]]:
    """
    Güncellemeyi kurar.

    Args:
        installer_path: Kurulum dosyası yolu

    Returns:
        (başarılı_mı, hata_mesajı)
    """
    try:
        if not os.path.exists(installer_path):
            return False, "Kurulum dosyası bulunamadı"

        # Windows'ta kurulum dosyasını çalıştır
        if sys.platform == 'win32':
            # /SILENT parametresi ile sessiz kurulum
            subprocess.Popen([installer_path, '/SILENT'])
            return True, None
        else:
            return False, "Bu işletim sistemi desteklenmiyor"

    except Exception as e:
        logger.error(f"Kurulum hatası: {e}")
        return False, str(e)


def open_download_page(url: str = None) -> None:
    """İndirme sayfasını tarayıcıda açar."""
    if url:
        webbrowser.open(url)
    else:
        webbrowser.open("https://takibiesasi.com/download")


def save_skip_version(version: str) -> None:
    """Atlanacak sürümü kaydeder."""
    try:
        config_dir = _get_config_dir()
        config_file = config_dir / "update_config.json"

        config = {}
        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)

        config["skip_version"] = version

        with open(config_file, "w") as f:
            json.dump(config, f)
    except Exception as e:
        logger.error(f"Sürüm atlama kaydedilemedi: {e}")


def get_skip_version() -> Optional[str]:
    """Atlanan sürümü döndürür."""
    try:
        config_dir = _get_config_dir()
        config_file = config_dir / "update_config.json"

        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)
                return config.get("skip_version")
    except Exception as e:
        logger.error(f"Sürüm atlama okunamadı: {e}")
    return None


def _get_config_dir() -> Path:
    """Yapılandırma dizinini döndürür."""
    if os.name == 'nt':  # Windows
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            config_dir = Path(app_data) / "TakibiEsasi"
        else:
            config_dir = Path.home() / "TakibiEsasi"
    else:
        config_dir = Path.home() / ".config" / "takibiesasi"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
