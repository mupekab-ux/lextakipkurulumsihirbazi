# -*- coding: utf-8 -*-
"""
TakibiEsasi - macOS Korumalı Build Script (Cython + Nuitka)

Bu script:
1. Kritik dosyaları Cython ile derler (.so)
2. Nuitka ile .app oluşturur (maksimum koruma)
3. DMG paketi oluşturur

Kullanım:
    python build_macos_release.py [--dmg]

Gereksinimler:
    pip install cython nuitka ordered-set zstandard

macOS gereksinimleri:
    xcode-select --install
"""

import os
import sys
import shutil
import subprocess
import platform
import glob

# Build ayarları
APP_NAME = "TakibiEsasi"
MAIN_FILE = "app/main.py"
ICON_FILE = "assets/icon.icns"
OUTPUT_DIR = "dist"
BUILD_TEMP = "build_temp"

# Cython ile derlenecek dosyalar (kritik/güvenlik modülleri)
CYTHON_MODULES = [
    "app/license.py",
    "app/demo_manager.py",
    "app/updater.py",
    "app/db_crypto.py",
    "app/services/user_service.py",
]


def check_platform():
    """macOS'ta mıyız kontrol et."""
    if platform.system() != "Darwin":
        print("✗ Bu script sadece macOS'ta çalışır!")
        print(f"  Şu anki sistem: {platform.system()}")
        return False
    print(f"✓ macOS {platform.mac_ver()[0]}")
    return True


def check_requirements():
    """Gerekli araçları kontrol et."""
    print("\nGereksinimler kontrol ediliyor...")

    # Xcode
    result = subprocess.run(["xcode-select", "-p"], capture_output=True)
    if result.returncode != 0:
        print("✗ Xcode Command Line Tools kurulu değil!")
        print("  Kurmak için: xcode-select --install")
        return False
    print("✓ Xcode Command Line Tools")

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
        print("✓ Nuitka kurulu")
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

    # Eski .so ve .c dosyalarını temizle
    for pattern in ["app/*.so", "app/**/*.so", "app/*.c", "app/**/*.c"]:
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
        [sys.executable, "setup_cython.py", "build_ext", "--inplace"]
    )

    if result.returncode != 0:
        print("✗ Cython derleme başarısız!")
        return False

    # Derlenen dosyaları kontrol et
    compiled_files = []
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        so_files = glob.glob(f"{base}*.so")
        compiled_files.extend(so_files)

    if not compiled_files:
        print("✗ Derlenmiş dosya bulunamadı!")
        return False

    print("\nDerlenen dosyalar:")
    for f in compiled_files:
        print(f"  ✓ {f}")

    return True


def build_nuitka():
    """Nuitka ile .app oluştur."""
    print("\n" + "=" * 60)
    print("ADIM 2: Nuitka Build")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",

        # macOS ayarları
        "--macos-create-app-bundle",
        f"--macos-app-name={APP_NAME}",
        "--macos-app-version=1.0.0",
        "--macos-disable-console",

        # PyQt6 plugin
        "--enable-plugin=pyqt6",

        # Ek modüller
        "--include-module=openpyxl",
        "--include-module=bcrypt",
        "--include-module=docx",
        "--include-module=pandas",
        "--include-module=requests",
        "--include-module=sqlite3",
        "--include-module=cryptography",
        "--nofollow-import-to=sqlcipher3",
        "--assume-yes-for-downloads",

        # Performans
        "--lto=yes",
    ]

    # Icon ekle
    if os.path.exists(ICON_FILE):
        cmd.append(f"--macos-app-icon={ICON_FILE}")
    elif os.path.exists("app/icon.icns"):
        cmd.append("--macos-app-icon=app/icon.icns")

    # .so dosyalarını dahil et
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        so_files = glob.glob(f"{base}*.so")
        for so_file in so_files:
            cmd.append(f"--include-data-files={so_file}={so_file}")

    # Data dosyaları
    cmd.append("--include-data-dir=app/themes=themes")
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

    # .app oluşturuldu mu kontrol et
    app_path = f"{OUTPUT_DIR}/{APP_NAME}.app"
    if os.path.exists(app_path):
        print(f"\n✓ Uygulama oluşturuldu: {app_path}")
        return True

    print("✗ .app bulunamadı!")
    return False


def create_dmg():
    """DMG installer oluştur."""
    print("\n" + "=" * 60)
    print("ADIM 3: DMG Oluşturma")
    print("=" * 60)

    app_path = f"{OUTPUT_DIR}/{APP_NAME}.app"
    if not os.path.exists(app_path):
        print(f"✗ Uygulama bulunamadı: {app_path}")
        return False

    dmg_path = f"{OUTPUT_DIR}/{APP_NAME}.dmg"

    # Eski DMG'yi sil
    if os.path.exists(dmg_path):
        os.remove(dmg_path)

    cmd = [
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", app_path,
        "-ov",
        "-format", "UDZO",
        dmg_path
    ]

    result = subprocess.run(cmd)

    if result.returncode == 0 and os.path.exists(dmg_path):
        size_mb = os.path.getsize(dmg_path) / (1024 * 1024)
        print(f"\n✓ DMG oluşturuldu: {dmg_path} ({size_mb:.1f} MB)")
        return True

    print("✗ DMG oluşturma başarısız!")
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

    # Build temp klasörünü sil
    for dir_name in [BUILD_TEMP, "build"]:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
            except:
                pass

    print("✓ Temizlik tamamlandı")


def main():
    print("=" * 60)
    print("TakibiEsasi - macOS Korumalı Build")
    print("Cython + Nuitka (Maksimum Koruma)")
    print("=" * 60)

    # Platform kontrolü
    if not check_platform():
        return False

    # Gereksinim kontrolü
    if not check_requirements():
        return False

    # Temizlik
    clean_build()

    # Cython derleme
    if not compile_cython():
        print("⚠ Cython derleme atlandı, sadece Nuitka ile devam ediliyor...")

    # Nuitka build
    if not build_nuitka():
        return False

    # DMG oluştur (--dmg parametresi varsa)
    if "--dmg" in sys.argv:
        if not create_dmg():
            return False

    # Temizlik
    cleanup()

    print("\n" + "=" * 60)
    print("✓ BUILD BAŞARILI!")
    print("=" * 60)
    print(f"\nÇıktılar:")
    print(f"  Uygulama: {OUTPUT_DIR}/{APP_NAME}.app")
    if "--dmg" in sys.argv:
        print(f"  DMG: {OUTPUT_DIR}/{APP_NAME}.dmg")
    print("\nÖNEMLİ: Bu build tersine mühendisliğe karşı korumalı.")
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
