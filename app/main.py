# -*- coding: utf-8 -*-
import os
import sys
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QDialog
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QIcon


def resource_path(relative_path: str) -> str:
    """
    PyInstaller veya Nuitka ile paketlendiğinde dosya yollarını düzgün çözer.
    Geliştirme ortamında normal yolu döndürür.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller ile paketlenmiş
        base_path = sys._MEIPASS
    elif '__nuitka_binary_dir' in dir():
        # Nuitka onefile - geçici klasör
        base_path = __nuitka_binary_dir  # noqa: F821
    elif getattr(sys, 'frozen', False) or '__compiled__' in dir():
        # Nuitka standalone veya diğer frozen durumlar
        base_path = os.path.dirname(sys.executable)
    else:
        # Normal Python çalıştırma - app klasörünün bir üst dizini
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

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

try:  # pragma: no cover - runtime import guard
    from app.ui_splash import SplashScreen
except ModuleNotFoundError:  # pragma: no cover
    from ui_splash import SplashScreen


def check_demo_on_startup() -> bool:
    """
    Demo durumunu kontrol et.

    Returns:
        bool: Uygulama devam edebilir mi?
    """
    try:
        # Önce mevcut lisans sistemini kontrol et (license.py)
        # Bu, demo sisteminden bağımsız olarak çalışan eski lisans sistemi
        try:
            from app.license import is_activated, get_license_info
        except ModuleNotFoundError:
            from license import is_activated, get_license_info

        if is_activated():
            # Mevcut lisans geçerli - demo kontrolüne gerek yok
            # Demo manager'ı da güncelle (senkronizasyon)
            license_info = get_license_info()
            if license_info:
                db_path = get_database_path()
                demo_manager = get_demo_manager(db_path)
                demo_manager.activate_license(license_info.get("license_key", ""))
            return True

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

        # Hata durumu - kullanıcıya bildir ve tekrar dene
        if status["status"] == "error":
            error_msg = status.get("error", "Bilinmeyen hata")
            result = QMessageBox.warning(
                None,
                "Demo Kontrol Hatası",
                f"Demo durumu kontrol edilemedi:\n{error_msg}\n\n"
                "Tekrar denemek ister misiniz?",
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
            )
            if result == QMessageBox.StandardButton.Retry:
                return check_demo_on_startup()
            return False

        # Bilinmeyen durum - güvenlik için izin verme
        print(f"Bilinmeyen demo durumu: {status.get('status')}")
        QMessageBox.critical(
            None,
            "Hata",
            f"Beklenmeyen demo durumu: {status.get('status')}\n"
            "Lütfen destek ekibiyle iletişime geçin."
        )
        return False

    except Exception as e:
        print(f"Demo kontrolü hatası: {e}")
        QMessageBox.critical(
            None,
            "Demo Kontrol Hatası",
            f"Demo durumu kontrol edilirken hata oluştu:\n{str(e)}\n\n"
            "Uygulama başlatılamıyor."
        )
        return False


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

    # Uygulama ikonunu ayarla
    icon_path = resource_path("assets/icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Splash Screen göster
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Sözleşme kontrolü - kabul edilmemişse uygulama açılmaz
    splash.close()  # Splash'i kapat, dialoglar gösterilecek
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
