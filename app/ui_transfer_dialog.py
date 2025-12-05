# -*- coding: utf-8 -*-
"""
TakibiEsasi Transfer Dialog

Bilgisayar transferi için dışa/içe aktarma arayüzü.
"""

import logging
import os
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QGroupBox,
    QProgressBar,
    QApplication,
)

try:
    from app.transfer import (
        export_transfer_package,
        import_transfer_package,
        get_transfer_info,
        TRANSFER_EXTENSION,
    )
except ModuleNotFoundError:
    from transfer import (
        export_transfer_package,
        import_transfer_package,
        get_transfer_info,
        TRANSFER_EXTENSION,
    )

logger = logging.getLogger(__name__)


class TransferExportDialog(QDialog):
    """Dışa aktarma diyaloğu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Bilgisayar Transferi - Dışa Aktar")
        self.setFixedSize(500, 350)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title = QLabel("Verilerinizi Dışa Aktarın")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Ayırıcı
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Açıklama
        desc = QLabel(
            "Bu işlem, tüm verilerinizi (davalar, müvekkiller, ayarlar ve lisans bilgisi) "
            "tek bir dosyaya paketler.\n\n"
            "Bu dosyayı yeni bilgisayarınıza taşıyarak verilerinize kaldığınız yerden "
            "devam edebilirsiniz."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        # İçerik bilgisi
        content_group = QGroupBox("Paket İçeriği")
        content_layout = QVBoxLayout(content_group)
        content_layout.addWidget(QLabel("✓ Veritabanı (davalar, müvekkiller, icra dosyaları)"))
        content_layout.addWidget(QLabel("✓ Vekalet dosyaları"))
        content_layout.addWidget(QLabel("✓ Uygulama ayarları"))
        content_layout.addWidget(QLabel("✓ Lisans bilgisi"))
        layout.addWidget(content_group)

        # Uyarı
        warning = QLabel(
            "⚠ Not: Transfer işlemi 1 transfer hakkı kullanır."
        )
        warning.setStyleSheet("color: #f57c00; font-weight: bold;")
        layout.addWidget(warning)

        layout.addStretch()

        # Butonlar
        btn_layout = QHBoxLayout()

        self.export_btn = QPushButton("Dışa Aktar")
        self.export_btn.setFixedHeight(40)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #43A047; }
        """)
        self.export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(self.export_btn)

        cancel_btn = QPushButton("İptal")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _do_export(self):
        """Dışa aktarma işlemini başlatır."""
        # Dosya kaydetme diyaloğu
        default_name = f"TakibiEsasi_Transfer_{datetime.now().strftime('%Y%m%d')}{TRANSFER_EXTENSION}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Transfer Paketini Kaydet",
            default_name,
            f"TakibiEsasi Transfer (*{TRANSFER_EXTENSION})"
        )

        if not file_path:
            return

        # Butonu devre dışı bırak
        self.export_btn.setEnabled(False)
        self.export_btn.setText("Dışa aktarılıyor...")
        QApplication.processEvents()

        try:
            success, message = export_transfer_package(file_path)

            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", message)
                self.export_btn.setEnabled(True)
                self.export_btn.setText("Dışa Aktar")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen hata: {str(e)}")
            self.export_btn.setEnabled(True)
            self.export_btn.setText("Dışa Aktar")


class TransferImportDialog(QDialog):
    """İçe aktarma diyaloğu."""

    def __init__(self, parent=None, pre_selected_file: str = None):
        super().__init__(parent)
        self._pre_selected_file = pre_selected_file
        self._license_key = None
        self._setup_ui()

        if pre_selected_file:
            self._load_file_info(pre_selected_file)

    def _setup_ui(self):
        self.setWindowTitle("Bilgisayar Transferi - İçe Aktar")
        self.setFixedSize(500, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title = QLabel("Verilerinizi İçe Aktarın")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Ayırıcı
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Açıklama
        desc = QLabel(
            "Eski bilgisayarınızdan aktardığınız transfer paketini (.teb) seçin.\n\n"
            "Mevcut verileriniz varsa yedeklenecektir."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        # Dosya seçimi
        file_group = QGroupBox("Transfer Dosyası")
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel("Dosya seçilmedi")
        self.file_label.setStyleSheet("color: #999;")
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("Gözat")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Dosya bilgileri
        self.info_group = QGroupBox("Paket Bilgileri")
        self.info_layout = QVBoxLayout(self.info_group)
        self.info_label = QLabel("Dosya seçildiğinde bilgiler burada görünecek.")
        self.info_label.setStyleSheet("color: #999;")
        self.info_layout.addWidget(self.info_label)
        self.info_group.setVisible(False)
        layout.addWidget(self.info_group)

        # Uyarı
        warning = QLabel(
            "⚠ Dikkat: Mevcut verileriniz yedeklendikten sonra değiştirilecektir."
        )
        warning.setStyleSheet("color: #f57c00;")
        layout.addWidget(warning)

        layout.addStretch()

        # Butonlar
        btn_layout = QHBoxLayout()

        self.import_btn = QPushButton("İçe Aktar")
        self.import_btn.setFixedHeight(40)
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #BDBDBD; }
        """)
        self.import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(self.import_btn)

        cancel_btn = QPushButton("İptal")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """Dosya seçme diyaloğunu açar."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Transfer Paketini Seç",
            "",
            f"TakibiEsasi Transfer (*{TRANSFER_EXTENSION})"
        )

        if file_path:
            self._load_file_info(file_path)

    def _load_file_info(self, file_path: str):
        """Dosya bilgilerini yükler."""
        self._selected_file = file_path
        self.file_label.setText(os.path.basename(file_path))
        self.file_label.setStyleSheet("color: #333; font-weight: bold;")

        info = get_transfer_info(file_path)
        if info:
            self.info_group.setVisible(True)

            # Mevcut label'ı temizle
            for i in reversed(range(self.info_layout.count())):
                self.info_layout.itemAt(i).widget().setParent(None)

            # Bilgileri göster
            created = info.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    pass

            self.info_layout.addWidget(QLabel(f"Oluşturulma: {created}"))
            self.info_layout.addWidget(QLabel(f"Boyut: {info.get('file_size_mb', 0)} MB"))
            self.info_layout.addWidget(QLabel(f"Sürüm: {info.get('version', '-')}"))

            self.import_btn.setEnabled(True)
        else:
            self.info_group.setVisible(False)
            QMessageBox.warning(self, "Uyarı", "Bu dosya geçerli bir transfer paketi değil.")

    def _do_import(self):
        """İçe aktarma işlemini başlatır."""
        reply = QMessageBox.question(
            self,
            "Onay",
            "Veriler içe aktarılacak. Mevcut verileriniz yedeklenecek.\n\nDevam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.import_btn.setEnabled(False)
        self.import_btn.setText("İçe aktarılıyor...")
        QApplication.processEvents()

        try:
            success, message, license_key = import_transfer_package(self._selected_file)

            if success:
                self._license_key = license_key
                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"{message}\n\nUygulama yeniden başlatılacak."
                )
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", message)
                self.import_btn.setEnabled(True)
                self.import_btn.setText("İçe Aktar")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen hata: {str(e)}")
            self.import_btn.setEnabled(True)
            self.import_btn.setText("İçe Aktar")

    def get_license_key(self) -> str:
        """İçe aktarılan lisans anahtarını döndürür."""
        return self._license_key


class TransferDialog(QDialog):
    """Ana transfer diyaloğu - dışa/içe aktar seçimi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Bilgisayar Transferi")
        self.setFixedSize(450, 300)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Başlık
        title = QLabel("Bilgisayar Transferi")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Açıklama
        desc = QLabel(
            "Verilerinizi başka bir bilgisayara taşımak için\n"
            "aşağıdaki seçeneklerden birini kullanın."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        layout.addStretch()

        # Dışa Aktar butonu
        export_btn = QPushButton("📤  Dışa Aktar (Bu Bilgisayardan)")
        export_btn.setFixedHeight(50)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #43A047; }
        """)
        export_btn.clicked.connect(self._show_export)
        layout.addWidget(export_btn)

        # İçe Aktar butonu
        import_btn = QPushButton("📥  İçe Aktar (Yeni Bilgisayara)")
        import_btn.setFixedHeight(50)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        import_btn.clicked.connect(self._show_import)
        layout.addWidget(import_btn)

        layout.addStretch()

        # Kapat butonu
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def _show_export(self):
        """Dışa aktarma diyaloğunu gösterir."""
        dialog = TransferExportDialog(self)
        dialog.exec()

    def _show_import(self):
        """İçe aktarma diyaloğunu gösterir."""
        dialog = TransferImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Uygulama yeniden başlatılmalı
            QMessageBox.information(
                self,
                "Yeniden Başlatma",
                "Değişikliklerin uygulanması için uygulamayı yeniden başlatın."
            )
            self.accept()
