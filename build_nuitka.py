# -*- coding: utf-8 -*-
"""
TakibiEsasi - Nuitka Build Script
Bu script uygulamayı Nuitka ile derler ve korur.

Kullanım:
    python build_nuitka.py

Gereksinimler:
    pip install nuitka ordered-set zstandard

Windows için ek gereksinimler:
    - Visual Studio Build Tools veya MinGW-w64
    - https://visualstudio.microsoft.com/visual-cpp-build-tools/
"""

import os
import sys
import subprocess
import shutil

# Build ayarları
APP_NAME = "TakibiEsasi"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(SCRIPT_DIR, "app/main.py")
ICON_FILE = os.path.join(SCRIPT_DIR, "app/icon.ico")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "dist_nuitka")

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

def build():
    """Nuitka ile build yap"""

    if not check_nuitka():
        return False

    # Output klasörünü temizle
    if os.path.exists(OUTPUT_DIR):
        print(f"Eski build temizleniyor: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    # Nuitka komutunu oluştur
    cmd = [
        sys.executable, "-m", "nuitka",

        # Temel ayarlar
        "--standalone",                    # Bağımsız çalışabilir
        "--onefile",                       # Tek exe dosyası
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}.exe",

        # Windows ayarları
        "--windows-console-mode=disable",  # Konsol penceresi gösterme
        "--windows-company-name=TakibiEsasi",
        "--windows-product-name=TakibiEsasi",
        "--windows-file-version=1.0.0.0",
        "--windows-product-version=1.0.0.0",
        "--windows-file-description=Hukuk Buroları İçin Dava Takip Sistemi",

        # PyQt6 plugin
        "--enable-plugin=pyqt6",

        # Ek modüller (import edilenler)
        "--include-module=openpyxl",
        "--include-module=bcrypt",
        "--include-module=docx",
        "--include-module=pandas",
        "--include-module=requests",
        "--include-module=sqlite3",

        # Data dosyaları
        f"--include-data-dir={os.path.join(SCRIPT_DIR, 'app/themes')}=app/themes",
        f"--include-data-dir={os.path.join(SCRIPT_DIR, 'app/ui')}=app/ui",

        # Performans ve koruma
        "--lto=yes",                       # Link Time Optimization
        "--python-flag=no_site",           # site.py yükleme
        "--python-flag=no_warnings",       # Uyarıları gizle

        # Ana dosya
        MAIN_FILE
    ]

    # Icon varsa ekle
    if os.path.exists(ICON_FILE):
        cmd.insert(-1, f"--windows-icon-from-ico={ICON_FILE}")
        print(f"✓ Icon bulundu: {ICON_FILE}")
    else:
        print(f"⚠ Icon bulunamadı: {ICON_FILE}")

    print("\n" + "="*60)
    print("Nuitka Build Başlıyor...")
    print("Bu işlem 10-30 dakika sürebilir.")
    print("="*60 + "\n")

    # Komutu çalıştır
    print("Komut:", " ".join(cmd))
    print("\n")

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)

    if result.returncode == 0:
        print("\n" + "="*60)
        print("✓ BUILD BAŞARILI!")
        print(f"  Çıktı: {OUTPUT_DIR}/{APP_NAME}.exe")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("✗ BUILD BAŞARISIZ!")
        print("  Hata kodunu yukarıda kontrol edin.")
        print("="*60)
        return False

def build_with_pyarmor():
    """PyArmor + Nuitka kombinasyonu (ekstra koruma)"""

    print("PyArmor ile önce kodu şifreleyip sonra Nuitka ile derleyeceğiz...")

    # PyArmor ile şifrele
    pyarmor_cmd = [
        sys.executable, "-m", "pyarmor", "gen",
        "--output", "app_protected",
        "--recursive",
        "app"
    ]

    print("PyArmor şifreleme başlıyor...")
    result = subprocess.run(pyarmor_cmd)

    if result.returncode != 0:
        print("PyArmor şifreleme başarısız!")
        return False

    # Şifrelenmiş kodu Nuitka ile derle
    # ... (devamı build() fonksiyonu gibi)

    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--pyarmor":
        build_with_pyarmor()
    else:
        build()
