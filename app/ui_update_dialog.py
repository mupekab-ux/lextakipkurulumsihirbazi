# -*- coding: utf-8 -*-
"""
TakibiEsasi Güncelleme Dialog

Kullanıcıya güncelleme bildirimlerini gösterir.
"""

import logging
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextBrowser,
    QMessageBox,
    QApplication,
    QCheckBox,
)

try:
    from app.updater import (
        check_for_updates,
        download_update,
        install_update,
        open_download_page,
        save_skip_version,
        get_skip_version,
        get_current_version,
        UpdateInfo,
    )
except ModuleNotFoundError:
    from updater import (
        check_for_updates,
        download_update,
        install_update,
        open_download_page,
        save_skip_version,
        get_skip_version,
        get_current_version,
        UpdateInfo,
    )

logger = logging.getLogger(__name__)


class DownloadThread(QThread):
    """Arka planda indirme yapan thread."""

    progress = pyqtSignal(int, int, int)  # percent, downloaded, total
    finished = pyqtSignal(bool, str)  # success, file_path or error

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        def progress_callback(percent, downloaded, total):
            self.progress.emit(percent, downloaded, total)

        success, file_path, error = download_update(
            self.download_url,
            progress_callback=progress_callback
        )

        if success:
            self.finished.emit(True, file_path)
        else:
            self.finished.emit(False, error or "Bilinmeyen hata")


class UpdateDialog(QDialog):
    """Güncelleme bildirimi diyaloğu."""

    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_thread = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Güncelleme Mevcut")
        self.resize(500, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title = QLabel("🎉 Yeni Güncelleme Mevcut!")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Sürüm bilgisi
        version_text = f"Mevcut sürüm: {self.update_info.current_version}\n"
        version_text += f"Yeni sürüm: {self.update_info.latest_version}"

        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(version_label)

        # Kritik güncelleme uyarısı
        if self.update_info.is_critical:
            critical_label = QLabel("⚠️ Bu kritik bir güncelleme! Lütfen hemen güncelleyin.")
            critical_label.setStyleSheet(
                "color: #d32f2f; font-weight: bold; padding: 10px; "
                "background-color: #ffebee; border-radius: 4px;"
            )
            critical_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(critical_label)

        # Sürüm notları
        if self.update_info.release_notes:
            notes_label = QLabel("Yenilikler:")
            notes_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            layout.addWidget(notes_label)

            notes_browser = QTextBrowser()
            notes_browser.setHtml(f"<p>{self.update_info.release_notes}</p>")
            notes_browser.setMaximumHeight(150)
            notes_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 10px;
                }
            """)
            layout.addWidget(notes_browser)

        # İlerleme çubuğu (başlangıçta gizli)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        layout.addStretch()

        # Kritik değilse "Bu sürümü atla" seçeneği
        if not self.update_info.is_critical:
            self.skip_check = QCheckBox("Bu sürümü bir daha sorma")
            self.skip_check.setStyleSheet("color: #888;")
            layout.addWidget(self.skip_check)
        else:
            self.skip_check = None

        # Butonlar
        btn_layout = QHBoxLayout()

        self.later_btn = QPushButton("Daha Sonra")
        self.later_btn.setFixedHeight(40)
        if self.update_info.is_critical:
            self.later_btn.setEnabled(False)
            self.later_btn.setToolTip("Kritik güncelleme atlanamaz")
        self.later_btn.clicked.connect(self._on_later)
        btn_layout.addWidget(self.later_btn)

        btn_layout.addStretch()

        self.download_btn = QPushButton("İndir ve Kur")
        self.download_btn.setFixedHeight(40)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 30px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #43A047; }
            QPushButton:disabled { background-color: #BDBDBD; }
        """)
        self.download_btn.clicked.connect(self._on_download)
        btn_layout.addWidget(self.download_btn)

        layout.addLayout(btn_layout)

    def _on_later(self):
        """Daha sonra butonuna tıklandığında."""
        if self.skip_check and self.skip_check.isChecked():
            save_skip_version(self.update_info.latest_version)
        self.reject()

    def _on_download(self):
        """İndir butonuna tıklandığında."""
        if not self.update_info.download_url:
            # İndirme URL'i yoksa web sitesine yönlendir
            open_download_page()
            self.accept()
            return

        # Butonları devre dışı bırak
        self.download_btn.setEnabled(False)
        self.download_btn.setText("İndiriliyor...")
        self.later_btn.setEnabled(False)

        # İlerleme çubuğunu göster
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)

        # İndirme thread'ini başlat
        self.download_thread = DownloadThread(self.update_info.download_url)
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_progress(self, percent: int, downloaded: int, total: int):
        """İndirme ilerlemesi."""
        self.progress_bar.setValue(percent)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.progress_label.setText(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")

    def _on_download_finished(self, success: bool, result: str):
        """İndirme tamamlandığında."""
        if success:
            self.progress_label.setText("Kurulum başlatılıyor...")
            QApplication.processEvents()

            # Kurulumu başlat
            install_success, error = install_update(result)

            if install_success:
                QMessageBox.information(
                    self,
                    "Güncelleme",
                    "Güncelleme kurulumu başlatıldı.\n\n"
                    "Uygulama şimdi kapatılacak. Kurulum tamamlandıktan sonra "
                    "uygulamayı tekrar açın."
                )
                self.accept()
                # Uygulamayı kapat
                QApplication.quit()
            else:
                QMessageBox.warning(
                    self,
                    "Kurulum Hatası",
                    f"Kurulum başlatılamadı: {error}\n\n"
                    "Güncellemeyi manuel olarak indirip kurabilirsiniz."
                )
                self._reset_ui()
        else:
            QMessageBox.warning(
                self,
                "İndirme Hatası",
                f"İndirme başarısız: {result}\n\n"
                "Güncellemeyi manuel olarak indirip kurabilirsiniz."
            )
            self._reset_ui()

    def _reset_ui(self):
        """UI'ı sıfırla."""
        self.download_btn.setEnabled(True)
        self.download_btn.setText("İndir ve Kur")
        if not self.update_info.is_critical:
            self.later_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

    def closeEvent(self, event):
        """Pencere kapatılırken."""
        if self.update_info.is_critical:
            event.ignore()
            QMessageBox.warning(
                self,
                "Kritik Güncelleme",
                "Bu kritik bir güncelleme ve atlanamaz.\n\n"
                "Lütfen güncellemeyi yükleyin."
            )
        else:
            if self.skip_check and self.skip_check.isChecked():
                save_skip_version(self.update_info.latest_version)
            event.accept()


def check_for_updates_on_startup(parent=None, silent: bool = True) -> bool:
    """
    Uygulama başlangıcında güncelleme kontrolü yapar.

    Args:
        parent: Parent widget
        silent: True ise güncelleme yoksa sessiz kal

    Returns:
        True: Devam edilebilir
        False: Uygulama kapatılmalı (kritik güncelleme kuruldu)
    """
    success, update_info, error = check_for_updates()

    if not success:
        if not silent:
            logger.warning(f"Güncelleme kontrolü başarısız: {error}")
        return True

    if not update_info or not update_info.has_update:
        return True

    # Atlanan sürümü kontrol et
    skip_version = get_skip_version()
    if skip_version == update_info.latest_version and not update_info.is_critical:
        return True

    # Güncelleme dialogunu göster
    dialog = UpdateDialog(update_info, parent)
    result = dialog.exec()

    # Kritik güncelleme kurulduysa uygulama kapanacak
    if update_info.is_critical and result == QDialog.DialogCode.Accepted:
        return False

    return True
