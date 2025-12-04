# -*- coding: utf-8 -*-
"""
LexTakip Servis Modülleri

Bu paket, iş mantığını servislere bölerek daha iyi organizasyon sağlar.
Geriye dönük uyumluluk için tüm fonksiyonlar models.py'den de erişilebilir.

Kullanım:
    # Yeni stil (önerilen)
    from app.services.dosya_service import add_dosya, get_dosya
    from app.services.user_service import authenticate, get_users

    # Eski stil (geriye dönük uyumluluk)
    from app.models import add_dosya, get_dosya, authenticate
"""

# Tüm servisleri import et (relative import for PyInstaller compatibility)
from .base import *
from .dosya_service import *
from .tebligat_service import *
from .arabuluculuk_service import *
from .user_service import *
from .export_service import *
