# -*- coding: utf-8 -*-
"""
TakibiEsasi - Cython Build Script

Bu script kritik Python dosyalarını Cython ile derler.
Derlenen dosyalar .so (macOS/Linux) veya .pyd (Windows) uzantılı olur.

Kullanım:
    python setup_cython.py build_ext --inplace

Gereksinimler:
    pip install cython

Platform gereksinimleri:
    - Windows: Visual Studio Build Tools
    - macOS: Xcode Command Line Tools (xcode-select --install)
    - Linux: gcc ve python-dev
"""

import os
import sys
import platform
from setuptools import setup, Extension
from Cython.Build import cythonize

# Derlenecek kritik dosyalar
# Bu dosyalar lisans, demo ve güvenlik mantığını içeriyor
CYTHON_MODULES = [
    "app/license.py",           # Lisans doğrulama, makine ID, şifreleme
    "app/demo_manager.py",      # Demo süre yönetimi
    "app/updater.py",           # Güncelleme sistemi
    "app/services/user_service.py",  # Kullanıcı kimlik doğrulama
]

# Derleme ayarları
COMPILER_DIRECTIVES = {
    'language_level': 3,        # Python 3
    'boundscheck': False,       # Performans için
    'wraparound': False,        # Performans için
    'cdivision': True,          # C tarzı bölme
}


def get_extensions():
    """Extension modüllerini oluşturur."""
    extensions = []

    for module_path in CYTHON_MODULES:
        if not os.path.exists(module_path):
            print(f"⚠ Dosya bulunamadı, atlanıyor: {module_path}")
            continue

        # Modül adını oluştur (app/license.py -> app.license)
        module_name = module_path.replace("/", ".").replace("\\", ".").replace(".py", "")

        ext = Extension(
            name=module_name,
            sources=[module_path],
        )
        extensions.append(ext)

    return extensions


def main():
    print("=" * 60)
    print("TakibiEsasi - Cython Build")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version}")
    print()

    # Kontroller
    try:
        import Cython
        print(f"✓ Cython version: {Cython.__version__}")
    except ImportError:
        print("✗ Cython kurulu değil!")
        print("  Kurmak için: pip install cython")
        sys.exit(1)

    # Windows'ta C derleyici kontrolü
    if platform.system() == "Windows":
        print("\n⚠ Windows'ta Visual Studio Build Tools gereklidir.")
        print("  İndirmek için: https://visualstudio.microsoft.com/visual-cpp-build-tools/")

    # macOS'ta Xcode kontrolü
    if platform.system() == "Darwin":
        import subprocess
        result = subprocess.run(["xcode-select", "-p"], capture_output=True)
        if result.returncode == 0:
            print("✓ Xcode Command Line Tools kurulu")
        else:
            print("✗ Xcode Command Line Tools kurulu değil!")
            print("  Kurmak için: xcode-select --install")
            sys.exit(1)

    print()
    print("Derlenecek dosyalar:")
    for module in CYTHON_MODULES:
        if os.path.exists(module):
            print(f"  ✓ {module}")
        else:
            print(f"  ✗ {module} (bulunamadı)")

    print()

    # Setup
    extensions = get_extensions()

    if not extensions:
        print("✗ Derlenecek dosya bulunamadı!")
        sys.exit(1)

    setup(
        name="TakibiEsasi-Cython",
        ext_modules=cythonize(
            extensions,
            compiler_directives=COMPILER_DIRECTIVES,
            annotate=False,  # HTML raporu oluşturma
        ),
        zip_safe=False,
    )

    print()
    print("=" * 60)
    print("✓ Cython derleme tamamlandı!")
    print()
    print("Oluşturulan dosyalar:")

    # Oluşturulan .so/.pyd dosyalarını listele
    for module_path in CYTHON_MODULES:
        base = module_path.replace(".py", "")
        if platform.system() == "Windows":
            pattern = f"{base}*.pyd"
        else:
            pattern = f"{base}*.so"

        import glob
        for compiled in glob.glob(pattern):
            print(f"  → {compiled}")

    print("=" * 60)


if __name__ == "__main__":
    main()
