# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QDialog
from PyQt6.QtCore import QSettings

try:  # pragma: no cover - runtime import guard
    from app.db import initialize_database, auto_backup_on_startup, get_database_path
except ModuleNotFoundError:  # pragma: no cover
    from db import initialize_database, auto_backup_on_startup, get_database_path

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
    from app.ui_activation_dialog import check_license_on_startup, ActivationDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_activation_dialog import check_license_on_startup, ActivationDialog

try:  # pragma: no cover - runtime import guard
    from app.ui_agreements_dialog import check_agreements_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from ui_agreements_dialog import check_agreements_on_startup

try:  # pragma: no cover - runtime import guard
    from app.ui_update_dialog import check_for_updates_on_startup
except ModuleNotFoundError:  # pragma: no cover
    from ui_update_dialog import check_for_updates_on_startup

try:  # pragma: no cover - runtime import guard
    from app.demo_manager import DemoManager, get_demo_manager
except ModuleNotFoundError:  # pragma: no cover
    from demo_manager import DemoManager, get_demo_manager

try:  # pragma: no cover - runtime import guard
    from app.ui_demo_dialog import DemoRegistrationDialog, DemoExpiredDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_demo_dialog import DemoRegistrationDialog, DemoExpiredDialog


def check_demo_on_startup() -> bool:
    """
    Demo durumunu kontrol et.

    Returns:
        bool: Uygulama devam edebilir mi?
    """
    try:
        db_path = get_database_path()
        demo_manager = get_demo_manager(db_path)
        status = demo_manager.get_demo_status()

        # Tam lisans varsa devam et
        if status["status"] == "licensed":
            return True

        # Demo kaydı yoksa kayıt dialogu göster
        if status["status"] == "no_demo":
            dialog = DemoRegistrationDialog()
            if dialog.exec() == QDialog.DialogCode.Accepted:
                result = dialog.get_result()

                if result["action"] == "license":
                    # Lisans aktivasyon dialogunu göster
                    activation = ActivationDialog()
                    if activation.exec() == QDialog.DialogCode.Accepted:
                        return True
                    return False

                elif result["action"] == "demo" and result["email"]:
                    # Demo başlat
                    demo_result = demo_manager.start_demo(result["email"])
                    if demo_result["success"]:
                        QMessageBox.information(
                            None,
                            "Demo Başlatıldı",
                            f"14 günlük demo süreniz başladı!\n\n"
                            f"Tüm özellikleri kullanabilirsiniz.\n"
                            f"Verileriniz satın aldığınızda korunacaktır.\n\n"
                            f"Bitiş tarihi: {demo_result['end_date']}"
                        )
                        return True
                    else:
                        QMessageBox.warning(
                            None,
                            "Demo Başlatılamadı",
                            demo_result.get("error", "Bilinmeyen hata oluştu.")
                        )
                        return check_demo_on_startup()  # Tekrar dene

            return False  # İptal edildi

        # Demo süresi dolmuş
        if status["status"] == "expired":
            dialog = DemoExpiredDialog(
                expired_days_ago=status.get("expired_days_ago", 0)
            )
            result = dialog.exec()

            if result == DemoExpiredDialog.RESULT_LICENSE:
                # Lisans aktivasyon dialogunu göster
                activation = ActivationDialog()
                if activation.exec() == QDialog.DialogCode.Accepted:
                    # Lisans aktifleştirildi
                    return True
                return check_demo_on_startup()  # Tekrar kontrol

            elif result == DemoExpiredDialog.RESULT_BUY:
                # Satın alma sayfasına yönlendirildi, dialog kapatıldı
                return check_demo_on_startup()  # Tekrar kontrol

            return False  # Çıkış

        # Demo aktif - devam et
        if status["status"] == "demo_active":
            return True

        # Bilinmeyen durum - devam et
        return True

    except Exception as e:
        print(f"Demo kontrolü hatası: {e}")
        # Hata durumunda devam et (kullanıcıyı engelleme)
        return True


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

    # Demo/Lisans kontrolü - önce demo kontrol et
    # Eğer tam lisans varsa demo kontrolü otomatik geçer
    # Eğer demo aktifse veya yeni başlatılırsa devam eder
    # Eğer demo dolmuşsa lisans girişi veya satın alma gerekir
    if not check_demo_on_startup():
        return

    # NOT: Mevcut lisans kontrolü demo sistemi ile entegre edildi
    # check_license_on_startup() artık demo_manager tarafından yönetiliyor

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
