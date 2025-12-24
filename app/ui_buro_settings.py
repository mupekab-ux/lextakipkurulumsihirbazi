# -*- coding: utf-8 -*-
"""
Büro Ayarları Tab/Dialog

Ayarlar panelinde büro senkronizasyon ayarları.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QMessageBox,
    QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QTextEdit,
    QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

try:
    from app.sync import SyncManager, SyncStatus
except ImportError:
    from sync import SyncManager, SyncStatus


class BuroSettingsTab(QWidget):
    """
    Büro ayarları sekmesi.

    Ayarlar dialog'unda bir tab olarak kullanılır.
    """

    def __init__(self, sync_manager: SyncManager = None, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager
        self._setup_ui()

    def _setup_ui(self):
        """UI oluştur"""
        layout = QVBoxLayout()

        # Bağlantı Durumu
        status_group = QGroupBox("Bağlantı Durumu")
        status_layout = QFormLayout()

        self.lbl_status = QLabel("-")
        self.lbl_firm_name = QLabel("-")
        self.lbl_device_id = QLabel("-")
        self.lbl_last_sync = QLabel("-")
        self.lbl_pending = QLabel("-")

        status_layout.addRow("Durum:", self.lbl_status)
        status_layout.addRow("Büro:", self.lbl_firm_name)
        status_layout.addRow("Cihaz ID:", self.lbl_device_id)
        status_layout.addRow("Son Senkronizasyon:", self.lbl_last_sync)
        status_layout.addRow("Bekleyen Değişiklik:", self.lbl_pending)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # İşlemler
        actions_group = QGroupBox("İşlemler")
        actions_layout = QVBoxLayout()

        # Sync butonu
        self.btn_sync_now = QPushButton("🔄 Şimdi Senkronize Et")
        self.btn_sync_now.clicked.connect(self._sync_now)
        actions_layout.addWidget(self.btn_sync_now)

        # Çakışmalar butonu
        self.btn_view_conflicts = QPushButton("⚠️ Çakışmaları Görüntüle")
        self.btn_view_conflicts.clicked.connect(self._view_conflicts)
        actions_layout.addWidget(self.btn_view_conflicts)

        # Kurulum butonu
        self.btn_setup = QPushButton("🔧 Büro Kurulumu")
        self.btn_setup.clicked.connect(self._open_setup)
        actions_layout.addWidget(self.btn_setup)

        # Ayır butonu
        self.btn_leave = QPushButton("🚪 Bürodan Ayrıl")
        self.btn_leave.setStyleSheet("background-color: #ffcccc;")
        self.btn_leave.clicked.connect(self._leave_firm)
        actions_layout.addWidget(self.btn_leave)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # Yönetici İşlemleri
        self.admin_group = QGroupBox("Yönetici İşlemleri")
        admin_layout = QVBoxLayout()

        self.btn_manage_devices = QPushButton("💻 Cihazları Yönet")
        self.btn_manage_devices.clicked.connect(self._manage_devices)
        admin_layout.addWidget(self.btn_manage_devices)

        self.btn_manage_users = QPushButton("👥 Kullanıcıları Yönet")
        self.btn_manage_users.clicked.connect(self._manage_users)
        admin_layout.addWidget(self.btn_manage_users)

        self.btn_generate_code = QPushButton("🔑 Katılım Kodu Oluştur")
        self.btn_generate_code.clicked.connect(self._generate_join_code)
        admin_layout.addWidget(self.btn_generate_code)

        self.admin_group.setLayout(admin_layout)
        layout.addWidget(self.admin_group)

        layout.addStretch()
        self.setLayout(layout)

        # Periyodik güncelleme
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._refresh)
        self._update_timer.start(5000)

    def set_sync_manager(self, sync_manager: SyncManager):
        """SyncManager'ı ayarla"""
        self.sync_manager = sync_manager
        self._refresh()

    def _refresh(self):
        """Bilgileri yenile"""
        if not self.sync_manager:
            self._show_not_configured()
            return

        info = self.sync_manager.get_status_info()
        status = SyncStatus(info.get('status', 'not_configured'))

        # Pending approval durumunda özel gösterim
        if status == SyncStatus.PENDING_APPROVAL:
            self._show_pending_approval(info)
            return

        if not info.get('is_configured'):
            self._show_not_configured()
            return

        # Durum
        status_icons = {
            SyncStatus.IDLE: "🟢",
            SyncStatus.SYNCING: "🔄",
            SyncStatus.ERROR: "🔴",
            SyncStatus.OFFLINE: "⚫",
            SyncStatus.NOT_CONFIGURED: "⚪",
            SyncStatus.PENDING_APPROVAL: "🟡",
        }
        status_texts = {
            SyncStatus.IDLE: "Senkronize",
            SyncStatus.SYNCING: "Senkronize ediliyor...",
            SyncStatus.ERROR: "Hata",
            SyncStatus.OFFLINE: "Çevrimdışı",
            SyncStatus.NOT_CONFIGURED: "Yapılandırılmamış",
            SyncStatus.PENDING_APPROVAL: "Onay bekleniyor",
        }

        icon = status_icons.get(status, "❓")
        text = status_texts.get(status, str(status))
        self.lbl_status.setText(f"{icon} {text}")

        # Diğer bilgiler
        self.lbl_firm_name.setText(info.get('firm_id', '-') or '-')
        self.lbl_device_id.setText(info.get('device_id', '-') or '-')
        self.lbl_last_sync.setText(info.get('last_sync_at', '-') or '-')
        self.lbl_pending.setText(str(info.get('pending_push', 0)))

        # Butonları güncelle
        is_configured = info.get('is_configured', False)
        is_pending = (status == SyncStatus.PENDING_APPROVAL)

        self.btn_sync_now.setEnabled(is_configured and status != SyncStatus.SYNCING and not is_pending)
        self.btn_sync_now.setText("🔄 Şimdi Senkronize Et")
        # Butonu doğru fonksiyona bağla
        try:
            self.btn_sync_now.clicked.disconnect()
        except:
            pass
        self.btn_sync_now.clicked.connect(self._sync_now)

        # Bürodan ayrıl butonu pending durumunda da aktif olmalı
        self.btn_leave.setEnabled(is_configured or is_pending)
        self.btn_leave.setText("🚪 Bürodan Ayrıl")  # Normal metin
        self.btn_setup.setText("🔧 Ayarları Değiştir" if is_configured else "🔧 Büro Kurulumu")

        # Admin grubu (şimdilik herkese göster)
        self.admin_group.setVisible(is_configured and not is_pending)

    def _show_not_configured(self):
        """Yapılandırılmamış durumu göster"""
        self.lbl_status.setText("⚪ Yapılandırılmamış")
        self.lbl_firm_name.setText("-")
        self.lbl_device_id.setText("-")
        self.lbl_last_sync.setText("-")
        self.lbl_pending.setText("-")

        self.btn_sync_now.setEnabled(False)
        self.btn_leave.setEnabled(False)
        self.btn_leave.setText("🚪 Bürodan Ayrıl")  # Metni sıfırla
        self.btn_setup.setText("🔧 Büro Kurulumu")
        self.admin_group.setVisible(False)

    def _show_pending_approval(self, info: dict):
        """Onay bekleniyor durumunu göster"""
        self.lbl_status.setText("🟡 Onay bekleniyor")
        self.lbl_firm_name.setText(info.get('firm_id', '-') or '-')
        self.lbl_device_id.setText(info.get('device_id', '-') or '-')
        self.lbl_last_sync.setText("Henüz senkronize edilmedi")
        self.lbl_pending.setText("-")

        # Onay durumunu kontrol et butonu
        self.btn_sync_now.setEnabled(True)
        self.btn_sync_now.setText("🔄 Onay Durumunu Kontrol Et")
        try:
            self.btn_sync_now.clicked.disconnect()
        except:
            pass
        self.btn_sync_now.clicked.connect(self._check_approval_status)

        self.btn_leave.setEnabled(True)  # Katılım talebini iptal etmek için
        self.btn_leave.setText("🚪 Katılım Talebini İptal Et")
        self.btn_setup.setText("🔧 Büro Kurulumu")
        self.admin_group.setVisible(False)

    def _check_approval_status(self):
        """Onay durumunu kontrol et"""
        if not self.sync_manager:
            return

        self.btn_sync_now.setEnabled(False)
        self.btn_sync_now.setText("Kontrol ediliyor...")
        QApplication.processEvents()

        try:
            result = self.sync_manager.check_approval_status()

            if result.get('is_approved'):
                QMessageBox.information(
                    self, "Onaylandı",
                    "Cihazınız onaylandı! Artık senkronizasyon yapabilirsiniz."
                )
                # Butonu normal sync'e geri döndür
                try:
                    self.btn_sync_now.clicked.disconnect()
                except:
                    pass
                self.btn_sync_now.clicked.connect(self._sync_now)
            else:
                QMessageBox.information(
                    self, "Onay Bekleniyor",
                    "Cihazınız henüz onaylanmadı. Yöneticinin onaylamasını bekleyin."
                )

        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Kontrol başarısız: {str(e)}")

        finally:
            self.btn_sync_now.setEnabled(True)
            self._refresh()

    def _sync_now(self):
        """Hemen senkronize et"""
        if not self.sync_manager:
            return

        self.btn_sync_now.setEnabled(False)
        self.btn_sync_now.setText("Senkronize ediliyor...")
        QApplication.processEvents()

        try:
            result = self.sync_manager.sync_now()

            if result.success:
                QMessageBox.information(
                    self, "Senkronizasyon",
                    f"Senkronizasyon tamamlandı.\n\n"
                    f"Gönderilen: {result.pushed_count}\n"
                    f"Alınan: {result.pulled_count}\n"
                    f"Çakışma: {len(result.conflicts)}"
                )
            else:
                QMessageBox.warning(
                    self, "Senkronizasyon",
                    f"Senkronizasyon başarısız.\n\n{', '.join(result.errors)}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

        finally:
            self.btn_sync_now.setEnabled(True)
            self.btn_sync_now.setText("🔄 Şimdi Senkronize Et")
            self._refresh()

    def _view_conflicts(self):
        """Çakışmaları göster"""
        dialog = ConflictsDialog(self.sync_manager, self)
        dialog.exec()

    def _open_setup(self):
        """Kurulum wizard'ını aç"""
        try:
            from app.ui_buro_setup_wizard import BuroSetupWizard
        except ImportError:
            from ui_buro_setup_wizard import BuroSetupWizard

        wizard = BuroSetupWizard(self.sync_manager, self)
        if wizard.exec():
            self._refresh()
            QMessageBox.information(
                self, "Kurulum",
                "Büro kurulumu tamamlandı!"
            )

    def _leave_firm(self):
        """Bürodan ayrıl veya katılım talebini iptal et"""
        # Pending approval durumunu kontrol et
        is_pending = self.sync_manager and self.sync_manager.status == SyncStatus.PENDING_APPROVAL

        if is_pending:
            # Katılım talebi iptal etme
            reply = QMessageBox.question(
                self, "Katılım Talebini İptal Et",
                "Katılım talebiniz iptal edilecek.\n\n"
                "Devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            keep_data = True  # Pending durumda veri yok zaten
        else:
            # Normal bürodan ayrılma
            reply = QMessageBox.question(
                self, "Bürodan Ayrıl",
                "Bu işlem geri alınamaz!\n\n"
                "Bürodan ayrıldıktan sonra verileriniz senkronize edilmeyecek.\n"
                "Yerel verileriniz silinsin mi?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            keep_data = (reply == QMessageBox.StandardButton.No)

        try:
            if self.sync_manager:
                result = self.sync_manager.leave_firm(keep_local_data=keep_data)
                msg = "Katılım talebi iptal edildi." if is_pending else "Büro bağlantısı kaldırıldı."
                QMessageBox.information(self, "Başarılı", msg)
            else:
                QMessageBox.warning(self, "Uyarı", "SyncManager bulunamadı.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Hata", f"İşlem başarısız: {str(e)}")
        finally:
            # Her durumda refresh yap
            self._refresh()

    def _manage_devices(self):
        """Cihaz yönetimi dialog'u"""
        dialog = DeviceManagementDialog(self.sync_manager, self)
        dialog.exec()

    def _manage_users(self):
        """Kullanıcı yönetimi dialog'u"""
        QMessageBox.information(
            self, "Kullanıcı Yönetimi",
            "Bu özellik henüz tamamlanmadı."
        )

    def _generate_join_code(self):
        """Katılım kodu oluştur"""
        if not self.sync_manager or not self.sync_manager.client:
            return

        try:
            result = self.sync_manager.client.generate_join_code()
            code = result.get('code', '')
            expires = result.get('expires_at', '')

            dialog = JoinCodeDialog(code, expires, self)
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


class ConflictsDialog(QDialog):
    """Çakışmalar dialog'u"""

    def __init__(self, sync_manager: SyncManager, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager

        self.setWindowTitle("Çakışmalar")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout()

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Tarih", "Tablo", "Kayıt UUID", "Çözüm", "Detay"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        # Butonlar
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self._load_conflicts)
        buttons.addButton(btn_refresh, QDialogButtonBox.ButtonRole.ActionRole)

        layout.addWidget(buttons)

        self.setLayout(layout)
        self._load_conflicts()

    def _load_conflicts(self):
        """Çakışmaları yükle"""
        if not self.sync_manager:
            return

        try:
            conflicts = self.sync_manager.conflict_handler.get_conflicts()

            self.table.setRowCount(len(conflicts))

            for i, conflict in enumerate(conflicts):
                self.table.setItem(i, 0, QTableWidgetItem(
                    conflict.get('created_at', '-')
                ))
                self.table.setItem(i, 1, QTableWidgetItem(
                    conflict.get('table_name', '-')
                ))
                self.table.setItem(i, 2, QTableWidgetItem(
                    conflict.get('record_uuid', '-')[:8] + '...'
                ))
                self.table.setItem(i, 3, QTableWidgetItem(
                    conflict.get('resolution', '-')
                ))
                self.table.setItem(i, 4, QTableWidgetItem("Görüntüle"))

        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))


class DeviceManagementDialog(QDialog):
    """Cihaz yönetimi dialog'u"""

    def __init__(self, sync_manager: SyncManager, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager

        self.setWindowTitle("Cihaz Yönetimi")
        self.setMinimumSize(700, 400)

        layout = QVBoxLayout()

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Cihaz ID", "Cihaz Adı", "Platform", "Son Sync", "Durum", "İşlem"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        # Butonlar
        btn_layout = QHBoxLayout()

        btn_refresh = QPushButton("🔃 Yenile")
        btn_refresh.clicked.connect(self._load_devices)
        btn_layout.addWidget(btn_refresh)

        btn_layout.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._load_devices()

    def _load_devices(self):
        """Cihazları yükle"""
        if not self.sync_manager or not self.sync_manager.client:
            return

        try:
            devices = self.sync_manager.client.get_devices()

            self.table.setRowCount(len(devices))

            for i, device in enumerate(devices):
                self.table.setItem(i, 0, QTableWidgetItem(
                    device.get('device_id', '-')[:12] + '...'
                ))
                self.table.setItem(i, 1, QTableWidgetItem(
                    device.get('device_name', '-') or '-'
                ))
                device_info = device.get('device_info') or {}
                self.table.setItem(i, 2, QTableWidgetItem(
                    device_info.get('platform', '-') if isinstance(device_info, dict) else '-'
                ))
                self.table.setItem(i, 3, QTableWidgetItem(
                    device.get('last_sync_at', '-') or '-'
                ))

                # Durum
                is_approved = device.get('is_approved', False)
                is_active = device.get('is_active', True)

                if not is_active:
                    status = "❌ Deaktif"
                elif is_approved:
                    status = "✅ Onaylı"
                else:
                    status = "⏳ Onay bekliyor"

                self.table.setItem(i, 4, QTableWidgetItem(status))

                # İşlem butonu
                if not is_approved and is_active:
                    btn = QPushButton("Onayla")
                    btn.clicked.connect(
                        lambda _, d=device: self._approve_device(d['device_id'])
                    )
                    self.table.setCellWidget(i, 5, btn)
                elif is_active:
                    btn = QPushButton("Deaktif Et")
                    btn.clicked.connect(
                        lambda _, d=device: self._deactivate_device(d['device_id'])
                    )
                    self.table.setCellWidget(i, 5, btn)

        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _approve_device(self, device_id: str):
        """Cihazı onayla"""
        try:
            self.sync_manager.client.approve_device(device_id)
            QMessageBox.information(self, "Başarılı", "Cihaz onaylandı.")
            self._load_devices()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _deactivate_device(self, device_id: str):
        """Cihazı deaktif et"""
        reply = QMessageBox.question(
            self, "Cihazı Deaktif Et",
            "Bu cihaz artık senkronizasyon yapamayacak.\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.sync_manager.client.deactivate_device(device_id)
            QMessageBox.information(self, "Başarılı", "Cihaz deaktif edildi.")
            self._load_devices()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


class JoinCodeDialog(QDialog):
    """Katılım kodu gösterme dialog'u"""

    def __init__(self, code: str, expires_at: str, parent=None):
        super().__init__(parent)
        self.code = code

        self.setWindowTitle("Katılım Kodu")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Kod
        code_label = QLabel(code)
        code_label.setFont(QFont("Courier", 18, QFont.Weight.Bold))
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        code_label.setStyleSheet("""
            padding: 20px;
            background: #f0f0f0;
            border: 2px dashed #999;
            border-radius: 10px;
        """)
        layout.addWidget(code_label)

        # Geçerlilik
        expires_label = QLabel(f"Geçerlilik: {expires_at}")
        expires_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        expires_label.setStyleSheet("color: #666;")
        layout.addWidget(expires_label)

        # Kopyala butonu
        btn_copy = QPushButton("📋 Panoya Kopyala")
        btn_copy.clicked.connect(self._copy)
        layout.addWidget(btn_copy)

        # Kapat
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        self.setLayout(layout)

    def _copy(self):
        """Panoya kopyala"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code)
        QMessageBox.information(self, "Kopyalandı", "Kod panoya kopyalandı.")
