# -*- coding: utf-8 -*-
"""
TakibiEsasi Splash Screen
Uygulama açılırken gösterilen başlangıç ekranı
"""

from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF
import os
import sys


class SplashScreen(QSplashScreen):
    """Özel splash screen"""

    def __init__(self):
        # Splash görseli oluştur
        pixmap = self.create_splash_pixmap()
        super().__init__(pixmap)

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
        )

    def create_splash_pixmap(self):
        """Splash ekranı görseli oluştur"""
        width, height = 500, 350
        pixmap = QPixmap(width, height)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Arka plan gradient
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor("#0A0A0F"))
        gradient.setColorAt(1, QColor("#18181F"))
        painter.fillRect(0, 0, width, height, gradient)

        # Altın kenarlık
        pen = QPen(QColor("#FBBF24"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(1, 1, width - 2, height - 2, 12, 12)

        # Logo (mevcut dosyadan yükle veya metin olarak göster)
        logo_path = self.get_resource_path("assets/icon.png")
        logo_loaded = False

        if os.path.exists(logo_path):
            logo = QPixmap(logo_path)
            if not logo.isNull():
                # Logo'yu 100x100'e ölçekle
                logo = logo.scaled(
                    100,
                    100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_x = (width - logo.width()) // 2
                painter.drawPixmap(logo_x, 50, logo)
                logo_loaded = True

        if not logo_loaded:
            # Logo yoksa metin logosu çiz
            painter.setPen(QColor("#FBBF24"))
            font = QFont("Segoe UI", 48, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 50, width, 100),
                Qt.AlignmentFlag.AlignCenter,
                "⚖"
            )

        # Uygulama adı
        painter.setPen(QColor("#FBBF24"))
        font = QFont("Segoe UI", 26, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 170, width, 40),
            Qt.AlignmentFlag.AlignCenter,
            "TakibiEsasi"
        )

        # Alt başlık
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 11)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 215, width, 25),
            Qt.AlignmentFlag.AlignCenter,
            "Avukatlar için Hukuki Takip Yazılımı"
        )

        # Yükleniyor mesajı
        painter.setPen(QColor("#888888"))
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 280, width, 20),
            Qt.AlignmentFlag.AlignCenter,
            "Yükleniyor..."
        )

        # Versiyon
        painter.setPen(QColor("#555555"))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 320, width, 20),
            Qt.AlignmentFlag.AlignCenter,
            "v1.0.0"
        )

        painter.end()
        return pixmap

    def get_resource_path(self, relative_path):
        """PyInstaller veya Nuitka ile uyumlu kaynak yolu"""
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller
            return os.path.join(sys._MEIPASS, relative_path)
        if '__nuitka_binary_dir' in dir():
            # Nuitka onefile
            return os.path.join(__nuitka_binary_dir, relative_path)  # noqa: F821
        if getattr(sys, 'frozen', False) or '__compiled__' in dir():
            # Nuitka standalone
            return os.path.join(os.path.dirname(sys.executable), relative_path)
        # Geliştirme ortamı - önce app klasöründen dene
        app_path = os.path.join(os.path.dirname(__file__), relative_path)
        if os.path.exists(app_path):
            return app_path
        # Sonra üst klasörden dene
        parent_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), relative_path
        )
        return parent_path

    def show_message(self, message):
        """Alt kısımda mesaj göster"""
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor("#888888"),
        )


def show_splash(app, duration_ms=2000):
    """
    Splash screen göster

    Kullanım:
        splash = show_splash(app)
        # Ana pencereyi oluştur
        main_window = MainWindow()
        # Splash'i kapat ve ana pencereyi göster
        splash.finish(main_window)
        main_window.show()
    """
    splash = SplashScreen()
    splash.show()

    # UI güncellemesi için
    app.processEvents()

    return splash
