# -*- mode: python ; coding: utf-8 -*-
"""
TakibiEsasi PyInstaller Spec Dosyası

Bu dosya, TakibiEsasi uygulamasını Windows için derlemek için kullanılır.
Derleme için: pyinstaller TakibiEsasi.spec
"""

import os
import sys

block_cipher = None

# Proje kök dizini
ROOT_DIR = os.path.dirname(os.path.abspath(SPEC))

# Uygulama versiyon bilgisi
APP_VERSION = "1.0.0"
APP_NAME = "TakibiEsasi"
APP_DESCRIPTION = "Avukatlar için Takip Yönetim Sistemi"
APP_COMPANY = "TakibiEsasi"
APP_COPYRIGHT = "Copyright (c) 2024 TakibiEsasi"

# Dahil edilecek veri dosyaları
datas = [
    # Tema dosyaları
    (os.path.join(ROOT_DIR, 'app', 'themes'), 'themes'),
    # Yasal belgeler
    (os.path.join(ROOT_DIR, 'legal'), 'legal'),
    # Versiyon dosyası
    (os.path.join(ROOT_DIR, 'version.txt'), '.'),
]

# Gizli importlar (dinamik yüklenen modüller)
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'openpyxl',
    'pandas',
    'requests',
    'docx',
    'bcrypt',
    'sqlite3',
    'json',
    'hashlib',
    'uuid',
    'subprocess',
    'tempfile',
    'webbrowser',
]

# Hariç tutulacak modüller (boyut küçültme)
excludes = [
    'tkinter',
    'unittest',
    'test',
    'tests',
    'matplotlib',
    'numpy.testing',
    'scipy',
    'PIL.ImageQt',
]

a = Analysis(
    [os.path.join(ROOT_DIR, 'app', 'main.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI uygulaması, konsol yok
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon dosyası (varsa)
    icon=os.path.join(ROOT_DIR, 'assets', 'icon.ico') if os.path.exists(os.path.join(ROOT_DIR, 'assets', 'icon.ico')) else None,
    # Windows version info
    version='version_info.txt' if os.path.exists(os.path.join(ROOT_DIR, 'version_info.txt')) else None,
)
