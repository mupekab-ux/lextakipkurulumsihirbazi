# -*- coding: utf-8 -*-
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Any, Dict
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QByteArray
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QTabWidget,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QFrame,
    QComboBox,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
)
from PyQt6.QtGui import QColor
try:  # pragma: no cover - runtime import guard
    from app.db import (
        DB_PATH,
        initialize_database,
        list_backups,
        create_backup,
        restore_backup,
        cleanup_old_backups,
        get_backup_dir,
        check_disk_space,
        validate_backup_file,
        get_backup_info,
        get_database_size,
        safe_delete_file,
        MINIMUM_BACKUP_COUNT,
    )
except ModuleNotFoundError:  # pragma: no cover
    from db import (
        DB_PATH,
        initialize_database,
        list_backups,
        create_backup,
        restore_backup,
        cleanup_old_backups,
        get_backup_dir,
        check_disk_space,
        validate_backup_file,
        get_backup_info,
        get_database_size,
        safe_delete_file,
        MINIMUM_BACKUP_COUNT,
    )

try:  # pragma: no cover - runtime import guard
    from app.models import (
        backup_database,
        get_statuses,
        add_status,
        update_status,
        delete_status,
        log_action,
        get_users,
        add_user as db_add_user,
        update_user as db_update_user,
        delete_user as db_delete_user,
        get_all_permissions,
        set_permissions_for_role,
        validate_database_file,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        backup_database,
        get_statuses,
        add_status,
        update_status,
        delete_status,
        log_action,
        get_users,
        add_user as db_add_user,
        update_user as db_update_user,
        delete_user as db_delete_user,
        get_all_permissions,
        set_permissions_for_role,
        validate_database_file,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import (
        apply_theme,
        is_valid_hex,
        normalize_hex,
        load_theme_from_settings_and_apply,
        save_theme_to_settings,
        USER_ROLE_CHOICES,
        USER_ROLE_LABELS,
        THEME_DEFAULT,
        THEME_DARK,
        THEME_BLUE,
        THEME_PASTEL,
        THEME_DARK_GREY,
        THEME_DARK_BLUE,
    )
except ModuleNotFoundError:  # pragma: no cover
    from utils import (
        apply_theme,
        is_valid_hex,
        normalize_hex,
        load_theme_from_settings_and_apply,
        save_theme_to_settings,
        USER_ROLE_CHOICES,
        USER_ROLE_LABELS,
        THEME_DEFAULT,
        THEME_DARK,
        THEME_BLUE,
        THEME_PASTEL,
        THEME_DARK_GREY,
        THEME_DARK_BLUE,
    )

try:  # pragma: no cover - runtime import guard
    from app.ui_activation_dialog import LicenseInfoDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_activation_dialog import LicenseInfoDialog

try:  # pragma: no cover - runtime import guard
    from app.ui_transfer_dialog import TransferDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_transfer_dialog import TransferDialog


PERMISSION_FIELDS: list[tuple[str, str]] = [
    ("view_all_cases", "Tüm dosyaları görebilir mi?"),
    ("manage_users", "Kullanıcı yönetebilir mi?"),
    ("can_view_finance", "Finans/Masraflar sekmesini görebilsin"),
    ("can_hard_delete", "Kalıcı silme (hard delete) yetkisi"),
    ("can_manage_backups", "Yedekleme yönetimi yetkisi"),
]

ADMIN_LOCKED_PERMISSIONS = {"can_hard_delete"}

# Durum kategorileri için Türkçe isimler ve açıklamalar
STATUS_CATEGORY_LABELS = {
    "SARI": ("Bizde", "Yapılacak işler - Top bizde"),
    "TURUNCU": ("Mahkemede", "Bekleyen işler - Mahkeme/kurum tarafında"),
    "GARIP_TURUNCU": ("Karşı Tarafta", "Cevap bekleniyor - Karşı taraf/üçüncü kişi"),
    "KIRMIZI": ("Kapandı", "Dosya kapandı - Arşiv"),
}

# Owner değerinden kategori adına dönüşüm
def get_category_display_name(owner: str) -> str:
    """Owner değerinden görünen kategori adını döndürür."""
    if owner in STATUS_CATEGORY_LABELS:
        return STATUS_CATEGORY_LABELS[owner][0]
    return owner or "Bilinmiyor"


class ColorEditor(QWidget):
    """Önceden tanımlı renklerden seçim yapılabilen düzenleyici."""

    colorChanged = pyqtSignal(str)

    ALLOWED_COLORS = [
        ("Sarı", "FFD700"),
        ("Turuncu", "FF8C00"),
        ("Bakır", "CD853F"),
        ("Kırmızı", "FF0000"),
    ]
    ALLOWED_HEXES = [code for _, code in ALLOWED_COLORS]

    def __init__(self, color: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        self.combo.setEditable(False)
        # Mouse wheel ile yanlışlıkla değiştirilmesini engelle
        self.combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.combo.wheelEvent = lambda e: e.ignore()
        for label, hex_code in self.ALLOWED_COLORS:
            self.combo.addItem(f"{label} (#{hex_code})", hex_code)

        self.preview = QFrame()
        self.preview.setFixedSize(20, 20)
        self.preview.setFrameShape(QFrame.Shape.Box)

        layout.addWidget(self.combo)
        layout.addWidget(self.preview)

        self.combo.currentIndexChanged.connect(self._on_index_changed)

        self.set_color(color or self.ALLOWED_HEXES[0])

    def get_hex(self) -> str:
        value = self.combo.currentData()
        return (value or self.ALLOWED_HEXES[0]).upper()

    def set_color(self, color: str) -> None:
        normalized = normalize_hex(color)
        try:
            index = self.ALLOWED_HEXES.index(normalized) if normalized else 0
        except ValueError:
            index = 0
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._update_preview()

    def _on_index_changed(self, index: int) -> None:  # noqa: ARG002 - sinyal imzası
        self._update_preview()
        self.colorChanged.emit(self.get_hex())

    def _update_preview(self) -> None:
        hex_code = self.get_hex()
        self.preview.setStyleSheet(f"background-color: #{hex_code};")


class UserEditorDialog(QDialog):
    """Kullanıcı ekleme/düzenleme diyalogu."""

    def __init__(self, parent=None, user: Dict[str, Any] | None = None):
        super().__init__(parent)
        self.setWindowTitle("TakibiEsasi - Kullanıcı")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.role = QComboBox()
        for value, label in USER_ROLE_CHOICES:
            self.role.addItem(label, value)
        self.active = QCheckBox("Aktif")
        if user:
            self.username.setText(user.get("username", ""))
            role_value = user.get("role", "avukat")
            index = self.role.findData(role_value)
            if index >= 0:
                self.role.setCurrentIndex(index)
            self.active.setChecked(bool(user.get("active", True)))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Kullanıcı Adı", self.username)
        form.addRow("Şifre", self.password)
        form.addRow("Rol", self.role)
        form.addRow(self.active)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("İptal")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def get_values(self) -> Dict[str, Any]:
        return {
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "role": self.role.currentData() or "avukat",
            "active": self.active.isChecked(),
        }

class SettingsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        main_window=None,
        user_id=None,
        is_admin: bool = False,
        can_edit_statuses: bool = True,
        show_status_tab: bool = True,
        can_manage_users: bool = False,
        can_manage_backups: bool = False,
    ):
        super().__init__(parent)
        self.main_window = main_window if main_window is not None else parent
        self.user_id = user_id
        self.is_admin = is_admin
        self.can_edit_statuses = can_edit_statuses
        self.show_status_tab = show_status_tab
        self.can_manage_users = can_manage_users
        self.can_manage_backups = can_manage_backups
        self.settings = QSettings("TakibiEsasi", "TakibiEsasiApp")
        self.setWindowTitle("TakibiEsasi - Ayarlar")
        self.tabs = QTabWidget()
        self.status_table: QTableWidget | None = None
        self.status_add_btn: QPushButton | None = None
        self.status_del_btn: QPushButton | None = None
        self.status_search_edit: QLineEdit | None = None
        self.status_count_label: QLabel | None = None
        self.status_tab_index: int | None = None
        self.status_original_ids: set[int] = set()
        self.user_table: QTableWidget | None = None
        self.user_add_btn: QPushButton | None = None
        self.user_edit_btn: QPushButton | None = None
        self.user_del_btn: QPushButton | None = None
        self.permission_checks: dict[str, dict[str, QCheckBox]] = {}
        self.permission_tab_index: int | None = None

        # Genel ayarlar sekmesi
        general_tab = QWidget()
        g_layout = QVBoxLayout()

        theme_row = QHBoxLayout()
        theme_label = QLabel("Tema")
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("comboTheme")
        for option in (
            THEME_DEFAULT,
            THEME_DARK,
            THEME_BLUE,
            THEME_PASTEL,
            THEME_DARK_GREY,
            THEME_DARK_BLUE,
        ):
            self.theme_combo.addItem(option, option)
        theme_row.addWidget(theme_label)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        g_layout.addLayout(theme_row)

        theme_info_label = QLabel(
            "Uygulama temasını seçin (yeniden başlatma gerekebilir)."
        )
        theme_info_label.setWordWrap(True)
        g_layout.addWidget(theme_info_label)

        # Lisans bilgileri grubu
        license_group = QGroupBox("Lisans Bilgileri")
        license_layout = QHBoxLayout(license_group)
        self.license_info_btn = QPushButton("Lisans Bilgilerini Görüntüle")
        self.license_info_btn.clicked.connect(self._show_license_info)
        license_layout.addWidget(self.license_info_btn)
        license_layout.addStretch()
        g_layout.addWidget(license_group)

        g_layout.addStretch()
        general_tab.setLayout(g_layout)
        self.tabs.addTab(general_tab, "Genel")

        # Yedekleme sekmesi
        backup_tab = QWidget()
        b_layout = QVBoxLayout()

        # Durum bilgisi
        self.backup_status_label = QLabel()
        self.backup_status_label.setStyleSheet(
            "padding: 8px; background-color: #f0f0f0; border-radius: 4px;"
        )
        b_layout.addWidget(self.backup_status_label)

        # Yedekleme Ayarları Grubu
        backup_settings_group = QGroupBox("Otomatik Yedekleme Ayarları")
        backup_form = QFormLayout(backup_settings_group)

        self.auto_backup_check = QCheckBox("Uygulama açılışında otomatik yedekle")
        backup_settings = QSettings("MyCompany", "TakibiEsasi")
        self.auto_backup_check.setChecked(
            backup_settings.value("backup/auto_backup", True, type=bool)
        )
        backup_form.addRow(self.auto_backup_check)

        self.backup_keep_spin = QSpinBox()
        self.backup_keep_spin.setRange(1, 100)
        self.backup_keep_spin.setValue(
            backup_settings.value("backup/keep_count", 10, type=int)
        )
        self.backup_keep_spin.setSuffix(" adet")
        backup_form.addRow("Maksimum yedek sayısı:", self.backup_keep_spin)

        backup_dir_layout = QHBoxLayout()
        self.backup_dir_label = QLabel(get_backup_dir())
        self.backup_dir_label.setStyleSheet("color: #666; font-size: 11px;")
        backup_dir_layout.addWidget(QLabel("Yedek konumu:"))
        backup_dir_layout.addWidget(self.backup_dir_label)
        backup_dir_layout.addStretch()
        backup_form.addRow(backup_dir_layout)

        b_layout.addWidget(backup_settings_group)

        # Manuel Yedekleme Butonları
        backup_action_group = QGroupBox("Yedekleme İşlemleri")
        backup_action_layout = QVBoxLayout(backup_action_group)

        backup_btn_row = QHBoxLayout()
        self.backup_btn = QPushButton("Şimdi Yedekle")
        self.backup_btn.setToolTip("Veritabanının yedeğini al")
        self.backup_btn.setMinimumWidth(120)
        backup_btn_row.addWidget(self.backup_btn)

        self.backup_custom_btn = QPushButton("Farklı Konuma Yedekle...")
        self.backup_custom_btn.setMinimumWidth(150)
        backup_btn_row.addWidget(self.backup_custom_btn)

        self.backup_verify_btn = QPushButton("Yedekleri Doğrula")
        self.backup_verify_btn.setToolTip("Tüm yedek dosyalarının bütünlüğünü kontrol et")
        self.backup_verify_btn.setMinimumWidth(120)
        backup_btn_row.addWidget(self.backup_verify_btn)

        backup_btn_row.addStretch()
        backup_action_layout.addLayout(backup_btn_row)

        b_layout.addWidget(backup_action_group)

        # Yedek Listesi
        backup_list_group = QGroupBox("Mevcut Yedekler")
        backup_list_layout = QVBoxLayout(backup_list_group)

        self.backup_table = QTableWidget(0, 4)
        self.backup_table.setHorizontalHeaderLabels(["Tarih", "Boyut", "Dosya Sayısı", "Dosya"])
        self.backup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.backup_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.backup_table.horizontalHeader().setStretchLastSection(True)
        self.backup_table.setColumnWidth(0, 130)
        self.backup_table.setColumnWidth(1, 80)
        self.backup_table.setColumnWidth(2, 80)
        backup_list_layout.addWidget(self.backup_table)

        backup_list_btn_layout = QHBoxLayout()
        self.backup_restore_btn = QPushButton("Seçili Yedeği Geri Yükle")
        self.backup_restore_btn.setToolTip("Seçili yedeği geri yükle (önce güvenlik kontrolü yapılır)")
        self.backup_delete_btn = QPushButton("Seçili Yedeği Sil")
        self.backup_refresh_btn = QPushButton("Listeyi Yenile")
        backup_list_btn_layout.addWidget(self.backup_restore_btn)
        backup_list_btn_layout.addWidget(self.backup_delete_btn)
        backup_list_btn_layout.addWidget(self.backup_refresh_btn)
        backup_list_btn_layout.addStretch()
        backup_list_layout.addLayout(backup_list_btn_layout)

        b_layout.addWidget(backup_list_group)

        # Veri İşlemleri Grubu
        data_ops_group = QGroupBox("Veri İşlemleri")
        data_ops_layout = QVBoxLayout(data_ops_group)

        self.export_btn = QPushButton("Dışa Aktar")
        self.export_btn.setToolTip("Verileri dışa aktarın")
        data_ops_layout.addWidget(self.export_btn)

        self.load_db_btn = QPushButton("Harici Veritabanı Yükle...")
        self.load_db_btn.setToolTip("Harici bir veritabanı dosyasını (.db) yükleyebilirsiniz")
        data_ops_layout.addWidget(self.load_db_btn)

        load_info_label = QLabel(
            "Harici bir veritabanı dosyasını yüklerseniz mevcut verilerinizin "
            "üzerine yazılır. Önce yedek almanız önerilir."
        )
        load_info_label.setWordWrap(True)
        load_info_label.setStyleSheet("color: #888; font-size: 11px;")
        data_ops_layout.addWidget(load_info_label)

        b_layout.addWidget(data_ops_group)

        # Bilgisayar Transferi Grubu
        transfer_group = QGroupBox("Bilgisayar Transferi")
        transfer_layout = QVBoxLayout(transfer_group)

        self.transfer_btn = QPushButton("Bilgisayar Transferi...")
        self.transfer_btn.setToolTip(
            "Verilerinizi başka bir bilgisayara taşımak için dışa/içe aktarın"
        )
        self.transfer_btn.clicked.connect(self._show_transfer_dialog)
        transfer_layout.addWidget(self.transfer_btn)

        transfer_info_label = QLabel(
            "Yeni bir bilgisayara geçerken tüm verilerinizi (davalar, ayarlar, "
            "lisans) tek bir dosya ile taşıyabilirsiniz."
        )
        transfer_info_label.setWordWrap(True)
        transfer_info_label.setStyleSheet("color: #888; font-size: 11px;")
        transfer_layout.addWidget(transfer_info_label)

        b_layout.addWidget(transfer_group)
        b_layout.addStretch()

        backup_tab.setLayout(b_layout)
        self.tabs.addTab(backup_tab, "Veri Yönetimi")

        # Veri yönetimi yetki kontrolü
        if not self.can_manage_backups:
            self.backup_btn.setEnabled(False)
            self.backup_btn.setToolTip("Bu işlem için yetkiniz yok")
            self.backup_custom_btn.setEnabled(False)
            self.backup_custom_btn.setToolTip("Bu işlem için yetkiniz yok")
            self.backup_restore_btn.setEnabled(False)
            self.backup_restore_btn.setToolTip("Bu işlem için yetkiniz yok")
            self.backup_delete_btn.setEnabled(False)
            self.backup_delete_btn.setToolTip("Bu işlem için yetkiniz yok")
            self.export_btn.setEnabled(False)
            self.export_btn.setToolTip("Bu işlem için yetkiniz yok")
            self.load_db_btn.setEnabled(False)
            self.load_db_btn.setToolTip("Bu işlem için yetkiniz yok")

        # Durum yönetimi sekmesi
        if self.show_status_tab:
            status_tab = QWidget()
            s_layout = QVBoxLayout()

            # Açıklama etiketi
            info_label = QLabel(
                "🟡 Bizde (Sarı)  |  🟠 Mahkemede (Turuncu)  |  "
                "🟤 Karşı Tarafta (Bakır)  |  🔴 Kapandı (Kırmızı)"
            )
            info_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
            s_layout.addWidget(info_label)

            # Arama kutusu
            search_layout = QHBoxLayout()
            search_label = QLabel("Ara:")
            self.status_search_edit = QLineEdit()
            self.status_search_edit.setPlaceholderText("Durum adı ara...")
            self.status_search_edit.setClearButtonEnabled(True)
            self.status_search_edit.textChanged.connect(self._filter_status_table)
            search_layout.addWidget(search_label)
            search_layout.addWidget(self.status_search_edit)
            s_layout.addLayout(search_layout)

            # Tablo
            self.status_table = QTableWidget(0, 3)
            self.status_table.setHorizontalHeaderLabels(["Durum Adı", "Renk", "Kategori"])
            self.status_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.status_table.setAlternatingRowColors(True)
            self.status_table.setSortingEnabled(True)

            # Kolon genişlikleri
            header = self.status_table.horizontalHeader()
            header.setSectionResizeMode(0, header.ResizeMode.Stretch)  # Durum Adı - esnek
            header.setSectionResizeMode(1, header.ResizeMode.Fixed)    # Renk - sabit
            header.setSectionResizeMode(2, header.ResizeMode.Fixed)    # Kategori - sabit
            self.status_table.setColumnWidth(1, 180)
            self.status_table.setColumnWidth(2, 120)

            s_layout.addWidget(self.status_table)

            s_btn_layout = QHBoxLayout()
            self.status_add_btn = QPushButton("➕ Yeni Durum Ekle")
            self.status_del_btn = QPushButton("🗑️ Seçili Durumu Sil")
            s_btn_layout.addWidget(self.status_add_btn)
            s_btn_layout.addWidget(self.status_del_btn)
            s_btn_layout.addStretch()

            # Durum sayısı etiketi
            self.status_count_label = QLabel("0 durum")
            self.status_count_label.setStyleSheet("color: #888;")
            s_btn_layout.addWidget(self.status_count_label)

            s_layout.addLayout(s_btn_layout)
            status_tab.setLayout(s_layout)
            self.status_tab_index = self.tabs.addTab(status_tab, "Durumları Yönet")

        # Kullanıcı yönetimi sekmesi
        if self.can_manage_users:
            user_tab = QWidget()
            u_layout = QVBoxLayout()
            self.user_table = QTableWidget(0, 4)
            self.user_table.setHorizontalHeaderLabels(["ID", "Kullanıcı Adı", "Rol", "Aktif"])
            self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.user_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            u_layout.addWidget(self.user_table)

            u_btn_layout = QHBoxLayout()
            self.user_add_btn = QPushButton("Ekle")
            self.user_edit_btn = QPushButton("Düzenle")
            self.user_del_btn = QPushButton("Sil")
            u_btn_layout.addWidget(self.user_add_btn)
            u_btn_layout.addWidget(self.user_edit_btn)
            u_btn_layout.addWidget(self.user_del_btn)
            u_btn_layout.addStretch()
            u_layout.addLayout(u_btn_layout)
            user_tab.setLayout(u_layout)
            self.tabs.addTab(user_tab, "Kullanıcı Yönetimi")

        # Yetki yönetimi sekmesi (yalnızca admin)
        if self.is_admin:
            perm_tab = QWidget()
            p_layout = QVBoxLayout()
            for role_value, role_label in USER_ROLE_CHOICES:
                group = QGroupBox(role_label)
                group_layout = QVBoxLayout()
                role_checks: dict[str, QCheckBox] = {}
                for action, label in PERMISSION_FIELDS:
                    checkbox = QCheckBox(label)
                    # Kurucu Avukat (admin) rolü için tüm yetkiler kilitli
                    if role_value == "admin":
                        checkbox.setChecked(True)
                        checkbox.setEnabled(False)
                        checkbox.setToolTip(
                            "Kurucu Avukat için tüm yetkiler her zaman aktiftir."
                        )
                    group_layout.addWidget(checkbox)
                    role_checks[action] = checkbox
                group_layout.addStretch()
                group.setLayout(group_layout)
                p_layout.addWidget(group)
                self.permission_checks[role_value] = role_checks
            p_layout.addStretch()
            perm_tab.setLayout(p_layout)
            self.permission_tab_index = self.tabs.addTab(perm_tab, "Yetki Yönetimi")

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("İptal")
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)
        self.backup_btn.clicked.connect(self.backup_now)
        self.backup_custom_btn.clicked.connect(self.backup_custom)
        self.backup_restore_btn.clicked.connect(self.restore_selected_backup)
        self.backup_delete_btn.clicked.connect(self.delete_selected_backup)
        self.backup_refresh_btn.clicked.connect(self.load_backup_list)
        self.backup_verify_btn.clicked.connect(self.verify_all_backups)
        self.export_btn.clicked.connect(self.open_export_dialog)
        self.load_db_btn.clicked.connect(self.load_database)
        if self.status_add_btn is not None:
            self.status_add_btn.clicked.connect(self.add_status_row)
        if self.status_del_btn is not None:
            self.status_del_btn.clicked.connect(self.remove_status_row)

        self._init_theme_selection()
        self._update_backup_status()
        self.load_backup_list()

        if self.can_manage_users and self.user_add_btn is not None:
            self.user_add_btn.clicked.connect(self.add_user_dialog)
        if self.can_manage_users and self.user_edit_btn is not None:
            self.user_edit_btn.clicked.connect(self.edit_user_dialog)
        if self.can_manage_users and self.user_del_btn is not None:
            self.user_del_btn.clicked.connect(self.delete_user_dialog)

        if self.status_table is not None and not self.can_edit_statuses:
            self.status_add_btn.setEnabled(False)
            self.status_del_btn.setEnabled(False)
            self.status_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        if self.status_table is not None:
            self.load_statuses()
        if self.can_manage_users:
            self.load_users()
        if self.is_admin and self.permission_checks:
            self.load_permissions()

        self._restore_geometry()

    def _init_theme_selection(self) -> None:
        saved_theme = load_theme_from_settings_and_apply()
        if not hasattr(self, "theme_combo"):
            return
        self.theme_combo.blockSignals(True)
        index = self.theme_combo.findData(saved_theme)
        if index < 0:
            index = self.theme_combo.findData(THEME_DEFAULT)
        if index < 0:
            index = 0
        self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

    def on_theme_changed(self, index: int) -> None:  # noqa: ARG002 - sinyal imzası
        if not hasattr(self, "theme_combo"):
            return
        theme = self.theme_combo.currentData() or self.theme_combo.currentText()
        save_theme_to_settings(theme)
        apply_theme(theme)
        refresh = getattr(self.main_window, "refresh_finance_colors", None)
        if callable(refresh):
            refresh()

    def save(self) -> None:
        # Yedekleme ayarlarını kaydet
        backup_settings = QSettings("MyCompany", "TakibiEsasi")
        backup_settings.setValue("backup/auto_backup", self.auto_backup_check.isChecked())
        backup_settings.setValue("backup/keep_count", self.backup_keep_spin.value())

        if self.status_table is not None and self.can_edit_statuses:
            seen_ids: set[int] = set()
            names: set[str] = set()
            for row in range(self.status_table.rowCount()):
                ad_item = self.status_table.item(row, 0)
                owner_item = self.status_table.item(row, 2)
                ad = ad_item.text().strip() if ad_item else ""
                if self.can_edit_statuses:
                    color_widget: ColorEditor | None = self.status_table.cellWidget(row, 1)
                    color_hex = (
                        color_widget.get_hex()
                        if color_widget
                        else ""
                    )
                else:
                    color_hex = self.status_table.item(row, 1).text().strip().lstrip("#")
                # Owner değerini UserRole'dan al (görünen isim değil, orijinal değer)
                owner = ""
                if owner_item:
                    owner = owner_item.data(Qt.ItemDataRole.UserRole) or owner_item.text().strip()
                if not ad:
                    QMessageBox.warning(self, "Hata", "Ad boş olamaz.")
                    return
                if ad in names:
                    QMessageBox.warning(self, "Hata", f"{ad} zaten listede mevcut.")
                    return
                names.add(ad)
                if not is_valid_hex(color_hex):
                    QMessageBox.warning(
                        self, "Hata", "Renk kodu RRGGBB formatında olmalıdır."
                    )
                    return
                if (
                    self.can_edit_statuses
                    and color_hex.upper() not in ColorEditor.ALLOWED_HEXES
                ):
                    QMessageBox.warning(
                        self,
                        "Hata",
                        "Renk seçenekleri yalnızca Sarı, Turuncu, Bakır veya Kırmızı olabilir.",
                    )
                    return
                status_id = ad_item.data(Qt.ItemDataRole.UserRole) if ad_item else None
                try:
                    if status_id:
                        update_status(status_id, ad, color_hex, owner)
                        seen_ids.add(status_id)
                        if self.user_id is not None:
                            log_action(self.user_id, "update_status", status_id)
                    else:
                        new_id = add_status(ad, color_hex, owner)
                        seen_ids.add(new_id)
                        if self.user_id is not None:
                            log_action(self.user_id, "add_status", new_id)
                except sqlite3.IntegrityError:
                    QMessageBox.critical(self, "Hata", "Aynı isimde statü mevcut.")
                    return
                except Exception as exc:  # pragma: no cover - genel hata
                    QMessageBox.critical(self, "Hata", str(exc))
                    return
            for status_id in self.status_original_ids - seen_ids:
                delete_status(status_id)
                if self.user_id is not None:
                    log_action(self.user_id, "delete_status", status_id)

        if self.is_admin and self.permission_checks:
            try:
                self.save_permissions()
            except Exception as exc:  # pragma: no cover - GUI safety
                QMessageBox.critical(self, "Hata", str(exc))
                return

        self.accept()

    # --- Yedekleme yardımcıları ---

    def _update_backup_status(self) -> None:
        """Yedekleme durum bilgisini günceller."""
        db_size = get_database_size()
        db_size_mb = db_size / (1024 * 1024)
        backups = list_backups()
        backup_count = len(backups)

        # Disk alanı kontrolü
        space_ok, space_msg = check_disk_space(get_backup_dir())
        space_status = "✓ Disk alanı yeterli" if space_ok else f"⚠ {space_msg}"

        status_text = (
            f"Veritabanı boyutu: {db_size_mb:.2f} MB | "
            f"Yedek sayısı: {backup_count} | "
            f"{space_status}"
        )
        self.backup_status_label.setText(status_text)

        # Duruma göre arka plan rengini ayarla
        if space_ok:
            self.backup_status_label.setStyleSheet(
                "padding: 8px; background-color: #e8f5e9; border-radius: 4px; color: #2e7d32;"
            )
        else:
            self.backup_status_label.setStyleSheet(
                "padding: 8px; background-color: #fff3e0; border-radius: 4px; color: #e65100;"
            )

    def load_backup_list(self) -> None:
        """Yedek listesini tabloya yükle."""
        self.backup_table.setRowCount(0)
        for backup in list_backups():
            row = self.backup_table.rowCount()
            self.backup_table.insertRow(row)

            date_item = QTableWidgetItem(backup["created_display"])
            date_item.setData(Qt.ItemDataRole.UserRole, backup["filepath"])
            self.backup_table.setItem(row, 0, date_item)

            size_item = QTableWidgetItem(backup["size_display"])
            self.backup_table.setItem(row, 1, size_item)

            # Dosya sayısı bilgisini al
            info = get_backup_info(backup["filepath"])
            if info:
                count_text = f"{info.get('dava_count', '?')} dosya"
            else:
                count_text = "?"
            count_item = QTableWidgetItem(count_text)
            self.backup_table.setItem(row, 2, count_item)

            file_item = QTableWidgetItem(backup["filename"])
            self.backup_table.setItem(row, 3, file_item)

        self._update_backup_status()

    def _set_backup_buttons_enabled(self, enabled: bool) -> None:
        """Yedekleme butonlarını aktif/pasif yapar."""
        self.backup_btn.setEnabled(enabled)
        self.backup_custom_btn.setEnabled(enabled)
        self.backup_restore_btn.setEnabled(enabled)
        self.backup_delete_btn.setEnabled(enabled)
        self.backup_verify_btn.setEnabled(enabled)

    def backup_now(self) -> None:
        """Şimdi yedekle butonuna tıklandığında."""
        # Disk alanı kontrolü
        space_ok, space_msg = check_disk_space(get_backup_dir())
        if not space_ok:
            QMessageBox.warning(
                self,
                "Yetersiz Alan",
                f"Yedekleme yapılamıyor:\n{space_msg}"
            )
            return

        self._set_backup_buttons_enabled(False)
        try:
            backup_path = create_backup()
            if backup_path:
                # Oluşturulan yedeği doğrula
                is_valid, validation_msg = validate_backup_file(backup_path)
                if not is_valid:
                    os.remove(backup_path)
                    QMessageBox.critical(
                        self,
                        "Hata",
                        f"Yedekleme oluşturuldu ancak doğrulama başarısız:\n{validation_msg}\n\n"
                        "Yedek dosyası silindi."
                    )
                    return

                # Eski yedekleri temizle
                keep_count = self.backup_keep_spin.value()
                cleanup_old_backups(keep_count)
                self.load_backup_list()
                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"Yedekleme oluşturuldu ve doğrulandı:\n{os.path.basename(backup_path)}",
                )
            else:
                QMessageBox.warning(self, "Uyarı", "Yedekleme oluşturulamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yedekleme hatası:\n{e}")
        finally:
            self._set_backup_buttons_enabled(True)

    def backup_custom(self) -> None:
        """Farklı konuma yedekle."""
        folder = QFileDialog.getExistingDirectory(self, "Yedekleme Klasörü Seç")
        if not folder:
            return

        # Disk alanı kontrolü
        space_ok, space_msg = check_disk_space(folder)
        if not space_ok:
            QMessageBox.warning(
                self,
                "Yetersiz Alan",
                f"Bu konuma yedekleme yapılamıyor:\n{space_msg}"
            )
            return

        dest = os.path.join(
            folder, f"data_backup_{datetime.now().strftime('%Y-%m-%d_%H%M')}.db"
        )

        self._set_backup_buttons_enabled(False)
        try:
            backup_path = create_backup(dest)
            if backup_path:
                # Oluşturulan yedeği doğrula
                is_valid, validation_msg = validate_backup_file(backup_path)
                if not is_valid:
                    QMessageBox.warning(
                        self,
                        "Uyarı",
                        f"Yedekleme oluşturuldu ancak doğrulama uyarısı:\n{validation_msg}"
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Başarılı",
                        f"Yedekleme tamamlandı ve doğrulandı:\n{backup_path}",
                    )
            else:
                QMessageBox.warning(self, "Uyarı", "Yedekleme oluşturulamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
        finally:
            self._set_backup_buttons_enabled(True)

    def restore_selected_backup(self) -> None:
        """Seçili yedeği geri yükle."""
        row = self.backup_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir yedek seçin.")
            return

        filepath = self.backup_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        filename = self.backup_table.item(row, 3).text()

        # Önce yedek dosyasını doğrula
        is_valid, validation_msg = validate_backup_file(filepath)
        if not is_valid:
            QMessageBox.critical(
                self,
                "Geçersiz Yedek",
                f"Bu yedek dosyası geri yüklenemez:\n{validation_msg}"
            )
            return

        # Yedek bilgilerini göster
        info = get_backup_info(filepath)
        info_text = ""
        if info:
            info_text = (
                f"\n\nYedek bilgileri:\n"
                f"- Dosya sayısı: {info.get('dava_count', '?')}\n"
                f"- Kullanıcı sayısı: {info.get('user_count', '?')}\n"
                f"- Boyut: {info.get('size_display', '?')}"
            )

        # İlk onay
        reply = QMessageBox.warning(
            self,
            "⚠️ DİKKAT - Geri Yükleme",
            f"'{filename}' yedeği geri yüklenecek.\n\n"
            "⚠️ UYARI: Mevcut verileriniz bu yedekle DEĞİŞTİRİLECEK!\n\n"
            "Güvenlik için mevcut verileriniz önce yedeklenecektir.\n"
            f"{info_text}\n\n"
            "Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # Varsayılan: Hayır
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # İkinci onay - yazarak onaylama
        from PyQt6.QtWidgets import QInputDialog
        confirm_text, ok = QInputDialog.getText(
            self,
            "Onay Gerekli",
            "Bu işlem geri alınamaz!\n\n"
            "Devam etmek için 'ONAYLA' yazın:"
        )
        if not ok or confirm_text.strip().upper() != "ONAYLA":
            QMessageBox.information(self, "İptal", "Geri yükleme iptal edildi.")
            return

        self._set_backup_buttons_enabled(False)
        try:
            success, message = restore_backup(filepath)
            if success:
                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"{message}\n\n"
                    "Değişikliklerin uygulanması için uygulamayı yeniden başlatın.",
                )
                self.load_backup_list()
            else:
                QMessageBox.warning(self, "Uyarı", f"Geri yükleme başarısız:\n{message}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Geri yükleme hatası:\n{e}")
        finally:
            self._set_backup_buttons_enabled(True)

    def delete_selected_backup(self) -> None:
        """Seçili yedeği sil."""
        row = self.backup_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir yedek seçin.")
            return

        # Minimum yedek sayısı kontrolü
        backup_count = len(list_backups())
        if backup_count <= MINIMUM_BACKUP_COUNT:
            QMessageBox.warning(
                self,
                "Silme Engellendi",
                f"En az {MINIMUM_BACKUP_COUNT} yedek tutulmalıdır.\n\n"
                f"Mevcut yedek sayısı: {backup_count}\n\n"
                "Güvenliğiniz için bu yedek silinemez."
            )
            return

        filepath = self.backup_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        filename = self.backup_table.item(row, 3).text()

        reply = QMessageBox.question(
            self,
            "Onay",
            f"'{filename}' yedeği silinecek.\n\nDevam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Güvenli silme fonksiyonunu kullan
        success, message = safe_delete_file(filepath)
        if success:
            self.load_backup_list()
            QMessageBox.information(self, "Başarılı", "Yedek silindi.")
        else:
            QMessageBox.critical(self, "Hata", f"Silme hatası:\n{message}")

    def verify_all_backups(self) -> None:
        """Tüm yedeklerin bütünlüğünü kontrol eder."""
        backups = list_backups()
        if not backups:
            QMessageBox.information(self, "Bilgi", "Doğrulanacak yedek bulunamadı.")
            return

        self._set_backup_buttons_enabled(False)
        try:
            valid_count = 0
            invalid_count = 0
            invalid_files = []

            for backup in backups:
                is_valid, msg = validate_backup_file(backup["filepath"])
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    invalid_files.append(f"{backup['filename']}: {msg}")

            if invalid_count == 0:
                QMessageBox.information(
                    self,
                    "Doğrulama Tamamlandı",
                    f"Tüm yedekler geçerli.\n\n"
                    f"Doğrulanan yedek sayısı: {valid_count}",
                )
            else:
                invalid_list = "\n".join(invalid_files[:5])  # İlk 5 hatayı göster
                if len(invalid_files) > 5:
                    invalid_list += f"\n... ve {len(invalid_files) - 5} daha"

                QMessageBox.warning(
                    self,
                    "Doğrulama Tamamlandı",
                    f"Bazı yedekler geçersiz!\n\n"
                    f"Geçerli: {valid_count}\n"
                    f"Geçersiz: {invalid_count}\n\n"
                    f"Geçersiz dosyalar:\n{invalid_list}",
                )
        finally:
            self._set_backup_buttons_enabled(True)

    def load_database(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Yedek Veritabanı Seç",
            "",
            "Veritabanı Dosyaları (*.db)",
        )
        if not file_path:
            return

        file_path = os.path.abspath(file_path)
        if not file_path.lower().endswith(".db"):
            QMessageBox.warning(self, "Uyarı", "Lütfen .db uzantılı bir dosya seçin.")
            return

        if os.path.abspath(DB_PATH) == file_path:
            QMessageBox.information(
                self,
                "Bilgi",
                "Seçtiğiniz dosya zaten kullanılan veritabanı.",
            )
            return

        try:
            is_valid, missing_tables = validate_database_file(file_path)
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(
                self,
                "Veritabanı Hatası",
                f"Veritabanı dosyası kontrol edilirken hata oluştu:\n{exc}",
            )
            return

        if not is_valid:
            missing_text = ", ".join(sorted(missing_tables)) if missing_tables else ""
            message = "Seçtiğiniz dosya geçerli bir Lex Takip veritabanı değil."
            if missing_text:
                message += f"\nEksik tablolar: {missing_text}"
            QMessageBox.warning(self, "Uyarı", message)
            return

        db_dir = os.path.dirname(DB_PATH)
        os.makedirs(db_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = os.path.join(db_dir, f"data_before_restore_{timestamp}.db")

        try:
            if os.path.exists(DB_PATH):
                shutil.copyfile(DB_PATH, backup_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hata",
                f"Mevcut veritabanı yedeklenemedi:\n{exc}",
            )
            return

        try:
            shutil.copyfile(file_path, DB_PATH)
            initialize_database()
        except Exception as exc:
            try:
                if os.path.exists(backup_path):
                    shutil.copyfile(backup_path, DB_PATH)
            except Exception:  # pragma: no cover - best effort
                pass
            QMessageBox.critical(
                self,
                "Hata",
                f"Veritabanı yüklenemedi: {exc}",
            )
            return

        restart_required = False
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.close()
        except sqlite3.Error:
            restart_required = True

        if self.main_window is not None and not restart_required:
            try:
                if hasattr(self.main_window, "populate_status_filter"):
                    self.main_window.populate_status_filter()
                if getattr(self.main_window, "user_filter_combo", None) is not None:
                    self.main_window.populate_user_filter()
                if getattr(self.main_window, "finance_user_filter_combo", None) is not None:
                    self.main_window.populate_finance_user_filter()
                if hasattr(self.main_window, "refresh_table"):
                    self.main_window.refresh_table()
                if hasattr(self.main_window, "refresh_finance_table"):
                    self.main_window.refresh_finance_table()
                try:  # pragma: no cover - runtime import guard
                    from app.ui_edit_dialog import EditDialog
                except ModuleNotFoundError:  # pragma: no cover
                    from ui_edit_dialog import EditDialog

                EditDialog.load_status_names()
            except Exception:
                restart_required = True

        if restart_required:
            QMessageBox.information(
                self,
                "Bilgi",
                "Veritabanı yüklendi. Değişikliklerin uygulanması için "
                "uygulamayı yeniden başlatmanız gerekebilir.",
            )
        else:
            QMessageBox.information(
                self,
                "Başarılı",
                "Veritabanı dosyası başarıyla yüklendi.",
            )

    def open_export_dialog(self) -> None:
        if self.main_window and hasattr(self.main_window, "export_data"):
            self.main_window.export_data()
            return
        QMessageBox.warning(
            self,
            "Bilgi",
            "Dışa aktarma işlemi ana pencereden başlatılamadı.",
        )

    def _apply_owner_rule(self, owner_item: QTableWidgetItem | None, hex_code: str) -> None:
        """Renk değiştiğinde kategori adını günceller."""
        if owner_item is None:
            return
        normalized = normalize_hex(hex_code)
        # Renk kodundan owner değerine dönüşüm
        color_to_owner = {
            "FFD700": "SARI",
            "FF8C00": "TURUNCU",
            "CD853F": "GARIP_TURUNCU",
            "FF0000": "KIRMIZI",
        }
        owner = color_to_owner.get(normalized, "")
        category_name = get_category_display_name(owner)
        owner_item.setText(category_name)
        owner_item.setData(Qt.ItemDataRole.UserRole, owner)

    def _attach_color_owner(self, color_widget: ColorEditor, owner_item: QTableWidgetItem) -> None:
        color_widget.colorChanged.connect(
            lambda hex_code, item=owner_item: self._apply_owner_rule(item, hex_code)
        )
        self._apply_owner_rule(owner_item, color_widget.get_hex())

    def load_statuses(self) -> None:
        if self.status_table is None:
            return
        self.status_table.setSortingEnabled(False)  # Yükleme sırasında sıralamayı kapat
        self.status_table.setRowCount(0)
        self.status_original_ids = set()
        statuses = get_statuses()
        for status in statuses:
            row = self.status_table.rowCount()
            self.status_table.insertRow(row)

            # Durum adı
            ad_item = QTableWidgetItem(status["ad"])
            ad_item.setData(Qt.ItemDataRole.UserRole, status["id"])
            self.status_table.setItem(row, 0, ad_item)

            # Renk - arka plan rengini de ayarla
            color_hex = status.get("color_hex", "FFFFFF")
            row_color = QColor("#" + color_hex)
            row_color.setAlpha(50)  # Hafif transparan

            if self.can_edit_statuses:
                color_widget = ColorEditor(color_hex)
                self.status_table.setCellWidget(row, 1, color_widget)
                # Kategori - Türkçe isimle göster (düzenlenemez)
                owner = status.get("owner", "")
                category_name = get_category_display_name(owner)
                owner_item = QTableWidgetItem(category_name)
                owner_item.setData(Qt.ItemDataRole.UserRole, owner)  # Orijinal değeri sakla
                owner_item.setFlags(owner_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Kategori değiştirilemez
                self.status_table.setItem(row, 2, owner_item)
                self._attach_color_owner(color_widget, owner_item)
            else:
                color_item = QTableWidgetItem(color_hex)
                color_item.setFlags(color_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                color_item.setBackground(QColor("#" + color_hex))
                self.status_table.setItem(row, 1, color_item)
                owner = status.get("owner", "")
                category_name = get_category_display_name(owner)
                owner_item = QTableWidgetItem(category_name)
                owner_item.setData(Qt.ItemDataRole.UserRole, owner)
                owner_item.setFlags(owner_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.status_table.setItem(row, 2, owner_item)

            # Satır arka plan rengi
            for col in range(3):
                item = self.status_table.item(row, col)
                if item:
                    item.setBackground(row_color)

            self.status_original_ids.add(status["id"])

        self.status_table.setSortingEnabled(True)
        # Varsayılan olarak kategoriye göre sırala
        self.status_table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self._update_status_count()

    def _update_status_count(self) -> None:
        """Durum sayısı etiketini günceller."""
        if self.status_count_label is None or self.status_table is None:
            return
        visible = 0
        for row in range(self.status_table.rowCount()):
            if not self.status_table.isRowHidden(row):
                visible += 1
        total = self.status_table.rowCount()
        if visible == total:
            self.status_count_label.setText(f"{total} durum")
        else:
            self.status_count_label.setText(f"{visible} / {total} durum")

    def _filter_status_table(self, text: str) -> None:
        """Durum tablosunu arama metnine göre filtreler."""
        if self.status_table is None:
            return
        search = text.strip().lower()
        for row in range(self.status_table.rowCount()):
            item = self.status_table.item(row, 0)
            if item:
                match = search in item.text().lower() if search else True
                self.status_table.setRowHidden(row, not match)
        self._update_status_count()

    def add_status_row(self) -> None:
        if self.status_table is None:
            return
        row = self.status_table.rowCount()
        self.status_table.insertRow(row)
        self.status_table.setItem(row, 0, QTableWidgetItem())
        color_widget = ColorEditor()
        self.status_table.setCellWidget(row, 1, color_widget)
        owner_item = QTableWidgetItem()
        owner_item.setFlags(owner_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Kategori değiştirilemez
        self.status_table.setItem(row, 2, owner_item)
        self._attach_color_owner(color_widget, owner_item)

    def remove_status_row(self) -> None:
        if self.status_table is None:
            return
        selection_model = self.status_table.selectionModel()
        if selection_model is None:
            return
        selected = selection_model.selectedRows()
        for index in reversed(selected):
            self.status_table.removeRow(index.row())

    # --- Yetki yönetimi yardımcıları ---

    def load_permissions(self) -> None:
        if not self.permission_checks:
            return
        permissions_map = get_all_permissions()
        for role, checkboxes in self.permission_checks.items():
            role_permissions = permissions_map.get(role, {})
            for action, checkbox in checkboxes.items():
                # Kurucu Avukat (admin) için tüm yetkiler her zaman aktif
                if role == "admin":
                    checkbox.setChecked(True)
                    checkbox.setEnabled(False)
                    continue
                checkbox.setChecked(bool(role_permissions.get(action, False)))

    def save_permissions(self) -> None:
        for role, checkboxes in self.permission_checks.items():
            # Kurucu Avukat (admin) yetkileri değiştirilemez, atla
            if role == "admin":
                continue
            updates: dict[str, bool] = {}
            for action, checkbox in checkboxes.items():
                updates[action] = checkbox.isChecked()
            set_permissions_for_role(role, updates)
            if self.user_id is not None:
                log_action(self.user_id, f"update_permissions_{role}")

    def _restore_geometry(self) -> None:
        ba = self.settings.value("ui/settings_dialog/geometry", None)
        if isinstance(ba, QByteArray) and not ba.isEmpty():
            try:
                self.restoreGeometry(ba)
                return
            except Exception:  # pragma: no cover - GUI safety
                pass
        self.resize(760, 560)

    def _save_geometry(self) -> None:
        try:
            ba = self.saveGeometry()
            self.settings.setValue("ui/settings_dialog/geometry", ba)
        except Exception:  # pragma: no cover - GUI safety
            pass

    def closeEvent(self, event):  # noqa: D401 - Qt override
        self._save_geometry()
        super().closeEvent(event)

    def accept(self):  # noqa: D401 - Qt override
        self._save_geometry()
        super().accept()

    def reject(self):  # noqa: D401 - Qt override
        self._save_geometry()
        super().reject()

    # --- Kullanıcı yönetimi yardımcıları ---

    def load_users(self) -> None:
        if self.user_table is None:
            return
        self.user_table.setRowCount(0)
        for user in get_users():
            row = self.user_table.rowCount()
            self.user_table.insertRow(row)
            id_item = QTableWidgetItem(str(user["id"]))
            id_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.user_table.setItem(row, 0, id_item)

            name_item = QTableWidgetItem(user["username"])
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.user_table.setItem(row, 1, name_item)

            role_label = USER_ROLE_LABELS.get(user["role"], user["role"])
            role_item = QTableWidgetItem(role_label)
            role_item.setData(Qt.ItemDataRole.UserRole, user["role"])
            role_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.user_table.setItem(row, 2, role_item)

            active_item = QTableWidgetItem()
            active_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            active_item.setCheckState(
                Qt.CheckState.Checked if user["active"] else Qt.CheckState.Unchecked
            )
            self.user_table.setItem(row, 3, active_item)

    def add_user_dialog(self) -> None:
        if self.user_table is None:
            return
        dialog = UserEditorDialog(self)
        if not dialog.exec():
            return
        data = dialog.get_values()
        if not data["username"] or not data["password"]:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı ve şifre gerekli.")
            return
        try:
            uid = db_add_user(
                data["username"], data["password"], data["role"], data["active"]
            )
            if self.user_id is not None:
                log_action(self.user_id, "add_user", uid)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı zaten mevcut.")
            return
        self.load_users()

    def edit_user_dialog(self) -> None:
        if self.user_table is None:
            return
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hata", "Lütfen bir kullanıcı seçin.")
            return
        user = {
            "id": int(self.user_table.item(row, 0).text()),
            "username": self.user_table.item(row, 1).text(),
            "role": self.user_table.item(row, 2).data(Qt.ItemDataRole.UserRole)
            or self.user_table.item(row, 2).text(),
            "active": self.user_table.item(row, 3).checkState()
            == Qt.CheckState.Checked,
        }
        dialog = UserEditorDialog(self, user)
        if not dialog.exec():
            return
        data = dialog.get_values()
        if not data["username"]:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı boş olamaz.")
            return
        try:
            db_update_user(
                user["id"],
                data["username"],
                data["password"] or None,
                data["role"],
                data["active"],
            )
            if self.user_id is not None:
                log_action(self.user_id, "update_user", user["id"])
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı zaten mevcut.")
            return
        self.load_users()

    def delete_user_dialog(self) -> None:
        if self.user_table is None:
            return
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hata", "Lütfen bir kullanıcı seçin.")
            return
        user_id = int(self.user_table.item(row, 0).text())
        if (
            QMessageBox.question(
                self,
                "Onay",
                "Seçili kullanıcı silinecek. Emin misiniz?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            db_delete_user(user_id)
            if self.user_id is not None:
                log_action(self.user_id, "delete_user", user_id)
        except ValueError:
            QMessageBox.warning(self, "Hata", "Admin kullanıcısı silinemez.")
            return
        self.load_users()

    def _show_license_info(self) -> None:
        """Lisans bilgileri diyaloğunu gösterir."""
        dialog = LicenseInfoDialog(self)
        dialog.exec()

    def _show_transfer_dialog(self) -> None:
        """Bilgisayar transferi diyaloğunu gösterir."""
        dialog = TransferDialog(self)
        dialog.exec()
