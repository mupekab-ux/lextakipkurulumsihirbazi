# -*- coding: utf-8 -*-
"""
TakibiEsasi Sözleşme Onay Ekranı

İlk kurulumda kullanıcıya KVKK ve EULA sözleşmelerini
gösterir ve onay alır.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QCheckBox,
    QTabWidget,
    QWidget,
    QMessageBox,
    QScrollArea,
    QFrame,
)

logger = logging.getLogger(__name__)

# Sözleşme dosyaları dizini
LEGAL_DIR = Path(__file__).parent.parent / "legal"

# Kabul durumu dosyası
def get_agreements_file() -> Path:
    """Sözleşme kabul dosyasının yolunu döndürür."""
    if os.name == 'nt':  # Windows
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            agreements_dir = Path(app_data) / "TakibiEsasi"
        else:
            agreements_dir = Path.home() / "TakibiEsasi"
    else:  # Linux/Mac
        agreements_dir = Path.home() / ".config" / "takibiesasi"

    agreements_dir.mkdir(parents=True, exist_ok=True)
    return agreements_dir / "agreements.json"


def load_agreement_status() -> Dict:
    """Sözleşme kabul durumunu yükler."""
    try:
        agreements_file = get_agreements_file()
        if agreements_file.exists():
            with open(agreements_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Sözleşme durumu okunamadı: {e}")
    return {}


def save_agreement_status(status: Dict) -> bool:
    """Sözleşme kabul durumunu kaydeder."""
    try:
        agreements_file = get_agreements_file()
        with open(agreements_file, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Sözleşme durumu kaydedilemedi: {e}")
        return False


def are_agreements_accepted() -> bool:
    """Sözleşmelerin kabul edilip edilmediğini kontrol eder."""
    status = load_agreement_status()
    return status.get("kvkk_accepted", False) and status.get("eula_accepted", False)


def load_legal_document(filename: str) -> str:
    """Yasal belgeyi dosyadan yükler."""
    try:
        file_path = LEGAL_DIR / filename
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Markdown'ı basit HTML'e çevir
            content = markdown_to_html(content)
            return content
        else:
            return f"<p>Belge bulunamadı: {filename}</p>"
    except Exception as e:
        logger.error(f"Belge yüklenemedi: {e}")
        return f"<p>Belge yüklenirken hata oluştu: {e}</p>"


def markdown_to_html(md: str) -> str:
    """Basit markdown'ı HTML'e çevirir."""
    lines = md.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        # Başlıklar
        if line.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3>{line[4:]}</h3>')
        # Kalın
        elif '**' in line:
            line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
            while '**' in line:
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
            html_lines.append(f'<p>{line}</p>')
        # Liste
        elif line.startswith('- '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{line[2:]}</li>')
        # Yatay çizgi
        elif line.strip() == '---':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<hr>')
        # Boş satır
        elif line.strip() == '':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<br>')
        # Normal paragraf
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if line.strip():
                html_lines.append(f'<p>{line}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


class AgreementsDialog(QDialog):
    """Sözleşme onay diyaloğu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_documents()

    def _setup_ui(self):
        self.setWindowTitle("TakibiEsasi - Kullanım Koşulları")
        self.setMinimumSize(700, 600)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Başlık
        title = QLabel("Kullanım Koşulları ve Gizlilik")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Açıklama
        desc = QLabel(
            "TakibiEsasi'ı kullanmadan önce lütfen aşağıdaki belgeleri okuyun ve onaylayın."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Tab widget
        self.tabs = QTabWidget()

        # KVKK Tab
        kvkk_tab = QWidget()
        kvkk_layout = QVBoxLayout(kvkk_tab)

        self.kvkk_browser = QTextBrowser()
        self.kvkk_browser.setOpenExternalLinks(True)
        self.kvkk_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
            }
        """)
        kvkk_layout.addWidget(self.kvkk_browser)

        self.kvkk_check = QCheckBox(
            "KVKK Aydınlatma Metni'ni okudum ve kişisel verilerimin "
            "yukarıda belirtilen şekilde işlenmesini kabul ediyorum."
        )
        self.kvkk_check.setStyleSheet("margin-top: 10px; font-weight: bold;")
        self.kvkk_check.stateChanged.connect(self._update_accept_button)
        kvkk_layout.addWidget(self.kvkk_check)

        self.tabs.addTab(kvkk_tab, "KVKK Aydınlatma Metni")

        # EULA Tab
        eula_tab = QWidget()
        eula_layout = QVBoxLayout(eula_tab)

        self.eula_browser = QTextBrowser()
        self.eula_browser.setOpenExternalLinks(True)
        self.eula_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
            }
        """)
        eula_layout.addWidget(self.eula_browser)

        self.eula_check = QCheckBox(
            "Son Kullanıcı Lisans Sözleşmesi'ni (EULA) okudum ve "
            "tüm koşulları kabul ediyorum."
        )
        self.eula_check.setStyleSheet("margin-top: 10px; font-weight: bold;")
        self.eula_check.stateChanged.connect(self._update_accept_button)
        eula_layout.addWidget(self.eula_check)

        self.tabs.addTab(eula_tab, "Kullanım Sözleşmesi (EULA)")

        layout.addWidget(self.tabs)

        # Alt bilgi
        info_label = QLabel(
            "⚠️ Her iki belgeyi de onaylamadan uygulamayı kullanamazsınız."
        )
        info_label.setStyleSheet("color: #f57c00; font-size: 12px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        # Butonlar
        btn_layout = QHBoxLayout()

        self.reject_btn = QPushButton("Reddet ve Çık")
        self.reject_btn.setFixedHeight(40)
        self.reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.reject_btn.clicked.connect(self._on_reject)
        btn_layout.addWidget(self.reject_btn)

        btn_layout.addStretch()

        self.accept_btn = QPushButton("Kabul Ediyorum")
        self.accept_btn.setFixedHeight(40)
        self.accept_btn.setEnabled(False)
        self.accept_btn.setStyleSheet("""
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
        self.accept_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.accept_btn)

        layout.addLayout(btn_layout)

    def _load_documents(self):
        """Belgeleri yükler."""
        # KVKK
        kvkk_content = load_legal_document("KVKK_AYDINLATMA_METNI.md")
        self.kvkk_browser.setHtml(f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    h1 {{ color: #1976D2; font-size: 18px; }}
                    h2 {{ color: #1976D2; font-size: 16px; margin-top: 20px; }}
                    h3 {{ color: #333; font-size: 14px; margin-top: 15px; }}
                    p {{ margin: 8px 0; }}
                    ul {{ margin: 10px 0; padding-left: 20px; }}
                    li {{ margin: 5px 0; }}
                    hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
                </style>
            </head>
            <body>{kvkk_content}</body>
            </html>
        """)

        # EULA
        eula_content = load_legal_document("EULA_TR.md")
        self.eula_browser.setHtml(f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    h1 {{ color: #1976D2; font-size: 18px; }}
                    h2 {{ color: #1976D2; font-size: 16px; margin-top: 20px; }}
                    h3 {{ color: #333; font-size: 14px; margin-top: 15px; }}
                    p {{ margin: 8px 0; }}
                    ul {{ margin: 10px 0; padding-left: 20px; }}
                    li {{ margin: 5px 0; }}
                    hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
                </style>
            </head>
            <body>{eula_content}</body>
            </html>
        """)

    def _update_accept_button(self):
        """Kabul butonunun durumunu günceller."""
        both_checked = self.kvkk_check.isChecked() and self.eula_check.isChecked()
        self.accept_btn.setEnabled(both_checked)

    def _on_accept(self):
        """Kabul butonuna tıklandığında."""
        status = {
            "kvkk_accepted": True,
            "eula_accepted": True,
            "accepted_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        if save_agreement_status(status):
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Hata",
                "Onay kaydedilemedi. Lütfen tekrar deneyin."
            )

    def _on_reject(self):
        """Reddet butonuna tıklandığında."""
        reply = QMessageBox.question(
            self,
            "Çıkış Onayı",
            "Sözleşmeleri kabul etmeden uygulamayı kullanamazsınız.\n\n"
            "Çıkmak istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.reject()

    def closeEvent(self, event):
        """Pencere kapatılırken."""
        if not are_agreements_accepted():
            reply = QMessageBox.question(
                self,
                "Çıkış Onayı",
                "Sözleşmeleri kabul etmeden uygulamayı kullanamazsınız.\n\n"
                "Çıkmak istediğinize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def check_agreements_on_startup() -> bool:
    """
    Uygulama başlangıcında sözleşme kontrolü yapar.

    Returns:
        True: Sözleşmeler kabul edilmiş
        False: Kullanıcı reddetti veya iptal etti
    """
    if are_agreements_accepted():
        return True

    dialog = AgreementsDialog()
    result = dialog.exec()

    return result == QDialog.DialogCode.Accepted
