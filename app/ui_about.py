# -*- coding: utf-8 -*-
"""
TakibiEsasi Hakkında Penceresi
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices
from PyQt6.QtCore import Qt, QUrl
import os
import sys


class AboutDialog(QDialog):
    """Hakkında penceresi"""

    VERSION = "1.0.0"
    BUILD_DATE = "Aralik 2024"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hakkinda - TakibiEsasi")
        self.setFixedSize(450, 420)
        self.setModal(True)

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 30, 30, 30)

        # Logo
        logo_label = QLabel()
        logo_path = self.get_resource_path("assets/icon.png")

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    80,
                    80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_label.setPixmap(pixmap)
        else:
            # Logo yoksa emoji göster
            logo_label.setText("⚖")
            logo_label.setStyleSheet("font-size: 64px;")

        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # Uygulama adı
        name_label = QLabel("TakibiEsasi")
        name_label.setObjectName("appName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Versiyon
        version_label = QLabel(f"Versiyon {self.VERSION}")
        version_label.setObjectName("version")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        # Açıklama
        desc_label = QLabel(
            "Turk Avukatlar icin Profesyonel\nHukuki Dosya Takip Yazilimi"
        )
        desc_label.setObjectName("description")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        # Ayırıcı çizgi
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("separator")
        layout.addWidget(line)

        # Bilgiler
        info_label = QLabel(
            f"<p><b>Gelistirici:</b> TakibiEsasi</p>"
            f"<p><b>Build:</b> {self.BUILD_DATE}</p>"
            f"<p><b>Lisans:</b> Ticari Yazilim</p>"
        )
        info_label.setObjectName("info")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        # Butonlar
        btn_layout = QHBoxLayout()

        website_btn = QPushButton("Web Sitesi")
        website_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://takibiesasi.com"))
        )
        btn_layout.addWidget(website_btn)

        support_btn = QPushButton("Destek")
        support_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("mailto:destek@takibiesasi.com"))
        )
        btn_layout.addWidget(support_btn)

        layout.addLayout(btn_layout)

        # Kapat butonu
        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Copyright
        copyright_label = QLabel("2024 TakibiEsasi. Tum haklari saklidir.")
        copyright_label.setObjectName("copyright")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

    def apply_styles(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1a1a24;
            }

            #appName {
                color: #FBBF24;
                font-size: 22px;
                font-weight: bold;
            }

            #version {
                color: #888888;
                font-size: 13px;
            }

            #description {
                color: #FFFFFF;
                font-size: 12px;
            }

            #separator {
                background-color: #333333;
                max-height: 1px;
            }

            #info {
                color: #CCCCCC;
                font-size: 11px;
            }

            QPushButton {
                background-color: #252530;
                color: #FFFFFF;
                border: 1px solid #333333;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 12px;
            }

            QPushButton:hover {
                background-color: #303040;
                border-color: #FBBF24;
            }

            #closeBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FBBF24, stop:1 #D97706);
                color: #0A0A0F;
                border: none;
                font-weight: bold;
            }

            #closeBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FCD34D, stop:1 #F59E0B);
            }

            #copyright {
                color: #555555;
                font-size: 10px;
            }
        """
        )

    def get_resource_path(self, relative_path):
        """PyInstaller ile uyumlu kaynak yolu"""
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        # Önce app klasöründen dene
        app_path = os.path.join(os.path.dirname(__file__), relative_path)
        if os.path.exists(app_path):
            return app_path
        # Sonra üst klasörden dene
        parent_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), relative_path
        )
        return parent_path
