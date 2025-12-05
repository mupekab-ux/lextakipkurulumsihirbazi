# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QDialog
from PyQt6.QtCore import QSettings

try:  # pragma: no cover - runtime import guard
    from app.db import initialize_database, auto_backup_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from db import initialize_database, auto_backup_on_startup

try:  # pragma: no cover - runtime import guard
    from app.ui_main import MainWindow
except ModuleNotFoundError:  # pragma: no cover
    from ui_main import MainWindow

try:  # pragma: no cover - runtime import guard
    from app.models import get_setting
except ModuleNotFoundError:  # pragma: no cover
    from models import get_setting

try:  # pragma: no cover - runtime import guard
    from app.utils import (
        ensure_vekalet_dir_exists,
        load_theme_from_settings_and_apply,
        verify_password,
    )
except ModuleNotFoundError:  # pragma: no cover
    from utils import (
        ensure_vekalet_dir_exists,
        load_theme_from_settings_and_apply,
        verify_password,
    )

try:  # pragma: no cover - runtime import guard
    from app.ui_login_dialog import LoginDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_login_dialog import LoginDialog

try:  # pragma: no cover - runtime import guard
    from app.ui_activation_dialog import check_license_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from ui_activation_dialog import check_license_on_startup

try:  # pragma: no cover - runtime import guard
    from app.ui_agreements_dialog import check_agreements_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from ui_agreements_dialog import check_agreements_on_startup

try:  # pragma: no cover - runtime import guard
    from app.ui_update_dialog import check_for_updates_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from ui_update_dialog import check_for_updates_on_startup


def main():
    initialize_database()
    ensure_vekalet_dir_exists()

    # Otomatik yedekleme (ayarlara göre)
    settings = QSettings("MyCompany", "TakibiEsasi")
    auto_backup_enabled = settings.value("backup/auto_backup", True, type=bool)
    backup_keep_count = settings.value("backup/keep_count", 10, type=int)

    if auto_backup_enabled:
        backup_path = auto_backup_on_startup(keep_count=backup_keep_count)
        if backup_path:
            print(f"Otomatik yedekleme oluşturuldu: {backup_path}")

    app = QApplication(sys.argv)
    load_theme_from_settings_and_apply()

    # Sözleşme kontrolü - kabul edilmemişse uygulama açılmaz
    if not check_agreements_on_startup():
        return

    # Lisans kontrolü - aktive edilmemişse uygulama açılmaz
    if not check_license_on_startup():
        return

    # Güncelleme kontrolü - kritik güncelleme varsa kurulum başlar
    if not check_for_updates_on_startup():
        return

    stored_hash = get_setting("app_password")
    if stored_hash:
        pwd, ok = QInputDialog.getText(
            None, "Parola", "Parolayı giriniz:", QLineEdit.EchoMode.Password
        )
        if not ok or not verify_password(pwd, stored_hash):
            QMessageBox.critical(None, "Hata", "Parola hatalı")
            return

    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        return

    window = MainWindow(login.user)
    window.showMaximized()
    print("Veritabanı oluşturuldu")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
