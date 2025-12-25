# -*- coding: utf-8 -*-
"""
Sync Durum Göstergesi

Status bar'da senkronizasyon durumunu gösterir.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QMenu, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor

try:
    from app.sync import SyncStatus, SyncManager
except ImportError:
    from sync import SyncStatus, SyncManager


class SyncIndicator(QWidget):
    """
    Senkronizasyon durumu göstergesi.

    Status bar'da gösterilir:
    - Durum ikonu (yeşil/sarı/kırmızı/gri)
    - Durum metni
    - Sync butonu

    Signals:
        sync_requested: Manuel sync istendiğinde
        settings_requested: Ayarlar istendiğinde
    """

    sync_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    STATUS_ICONS = {
        SyncStatus.IDLE: "🟢",
        SyncStatus.SYNCING: "🔄",
        SyncStatus.ERROR: "🔴",
        SyncStatus.OFFLINE: "⚫",
        SyncStatus.NOT_CONFIGURED: "⚪",
        SyncStatus.PENDING_APPROVAL: "🟡",
    }

    STATUS_TEXTS = {
        SyncStatus.IDLE: "Senkronize",
        SyncStatus.SYNCING: "Senkronize ediliyor...",
        SyncStatus.ERROR: "Senkronizasyon hatası",
        SyncStatus.OFFLINE: "Çevrimdışı",
        SyncStatus.NOT_CONFIGURED: "Büro bağlantısı yok",
        SyncStatus.PENDING_APPROVAL: "Onay bekleniyor",
    }

    def __init__(self, sync_manager: SyncManager = None, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager

        self._setup_ui()
        self._connect_signals()

        # Periyodik güncelleme
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._refresh_status)
        self._update_timer.start(5000)  # 5 saniyede bir

    def _setup_ui(self):
        """UI bileşenlerini oluştur"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)

        # Durum ikonu
        self.icon_label = QLabel("⚪")
        self.icon_label.setStyleSheet("font-size: 14px;")

        # Durum metni
        self.status_label = QLabel("Büro bağlantısı yok")
        self.status_label.setStyleSheet("font-size: 12px;")

        # Bekleyen değişiklik sayısı
        self.pending_label = QLabel("")
        self.pending_label.setStyleSheet("font-size: 11px; color: #888;")
        self.pending_label.setVisible(False)

        # Sync butonu
        self.sync_button = QPushButton("🔄")
        self.sync_button.setToolTip("Şimdi senkronize et")
        self.sync_button.setFixedSize(24, 24)
        self.sync_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.1);
                border-radius: 12px;
            }
        """)
        self.sync_button.setVisible(False)

        # Ayarlar butonu
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setToolTip("Büro ayarları")
        self.settings_button.setFixedSize(24, 24)
        self.settings_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.1);
                border-radius: 12px;
            }
        """)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.pending_label)
        layout.addWidget(self.sync_button)
        layout.addWidget(self.settings_button)

        self.setLayout(layout)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_signals(self):
        """Sinyalleri bağla"""
        self.sync_button.clicked.connect(self._on_sync_clicked)
        self.settings_button.clicked.connect(self.settings_requested.emit)

        if self.sync_manager:
            self.sync_manager.on_status_change = self._on_status_change

    def _on_sync_clicked(self):
        """Sync butonu tıklandığında"""
        self.sync_requested.emit()
        if self.sync_manager:
            self.sync_manager.sync_now()

    def _on_status_change(self, status: SyncStatus):
        """Durum değiştiğinde"""
        self.set_status(status)

    def set_sync_manager(self, sync_manager: SyncManager):
        """SyncManager'ı ayarla"""
        self.sync_manager = sync_manager
        sync_manager.on_status_change = self._on_status_change
        self._refresh_status()

    def set_status(self, status: SyncStatus, detail: str = None):
        """
        Durumu güncelle.

        Args:
            status: SyncStatus enum
            detail: Ek detay metni
        """
        icon = self.STATUS_ICONS.get(status, "❓")
        text = self.STATUS_TEXTS.get(status, str(status))

        self.icon_label.setText(icon)

        if detail:
            self.status_label.setText(f"{text} - {detail}")
        else:
            self.status_label.setText(text)

        # Sync butonu sadece belirli durumlarda görünür
        show_sync = status in [SyncStatus.IDLE, SyncStatus.ERROR, SyncStatus.OFFLINE]
        self.sync_button.setVisible(show_sync)

        # Syncing durumunda dönen animasyon
        if status == SyncStatus.SYNCING:
            self.sync_button.setEnabled(False)
        else:
            self.sync_button.setEnabled(True)

    def set_pending_count(self, count: int):
        """Bekleyen değişiklik sayısını göster"""
        if count > 0:
            self.pending_label.setText(f"({count} bekliyor)")
            self.pending_label.setVisible(True)
        else:
            self.pending_label.setVisible(False)

    def set_last_sync(self, timestamp: str):
        """Son sync zamanını tooltip olarak göster"""
        self.setToolTip(f"Son senkronizasyon: {timestamp}")

    def _refresh_status(self):
        """Durumu yenile"""
        if not self.sync_manager:
            return

        status_info = self.sync_manager.get_status_info()
        status = SyncStatus(status_info.get('status', 'not_configured'))

        self.set_status(status)
        self.set_pending_count(status_info.get('pending_push', 0))

        if status_info.get('last_sync_at'):
            self.set_last_sync(status_info['last_sync_at'])

    def _on_force_sync_clicked(self):
        """Zorla senkronize et butonu tıklandığında"""
        if self.sync_manager:
            self.set_status(SyncStatus.SYNCING, "Tüm veriler senkronize ediliyor...")
            result = self.sync_manager.force_sync_all()
            if result.get('success'):
                seeded = result.get('seeded', 0)
                received = result.get('received', 0)
                sent = result.get('sent', 0)
                detail = f"{seeded} eklendi, {received} alındı, {sent} gönderildi"
                self.set_status(SyncStatus.IDLE, detail)
            else:
                errors = result.get('errors', ['Bilinmeyen hata'])
                self.set_status(SyncStatus.ERROR, errors[0] if errors else None)

    def _show_context_menu(self, pos):
        """Context menu göster"""
        menu = QMenu(self)

        # Şimdi senkronize et
        sync_action = menu.addAction("🔄 Şimdi Senkronize Et")
        sync_action.triggered.connect(self._on_sync_clicked)

        # Tüm verileri senkronize et
        force_sync_action = menu.addAction("📤 Tüm Verileri Senkronize Et")
        force_sync_action.triggered.connect(self._on_force_sync_clicked)
        force_sync_action.setToolTip("Mevcut tüm verileri sunucuya gönderir")

        menu.addSeparator()

        # Büro ayarları
        settings_action = menu.addAction("⚙️ Büro Ayarları")
        settings_action.triggered.connect(self.settings_requested.emit)

        # Durum bilgisi
        if self.sync_manager:
            menu.addSeparator()
            info = self.sync_manager.get_status_info()

            info_action = menu.addAction(f"📊 Durum: {info.get('status', '?')}")
            info_action.setEnabled(False)

            if info.get('last_sync_at'):
                time_action = menu.addAction(f"🕐 Son: {info['last_sync_at']}")
                time_action.setEnabled(False)

        menu.exec(self.mapToGlobal(pos))


class SyncStatusWidget(QWidget):
    """
    Daha detaylı sync durumu widget'ı.

    Dialog veya panel içinde kullanılabilir.
    """

    def __init__(self, sync_manager: SyncManager = None, parent=None):
        super().__init__(parent)
        self.sync_manager = sync_manager
        self._setup_ui()

    def _setup_ui(self):
        """UI oluştur"""
        from PyQt6.QtWidgets import QVBoxLayout, QFormLayout, QGroupBox

        layout = QVBoxLayout()

        # Bağlantı durumu
        status_group = QGroupBox("Bağlantı Durumu")
        status_layout = QFormLayout()

        self.lbl_status = QLabel("-")
        self.lbl_server = QLabel("-")
        self.lbl_firm_id = QLabel("-")
        self.lbl_device_id = QLabel("-")
        self.lbl_last_sync = QLabel("-")
        self.lbl_pending = QLabel("-")

        status_layout.addRow("Durum:", self.lbl_status)
        status_layout.addRow("Sunucu:", self.lbl_server)
        status_layout.addRow("Büro ID:", self.lbl_firm_id)
        status_layout.addRow("Cihaz ID:", self.lbl_device_id)
        status_layout.addRow("Son Sync:", self.lbl_last_sync)
        status_layout.addRow("Bekleyen:", self.lbl_pending)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Butonlar
        from PyQt6.QtWidgets import QHBoxLayout

        btn_layout = QHBoxLayout()

        self.btn_sync = QPushButton("🔄 Şimdi Senkronize Et")
        self.btn_sync.clicked.connect(self._on_sync)

        self.btn_force_sync = QPushButton("📤 Tüm Verileri Senkronize Et")
        self.btn_force_sync.clicked.connect(self._on_force_sync)
        self.btn_force_sync.setToolTip("Mevcut tüm verileri sunucuya gönderir")

        self.btn_refresh = QPushButton("🔃 Yenile")
        self.btn_refresh.clicked.connect(self.refresh)

        btn_layout.addWidget(self.btn_sync)
        btn_layout.addWidget(self.btn_force_sync)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

        self.setLayout(layout)

    def set_sync_manager(self, sync_manager: SyncManager):
        """SyncManager'ı ayarla"""
        self.sync_manager = sync_manager
        self.refresh()

    def refresh(self):
        """Bilgileri yenile"""
        if not self.sync_manager:
            return

        info = self.sync_manager.get_status_info()

        status = info.get('status', 'not_configured')
        status_text = SyncIndicator.STATUS_TEXTS.get(
            SyncStatus(status), status
        )

        self.lbl_status.setText(f"{SyncIndicator.STATUS_ICONS.get(SyncStatus(status), '?')} {status_text}")
        self.lbl_server.setText(info.get('server_url', '-') or '-')
        self.lbl_firm_id.setText(info.get('firm_id', '-') or '-')
        self.lbl_device_id.setText(info.get('device_id', '-') or '-')
        self.lbl_last_sync.setText(info.get('last_sync_at', '-') or '-')
        self.lbl_pending.setText(str(info.get('pending_push', 0)))

    def _on_sync(self):
        """Sync butonu"""
        if self.sync_manager:
            self.btn_sync.setEnabled(False)
            self.btn_sync.setText("Senkronize ediliyor...")

            result = self.sync_manager.sync_now()

            self.btn_sync.setEnabled(True)
            self.btn_sync.setText("🔄 Şimdi Senkronize Et")
            self.refresh()

    def _on_force_sync(self):
        """Zorla senkronize et butonu"""
        if self.sync_manager:
            self.btn_force_sync.setEnabled(False)
            self.btn_force_sync.setText("Tüm veriler senkronize ediliyor...")

            result = self.sync_manager.force_sync_all()

            self.btn_force_sync.setEnabled(True)
            self.btn_force_sync.setText("📤 Tüm Verileri Senkronize Et")

            if result.get('success'):
                seeded = result.get('seeded', 0)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Senkronizasyon Tamamlandı",
                    f"Tüm veriler senkronize edildi.\n\n"
                    f"Eklenen kayıt: {seeded}\n"
                    f"Alınan: {result.get('received', 0)}\n"
                    f"Gönderilen: {result.get('sent', 0)}"
                )
            else:
                from PyQt6.QtWidgets import QMessageBox
                errors = result.get('errors', ['Bilinmeyen hata'])
                QMessageBox.warning(
                    self,
                    "Senkronizasyon Hatası",
                    f"Senkronizasyon sırasında hata oluştu:\n\n{errors[0]}"
                )

            self.refresh()
