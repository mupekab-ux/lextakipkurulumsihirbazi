# -*- coding: utf-8 -*-
"""
TakibiEsasi - macOS Nuitka Build Script
Bu script uygulamayı macOS için Nuitka ile derler.

Kullanım:
    python build_nuitka_macos.py

Gereksinimler:
    pip install nuitka ordered-set zstandard

macOS için ek gereksinimler:
    - Xcode Command Line Tools: xcode-select --install
    - Python 3.9+ (python.org'dan, homebrew veya pyenv ile)
"""

import os
import sys
import subprocess
import shutil
import platform

# Build ayarları
APP_NAME = "TakibiEsasi"
MAIN_FILE = "app/main.py"
ICON_FILE = "app/icon.icns"  # macOS için .icns formatı
OUTPUT_DIR = "dist_macos"
BUNDLE_ID = "com.takibiesasi.app"

def check_macos():
    """macOS'ta mıyız kontrol et"""
    if platform.system() != "Darwin":
        print("✗ Bu script sadece macOS'ta çalışır!")
        print(f"  Şu anki sistem: {platform.system()}")
        return False
    print(f"✓ macOS tespit edildi: {platform.mac_ver()[0]}")
    return True

def check_xcode():
    """Xcode Command Line Tools kurulu mu?"""
    result = subprocess.run(["xcode-select", "-p"], capture_output=True)
    if result.returncode == 0:
        print("✓ Xcode Command Line Tools kurulu")
        return True
    else:
        print("✗ Xcode Command Line Tools kurulu değil!")
        print("  Kurmak için: xcode-select --install")
        return False

def check_nuitka():
    """Nuitka kurulu mu kontrol et"""
    try:
        import nuitka.Version
        print(f"✓ Nuitka kurulu: {nuitka.Version.getNuitkaVersion()}")
        return True
    except ImportError:
        print("✗ Nuitka kurulu değil!")
        print("  Kurmak için: pip install nuitka ordered-set zstandard")
        return False
    except Exception:
        print("✓ Nuitka kurulu")
        return True

def convert_ico_to_icns():
    """Windows .ico dosyasını macOS .icns'e çevir"""
    ico_file = "app/icon.ico"
    icns_file = "app/icon.icns"

    if os.path.exists(icns_file):
        print(f"✓ Icon zaten mevcut: {icns_file}")
        return True

    if not os.path.exists(ico_file):
        print(f"⚠ Icon bulunamadı: {ico_file}")
        return False

    # sips ile dönüştürme (macOS built-in)
    print("Icon dönüştürülüyor (.ico -> .icns)...")

    # Önce PNG'ye çevir
    png_file = "app/icon.png"
    subprocess.run(["sips", "-s", "format", "png", ico_file, "--out", png_file])

    # iconutil için iconset klasörü oluştur
    iconset_dir = "app/icon.iconset"
    os.makedirs(iconset_dir, exist_ok=True)

    # Farklı boyutlarda iconlar oluştur
    sizes = [16, 32, 64, 128, 256, 512]
    for size in sizes:
        subprocess.run([
            "sips", "-z", str(size), str(size),
            png_file, "--out", f"{iconset_dir}/icon_{size}x{size}.png"
        ])
        # @2x versiyonları
        if size <= 256:
            subprocess.run([
                "sips", "-z", str(size*2), str(size*2),
                png_file, "--out", f"{iconset_dir}/icon_{size}x{size}@2x.png"
            ])

    # iconutil ile .icns oluştur
    result = subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_file])

    # Temizlik
    shutil.rmtree(iconset_dir, ignore_errors=True)
    if os.path.exists(png_file):
        os.remove(png_file)

    if result.returncode == 0:
        print(f"✓ Icon oluşturuldu: {icns_file}")
        return True
    return False

def build():
    """Nuitka ile macOS build yap"""

    # Kontroller
    if not check_macos():
        return False

    if not check_xcode():
        return False

    if not check_nuitka():
        return False

    # Icon dönüştür
    convert_ico_to_icns()

    # Output klasörünü temizle
    if os.path.exists(OUTPUT_DIR):
        print(f"Eski build temizleniyor: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    # Nuitka komutunu oluştur
    cmd = [
        sys.executable, "-m", "nuitka",

        # Temel ayarlar
        "--standalone",                    # Bağımsız çalışabilir
        "--onefile",                       # Tek dosya (macOS'ta Unix executable)
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",

        # macOS ayarları
        "--macos-create-app-bundle",       # .app bundle oluştur
        f"--macos-app-name={APP_NAME}",
        f"--macos-app-version=1.0.0",
        "--macos-disable-console",         # Terminal penceresi açma

        # PyQt6 plugin
        "--enable-plugin=pyqt6",

        # Ek modüller
        "--include-module=openpyxl",
        "--include-module=bcrypt",
        "--include-module=docx",
        "--include-module=pandas",
        "--include-module=requests",
        "--include-module=sqlite3",

        # Data dosyaları
        "--include-data-dir=app/themes=app/themes",
        "--include-data-dir=app/ui=app/ui",

        # Performans ve koruma
        "--lto=yes",                       # Link Time Optimization
        "--python-flag=no_site",
        "--python-flag=no_warnings",

        # Ana dosya
        MAIN_FILE
    ]

    # Icon varsa ekle
    if os.path.exists(ICON_FILE):
        cmd.insert(-1, f"--macos-app-icon={ICON_FILE}")
        print(f"✓ Icon bulundu: {ICON_FILE}")

    print("\n" + "="*60)
    print("Nuitka macOS Build Başlıyor...")
    print("Bu işlem 10-30 dakika sürebilir.")
    print("="*60 + "\n")

    print("Komut:", " ".join(cmd))
    print("\n")

    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)) or ".")

    if result.returncode == 0:
        print("\n" + "="*60)
        print("✓ BUILD BAŞARILI!")
        print(f"  Çıktı: {OUTPUT_DIR}/{APP_NAME}.app")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("✗ BUILD BAŞARISIZ!")
        print("="*60)
        return False

def create_dmg():
    """DMG installer oluştur"""
    app_path = f"{OUTPUT_DIR}/{APP_NAME}.app"
    dmg_path = f"{OUTPUT_DIR}/{APP_NAME}.dmg"

    if not os.path.exists(app_path):
        print(f"✗ App bulunamadı: {app_path}")
        print("  Önce build yapın: python build_nuitka_macos.py")
        return False

    print("DMG oluşturuluyor...")

    # Basit DMG oluşturma
    cmd = [
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", app_path,
        "-ov",  # Overwrite
        "-format", "UDZO",  # Compressed
        dmg_path
    ]

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"✓ DMG oluşturuldu: {dmg_path}")
        return True
    else:
        print("✗ DMG oluşturma başarısız!")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dmg":
        # Önce build, sonra DMG
        if build():
            create_dmg()
    elif len(sys.argv) > 1 and sys.argv[1] == "--dmg-only":
        # Sadece DMG (build zaten yapılmış)
        create_dmg()
    else:
        build()
