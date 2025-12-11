#!/bin/bash
# TakibiEsasi macOS Build Script
# Kullanım: ./build_macos.sh [--dmg]

echo "========================================"
echo "TakibiEsasi macOS Build"
echo "========================================"

# Xcode Command Line Tools kontrol
if ! xcode-select -p &> /dev/null; then
    echo "Xcode Command Line Tools kuruluyor..."
    xcode-select --install
    echo "Kurulum tamamlandıktan sonra bu scripti tekrar çalıştırın."
    exit 1
fi

# Python kontrolü
if ! command -v python3 &> /dev/null; then
    echo "Python3 bulunamadı!"
    echo "Kurmak için: brew install python3"
    exit 1
fi

# Nuitka kontrolü ve kurulumu
if ! python3 -c "import nuitka" &> /dev/null; then
    echo "Nuitka kuruluyor..."
    pip3 install nuitka ordered-set zstandard
fi

# PyQt6 ve diğer bağımlılıklar
echo "Bağımlılıklar kontrol ediliyor..."
pip3 install -r requirements.txt 2>/dev/null || true

# Build
if [ "$1" == "--dmg" ]; then
    echo "Build + DMG oluşturuluyor..."
    python3 build_nuitka_macos.py --dmg
else
    echo "Build başlıyor..."
    python3 build_nuitka_macos.py
fi

echo ""
echo "İşlem tamamlandı!"
