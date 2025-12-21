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
    # Assets (ikonlar, görseller)
    (os.path.join(ROOT_DIR, 'assets'), 'assets'),
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
    # SQLCipher veritabanı şifreleme
    'sqlcipher3',
    'pysqlcipher3',
    'pysqlcipher3.dbapi2',
]

# SQLCipher DLL'lerini bul ve ekle
sqlcipher_binaries = []
try:
    import pysqlcipher3
    import os as _os
    pysqlcipher_dir = _os.path.dirname(pysqlcipher3.__file__)
    for f in _os.listdir(pysqlcipher_dir):
        if f.endswith('.dll') or f.endswith('.so') or f.endswith('.pyd'):
            sqlcipher_binaries.append(
                (_os.path.join(pysqlcipher_dir, f), '.')
            )
    print(f"[build] pysqlcipher3 DLL'leri bulundu: {len(sqlcipher_binaries)}")
except ImportError:
    print("[build] pysqlcipher3 yüklü değil, SQLCipher devre dışı")
except Exception as e:
    print(f"[build] SQLCipher DLL arama hatası: {e}")

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
    binaries=sqlcipher_binaries,  # SQLCipher DLL'leri dahil
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
