# -*- coding: utf-8 -*-
import os
import sys
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtGui import QIcon

try:  # pragma: no cover - runtime import guard
    from app.models import authenticate
except ModuleNotFoundError:  # pragma: no cover
    from models import authenticate


def _resource_path(relative_path: str) -> str:
    """Kaynak dosya yolunu çözer."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    elif getattr(sys, 'frozen', False) or '__compiled__' in dir():
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TakibiEsasi - Giriş")

        # Pencere ikonunu ayarla
        icon_path = _resource_path("assets/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Kullanıcı Adı"))
        self.user_edit = QLineEdit()
        layout.addWidget(self.user_edit)

        layout.addWidget(QLabel("Parola"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pass_edit)

        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("Giriş")
        self.cancel_btn = QPushButton("İptal")
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.login_btn.clicked.connect(self.handle_login)
        self.cancel_btn.clicked.connect(self.reject)
        self.user = None

    def handle_login(self) -> None:
        username = self.user_edit.text().strip()
        password = self.pass_edit.text()
        user = authenticate(username, password)
        if user:
            self.user = user
            self.accept()
        else:
            QMessageBox.warning(self, "Hata", "Geçersiz kullanıcı adı veya parola")
