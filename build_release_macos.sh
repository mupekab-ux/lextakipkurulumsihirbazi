#!/bin/bash
# TakibiEsasi - macOS Korumalı Release Build
# Cython + Nuitka (Maksimum Koruma)
#
# Kullanım:
#   ./build_release_macos.sh         # Sadece .app
#   ./build_release_macos.sh --dmg   # .app + DMG

echo "========================================"
echo "TakibiEsasi - macOS Release Build"
echo "Cython + Nuitka (Maksimum Koruma)"
echo "========================================"
echo ""

# Xcode Command Line Tools kontrol
if ! xcode-select -p &> /dev/null; then
    echo "❌ Xcode Command Line Tools kuruluyor..."
    xcode-select --install
    echo "Kurulum tamamlandıktan sonra bu scripti tekrar çalıştırın."
    exit 1
fi
echo "✓ Xcode Command Line Tools"

# Python kontrolü
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 bulunamadı!"
    echo "Kurmak için: brew install python3"
    exit 1
fi
echo "✓ Python3 $(python3 --version | cut -d' ' -f2)"

# Gerekli paketleri kur
echo ""
echo "Bağımlılıklar kontrol ediliyor..."
pip3 install cython nuitka ordered-set zstandard 2>/dev/null || true
pip3 install -r requirements.txt 2>/dev/null || true

# Build
echo ""
if [ "$1" == "--dmg" ]; then
    echo "Build + DMG oluşturuluyor..."
    python3 build_macos_release.py --dmg
else
    echo "Build başlıyor..."
    python3 build_macos_release.py
fi

# Sonuç kontrolü
if [ -d "dist/TakibiEsasi.app" ]; then
    echo ""
    echo "========================================"
    echo "✓ BUILD BAŞARILI!"
    echo "========================================"
    echo ""
    echo "Çıktılar:"
    ls -lh dist/TakibiEsasi.app 2>/dev/null || true
    ls -lh dist/TakibiEsasi.dmg 2>/dev/null || true
    echo ""
    echo "ÖNEMLİ: Bu build tersine mühendisliğe karşı korumalı."
else
    echo ""
    echo "========================================"
    echo "❌ BUILD BAŞARISIZ!"
    echo "========================================"
fi
