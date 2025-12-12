# -*- coding: utf-8 -*-
"""
TakibiEsasi - macOS Korumalı Build Script

Bu script:
1. Kritik dosyaları Cython ile derler
2. PyInstaller ile .app oluşturur
3. DMG paketi oluşturur

Kullanım:
    python build_macos_protected.py [--dmg]

Gereksinimler:
    pip install cython pyinstaller

macOS gereksinimleri:
    xcode-select --install
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
ICON_FILE = "app/icon.icns"
OUTPUT_DIR = "dist_protected"
BUILD_TEMP = "build_temp"

# Cython ile derlenecek dosyalar
CYTHON_MODULES = [
    "app/license.py",
    "app/demo_manager.py",
    "app/updater.py",
    "app/services/user_service.py",
]

# PyInstaller'a dahil edilecek veri dosyaları
DATA_FILES = [
    ("app/themes", "app/themes"),
    ("app/icon.png", "app"),
    ("app/icon.ico", "app"),
    ("assets", "assets"),
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

    # PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("✗ PyInstaller kurulu değil!")
        print("  Kurmak için: pip install pyinstaller")
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

    # Eski .so dosyalarını temizle
    for pattern in ["app/*.so", "app/**/*.so"]:
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
        capture_output=False
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


def prepare_build_directory():
    """Build için geçici dizin hazırla."""
    print("\n" + "=" * 60)
    print("ADIM 2: Build Dizini Hazırlama")
    print("=" * 60)

    os.makedirs(BUILD_TEMP, exist_ok=True)

    # app klasörünü kopyala
    shutil.copytree("app", f"{BUILD_TEMP}/app", dirs_exist_ok=True)

    # assets klasörünü kopyala
    if os.path.exists("assets"):
        shutil.copytree("assets", f"{BUILD_TEMP}/assets", dirs_exist_ok=True)

    # Derlenen .so dosyalarını kopyala ve orijinal .py dosyalarını sil
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        py_file = f"{BUILD_TEMP}/{module}"

        # .so dosyasını bul ve kopyala
        so_files = glob.glob(f"{base}*.so")
        for so_file in so_files:
            dest = f"{BUILD_TEMP}/{so_file}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(so_file, dest)
            print(f"  Kopyalandı: {so_file} → {dest}")

        # Orijinal .py dosyasını sil (koruma için)
        if os.path.exists(py_file):
            os.remove(py_file)
            print(f"  Silindi: {py_file}")

    # __init__.py dosyalarını koru (import için gerekli)
    for root, dirs, files in os.walk(f"{BUILD_TEMP}/app"):
        init_file = os.path.join(root, "__init__.py")
        if not os.path.exists(init_file):
            Path(init_file).touch()

    print("✓ Build dizini hazır")
    return True


def build_pyinstaller():
    """PyInstaller ile .app oluştur."""
    print("\n" + "=" * 60)
    print("ADIM 3: PyInstaller Build")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # PyInstaller komutunu oluştur
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # GUI uygulama
        "--onedir",  # Tek klasör (onefile .so ile sorun çıkarabilir)
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={BUILD_TEMP}/pyinstaller_work",
        f"--specpath={BUILD_TEMP}",
        "--clean",
        "--noconfirm",
    ]

    # Icon ekle
    if os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])

    # Veri dosyalarını ekle
    for src, dest in DATA_FILES:
        src_path = f"{BUILD_TEMP}/{src}" if os.path.exists(f"{BUILD_TEMP}/{src}") else src
        if os.path.exists(src_path):
            cmd.extend(["--add-data", f"{src_path}:{dest}"])

    # .so dosyalarını ekle
    for module in CYTHON_MODULES:
        base = module.replace(".py", "")
        so_files = glob.glob(f"{BUILD_TEMP}/{base}*.so")
        for so_file in so_files:
            # Hedef dizini belirle
            dest_dir = os.path.dirname(module)
            cmd.extend(["--add-binary", f"{so_file}:{dest_dir}"])

    # Hidden imports
    cmd.extend([
        "--hidden-import=openpyxl",
        "--hidden-import=bcrypt",
        "--hidden-import=docx",
        "--hidden-import=pandas",
        "--hidden-import=requests",
        "--hidden-import=sqlite3",
        "--hidden-import=PyQt6",
    ])

    # Ana dosya
    cmd.append(f"{BUILD_TEMP}/{MAIN_FILE}")

    print("PyInstaller komutu:")
    print(" ".join(cmd[:10]) + " ...")
    print()

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("✗ PyInstaller build başarısız!")
        return False

    # .app oluşturuldu mu kontrol et
    app_path = f"{OUTPUT_DIR}/{APP_NAME}.app"
    if os.path.exists(app_path):
        print(f"\n✓ Uygulama oluşturuldu: {app_path}")
        return True
    else:
        # Klasör modu
        app_path = f"{OUTPUT_DIR}/{APP_NAME}"
        if os.path.exists(app_path):
            print(f"\n✓ Uygulama oluşturuldu: {app_path}")
            return True

    print("✗ Uygulama bulunamadı!")
    return False


def create_dmg():
    """DMG installer oluştur."""
    print("\n" + "=" * 60)
    print("ADIM 4: DMG Oluşturma")
    print("=" * 60)

    app_path = f"{OUTPUT_DIR}/{APP_NAME}.app"
    if not os.path.exists(app_path):
        app_path = f"{OUTPUT_DIR}/{APP_NAME}"

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
            os.remove(f)

    # Build temp klasörünü sil
    if os.path.exists(BUILD_TEMP):
        shutil.rmtree(BUILD_TEMP)

    print("✓ Temizlik tamamlandı")


def main():
    print("=" * 60)
    print(f"TakibiEsasi - macOS Korumalı Build")
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
        return False

    # Build dizini hazırla
    if not prepare_build_directory():
        return False

    # PyInstaller build
    if not build_pyinstaller():
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
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
