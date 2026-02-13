# -*- coding: utf-8 -*-
"""
Büro Kurulum Sihirbazı

Yeni büro oluşturma veya mevcut büroya katılma wizard'ı.
"""

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QRadioButton, QButtonGroup, QGroupBox,
    QFormLayout, QMessageBox, QProgressBar,
    QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

try:
    from app.sync import SyncManager, SyncConfig
    from app.sync.models import DeviceInfo
except ImportError:
    from sync import SyncManager, SyncConfig
    from sync.models import DeviceInfo


class SetupWorker(QThread):
    """Arka planda setup işlemi yapan worker"""

    finished = pyqtSignal(bool, dict)
    progress = pyqtSignal(str)

    def __init__(self, sync_manager, action, params):
        super().__init__()
        self.sync_manager = sync_manager
        self.action = action
        self.params = params

    def run(self):
        try:
            if self.action == 'create_firm':
                self.progress.emit("Büro oluşturuluyor...")
                result = self.sync_manager.setup_new_firm(**self.params)
                self.finished.emit(True, result)

            elif self.action == 'join_firm':
                self.progress.emit("Büroya katılınıyor...")
                result = self.sync_manager.join_firm(**self.params)
                self.finished.emit(True, result)

        except Exception as e:
            self.finished.emit(False, {'error': str(e)})


class BuroSetupWizard(QWizard):
    """
    Büro kurulum sihirbazı.

    Sayfalar:
    1. Hoşgeldiniz
    2. Mod seçimi (Yeni oluştur / Katıl)
    3. Sunucu yapılandırması
    4a. Yeni büro bilgileri (mod: new)
    4b. Katılım kodu (mod: join)
    5. Kurtarma kodu gösterimi (mod: new)
    6. Tamamlandı
    """

    # Page IDs
    PAGE_WELCOME = 0
    PAGE_MODE = 1
    PAGE_SERVER = 2
    PAGE_NEW_FIRM = 3
    PAGE_JOIN_FIRM = 4
    PAGE_RECOVERY = 5
    PAGE_COMPLETE = 6

    def __init__(self, sync_manager: SyncManager = None, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager or SyncManager("")
        self.setup_result = {}

        self.setWindowTitle("Büro Kurulumu")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(600, 500)

        # Sayfaları ekle
        self.setPage(self.PAGE_WELCOME, WelcomePage())
        self.setPage(self.PAGE_MODE, ModeSelectPage())
        self.setPage(self.PAGE_SERVER, ServerConfigPage())
        self.setPage(self.PAGE_NEW_FIRM, NewFirmPage(self))
        self.setPage(self.PAGE_JOIN_FIRM, JoinFirmPage(self))
        self.setPage(self.PAGE_RECOVERY, RecoveryCodePage(self))
        self.setPage(self.PAGE_COMPLETE, CompletePage(self))

        # Başlangıç sayfası
        self.setStartId(self.PAGE_WELCOME)

    def get_mode(self) -> str:
        """Seçilen modu döndür: 'new' veya 'join'"""
        mode_page = self.page(self.PAGE_MODE)
        return mode_page.get_mode() if mode_page else 'new'


class WelcomePage(QWizardPage):
    """Hoşgeldiniz sayfası"""

    def __init__(self):
        super().__init__()
        self.setTitle("Büro Senkronizasyonu")
        self.setSubTitle("Birden fazla bilgisayarda çalışmak için büro kurulumu yapın.")

        layout = QVBoxLayout()

        # Açıklama
        info_label = QLabel("""
        <h3>Büro Senkronizasyonu Nedir?</h3>
        <p>Büro senkronizasyonu, TakibiEsasi verilerinizi birden fazla
        bilgisayar arasında güvenli şekilde paylaşmanızı sağlar.</p>

        <h4>Özellikler:</h4>
        <ul>
            <li>Tüm dosya ve finansal veriler otomatik senkronize edilir</li>
            <li>Veriler AES-256 ile şifrelenir</li>
            <li>Çevrimdışı çalışma desteği</li>
            <li>Çakışma çözümü (son değişiklik kazanır)</li>
        </ul>

        <h4>Gereksinimler:</h4>
        <ul>
            <li>Yerel ağda çalışan bir Raspberry Pi sunucusu</li>
            <li>Tüm cihazların aynı ağda olması</li>
        </ul>
        """)
        info_label.setWordWrap(True)
        info_label.setTextFormat(Qt.TextFormat.RichText)

        layout.addWidget(info_label)
        layout.addStretch()

        self.setLayout(layout)


class ModeSelectPage(QWizardPage):
    """Mod seçimi sayfası"""

    def __init__(self):
        super().__init__()
        self.setTitle("Kurulum Türü")
        self.setSubTitle("Ne yapmak istiyorsunuz?")

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Yeni büro
        self.btn_new = QRadioButton()
        new_layout = QVBoxLayout()
        new_title = QLabel("<b>Yeni Büro Oluştur</b>")
        new_desc = QLabel("İlk kez kurulum yapıyorsanız bu seçeneği seçin.\nSunucu yapılandırması ve admin hesabı oluşturulacak.")
        new_desc.setStyleSheet("color: #666;")
        new_layout.addWidget(new_title)
        new_layout.addWidget(new_desc)

        new_group = QGroupBox()
        new_group.setLayout(new_layout)
        new_group.mousePressEvent = lambda e: self.btn_new.setChecked(True)

        # Mevcut büroya katıl
        self.btn_join = QRadioButton()
        join_layout = QVBoxLayout()
        join_title = QLabel("<b>Mevcut Büroya Katıl</b>")
        join_desc = QLabel("Başka bir bilgisayardan paylaşılan katılım kodunuz varsa\nbu seçeneği seçin.")
        join_desc.setStyleSheet("color: #666;")
        join_layout.addWidget(join_title)
        join_layout.addWidget(join_desc)

        join_group = QGroupBox()
        join_group.setLayout(join_layout)
        join_group.mousePressEvent = lambda e: self.btn_join.setChecked(True)

        # Button group
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.btn_new, 1)
        self.button_group.addButton(self.btn_join, 2)

        # Layout
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_new)
        row1.addWidget(new_group, 1)

        row2 = QHBoxLayout()
        row2.addWidget(self.btn_join)
        row2.addWidget(join_group, 1)

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addStretch()

        self.setLayout(layout)

        # Varsayılan
        self.btn_new.setChecked(True)

    def get_mode(self) -> str:
        """Seçilen modu döndür"""
        if self.btn_new.isChecked():
            return 'new'
        return 'join'

    def nextId(self) -> int:
        return BuroSetupWizard.PAGE_SERVER


class ServerConfigPage(QWizardPage):
    """Sunucu yapılandırması sayfası"""

    def __init__(self):
        super().__init__()
        self.setTitle("Sunucu Yapılandırması")
        self.setSubTitle("Sync sunucusunun adresini girin.")

        layout = QVBoxLayout()

        # Sunucu adresi
        form_layout = QFormLayout()

        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("http://192.168.1.126:8080")
        self.server_url.setText("http://192.168.1.126:8080")
        self.server_url.textChanged.connect(self.completeChanged)

        form_layout.addRow("Sunucu Adresi:", self.server_url)

        layout.addLayout(form_layout)

        # Test butonu
        test_layout = QHBoxLayout()
        self.btn_test = QPushButton("Bağlantıyı Test Et")
        self.btn_test.clicked.connect(self._test_connection)
        self.test_result = QLabel("")

        test_layout.addWidget(self.btn_test)
        test_layout.addWidget(self.test_result)
        test_layout.addStretch()

        layout.addLayout(test_layout)

        # Bilgi
        info = QLabel("""
        <p><b>Not:</b> Raspberry Pi'nizin IP adresini girin.
        Varsayılan port 8080'dir.</p>
        <p>IP adresini bulmak için Raspberry Pi'de <code>hostname -I</code>
        komutunu çalıştırın.</p>
        """)
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; margin-top: 20px;")

        layout.addWidget(info)
        layout.addStretch()

        self.setLayout(layout)

        # Field olarak kaydet (zorunlu değil artık, isComplete ile kontrol ediyoruz)
        self.registerField("server_url", self.server_url)

    def isComplete(self) -> bool:
        """Next butonu için sayfa tamamlanma durumu"""
        return bool(self.server_url.text().strip())

    def _test_connection(self):
        """Bağlantıyı test et"""
        url = self.server_url.text().strip()
        if not url:
            self.test_result.setText("❌ Adres girin")
            return

        self.btn_test.setEnabled(False)
        self.test_result.setText("⏳ Test ediliyor...")
        QApplication.processEvents()

        try:
            import requests
            response = requests.get(f"{url}/api/health", timeout=5, verify=False)
            if response.status_code == 200:
                self.test_result.setText("✅ Bağlantı başarılı")
                self.test_result.setStyleSheet("color: green;")
            else:
                self.test_result.setText(f"❌ Hata: {response.status_code}")
                self.test_result.setStyleSheet("color: red;")
        except Exception as e:
            self.test_result.setText(f"❌ Bağlantı hatası")
            self.test_result.setStyleSheet("color: red;")

        self.btn_test.setEnabled(True)

    def nextId(self) -> int:
        wizard = self.wizard()
        if wizard.get_mode() == 'new':
            return BuroSetupWizard.PAGE_NEW_FIRM
        return BuroSetupWizard.PAGE_JOIN_FIRM


class NewFirmPage(QWizardPage):
    """Yeni büro bilgileri sayfası"""

    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Yeni Büro Oluştur")
        self.setSubTitle("Büro ve yönetici bilgilerini girin.")

        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Büro adı
        self.firm_name = QLineEdit()
        self.firm_name.setPlaceholderText("Örn: Avukat Mehmet Hukuk Bürosu")
        form_layout.addRow("Büro Adı:", self.firm_name)

        # Admin kullanıcı adı
        self.admin_username = QLineEdit()
        self.admin_username.setPlaceholderText("admin")
        form_layout.addRow("Yönetici Kullanıcı Adı:", self.admin_username)

        # Admin şifre
        self.admin_password = QLineEdit()
        self.admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password.setPlaceholderText("En az 8 karakter")
        form_layout.addRow("Yönetici Şifresi:", self.admin_password)

        # Şifre tekrar
        self.admin_password2 = QLineEdit()
        self.admin_password2.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Şifre (Tekrar):", self.admin_password2)

        # E-posta (opsiyonel)
        self.admin_email = QLineEdit()
        self.admin_email.setPlaceholderText("(opsiyonel)")
        form_layout.addRow("E-posta:", self.admin_email)

        layout.addLayout(form_layout)

        # İlerleme
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

        # Fields
        self.registerField("firm_name*", self.firm_name)
        self.registerField("admin_username*", self.admin_username)
        self.registerField("admin_password*", self.admin_password)

    def validatePage(self) -> bool:
        """Sayfa doğrulama"""
        # Şifre kontrolü
        if self.admin_password.text() != self.admin_password2.text():
            QMessageBox.warning(self, "Hata", "Şifreler eşleşmiyor!")
            return False

        if len(self.admin_password.text()) < 8:
            QMessageBox.warning(self, "Hata", "Şifre en az 8 karakter olmalı!")
            return False

        # Büro oluştur
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Büro oluşturuluyor...")
        QApplication.processEvents()

        try:
            server_url = self.field("server_url")
            result = self._wizard.sync_manager.setup_new_firm(
                server_url=server_url,
                firm_name=self.firm_name.text(),
                admin_username=self.admin_username.text(),
                admin_password=self.admin_password.text(),
                admin_email=self.admin_email.text(),
            )

            self._wizard.setup_result = result
            self.progress_bar.setVisible(False)
            self.status_label.setText("✅ Büro oluşturuldu!")
            return True

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"❌ Hata: {e}")
            QMessageBox.critical(self, "Hata", str(e))
            return False

    def nextId(self) -> int:
        return BuroSetupWizard.PAGE_RECOVERY


class JoinFirmPage(QWizardPage):
    """Mevcut büroya katılma sayfası"""

    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Büroya Katıl")
        self.setSubTitle("Yöneticinizden aldığınız katılım kodunu girin.")

        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Katılım kodu
        self.join_code = QLineEdit()
        self.join_code.setPlaceholderText("BURO-XXXX-XXXX-XXXX")
        self.join_code.setFont(QFont("Courier", 14))
        form_layout.addRow("Katılım Kodu:", self.join_code)

        layout.addLayout(form_layout)

        # Bilgi
        info = QLabel("""
        <p><b>Katılım kodu nereden alınır?</b></p>
        <p>Büro yöneticisi, TakibiEsasi ayarlarından
        "Katılım Kodu Oluştur" seçeneğini kullanarak
        size bir kod verebilir.</p>
        <p>Kod tek kullanımlık olabilir ve süresi dolabilir.</p>
        """)
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; margin-top: 20px;")
        layout.addWidget(info)

        # İlerleme
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

        self.registerField("join_code*", self.join_code)

    def validatePage(self) -> bool:
        """Sayfa doğrulama"""
        code = self.join_code.text().strip()
        if not code:
            QMessageBox.warning(self, "Hata", "Katılım kodu girin!")
            return False

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Büroya katılınıyor...")
        QApplication.processEvents()

        try:
            server_url = self.field("server_url")
            result = self._wizard.sync_manager.join_firm(
                server_url=server_url,
                join_code=code,
            )

            self._wizard.setup_result = result
            self.progress_bar.setVisible(False)

            if result.get('status') == 'pending_approval':
                self.status_label.setText("⏳ Yönetici onayı bekleniyor")
                QMessageBox.information(
                    self, "Onay Bekleniyor",
                    "Cihazınız yönetici onayı bekliyor.\n"
                    "Yönetici onayladıktan sonra senkronizasyon başlayacak."
                )
            else:
                self.status_label.setText("✅ Büroya katıldınız!")

            return True

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"❌ Hata: {e}")
            QMessageBox.critical(self, "Hata", str(e))
            return False

    def nextId(self) -> int:
        return BuroSetupWizard.PAGE_COMPLETE


class RecoveryCodePage(QWizardPage):
    """Kurtarma kodu gösterimi sayfası"""

    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Kurtarma Kodu")
        self.setSubTitle("Bu kodu güvenli bir yere kaydedin!")

        layout = QVBoxLayout()

        # Uyarı
        warning = QLabel("""
        <p style="color: red; font-weight: bold;">
        ⚠️ ÖNEMLİ: Bu kodu bir kağıda yazın ve güvenli bir yerde saklayın!
        </p>
        <p>Sunucu arızası veya şifre kaybı durumunda verilerinizi
        kurtarmak için bu koda ihtiyacınız olacak.</p>
        """)
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Kurtarma kodu
        self.recovery_text = QTextEdit()
        self.recovery_text.setReadOnly(True)
        self.recovery_text.setFont(QFont("Courier", 12))
        self.recovery_text.setMinimumHeight(100)
        layout.addWidget(self.recovery_text)

        # Kopyala butonu
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton("📋 Panoya Kopyala")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Onay checkbox
        from PyQt6.QtWidgets import QCheckBox
        self.chk_saved = QCheckBox("Kurtarma kodunu güvenli bir yere kaydettim")
        layout.addWidget(self.chk_saved)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Sayfa gösterildiğinde"""
        result = self._wizard.setup_result
        recovery_code = result.get('recovery_code', '')

        if recovery_code:
            # 24 kelimeyi 4'erli gruplara ayır
            words = recovery_code.split()
            formatted = []
            for i in range(0, len(words), 4):
                group = words[i:i+4]
                formatted.append(f"{i+1:2}. " + "  ".join(group))

            self.recovery_text.setText("\n".join(formatted))
        else:
            self.recovery_text.setText("Kurtarma kodu oluşturulamadı.")

    def _copy_to_clipboard(self):
        """Panoya kopyala"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.recovery_text.toPlainText())
        self.btn_copy.setText("✅ Kopyalandı!")

    def validatePage(self) -> bool:
        """Devam etmeden önce onay kontrolü"""
        if not self.chk_saved.isChecked():
            QMessageBox.warning(
                self, "Uyarı",
                "Devam etmeden önce kurtarma kodunu kaydettiğinizi onaylayın."
            )
            return False
        return True

    def nextId(self) -> int:
        return BuroSetupWizard.PAGE_COMPLETE


class CompletePage(QWizardPage):
    """Tamamlandı sayfası"""

    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Kurulum Tamamlandı")
        self.setSubTitle("Büro senkronizasyonu hazır!")

        layout = QVBoxLayout()

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Katılım kodu (yeni büro için)
        self.join_code_group = QGroupBox("Katılım Kodu")
        join_layout = QVBoxLayout()

        self.join_code_label = QLabel("")
        self.join_code_label.setFont(QFont("Courier", 14))
        self.join_code_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        join_layout.addWidget(self.join_code_label)

        join_info = QLabel(
            "Bu kodu diğer bilgisayarlarda TakibiEsasi'ya katılmak için kullanın."
        )
        join_info.setStyleSheet("color: #666;")
        join_layout.addWidget(join_info)

        self.join_code_group.setLayout(join_layout)
        self.join_code_group.setVisible(False)
        layout.addWidget(self.join_code_group)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Sayfa gösterildiğinde"""
        result = self._wizard.setup_result

        if result.get('status') == 'pending_approval':
            self.result_label.setText("""
            <h3>⏳ Onay Bekleniyor</h3>
            <p>Cihazınız yönetici onayı bekliyor.</p>
            <p>Yönetici cihazınızı onayladıktan sonra
            senkronizasyon otomatik olarak başlayacak.</p>
            """)
        else:
            self.result_label.setText("""
            <h3>✅ Kurulum Tamamlandı!</h3>
            <p>Büro senkronizasyonu başarıyla yapılandırıldı.</p>
            <p>Verileriniz artık otomatik olarak senkronize edilecek.</p>
            """)

            # Yeni büro için katılım kodu göster
            join_code = result.get('join_code')
            if join_code:
                self.join_code_group.setVisible(True)
                self.join_code_label.setText(join_code)

    def nextId(self) -> int:
        return -1  # Son sayfa
