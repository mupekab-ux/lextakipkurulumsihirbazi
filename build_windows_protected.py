# -*- coding: utf-8 -*-
"""
TakibiEsasi - Windows Korumalı Build Script

Bu script:
1. Kritik dosyaları Cython ile derler (.pyd)
2. Nuitka ile .exe oluşturur (daha güçlü koruma)

Kullanım:
    python build_windows_protected.py

Gereksinimler:
    pip install cython nuitka ordered-set zstandard

Windows gereksinimleri:
    Visual Studio Build Tools (C++ derleyici)
"""

import os
import sys
import shutil
import subprocess
import platform
import glob
from pathlib import Path

# Build ayarları
APP_NAME = "TakibiEsasi"
MAIN_FILE = "app/main.py"
ICON_FILE = "app/icon.ico"
OUTPUT_DIR = "dist"
BUILD_TEMP = "build_temp"

# Cython ile derlenecek dosyalar (kritik/güvenlik modülleri)
CYTHON_MODULES = [
    "app/license.py",
    "app/demo_manager.py",
    "app/updater.py",
    "app/db_crypto.py",  # Veritabanı şifreleme
    "app/services/user_service.py",
]


def check_platform():
    """Windows'ta mıyız kontrol et."""
    if platform.system() != "Windows":
        print("✗ Bu script sadece Windows'ta çalışır!")
        print(f"  Şu anki sistem: {platform.system()}")
        return False
    print(f"✓ Windows {platform.version()}")
    return True


def check_requirements():
    """Gerekli araçları kontrol et."""
    print("\nGereksinimler kontrol ediliyor...")

    # Cython
    try:
        import Cython
        print(f"✓ Cython {Cython.__version__}")
    except ImportError:
        print("✗ Cython kurulu değil!")
        print("  Kurmak için: pip install cython")
        return False

    # Nuitka
    try:
        import nuitka
        print(f"✓ Nuitka kurulu")
    except ImportError:
        print("✗ Nuitka kurulu değil!")
        print("  Kurmak için: pip install nuitka ordered-set zstandard")
        return False

    return True


def clean_build():
    """Önceki build dosyalarını temizle."""
    print("\nÖnceki build temizleniyor...")

    dirs_to_clean = [OUTPUT_DIR, BUILD_TEMP, "build", "__pycache__"]

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Silindi: {dir_name}")

    # Eski .pyd dosyalarını temizle
    for pattern in ["app/*.pyd", "app/**/*.pyd", "app/*.c", "app/**/*.c"]:
        for f in glob.glob(pattern, recursive=True):
            os.remove(f)
            print(f"  Silindi: {f}")


def compile_cython():
    """Kritik dosyaları Cython ile derle."""
    print("\n" + "=" * 60)
    print("ADIM 1: Cython Derleme")
    print("=" * 60)

    # setup_cython.py çalıştır
    result = subprocess.run(
        [sys.executable, "setup_cython.py", "build_ext", "--inplace"],
        shell=True
    )

    if result.returncode != 0:
        print("✗ Cython derleme başarısız!")
        return False

    # Derlenen dosyaları kontrol et
    compiled_files = []
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        pyd_files = glob.glob(f"{base}*.pyd")
        compiled_files.extend(pyd_files)

    if not compiled_files:
        print("✗ Derlenmiş dosya bulunamadı!")
        return False

    print("\nDerlenen dosyalar:")
    for f in compiled_files:
        print(f"  ✓ {f}")

    return True


def build_nuitka():
    """Nuitka ile .exe oluştur."""
    print("\n" + "=" * 60)
    print("ADIM 2: Nuitka Build")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}.exe",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        "--include-module=openpyxl",
        "--include-module=bcrypt",
        "--include-module=docx",
        "--include-module=pandas",
        "--include-module=requests",
        "--include-module=sqlite3",
        "--include-module=cryptography",  # Veritabanı şifreleme (fallback)
        "--nofollow-import-to=sqlcipher3",  # SQLCipher opsiyonel
        "--assume-yes-for-downloads",
        f"--windows-company-name={APP_NAME}",
        f"--windows-product-name={APP_NAME}",
        "--lto=yes",
    ]

    # Icon ekle
    if os.path.exists(ICON_FILE):
        cmd.append(f"--windows-icon-from-ico={ICON_FILE}")

    # .pyd dosyalarını dahil et
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        pyd_files = glob.glob(f"{base}*.pyd")
        for pyd_file in pyd_files:
            cmd.append(f"--include-data-files={pyd_file}={pyd_file}")

    # Data dosyaları
    cmd.append("--include-data-dir=app/themes=app/themes")
    cmd.append("--include-data-dir=assets=assets")

    # Ana dosya
    cmd.append(MAIN_FILE)

    print("Nuitka komutu çalıştırılıyor...")
    print("Bu işlem 15-30 dakika sürebilir.")
    print()

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("✗ Nuitka build başarısız!")
        return False

    # .exe oluşturuldu mu kontrol et
    exe_path = f"{OUTPUT_DIR}/{APP_NAME}.exe"
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n✓ Uygulama oluşturuldu: {exe_path} ({size_mb:.1f} MB)")
        return True

    print("✗ EXE bulunamadı!")
    return False


def cleanup():
    """Geçici dosyaları temizle."""
    print("\nTemizlik yapılıyor...")

    # C dosyalarını sil
    for pattern in ["app/*.c", "app/**/*.c"]:
        for f in glob.glob(pattern, recursive=True):
            try:
                os.remove(f)
            except:
                pass

    # Build temp klasörlerini sil
    for dir_name in [BUILD_TEMP, "build"]:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
            except:
                pass

    print("✓ Temizlik tamamlandı")


def main():
    print("=" * 60)
    print(f"TakibiEsasi - Windows Korumalı Build")
    print("=" * 60)

    # Platform kontrolü
    if not check_platform():
        return False

    # Gereksinim kontrolü
    if not check_requirements():
        return False

    # Temizlik
    clean_build()

    # Cython derleme (opsiyonel - Nuitka zaten koruma sağlıyor)
    # compile_cython()

    # Nuitka build
    if not build_nuitka():
        return False

    # Temizlik
    cleanup()

    print("\n" + "=" * 60)
    print("✓ BUILD BAŞARILI!")
    print("=" * 60)
    print(f"\nÇıktı: {OUTPUT_DIR}/{APP_NAME}.exe")
    print("\nSonraki adım: Inno Setup ile installer oluşturun")
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
