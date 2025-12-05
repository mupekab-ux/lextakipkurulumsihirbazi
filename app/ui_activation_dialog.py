# -*- coding: utf-8 -*-
"""
TakibiEsasi Aktivasyon Ekranı

Uygulama ilk açıldığında veya lisans geçersiz olduğunda
bu ekran gösterilir.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QClipboard, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QApplication,
    QGroupBox,
    QSpacerItem,
    QSizePolicy,
)

try:  # pragma: no cover - runtime import guard
    from app.license import (
        get_short_machine_id,
        activate_online,
        is_activated,
        get_license_info,
        format_license_for_display,
        get_system_info,
    )
except ModuleNotFoundError:  # pragma: no cover
    from license import (
        get_short_machine_id,
        activate_online,
        is_activated,
        get_license_info,
        format_license_for_display,
        get_system_info,
    )

logger = logging.getLogger(__name__)


class ActivationDialog(QDialog):
    """Lisans aktivasyon diyaloğu."""

    activation_successful = pyqtSignal()

    def __init__(self, parent=None, force_show: bool = False):
        """
        Args:
            parent: Parent widget
            force_show: True ise lisans geçerli olsa bile göster
        """
        super().__init__(parent)
        self._force_show = force_show
        self._setup_ui()
        self._connect_signals()
        self._load_current_status()

    def _setup_ui(self) -> None:
        """UI bileşenlerini oluşturur."""
        self.setWindowTitle("TakibiEsasi - Lisans Aktivasyonu")
        self.setFixedSize(500, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title_label = QLabel("TakibiEsasi Lisans Aktivasyonu")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Ayırıcı çizgi
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Makine ID Grubu
        machine_group = QGroupBox("Makine Kimliği")
        machine_layout = QHBoxLayout(machine_group)

        self.machine_id_label = QLabel()
        self.machine_id_label.setFont(QFont("Consolas", 12))
        self.machine_id_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        machine_layout.addWidget(self.machine_id_label, 1)

        self.copy_btn = QPushButton("Kopyala")
        self.copy_btn.setFixedWidth(80)
        machine_layout.addWidget(self.copy_btn)

        layout.addWidget(machine_group)

        # Bilgi metni
        info_label = QLabel(
            "Lisans satın almak için takibiesasi.com adresini ziyaret edin.\n"
            "Satın alma sonrası size verilen lisans anahtarını aşağıya girin."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666;")
        layout.addWidget(info_label)

        # Lisans Anahtarı Grubu
        license_group = QGroupBox("Lisans Anahtarı")
        license_layout = QVBoxLayout(license_group)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.license_input.setFont(QFont("Consolas", 14))
        self.license_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.license_input.setMaxLength(19)  # XXXX-XXXX-XXXX-XXXX = 19 karakter
        license_layout.addWidget(self.license_input)

        layout.addWidget(license_group)

        # Durum mesajı
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Butonlar
        button_layout = QHBoxLayout()

        self.activate_btn = QPushButton("Aktive Et")
        self.activate_btn.setDefault(True)
        self.activate_btn.setFixedHeight(40)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        button_layout.addWidget(self.activate_btn)

        self.close_btn = QPushButton("Kapat")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setFixedWidth(100)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Makine ID'yi göster
        self.machine_id_label.setText(get_short_machine_id())

    def _connect_signals(self) -> None:
        """Sinyalleri bağlar."""
        self.copy_btn.clicked.connect(self._copy_machine_id)
        self.activate_btn.clicked.connect(self._activate_license)
        self.close_btn.clicked.connect(self._handle_close)
        self.license_input.textChanged.connect(self._format_license_input)
        self.license_input.returnPressed.connect(self._activate_license)

    def _load_current_status(self) -> None:
        """Mevcut lisans durumunu yükler."""
        if is_activated():
            license_info = get_license_info()
            self.status_label.setText(
                "Lisans zaten aktive edilmiş."
            )
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

            if license_info:
                key = license_info.get("license_key", "")
                self.license_input.setText(key)
                self.license_input.setEnabled(False)
                self.activate_btn.setText("Aktive Edildi")
                self.activate_btn.setEnabled(False)

    def _copy_machine_id(self) -> None:
        """Makine ID'yi panoya kopyalar."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.machine_id_label.text())
            self.status_label.setText("Makine kimliği panoya kopyalandı!")
            self.status_label.setStyleSheet("color: #2196F3;")

    def _format_license_input(self, text: str) -> None:
        """Lisans anahtarı girişini formatlar (otomatik tire ekleme)."""
        # Sadece alfanumerik karakterleri al
        clean = ''.join(c for c in text.upper() if c.isalnum())

        # 4'erli gruplara böl
        parts = [clean[i:i+4] for i in range(0, len(clean), 4)]

        # Tire ile birleştir (max 4 grup)
        formatted = '-'.join(parts[:4])

        # Cursor pozisyonunu koru
        cursor_pos = self.license_input.cursorPosition()

        # Güncelle (sonsuz döngüyü önle)
        if formatted != text:
            self.license_input.blockSignals(True)
            self.license_input.setText(formatted)
            # Cursor'ı doğru konuma getir
            new_pos = min(cursor_pos + (len(formatted) - len(text)), len(formatted))
            self.license_input.setCursorPosition(max(0, new_pos))
            self.license_input.blockSignals(False)

    def _activate_license(self) -> None:
        """Lisansı aktive eder."""
        license_key = self.license_input.text().strip()

        if not license_key:
            self.status_label.setText("Lütfen lisans anahtarını girin.")
            self.status_label.setStyleSheet("color: #F44336;")
            return

        # Aktivasyon butonunu devre dışı bırak
        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Aktive ediliyor...")
        QApplication.processEvents()

        try:
            # Online aktivasyon işlemi
            success, message = activate_online(license_key)

            if success:
                self.status_label.setText(message)
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                self.activate_btn.setText("Aktive Edildi")
                self.license_input.setEnabled(False)

                # Başarı sinyali gönder
                self.activation_successful.emit()

                # 1.5 saniye sonra kapat
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1500, self.accept)

            else:
                self.status_label.setText(message)
                self.status_label.setStyleSheet("color: #F44336;")
                self.activate_btn.setEnabled(True)
                self.activate_btn.setText("Aktive Et")

        except Exception as e:
            logger.exception("Aktivasyon hatası")
            self.status_label.setText(f"Aktivasyon hatası: {str(e)}")
            self.status_label.setStyleSheet("color: #F44336;")
            self.activate_btn.setEnabled(True)
            self.activate_btn.setText("Aktive Et")

    def _handle_close(self) -> None:
        """Kapat butonuna basıldığında."""
        if is_activated() or self._force_show:
            self.accept()
        else:
            # Lisans yoksa uygulamadan çık
            reply = QMessageBox.question(
                self,
                "Çıkış",
                "Lisans aktive edilmeden uygulama kullanılamaz.\n\nÇıkmak istediğinize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reject()

    def closeEvent(self, event) -> None:
        """Pencere kapatılırken."""
        if is_activated() or self._force_show:
            event.accept()
        else:
            # Lisans yoksa çıkış onayı iste
            reply = QMessageBox.question(
                self,
                "Çıkış",
                "Lisans aktive edilmeden uygulama kullanılamaz.\n\nÇıkmak istediğinize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                event.accept()
            else:
                event.ignore()


class LicenseInfoDialog(QDialog):
    """Lisans bilgilerini gösteren diyalog (Ayarlar'dan erişim için)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Lisans Bilgileri")
        self.setFixedSize(400, 300)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title = QLabel("TakibiEsasi Lisans Bilgileri")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Ayırıcı
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Lisans bilgileri
        license_info = get_license_info()

        if license_info:
            # Lisans Anahtarı
            key_label = QLabel(f"Lisans Anahtarı: {license_info.get('license_key', '-')}")
            key_label.setFont(QFont("Consolas", 10))
            layout.addWidget(key_label)

            # Aktivasyon Tarihi
            date = license_info.get('activation_date', '')
            if date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date)
                    date = dt.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    pass
            date_label = QLabel(f"Aktivasyon Tarihi: {date}")
            layout.addWidget(date_label)

            # Makine ID
            machine_label = QLabel(f"Makine Kimliği: {get_short_machine_id()}")
            machine_label.setFont(QFont("Consolas", 10))
            layout.addWidget(machine_label)

            # Durum
            status_label = QLabel("Durum: Aktif")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            layout.addWidget(status_label)

        else:
            no_license = QLabel("Lisans aktive edilmemiş.")
            no_license.setStyleSheet("color: #F44336;")
            no_license.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_license)

        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Sistem bilgileri
        sys_info = get_system_info()
        sys_group = QGroupBox("Sistem Bilgileri")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.addWidget(QLabel(f"İşletim Sistemi: {sys_info.get('os', '-')}"))
        sys_layout.addWidget(QLabel(f"Sürüm: {sys_info.get('os_version', '-')[:50]}..."))
        layout.addWidget(sys_group)

        # Kapat butonu
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


def check_license_on_startup() -> bool:
    """
    Uygulama başlangıcında lisans kontrolü yapar.

    Returns:
        True: Lisans geçerli, uygulama açılabilir
        False: Lisans geçersiz veya kullanıcı iptal etti
    """
    if is_activated():
        return True

    # Aktivasyon diyaloğunu göster
    dialog = ActivationDialog()
    result = dialog.exec()

    return result == QDialog.DialogCode.Accepted and is_activated()
