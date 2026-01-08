# -*- coding: utf-8 -*-
"""
TakibiEsasi - Versiyon Güncelleme Scripti

Bu script tüm versiyon dosyalarını tek seferde günceller.

Kullanım:
    python set_version.py 1.2.0
    python set_version.py 2.0.0
    python set_version.py --show  (mevcut versiyonu göster)
"""

import re
import sys
from pathlib import Path

# Proje kök dizini
ROOT = Path(__file__).parent

# Güncellenecek dosyalar ve pattern'ler
VERSION_FILES = [
    {
        "file": "version.txt",
        "pattern": r".*",
        "replacement": "{version}",
        "full_replace": True,
    },
    {
        "file": "app/__init__.py",
        "pattern": r'__version__\s*=\s*"[^"]*"',
        "replacement": '__version__ = "{version}"',
    },
    {
        "file": "installer/setup.iss",
        "pattern": r'#define MyAppVersion "[^"]*"',
        "replacement": '#define MyAppVersion "{version}"',
    },
    {
        "file": "build_nuitka.bat",
        "pattern": r"--windows-file-version=[0-9.]+",
        "replacement": "--windows-file-version={version}.0",
    },
    {
        "file": "build_nuitka.bat",
        "pattern": r"--windows-product-version=[0-9.]+",
        "replacement": "--windows-product-version={version}.0",
    },
    {
        "file": "build_nuitka_macos.py",
        "pattern": r'"--macos-app-version=[^"]*"',
        "replacement": '"--macos-app-version={version}"',
    },
]


def get_current_version():
    """Mevcut versiyonu version.txt'den oku."""
    version_file = ROOT / "version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    return "1.0.0"


def validate_version(version):
    """Versiyon formatını doğrula (X.Y.Z)."""
    pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(pattern, version):
        print(f"❌ Geçersiz versiyon formatı: {version}")
        print("   Format: X.Y.Z (örn: 1.2.0, 2.0.0)")
        return False
    return True


def update_file(file_info, new_version):
    """Tek bir dosyayı güncelle."""
    file_path = ROOT / file_info["file"]

    if not file_path.exists():
        print(f"  ⚠ Dosya bulunamadı: {file_info['file']}")
        return False

    content = file_path.read_text(encoding="utf-8")

    if file_info.get("full_replace"):
        new_content = new_version
    else:
        replacement = file_info["replacement"].format(version=new_version)
        new_content = re.sub(file_info["pattern"], replacement, content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"  ✓ {file_info['file']}")
        return True
    else:
        print(f"  - {file_info['file']} (değişiklik yok)")
        return False


def set_version(new_version):
    """Tüm dosyalarda versiyonu güncelle."""
    if not validate_version(new_version):
        return False

    current = get_current_version()
    print(f"\nVersiyon güncelleniyor: {current} → {new_version}\n")

    updated = 0
    for file_info in VERSION_FILES:
        if update_file(file_info, new_version):
            updated += 1

    print(f"\n✓ {updated} dosya güncellendi")
    print(f"\nYeni versiyon: {new_version}")
    print("\nBuild almak için:")
    print("  Windows: build_release.bat")
    print("  macOS:   ./build_release_macos.sh")

    return True


def show_version():
    """Mevcut versiyonu göster."""
    version = get_current_version()
    print(f"Mevcut versiyon: {version}")

    print("\nVersiyon dosyaları:")
    for file_info in VERSION_FILES:
        file_path = ROOT / file_info["file"]
        if file_path.exists():
            print(f"  ✓ {file_info['file']}")
        else:
            print(f"  ✗ {file_info['file']} (bulunamadı)")


def main():
    if len(sys.argv) < 2:
        print("Kullanım:")
        print("  python set_version.py 1.2.0     # Versiyon güncelle")
        print("  python set_version.py --show    # Mevcut versiyonu göster")
        return

    arg = sys.argv[1]

    if arg == "--show":
        show_version()
    else:
        set_version(arg)


if __name__ == "__main__":
    main()
