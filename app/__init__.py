# -*- coding: utf-8 -*-
"""
LexTakip - Avukat Dosya Takip Sistemi

Bu paket, hukuk büroları için dosya/dava takip, finans yönetimi ve
tebligat takibi işlevlerini sağlar.
"""

import sys
from pathlib import Path

# app/ dizinini sys.path'e ekle (relative import desteği için)
_app_dir = Path(__file__).parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

__version__ = "1.0.0"
__author__ = "LexTakip Team"
