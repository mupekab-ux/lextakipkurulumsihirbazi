# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QDate, QEvent, Qt, QThread, QTimer, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QSplitter,
)
try:  # pragma: no cover - runtime import guard
    from app.db import (
        get_connection,
        get_timeline_for_dosya,
        insert_timeline_entry,
        update_dosya_with_auto_timeline,
        insert_completed_task,
        open_case_folder,
    )
except ModuleNotFoundError:  # pragma: no cover
    from db import (
        get_connection,
        get_timeline_for_dosya,
        insert_timeline_entry,
        update_dosya_with_auto_timeline,
        insert_completed_task,
        open_case_folder,
    )

try:  # pragma: no cover - runtime import guard
    from app.models import (
        add_dosya,
        get_dosya,
        get_next_buro_takip_no,
        get_statuses,
        get_users,
        get_dosya_assignees,
        set_dosya_assignees,
        delete_case_hard,
        list_custom_tabs,
        get_tab_assignments_for_dosya,
        set_tab_assignments_for_dosya,
        get_attachments,
        add_attachment,
        delete_attachment,
        delete_attachment_with_file,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        add_dosya,
        get_dosya,
        get_next_buro_takip_no,
        get_statuses,
        get_users,
        get_dosya_assignees,
        set_dosya_assignees,
        delete_case_hard,
        list_custom_tabs,
        get_tab_assignments_for_dosya,
        set_tab_assignments_for_dosya,
        get_attachments,
        add_attachment,
        delete_attachment,
        delete_attachment_with_file,
    )

try:  # pragma: no cover - runtime import guard
    from app.workers import AttachmentScanWorker
except ModuleNotFoundError:  # pragma: no cover
    from workers import AttachmentScanWorker

try:  # pragma: no cover - runtime import guard
    from app.attachments import AttachmentError, icon_for_ext, open_attachment
except ModuleNotFoundError:  # pragma: no cover
    from attachments import AttachmentError, icon_for_ext, open_attachment

try:  # pragma: no cover - runtime import guard
    from app.utils import (
        ROLE_NAMES,
        ROLE_COLOR_MAP,
        DEFAULT_ROLE_COLOR,
        iso_to_tr,
        tr_to_iso,
        setup_autocomplete,
        get_status_text_color,
        hex_to_qcolor,
        USER_ROLE_LABELS,
        ASSIGNMENT_EDIT_ROLES,
    )
except ModuleNotFoundError:  # pragma: no cover
    from utils import (
        ROLE_NAMES,
        ROLE_COLOR_MAP,
        DEFAULT_ROLE_COLOR,
        iso_to_tr,
        tr_to_iso,
        setup_autocomplete,
        get_status_text_color,
        hex_to_qcolor,
        USER_ROLE_LABELS,
        ASSIGNMENT_EDIT_ROLES,
    )

try:  # pragma: no cover - runtime import guard
    from app.status_helpers import get_dava_durumu_list
except ModuleNotFoundError:  # pragma: no cover
    from status_helpers import get_dava_durumu_list  # type: ignore
DEBUG_MODE = False
OPTIONAL_DATE_MIN = QDate(1900, 1, 1)
OPTIONAL_DATE_MAX = QDate(7999, 12, 31)


class SmartDateEdit(QDateEdit):
    """Boş tarih seçildiğinde takvimi bugüne odaklayan QDateEdit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_date = OPTIONAL_DATE_MIN

    def setMinimumDate(self, date: QDate) -> None:
        self._min_date = date
        super().setMinimumDate(date)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Takvim popup açıldığında bugüne git (eğer tarih boşsa)
        self._navigate_calendar_to_today_if_empty()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self._navigate_calendar_to_today_if_empty()

    def _navigate_calendar_to_today_if_empty(self) -> None:
        """Tarih boşsa (minimum tarih) takvimi bugüne odakla."""
        if self.date() == self._min_date:
            calendar = self.calendarWidget()
            if calendar is not None:
                calendar.setSelectedDate(QDate.currentDate())


def perf_now() -> float:
    return time.perf_counter()


def perf(message: str) -> None:
    if DEBUG_MODE:
        print(message)


def perf_elapsed(label: str, started_at: float) -> None:
    perf(f"[perf] {label} took {time.perf_counter() - started_at:.3f}s")


class AttachmentTableWidget(QTableWidget):
    filesDropped = pyqtSignal(list)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # type: ignore[override]
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths: list[str] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self.filesDropped.emit(paths)
        event.acceptProposedAction()


class AttachmentPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._dosya_id: Optional[int] = None
        self._scan_thread: Optional[QThread] = None
        self._scan_worker: Optional[AttachmentScanWorker] = None
        self._row_by_id: Dict[int, int] = {}
        self._scan_started_at: Optional[float] = None
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.status_label = QLabel("")
        self.status_label.setObjectName("AttachmentStatus")
        self.status_label.setStyleSheet("color: #bdbdbd;")
        layout.addWidget(self.status_label)

        self.table = AttachmentTableWidget(0, 4, self)
        self.table.setObjectName("AttachmentTable")
        self.table.setHorizontalHeaderLabels(["Ad", "Boyut", "Tür", "Eklenme"])
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected())
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for column in (1, 2, 3):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
            self.table.setColumnWidth(0, 280)
        layout.addWidget(self.table, 1)
        self.table.filesDropped.connect(self._add_files_from_paths)
        self.table.itemSelectionChanged.connect(self._update_selection_buttons)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.add_button = QPushButton("Ekle…")
        self.add_button.clicked.connect(self._choose_files)
        button_row.addWidget(self.add_button)

        self.open_button = QPushButton("Sistemle Aç")
        self.open_button.clicked.connect(self.open_selected)
        button_row.addWidget(self.open_button)

        self.delete_button = QPushButton("Sil")
        self.delete_button.clicked.connect(self.delete_selected)
        button_row.addWidget(self.delete_button)

        button_row.addStretch(1)

        self.open_folder_button = QPushButton("Klasörü Aç")
        self.open_folder_button.setToolTip("Dosya klasörünü dosya yöneticisinde aç")
        self.open_folder_button.clicked.connect(self._open_case_folder)
        button_row.addWidget(self.open_folder_button)

        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QWidget#AttachmentCard, QWidget#AttachmentCard QWidget {
                background-color: #1f1f1f;
                border-radius: 10px;
            }
            QTableWidget#AttachmentTable {
                background-color: #242424;
                alternate-background-color: #1f1f1f;
                color: #f0f0f0;
                border: 1px solid #2c2c2c;
                border-radius: 8px;
            }
            QLabel#AttachmentStatus {
                color: #bdbdbd;
            }
            QPushButton {
                border: 1px solid #3f3f3f;
                border-radius: 8px;
                padding: 4px 10px;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #343434;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            """
        )
        self._update_controls()
        self.destroyed.connect(lambda: self._cancel_worker())

    def set_dosya_id(self, dosya_id: Optional[int]) -> None:
        self._dosya_id = dosya_id
        self._update_controls()
        if dosya_id is None:
            self._clear_table()
            self._set_status("Ek eklemek için önce dosyayı kaydedin.")

    def refresh(self) -> None:
        if self._dosya_id is None:
            self._clear_table()
            self._set_status("Ek eklemek için önce dosyayı kaydedin.")
            return
        self._cancel_worker()
        self._clear_table()
        self._set_status("Ekler yükleniyor…")
        self._scan_started_at = perf_now()
        worker = AttachmentScanWorker(self._dosya_id)
        thread = QThread(self)
        self._scan_worker = worker
        self._scan_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.batchReady.connect(self._on_worker_batch)
        worker.errorOccurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _clear_table(self) -> None:
        self.table.setRowCount(0)
        self._row_by_id.clear()
        self._update_selection_buttons()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _cancel_worker(self) -> None:
        if self._scan_worker is not None:
            try:
                self._scan_worker.cancel()
            except Exception:
                pass
        if self._scan_thread is not None:
            self._scan_thread.quit()
            self._scan_thread.wait(200)
        self._scan_worker = None
        self._scan_thread = None

    def _on_worker_batch(self, records: List[Dict[str, Any]]) -> None:
        self.table.setUpdatesEnabled(False)
        try:
            for record in records:
                row = self._append_record(record)
                try:
                    self._row_by_id[int(record.get("id"))] = row
                except (TypeError, ValueError):
                    continue
        finally:
            self.table.setUpdatesEnabled(True)
        count = len(self._row_by_id)
        if count:
            self._set_status(f"{count} ek listelendi.")
        self._update_selection_buttons()

    def _append_record(self, record: Dict[str, Any]) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(record.get("name") or "(adsız)")
        name_item.setData(Qt.ItemDataRole.UserRole, record)
        ext_source = record.get("name") or record.get("stored_path") or ""
        icon = icon_for_ext(Path(ext_source).suffix)
        if not icon.isNull():
            name_item.setIcon(icon)
        size_item = QTableWidgetItem(record.get("size_display") or "-")
        mime_item = QTableWidgetItem(record.get("mime") or "")
        added_item = QTableWidgetItem(record.get("added_display") or "")
        for item in (name_item, size_item, mime_item, added_item):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, size_item)
        self.table.setItem(row, 2, mime_item)
        self.table.setItem(row, 3, added_item)
        if not record.get("exists", True):
            for column in range(4):
                item = self.table.item(row, column)
                if item:
                    item.setBackground(QColor("#4a1f1f"))
                    item.setToolTip(
                        "Dosya bulunamadı. 'Yolu Güncelle' ile yeni kaynak seçebilirsiniz."
                    )
        return row

    def _on_worker_error(self, message: str) -> None:
        self._set_status("Ekler yüklenemedi.")
        QMessageBox.critical(self, "Hata", f"Ekler yüklenemedi:\n{message}")

    def _on_worker_finished(self) -> None:
        if self._scan_started_at is not None:
            perf_elapsed("attachment_scan", self._scan_started_at)
            self._scan_started_at = None
        if not self._row_by_id:
            self._set_status("Herhangi bir ek bulunamadı.")
        self._scan_worker = None
        self._scan_thread = None

    def _selected_record(self) -> Optional[Dict[str, Any]]:
        items = self.table.selectedItems()
        if not items:
            return None
        record = items[0].data(Qt.ItemDataRole.UserRole)
        return record if isinstance(record, dict) else None

    def _selected_id(self) -> Optional[int]:
        record = self._selected_record()
        if not record:
            return None
        try:
            return int(record.get("id"))
        except (TypeError, ValueError):
            return None

    def _update_controls(self) -> None:
        has_case = self._dosya_id is not None
        self.add_button.setEnabled(has_case)
        self.open_folder_button.setEnabled(has_case)
        self._update_selection_buttons()

    def _open_case_folder(self) -> None:
        """Dava klasörünü dosya yöneticisinde açar."""
        if self._dosya_id is None:
            QMessageBox.information(
                self,
                "Bilgi",
                "Klasörü açmak için önce dosyayı kaydedin."
            )
            return
        if not open_case_folder(self._dosya_id):
            QMessageBox.warning(
                self,
                "Hata",
                "Klasör açılamadı."
            )

    def dragEnterEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # type: ignore[override]
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self._add_files_from_paths(paths)
        event.acceptProposedAction()

    def _choose_files(self) -> None:
        if self._dosya_id is None:
            QMessageBox.information(self, "Bilgi", "Ek eklemek için önce dosyayı kaydedin.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Ek Seç", "")
        if not files:
            return
        self._add_files_from_paths(files)

    def _add_files_from_paths(self, paths: List[str]) -> None:
        if self._dosya_id is None:
            return
        errors: List[str] = []
        for path in paths:
            try:
                add_attachment(self._dosya_id, path)
            except (AttachmentError, FileNotFoundError) as exc:
                errors.append(str(exc))
            except Exception as exc:  # pragma: no cover - güvenlik
                errors.append(str(exc))
        if errors:
            QMessageBox.warning(
                self,
                "Ekler eklenirken hata oluştu",
                "\n".join(errors),
            )
        self._load_files()

    def _load_files(self) -> None:
        self.refresh()

    def _update_selection_buttons(self) -> None:
        has_case = self._dosya_id is not None
        has_selection = self._selected_record() is not None
        enable_actions = has_case and has_selection
        self.open_button.setEnabled(enable_actions)
        self.delete_button.setEnabled(enable_actions)

    def open_selected(self) -> None:
        record = self._selected_record()
        if not record:
            return
        path = record.get("absolute_path") or record.get("path")
        if not path:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Dosya yolu bulunamadı. 'Yolu Güncelle' ile düzeltin.",
            )
            return
        file_path = Path(path)
        if not file_path.exists():
            QMessageBox.warning(
                self,
                "Uyarı",
                "Dosya bulunamadı. 'Yolu Güncelle' ile düzeltin.",
            )
            return
        try:
            open_attachment(str(file_path))
        except AttachmentError as exc:
            QMessageBox.warning(self, "Uyarı", str(exc))

    def delete_selected(self) -> None:
        attachment_id = self._selected_id()
        if attachment_id is None:
            QMessageBox.information(self, "Bilgi", "Lütfen silmek için bir ek seçin.")
            return
        message = QMessageBox(self)
        message.setWindowTitle("Ek Sil")
        message.setText("Bu eki silmek istediğinize emin misiniz?")
        remove_disk = message.addButton(
            "Diskten Sil", QMessageBox.ButtonRole.DestructiveRole
        )
        remove_db = message.addButton(
            "Sadece Kaydı Sil",
            QMessageBox.ButtonRole.AcceptRole,
        )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        clicked = message.clickedButton()
        try:
            if clicked is remove_disk:
                delete_attachment_with_file(attachment_id)
            elif clicked is remove_db:
                delete_attachment(attachment_id)
            else:
                return
        except Exception as exc:  # pragma: no cover - güvenlik
            QMessageBox.critical(self, "Hata", f"Ek silinemedi:\n{exc}")
            return
        self.refresh()


class EditDialog(QDialog):
    STATUS_NAMES: list[str] = []

    @classmethod
    def load_status_names(cls) -> None:
        cls.STATUS_NAMES = get_dava_durumu_list()

    def _configure_status_combobox(self, combo: QComboBox, items: list[str]) -> None:
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMaxVisibleItems(10)
        # Dropdown okunu görünür yap
        combo.setStyleSheet("""
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #999;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
        """)
        combo.clear()
        combo.addItems(items)
        line_edit = combo.lineEdit()
        if line_edit is not None:
            completer = setup_autocomplete(line_edit, items)
            line_edit.installEventFilter(self)
            line_edit.clear()
            self._lineedit_combo_map[line_edit] = combo
            # Completer'dan seçim yapıldığında combo'yu güncelle
            completer.activated.connect(lambda text, c=combo: c.setCurrentText(text))
        combo.setCurrentText("")

    def _set_status_combobox_text(self, combo: QComboBox, text: str) -> None:
        value = (text or "").strip()
        if not value:
            combo.setCurrentText("")
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.clear()
            return
        index = combo.findText(value, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.insertItem(0, value)
            combo.setCurrentIndex(0)

    def __init__(
        self,
        parent: Optional[QDialog] = None,
        dosya_id: Optional[int] = None,
        current_user: Optional[dict] = None,
    ):
        super().__init__(parent)
        resolved_user = current_user or getattr(parent, "current_user", {}) or {}
        self.setUpdatesEnabled(False)
        self._primary_table_view = None
        try:
            self._initialize_dialog_contents(dosya_id, resolved_user)
        finally:
            view = getattr(self, "_primary_table_view", None)
            if view is not None:
                try:
                    view.setSortingEnabled(True)
                except Exception:
                    pass
                if hasattr(view, "model"):
                    model = view.model()
                    if model is not None:
                        try:
                            model.blockSignals(False)
                        except Exception:
                            pass
            self.setUpdatesEnabled(True)
        # Kaydedilmiş pencere boyutunu yükle
        self._restore_dialog_size()

    def _restore_dialog_size(self) -> None:
        """Kaydedilmiş pencere boyutunu yükle."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        size = settings.value("EditDialog/size")
        if size:
            self.resize(size)

    def closeEvent(self, event) -> None:
        """Pencere boyutunu kaydet ve kapat."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        settings.setValue("EditDialog/size", self.size())
        super().closeEvent(event)

    def _initialize_dialog_contents(self, dosya_id: Optional[int], resolved_user: dict) -> None:
        self.dosya_id = dosya_id
        self.is_new = dosya_id is None
        self.was_archived = False
        self.was_hard_deleted = False
        self.hard_deleted_id: Optional[int] = None
        self.is_archived = False
        self.current_user = resolved_user
        self.current_user_id = self.current_user.get("id")
        self.is_admin = self.current_user.get("role") == "admin"
        user_permissions = self.current_user.get("permissions", {}) or {}
        self.can_hard_delete = self.is_admin or bool(
            user_permissions.get("can_hard_delete", False)
        )
        self.can_edit_assignments = (
            self.current_user.get("role") in ASSIGNMENT_EDIT_ROLES
        )
        self._initial_assignee_ids: list[int] = []
        self.setWindowTitle(
            "TakibiEsasi - Dosya Düzenle" if dosya_id else "TakibiEsasi - Yeni Dosya"
        )

        main_layout = QVBoxLayout(self)
        self._lineedit_combo_map: dict[QLineEdit, QComboBox] = {}
        self._job_date_edits: dict[str, QDateEdit] = {}
        self._job_shortcut_groups: dict[str, QButtonGroup] = {}
        self._suspended_job_shortcuts: set[str] = set()
        self._original_record: dict[str, object] = {}
        self._original_tracked_state: dict[str, object] = {}
        # Dava durumu değişikliklerini takip etmek için
        self._last_dava_durumu: str = ""
        self._last_dava_durumu_2: str = ""
        self._suppress_status_change_handler: bool = False

        info_form = QFormLayout()

        self.esas_no_edit = QLineEdit()
        info_form.addRow("Dosya Esas No", self.esas_no_edit)

        self.muvekkil_ad_edit = QLineEdit()
        info_form.addRow("Müvekkil Adı", self.muvekkil_ad_edit)

        role_layout = QHBoxLayout()
        self.muvekkil_rolu_combo = QComboBox()
        self.muvekkil_rolu_combo.addItems(ROLE_NAMES)
        self.role_color = QFrame()
        self.role_color.setFixedSize(20, 20)
        self.role_color.setFrameShape(QFrame.Shape.Box)
        role_layout.addWidget(self.muvekkil_rolu_combo)
        role_layout.addWidget(self.role_color)
        info_form.addRow("Müvekkil Rolü", role_layout)

        self.karsi_taraf_edit = QLineEdit()
        info_form.addRow("Karşı Taraf", self.karsi_taraf_edit)

        self.dosya_konusu_edit = QLineEdit()
        info_form.addRow("Dosya Konusu", self.dosya_konusu_edit)

        self.mahkeme_adi_edit = QLineEdit()
        info_form.addRow("Mahkeme Adı", self.mahkeme_adi_edit)

        self.dava_acilis_tarih_edit = QDateEdit()
        self.dava_acilis_tarih_edit.setDisplayFormat("dd.MM.yyyy")
        self.dava_acilis_tarih_edit.setCalendarPopup(True)
        self.dava_acilis_tarih_edit.setDate(QDate.currentDate())
        info_form.addRow("Dava Açılış Tarihi", self.dava_acilis_tarih_edit)

        info_tab = QWidget()
        info_tab.setLayout(info_form)

        self.load_status_names()
        statuses = self.STATUS_NAMES

        status_form = QFormLayout()

        self.dava_durumu_combo = QComboBox()
        self._configure_status_combobox(self.dava_durumu_combo, statuses)
        status_form.addRow("Dava Durumu", self.dava_durumu_combo)

        is_tarihi_widget = self._build_job_date_field("is_tarihi")
        status_form.addRow("İş Tarihi", is_tarihi_widget)

        self.aciklama_edit = QTextEdit()
        status_form.addRow("Açıklama", self.aciklama_edit)

        self.tekrar_dava_durumu_combo = QComboBox()
        self._configure_status_combobox(self.tekrar_dava_durumu_combo, statuses)
        status_form.addRow("Dava Durumu 2", self.tekrar_dava_durumu_combo)

        is_tarihi2_widget = self._build_job_date_field("is_tarihi_2")
        status_form.addRow("İş Tarihi 2", is_tarihi2_widget)

        self.aciklama2_edit = QTextEdit()
        status_form.addRow("Açıklama 2", self.aciklama2_edit)

        for widget in (self.aciklama_edit, self.aciklama2_edit):
            if isinstance(widget, (QTextEdit, QPlainTextEdit)):
                widget.setUndoRedoEnabled(True)

        durusma_layout = QHBoxLayout()
        self.durusma_tarih_edit = QDateEdit()
        self.durusma_tarih_edit.setDisplayFormat("dd.MM.yyyy")
        self.durusma_tarih_edit.setCalendarPopup(True)
        self.durusma_tarih_edit.setDate(QDate.currentDate())
        self.durusma_bos_checkbox = QCheckBox("Boş / Belirsiz")
        # Yeni dosyada duruşma tarihi varsayılan olarak boş başlasın
        if self.is_new:
            self.durusma_bos_checkbox.setChecked(True)
        durusma_layout.addWidget(self.durusma_tarih_edit)
        durusma_layout.addWidget(self.durusma_bos_checkbox)
        status_form.addRow("Duruşma Tarihi", durusma_layout)

        self.assignees_list = QListWidget()
        self.assignees_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        self.assignees_list.setMinimumHeight(120)
        status_form.addRow("Atanan Kullanıcılar", self.assignees_list)
        self._assignment_user_items: dict[int, QListWidgetItem] = {}
        self._populate_assignees_list()
        self.assignees_list.setEnabled(self.can_edit_assignments)
        if self.is_new and not self.can_edit_assignments and self.current_user_id is not None:
            self._initial_assignee_ids = [int(self.current_user_id)]
            self._select_assignees(self._initial_assignee_ids)

        self.custom_tabs_group = QGroupBox("Sekmelere Ata")
        tabs_layout = QVBoxLayout(self.custom_tabs_group)
        tabs_layout.setContentsMargins(6, 6, 6, 6)
        tabs_layout.setSpacing(4)
        self.custom_tabs_list = QListWidget()
        self.custom_tabs_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        self.custom_tabs_list.setMinimumHeight(120)
        tabs_layout.addWidget(self.custom_tabs_list)
        status_form.addRow(self.custom_tabs_group)
        self._custom_tab_items: dict[int, QListWidgetItem] = {}
        self._initial_custom_tab_ids: list[int] = []
        self._populate_custom_tabs_list()

        self.status_list_checkbox = QCheckBox("Durum Listesini Göster")
        status_form.addRow("", self.status_list_checkbox)

        status_form_widget = QWidget()
        status_form_widget.setLayout(status_form)

        self.status_panel = QFrame()
        self.status_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_panel.setMinimumWidth(220)
        self.status_panel.setVisible(False)
        panel_layout = QVBoxLayout(self.status_panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(6)
        panel_label = QLabel("Durumlar")
        panel_layout.addWidget(panel_label)
        self.status_list_widget = QListWidget()
        self.status_list_widget.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        panel_layout.addWidget(self.status_list_widget)

        status_layout = QHBoxLayout()
        status_layout.addWidget(status_form_widget, 1)
        status_layout.addWidget(self.status_panel)

        status_tab = QWidget()
        status_tab.setLayout(status_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.attachments_panel: Optional[AttachmentPanel] = None
        self.timeline_list: Optional[QListWidget] = None
        self.timeline_input_title: Optional[QLineEdit] = None
        self.timeline_input_body: Optional[QPlainTextEdit] = None
        self.timeline_add_button: Optional[QPushButton] = None
        self.timeline_tab_index: Optional[int] = None
        self.timeline_entries: list[dict] = []
        self._tab_initializers: Dict[int, Callable[[], None]] = {}
        self._tab_initialized: Dict[int, bool] = {}

        info_index = self.tab_widget.addTab(info_tab, "Dosya Bilgileri")
        status_index = self.tab_widget.addTab(status_tab, "Dosya Durumu")
        self._tab_initialized[info_index] = True
        self._tab_initialized[status_index] = True

        attachments_container = QWidget()
        attachments_container.setObjectName("AttachmentTabContainer")
        attachments_layout = QVBoxLayout(attachments_container)
        attachments_layout.setContentsMargins(0, 0, 0, 0)
        attachments_layout.setSpacing(0)
        placeholder = QLabel("Ekler henüz yüklenmedi.")
        placeholder.setObjectName("AttachmentPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        attachments_layout.addWidget(placeholder, 1)

        attachments_index = self.tab_widget.addTab(attachments_container, "Ekler")
        self._attachments_tab_index = attachments_index
        self._attachments_container = attachments_container
        self._tab_initializers[attachments_index] = self._init_attachments_tab
        self._tab_initialized[attachments_index] = False

        timeline_tab = self._build_timeline_tab()
        self.timeline_tab_index = self.tab_widget.addTab(timeline_tab, "Zaman Çizgisi")
        self._tab_initialized[self.timeline_tab_index] = True

        default_tab = info_index if self.is_new else status_index
        self.tab_widget.setCurrentIndex(default_tab)

        main_layout.addWidget(self.tab_widget)
        self._update_timeline_inputs_state()
        self._refresh_timeline_list()

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Kaydet")
        self.archive_button = QPushButton("Arşive Gönder")
        self.cancel_button = QPushButton("İptal")
        self.hard_delete_button = QPushButton("Kalıcı Sil")
        self.hard_delete_button.setObjectName("btnHardDelete")
        self.hard_delete_button.setToolTip(
            "Dosyayı kalıcı olarak siler. Geri alınamaz."
        )
        self.hard_delete_button.setStyleSheet(
            "QPushButton#btnHardDelete { background-color: #C62828; color: #FFFFFF; }"
            "QPushButton#btnHardDelete:pressed { background-color: #B71C1C; }"
        )
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.archive_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.hard_delete_button)
        main_layout.addLayout(button_layout)

        self.save_button.clicked.connect(self.save)
        self.archive_button.clicked.connect(self.archive_record)
        self.cancel_button.clicked.connect(self.reject)
        self.hard_delete_button.clicked.connect(self.hard_delete_record)
        self.muvekkil_rolu_combo.currentTextChanged.connect(self.update_role_color)
        self.durusma_bos_checkbox.toggled.connect(self.on_durusma_bos_toggled)
        self.status_list_checkbox.toggled.connect(self.on_status_list_toggled)
        self.update_role_color(self.muvekkil_rolu_combo.currentText())
        self.on_durusma_bos_toggled(self.durusma_bos_checkbox.isChecked())

        self._save_shortcut = QShortcut(
            QKeySequence(QKeySequence.StandardKey.Save), self
        )
        self._save_shortcut.activated.connect(self.save)

        self._close_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._close_shortcut.activated.connect(self.reject)
        self._tab_shortcuts: list[QShortcut] = []
        tab_shortcut_specs: list[tuple[str, int]] = [
            ("Ctrl+1", info_index),
            ("Ctrl+2", status_index),
        ]
        if self.timeline_tab_index is not None:
            tab_shortcut_specs.append(("Ctrl+3", self.timeline_tab_index))
        for sequence, tab_index in tab_shortcut_specs:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(
                lambda idx=tab_index: self.tab_widget.setCurrentIndex(idx)
            )
            self._tab_shortcuts.append(shortcut)

        self._history: list[dict[str, object]] = []
        self._history_index = -1
        self._block_history = False
        self._register_history_signals()

        self.archive_button.setVisible(self.is_admin and not self.is_new)
        self.hard_delete_button.setVisible(self.can_hard_delete and not self.is_new)

        self._initial_load_scheduled = False
        self._initial_load_completed = False
        self._block_history = True


    def _on_tab_changed(self, index: int) -> None:
        self._ensure_tab_initialized(index)

    def _ensure_tab_initialized(self, index: int) -> None:
        if self._tab_initialized.get(index):
            return
        initializer = self._tab_initializers.get(index)
        if initializer is None:
            self._tab_initialized[index] = True
            return
        try:
            initializer()
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(
                self,
                "Hata",
                f"Sekme yüklenemedi:\n{exc}",
            )
        finally:
            self._tab_initialized[index] = True

    def _init_attachments_tab(self) -> None:
        container = getattr(self, "_attachments_container", None)
        if container is None:
            return
        started = perf_now()
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    child_layout.deleteLater()
        panel = AttachmentPanel(container)
        panel.setObjectName("AttachmentCard")
        layout.addWidget(panel)
        self.attachments_panel = panel
        panel.set_dosya_id(self.dosya_id)
        if self.dosya_id is not None:
            panel.refresh()
        perf_elapsed("init_attachments_tab", started)

    def _build_timeline_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.timeline_list = QListWidget(container)
        self.timeline_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.timeline_list, 1)

        form_group = QGroupBox("Yeni Not Ekle", container)
        form_layout = QFormLayout(form_group)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(6)
        self.timeline_input_title = QLineEdit(form_group)
        form_layout.addRow("Başlık", self.timeline_input_title)
        self.timeline_input_body = QPlainTextEdit(form_group)
        self.timeline_input_body.setMaximumHeight(120)
        form_layout.addRow("Açıklama", self.timeline_input_body)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.timeline_add_button = QPushButton("Ekle", form_group)
        self.timeline_add_button.clicked.connect(self._on_timeline_add_clicked)
        button_row.addWidget(self.timeline_add_button)
        form_layout.addRow(button_row)
        layout.addWidget(form_group)
        return container

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        if not self._initial_load_scheduled:
            self._initial_load_scheduled = True
            QTimer.singleShot(0, self._perform_initial_load)

    def _perform_initial_load(self) -> None:
        if self._initial_load_completed:
            return
        started = perf_now()
        try:
            if self.dosya_id:
                self.load_data(self.dosya_id)
            else:
                # Yeni dosya için iş tarihi alanlarını temizle
                self._set_job_date_value("is_tarihi", None)
                self._set_job_date_value("is_tarihi_2", None)
                # Yeni kayıtta dava durumları boş başlar → widget'ları devre dışı bırak
                self._update_is_tarihi_widgets_state()
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(
                self,
                "Hata",
                f"Dosya verileri yüklenemedi:\n{exc}",
            )
        finally:
            self._original_tracked_state = self._capture_tracked_state()
            # ÖNEMLI: _original_record sadece yeni kayıtlar için set edilmeli
            # Mevcut kayıtlar için load_data() içinde veritabanından okunan değerler korunmalı
            if not self._original_record:
                self._original_record = dict(self._original_tracked_state)
            self._initial_load_completed = True
            self._block_history = False
            self._push_history_state()
            perf_elapsed("edit_dialog_initial_load", started)

    def _load_timeline_entries(self) -> None:
        entries: list[dict] = []
        if self.dosya_id is not None:
            try:
                entries = get_timeline_for_dosya(int(self.dosya_id))
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Uyarı",
                    f"Zaman çizgisi yüklenemedi:\n{exc}",
                )
        self.timeline_entries = entries
        self._refresh_timeline_list()

    def _refresh_timeline_list(self) -> None:
        if self.timeline_list is None:
            return
        self.timeline_list.blockSignals(True)
        self.timeline_list.clear()
        for entry in self.timeline_entries:
            full_text = self._build_timeline_entry_text(entry)
            item = QListWidgetItem(full_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(full_text)
            self.timeline_list.addItem(item)
        self.timeline_list.blockSignals(False)
        if self.timeline_list.count():
            self.timeline_list.setCurrentRow(self.timeline_list.count() - 1)

    def _build_timeline_entry_text(self, entry: dict) -> str:
        """Format a timeline entry as a single-line display text."""

        timestamp = self._format_timeline_timestamp(entry.get("created_at"))
        title = entry.get("title") or "(Başlıksız)"
        user = entry.get("user") or ""
        header = f"[{timestamp}] {title}"
        if user:
            header = f"{header} - {user}"
        body = entry.get("body") or ""
        if body:
            return f"{header}\n{body}"
        return header

    def _on_timeline_add_clicked(self) -> None:
        if self.dosya_id is None:
            QMessageBox.warning(self, "Uyarı", "Not eklemek için dosyayı kaydedin.")
            return
        try:
            dosya_id = int(self.dosya_id)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Uyarı", "Dosya numarası geçersiz.")
            return
        title = self.timeline_input_title.text().strip() if self.timeline_input_title else ""
        body = (
            self.timeline_input_body.toPlainText().strip()
            if self.timeline_input_body
            else ""
        )
        if not title and not body:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Başlık veya açıklama girmeniz gerekiyor.",
            )
            return
        user = self.current_user.get("username") or "Bilinmiyor"
        try:
            insert_timeline_entry(dosya_id, user, "manual", title or "(Başlıksız)", body)
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Not eklenemedi:\n{exc}")
            return
        if self.timeline_input_title:
            self.timeline_input_title.clear()
        if self.timeline_input_body:
            self.timeline_input_body.clear()
        self._load_timeline_entries()
        if self.timeline_list and self.timeline_list.count():
            self.timeline_list.setCurrentRow(self.timeline_list.count() - 1)

    def _update_timeline_inputs_state(self) -> None:
        enabled = self.dosya_id is not None
        for widget in (
            self.timeline_input_title,
            self.timeline_input_body,
            self.timeline_add_button,
        ):
            if widget is not None:
                widget.setEnabled(enabled)

    @staticmethod
    def _format_timeline_timestamp(value: Any) -> str:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(value[:19], fmt)
                    break
                except ValueError:
                    continue
            else:
                return value
        else:
            return "—"
        return dt.strftime("%d.%m.%Y %H:%M")

    def update_role_color(self, role: str) -> None:
        color = ROLE_COLOR_MAP.get(role, DEFAULT_ROLE_COLOR)
        self.role_color.setStyleSheet(f"background-color: {color};")

    def on_durusma_bos_toggled(self, checked: bool) -> None:
        self.durusma_tarih_edit.setEnabled(not checked)

    def on_status_list_toggled(self, checked: bool) -> None:
        self.status_panel.setVisible(checked)
        if checked:
            self.populate_status_list()
        else:
            self.status_list_widget.clear()
        self.adjustSize()

    def populate_status_list(self) -> None:
        statuses = get_statuses()
        self.status_list_widget.clear()
        for status in statuses:
            name = status.get("ad", "")
            if not name:
                continue
            item = QListWidgetItem(name)
            color_hex = status.get("color_hex") or ""
            qcolor = hex_to_qcolor(color_hex)
            if qcolor.isValid():
                item.setBackground(qcolor)
                fg_color = QColor(get_status_text_color(color_hex))
                item.setForeground(fg_color)
            self.status_list_widget.addItem(item)

    def _create_optional_date_edit(self) -> QDateEdit:
        edit = SmartDateEdit()
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setCalendarPopup(True)
        edit.setDateRange(OPTIONAL_DATE_MIN, OPTIONAL_DATE_MAX)
        edit.setSpecialValueText("—")
        edit.setDate(OPTIONAL_DATE_MIN)  # Boş başlat (— gösterilir)
        return edit

    def _build_job_date_field(self, field: str) -> QWidget:
        edit = self._create_optional_date_edit()
        self._job_date_edits[field] = edit
        edit.dateChanged.connect(
            lambda _date, key=field: self._handle_job_date_changed(key)
        )
        shortcuts = self._build_job_shortcut_buttons(field)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(edit)
        layout.addWidget(shortcuts)
        return container

    def _build_job_shortcut_buttons(self, field: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        group = QButtonGroup(container)
        group.setExclusive(True)
        shortcuts = [
            ("Yok", None, "İş tarihini temizle"),
            ("Yarın", 1, None),
            ("3 gün sonra", 3, None),
            ("Gelecek hafta", 7, None),
        ]
        for label, days, tooltip in shortcuts:
            button = QPushButton(label)
            button.setCheckable(True)
            if tooltip:
                button.setToolTip(tooltip)
            group.addButton(button)
            button.toggled.connect(
                lambda checked, key=field, delta=days: self._handle_job_shortcut_toggled(
                    key, delta, checked
                )
            )
            layout.addWidget(button)
        layout.addStretch(1)
        self._job_shortcut_groups[field] = group
        return container

    def _handle_job_shortcut_toggled(
        self, field: str, days: int | None, checked: bool
    ) -> None:
        if not checked:
            return
        if days is None:
            self._set_job_date_value(field, None, preserve_shortcut=True)
            return
        target = QDate.currentDate().addDays(days)
        self._set_job_date_value(field, target, preserve_shortcut=True)

    def _handle_job_date_changed(self, field: str) -> None:
        if field in self._suspended_job_shortcuts:
            return
        self._clear_job_shortcut_selection(field)

    def _clear_job_shortcut_selection(self, field: str) -> None:
        group = self._job_shortcut_groups.get(field)
        if group is None:
            return
        for button in group.buttons():
            if button.isChecked():
                button.setChecked(False)

    def _set_job_date_value(
        self,
        field: str,
        value: QDate | str | None,
        *,
        default_to_today: bool = False,
        preserve_shortcut: bool = False,
    ) -> None:
        edit = self._job_date_edits.get(field)
        if edit is None:
            return
        self._suspended_job_shortcuts.add(field)
        try:
            target: Optional[QDate] = None
            if isinstance(value, QDate):
                target = value if value.isValid() else None
            elif isinstance(value, str) and value:
                parsed = QDate.fromString(value, "yyyy-MM-dd")
                if parsed.isValid():
                    target = parsed
            if target is not None:
                edit.setDate(target)
            elif default_to_today:
                edit.setDate(QDate.currentDate())
            else:
                edit.clear()
        finally:
            self._suspended_job_shortcuts.discard(field)
        if not preserve_shortcut:
            self._clear_job_shortcut_selection(field)

    def _get_job_date_value(self, field: str) -> Optional[str]:
        edit = self._job_date_edits.get(field)
        if edit is None:
            return None
        date_value = edit.date()
        if not date_value.isValid() or date_value == OPTIONAL_DATE_MIN:
            return None
        return date_value.toString("yyyy-MM-dd")

    def _populate_assignees_list(self) -> None:
        self.assignees_list.clear()
        self._assignment_user_items.clear()
        users = get_users()
        users.sort(key=lambda item: item.get("username", "").lower())
        for user in users:
            role_label = USER_ROLE_LABELS.get(user.get("role"), user.get("role", ""))
            username = user.get("username", "")
            display = username
            if role_label:
                display = f"{username} ({role_label})"
            if not user.get("active"):
                display = f"{display} [Pasif]"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, user.get("id"))
            if not user.get("active"):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.assignees_list.addItem(item)
            try:
                user_id = int(user.get("id"))
                self._assignment_user_items[user_id] = item
            except (TypeError, ValueError):
                continue

    def _populate_custom_tabs_list(self) -> None:
        self.custom_tabs_list.blockSignals(True)
        self.custom_tabs_list.clear()
        self._custom_tab_items.clear()
        conn = None
        tabs: list[dict] = []
        try:
            conn = get_connection()
            tabs = list_custom_tabs(conn)
        except Exception:
            tabs = []
        finally:
            if conn is not None:
                conn.close()
        tabs.sort(key=lambda tab: str(tab.get("name", "")).lower())
        for tab in tabs:
            tab_id = tab.get("id")
            name = tab.get("name") or "(İsimsiz Sekme)"
            try:
                normalized_id = int(tab_id)
            except (TypeError, ValueError):
                continue
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, normalized_id)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self.custom_tabs_list.addItem(item)
            self._custom_tab_items[normalized_id] = item
        self.custom_tabs_group.setVisible(bool(self._custom_tab_items))
        self.custom_tabs_list.blockSignals(False)

    def _get_selected_assignee_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.assignees_list.selectedItems():
            user_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                ids.append(int(user_id))
            except (TypeError, ValueError):
                continue
        return ids

    def _select_assignees(self, user_ids: list[int]) -> None:
        target_ids = {int(uid) for uid in user_ids}
        self.assignees_list.blockSignals(True)
        for user_id, item in self._assignment_user_items.items():
            item.setSelected(user_id in target_ids)
        self.assignees_list.blockSignals(False)

    def _get_selected_custom_tab_ids(self) -> list[int]:
        selected: list[int] = []
        for index in range(self.custom_tabs_list.count()):
            item = self.custom_tabs_list.item(index)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                tab_id = item.data(Qt.ItemDataRole.UserRole)
                try:
                    selected.append(int(tab_id))
                except (TypeError, ValueError):
                    continue
        return selected

    def _select_custom_tabs(self, tab_ids: list[int]) -> None:
        targets = {int(tab_id) for tab_id in tab_ids}
        self.custom_tabs_list.blockSignals(True)
        for tab_id, item in self._custom_tab_items.items():
            item.setCheckState(
                Qt.CheckState.Checked if tab_id in targets else Qt.CheckState.Unchecked
            )
        self.custom_tabs_list.blockSignals(False)

    def load_data(self, dosya_id: int) -> None:
        record = get_dosya(dosya_id)
        if not record:
            return
        self.is_archived = bool(record.get("is_archived"))
        self.esas_no_edit.setText(record.get("dosya_esas_no", ""))
        self.muvekkil_ad_edit.setText(record.get("muvekkil_adi", ""))
        role = record.get("muvekkil_rolu", ROLE_NAMES[0])
        idx = self.muvekkil_rolu_combo.findText(role)
        if idx >= 0:
            self.muvekkil_rolu_combo.setCurrentIndex(idx)
        else:
            self.muvekkil_rolu_combo.insertItem(0, role)
            self.muvekkil_rolu_combo.setCurrentIndex(0)
        self.update_role_color(self.muvekkil_rolu_combo.currentText())
        self.karsi_taraf_edit.setText(record.get("karsi_taraf", ""))
        self.dosya_konusu_edit.setText(record.get("dosya_konusu", ""))
        self.mahkeme_adi_edit.setText(record.get("mahkeme_adi", ""))
        if record.get("dava_acilis_tarihi"):
            self.dava_acilis_tarih_edit.setDate(QDate.fromString(record["dava_acilis_tarihi"], "yyyy-MM-dd"))
        self._set_job_date_value("is_tarihi", record.get("is_tarihi"))
        self._set_job_date_value("is_tarihi_2", record.get("is_tarihi_2"))
        if record.get("durusma_tarihi"):
            self.durusma_tarih_edit.setDate(QDate.fromString(record["durusma_tarihi"], "yyyy-MM-dd"))
            self.durusma_bos_checkbox.setChecked(False)
        else:
            self.durusma_bos_checkbox.setChecked(True)
        self._set_status_combobox_text(
            self.dava_durumu_combo, record.get("dava_durumu", "")
        )
        # ADIM 1: Dava durumu boşsa is_tarihi sıfırla (yedek kontrol)
        if not (record.get("dava_durumu") or "").strip():
            self._set_job_date_value("is_tarihi", None)
        self.aciklama_edit.setPlainText(record.get("aciklama", ""))
        self._set_status_combobox_text(
            self.tekrar_dava_durumu_combo, record.get("tekrar_dava_durumu_2", "")
        )
        # ADIM 1: Dava durumu 2 boşsa is_tarihi_2 sıfırla
        if not (record.get("tekrar_dava_durumu_2") or "").strip():
            self._set_job_date_value("is_tarihi_2", None)
        self.aciklama2_edit.setPlainText(record.get("aciklama_2", ""))
        assignees = get_dosya_assignees(dosya_id)
        ids: list[int] = []
        for user in assignees:
            try:
                ids.append(int(user.get("id")))
            except (TypeError, ValueError):
                continue
        self._initial_assignee_ids = ids
        self._select_assignees(ids)
        conn = get_connection()
        try:
            tab_ids = list(get_tab_assignments_for_dosya(conn, dosya_id))
        finally:
            conn.close()
        self._initial_custom_tab_ids = tab_ids
        self._select_custom_tabs(tab_ids)
        self._original_record = {
            "dava_durumu": record.get("dava_durumu", ""),
            "dava_durumu_2": record.get("tekrar_dava_durumu_2", ""),
            "aciklama": record.get("aciklama", ""),
            "aciklama_2": record.get("aciklama_2", ""),
            "is_tarihi": record.get("is_tarihi", ""),
            "is_tarihi_2": record.get("is_tarihi_2", ""),
            "durusma_tarihi": record.get("durusma_tarihi", ""),
        }
        if self.is_archived:
            self.archive_button.setEnabled(False)
        if self.is_admin:
            self.hard_delete_button.setVisible(True)
        self._load_timeline_entries()
        self._update_timeline_inputs_state()

        # Dava durumu değerlerini takip için kaydet ve widget durumlarını ayarla
        self._last_dava_durumu = (record.get("dava_durumu") or "").strip()
        self._last_dava_durumu_2 = (record.get("tekrar_dava_durumu_2") or "").strip()
        self._update_is_tarihi_widgets_state()

    def eventFilter(self, obj, event):  # type: ignore[override]
        # FocusOut olayında completer popup'ını kapat
        if event.type() == QEvent.Type.FocusOut:
            combo = self._lineedit_combo_map.get(obj)
            if combo is not None:
                completer = obj.completer() if hasattr(obj, "completer") else None
                if completer is not None:
                    popup = completer.popup()
                    if popup is not None and popup.isVisible():
                        popup.hide()
                # Combo box dropdown'ını da kapat
                view = combo.view()
                if view is not None and view.isVisible():
                    combo.hidePopup()
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            # Shift veya Enter tuşu ile otomatik seçim
            if key in (Qt.Key.Key_Shift, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                combo = self._lineedit_combo_map.get(obj)
                handled = False
                completer = obj.completer() if hasattr(obj, "completer") else None
                popup_visible = False
                if completer is not None:
                    popup = completer.popup()
                    popup_visible = popup is not None and popup.isVisible()
                if popup_visible and completer is not None:
                    model = completer.completionModel()
                    column = completer.completionColumn()
                    if model is not None and model.rowCount() > 0:
                        # Popup'ta seçili öğe varsa onu, yoksa ilk öğeyi al
                        popup = completer.popup()
                        selected_index = popup.currentIndex() if popup else None
                        if selected_index is not None and selected_index.isValid():
                            selected_text = selected_index.data()
                        else:
                            first_index = model.index(0, column)
                            selected_text = first_index.data()
                        if selected_text:
                            obj.setText(selected_text)
                            if combo is not None:
                                combo.setCurrentText(selected_text)
                            # Popup'ı kapat
                            if popup is not None:
                                popup.hide()
                            handled = True
                if not handled and combo is not None:
                    view = combo.view()
                    current_text = None
                    if view is not None and view.isVisible():
                        current_index = view.currentIndex()
                        if current_index.isValid():
                            current_text = current_index.data()
                    if current_text is None and combo.currentIndex() >= 0:
                        current_text = combo.itemText(combo.currentIndex())
                    if current_text:
                        combo.setCurrentText(current_text)
                        line_edit = combo.lineEdit()
                        if line_edit is not None and line_edit is not obj:
                            line_edit.setText(current_text)
                        handled = True
                if handled:
                    return True
            # Tab tuşu ile popup'ları kapat ve sonraki widget'a geç
            if key == Qt.Key.Key_Tab:
                combo = self._lineedit_combo_map.get(obj)
                if combo is not None:
                    completer = obj.completer() if hasattr(obj, "completer") else None
                    if completer is not None:
                        popup = completer.popup()
                        if popup is not None and popup.isVisible():
                            popup.hide()
                    view = combo.view()
                    if view is not None and view.isVisible():
                        combo.hidePopup()
        return super().eventFilter(obj, event)

    def _register_history_signals(self) -> None:
        self.esas_no_edit.textChanged.connect(self._on_field_modified)
        self.muvekkil_ad_edit.textChanged.connect(self._on_field_modified)
        self.muvekkil_rolu_combo.currentTextChanged.connect(self._on_field_modified)
        self.karsi_taraf_edit.textChanged.connect(self._on_field_modified)
        self.dosya_konusu_edit.textChanged.connect(self._on_field_modified)
        self.mahkeme_adi_edit.textChanged.connect(self._on_field_modified)
        self.dava_acilis_tarih_edit.dateChanged.connect(self._on_field_modified)
        self.durusma_tarih_edit.dateChanged.connect(self._on_field_modified)
        self.durusma_bos_checkbox.toggled.connect(self._on_field_modified)
        self.dava_durumu_combo.currentTextChanged.connect(self._on_field_modified)
        # Dava durumu değiştiğinde is_tarihi widget'ını kontrol et
        self.dava_durumu_combo.currentTextChanged.connect(self._on_dava_durumu_changed)
        self.aciklama_edit.textChanged.connect(self._on_field_modified)
        self.tekrar_dava_durumu_combo.currentTextChanged.connect(self._on_field_modified)
        # Dava durumu 2 değiştiğinde is_tarihi_2 widget'ını kontrol et
        self.tekrar_dava_durumu_combo.currentTextChanged.connect(self._on_dava_durumu_2_changed)
        self.aciklama2_edit.textChanged.connect(self._on_field_modified)
        self.assignees_list.itemSelectionChanged.connect(self._on_field_modified)
        self.custom_tabs_list.itemChanged.connect(self._on_field_modified)
        for edit in self._job_date_edits.values():
            edit.dateChanged.connect(self._on_field_modified)

    def _on_dava_durumu_changed(self, new_value: str) -> None:
        """Dava durumu değiştiğinde is_tarihi widget'ını kontrol et.

        Kurallar:
        - Dava durumu boşsa → is_tarihi devre dışı + temizle
        - Dava durumu değiştiyse (eski değer doluydu) → tamamlanan görevi kaydet + is_tarihi temizle
        - Dava durumu doluysa → is_tarihi aktif
        """
        if self._suppress_status_change_handler:
            return

        new_value = new_value.strip()
        old_value = self._last_dava_durumu

        # Widget'ları güncelle
        is_tarihi_edit = self._job_date_edits.get("is_tarihi")
        if is_tarihi_edit is None:
            return

        if not new_value:
            # Dava durumu boş → is_tarihi ve aciklama devre dışı ve temizle
            self._set_job_date_value("is_tarihi", None)
            is_tarihi_edit.setEnabled(False)
            self.aciklama_edit.setPlainText("")
            self.aciklama_edit.setEnabled(False)
        else:
            # Dava durumu dolu → is_tarihi ve aciklama aktif
            is_tarihi_edit.setEnabled(True)
            self.aciklama_edit.setEnabled(True)

            # Dava durumu değiştiyse ve eski değer doluydu → tamamlanan görevi kaydet + temizle
            # NOT: Kısa değerler (< 3 karakter) için görev oluşturma - bu kullanıcı yazarken
            # oluşan ara kayıtları önler
            if old_value and old_value != new_value and len(old_value.strip()) >= 3:
                # Tamamlanan görevi kaydet
                old_is_tarihi = self._get_job_date_value("is_tarihi")
                old_aciklama = self.aciklama_edit.toPlainText().strip()
                if old_is_tarihi:
                    user_name = (
                        self.current_user.get("username")
                        or self.current_user.get("kullanici_adi")
                        or ""
                    )
                    try:
                        insert_completed_task(
                            tarih=old_is_tarihi,
                            konu=old_value,
                            aciklama=old_aciklama or f"Dava durumu değişti: {old_value} → {new_value}",
                            olusturan_kullanici=user_name,
                            gorev_turu="IS_TARIHI",
                            dosya_id=self.dosya_id,
                        )
                    except Exception:
                        pass
                # is_tarihi ve aciklama'yı temizle
                self._set_job_date_value("is_tarihi", None)
                self.aciklama_edit.setPlainText("")

        self._last_dava_durumu = new_value

    def _on_dava_durumu_2_changed(self, new_value: str) -> None:
        """Dava durumu 2 değiştiğinde is_tarihi_2 ve aciklama_2 widget'larını kontrol et.

        Kurallar:
        - Dava durumu 2 boşsa → is_tarihi_2 ve aciklama_2 devre dışı + temizle
        - Dava durumu 2 değiştiyse (eski değer doluydu) → tamamlanan görevi kaydet + is_tarihi_2 ve aciklama_2 temizle
        - Dava durumu 2 doluysa → is_tarihi_2 ve aciklama_2 aktif
        """
        if self._suppress_status_change_handler:
            return

        new_value = new_value.strip()
        old_value = self._last_dava_durumu_2

        # Widget'ları güncelle
        is_tarihi_2_edit = self._job_date_edits.get("is_tarihi_2")
        if is_tarihi_2_edit is None:
            return

        if not new_value:
            # Dava durumu 2 boş → is_tarihi_2 ve aciklama_2 devre dışı ve temizle
            self._set_job_date_value("is_tarihi_2", None)
            is_tarihi_2_edit.setEnabled(False)
            self.aciklama2_edit.setPlainText("")
            self.aciklama2_edit.setEnabled(False)
        else:
            # Dava durumu 2 dolu → is_tarihi_2 ve aciklama_2 aktif
            is_tarihi_2_edit.setEnabled(True)
            self.aciklama2_edit.setEnabled(True)

            # Dava durumu 2 değiştiyse ve eski değer doluydu → tamamlanan görevi kaydet + temizle
            # NOT: Kısa değerler (< 3 karakter) için görev oluşturma - bu kullanıcı yazarken
            # oluşan ara kayıtları önler
            if old_value and old_value != new_value and len(old_value.strip()) >= 3:
                # Tamamlanan görevi kaydet
                old_is_tarihi_2 = self._get_job_date_value("is_tarihi_2")
                old_aciklama_2 = self.aciklama2_edit.toPlainText().strip()
                if old_is_tarihi_2:
                    user_name = (
                        self.current_user.get("username")
                        or self.current_user.get("kullanici_adi")
                        or ""
                    )
                    try:
                        insert_completed_task(
                            tarih=old_is_tarihi_2,
                            konu=old_value,
                            aciklama=old_aciklama_2 or f"Dava durumu 2 değişti: {old_value} → {new_value}",
                            olusturan_kullanici=user_name,
                            gorev_turu="IS_TARIHI_2",
                            dosya_id=self.dosya_id,
                        )
                    except Exception:
                        pass
                # is_tarihi_2 ve aciklama_2'yi temizle
                self._set_job_date_value("is_tarihi_2", None)
                self.aciklama2_edit.setPlainText("")

        self._last_dava_durumu_2 = new_value

    def _update_is_tarihi_widgets_state(self) -> None:
        """Dava durumlarına göre is_tarihi ve aciklama widget'larının durumunu güncelle.

        Dava durumu boşsa:
        - Widget devre dışı bırakılır
        - Değer sıfırlanır (null yapılır)
        """
        dava_durumu = self.dava_durumu_combo.currentText().strip()
        dava_durumu_2 = self.tekrar_dava_durumu_combo.currentText().strip()

        is_tarihi_edit = self._job_date_edits.get("is_tarihi")
        if is_tarihi_edit is not None:
            if not dava_durumu:
                # Dava durumu boş → is_tarihi ve aciklama devre dışı ve sıfırla
                self._set_job_date_value("is_tarihi", None)
                is_tarihi_edit.setEnabled(False)
                self.aciklama_edit.setPlainText("")
                self.aciklama_edit.setEnabled(False)
            else:
                is_tarihi_edit.setEnabled(True)
                self.aciklama_edit.setEnabled(True)

        is_tarihi_2_edit = self._job_date_edits.get("is_tarihi_2")
        if is_tarihi_2_edit is not None:
            if not dava_durumu_2:
                # Dava durumu 2 boş → is_tarihi_2 ve aciklama_2 devre dışı ve sıfırla
                self._set_job_date_value("is_tarihi_2", None)
                is_tarihi_2_edit.setEnabled(False)
                self.aciklama2_edit.setPlainText("")
                self.aciklama2_edit.setEnabled(False)
            else:
                is_tarihi_2_edit.setEnabled(True)
                self.aciklama2_edit.setEnabled(True)

    def _capture_state(self) -> dict[str, object]:
        durusma_bos = self.durusma_bos_checkbox.isChecked()
        durusma_value = (
            None
            if durusma_bos
            else self.durusma_tarih_edit.date().toString("yyyy-MM-dd")
        )
        return {
            "dosya_esas_no": self.esas_no_edit.text(),
            "muvekkil_adi": self.muvekkil_ad_edit.text(),
            "muvekkil_rolu": self.muvekkil_rolu_combo.currentText(),
            "karsi_taraf": self.karsi_taraf_edit.text(),
            "dosya_konusu": self.dosya_konusu_edit.text(),
            "mahkeme_adi": self.mahkeme_adi_edit.text(),
            "dava_acilis_tarihi": self.dava_acilis_tarih_edit.date().toString("yyyy-MM-dd"),
            "durusma_bos": durusma_bos,
            "durusma_tarihi": durusma_value,
            "dava_durumu": self.dava_durumu_combo.currentText(),
            "is_tarihi": self._get_job_date_value("is_tarihi"),
            "aciklama": self.aciklama_edit.toPlainText(),
            "tekrar_dava_durumu_2": self.tekrar_dava_durumu_combo.currentText(),
            "is_tarihi_2": self._get_job_date_value("is_tarihi_2"),
            "aciklama_2": self.aciklama2_edit.toPlainText(),
            "assignees": tuple(sorted(self._get_selected_assignee_ids())),
            "custom_tabs": tuple(sorted(self._get_selected_custom_tab_ids())),
        }

    def _capture_tracked_state(self) -> dict[str, object]:
        """Snapshot tracked fields for automatic timeline logging."""

        def normalize_date_text(value: Optional[str]) -> str:
            if not value:
                return ""
            return str(value).strip()

        def normalize_text(value: Optional[str]) -> str:
            if value is None:
                return ""
            return str(value).strip()

        durusma_value = None
        if not self.durusma_bos_checkbox.isChecked():
            durusma_value = tr_to_iso(self.durusma_tarih_edit.text())

        return {
            "dava_durumu": self.dava_durumu_combo.currentText().strip(),
            "dava_durumu_2": self.tekrar_dava_durumu_combo.currentText().strip(),
            "aciklama": normalize_text(self.aciklama_edit.toPlainText()),
            "aciklama_2": normalize_text(self.aciklama2_edit.toPlainText()),
            "is_tarihi": normalize_date_text(self._get_job_date_value("is_tarihi")),
            "is_tarihi_2": normalize_date_text(self._get_job_date_value("is_tarihi_2")),
            "durusma_tarihi": normalize_date_text(durusma_value),
        }

    def _push_history_state(self) -> None:
        state = self._capture_state()
        if self._history_index >= 0 and self._history[self._history_index] == state:
            return
        self._history = self._history[: self._history_index + 1]
        self._history.append(state)
        self._history_index = len(self._history) - 1
        max_len = 100
        if len(self._history) > max_len:
            self._history = self._history[-max_len:]
            self._history_index = len(self._history) - 1

    def _on_field_modified(self, *args) -> None:
        if self._block_history:
            return
        self._push_history_state()

    def _safe_qdate(self, value: object) -> QDate:
        if isinstance(value, str) and value:
            parsed = QDate.fromString(value, "yyyy-MM-dd")
            if parsed.isValid():
                return parsed
        return QDate.currentDate()

    def _apply_state(self, state: dict[str, object]) -> None:
        self._block_history = True
        self.esas_no_edit.setText(str(state.get("dosya_esas_no", "") or ""))
        self.muvekkil_ad_edit.setText(str(state.get("muvekkil_adi", "") or ""))
        self.muvekkil_rolu_combo.setCurrentText(
            str(state.get("muvekkil_rolu", "") or "")
        )
        self.karsi_taraf_edit.setText(str(state.get("karsi_taraf", "") or ""))
        self.dosya_konusu_edit.setText(str(state.get("dosya_konusu", "") or ""))
        self.mahkeme_adi_edit.setText(str(state.get("mahkeme_adi", "") or ""))

        acilis_value = state.get("dava_acilis_tarihi")
        self.dava_acilis_tarih_edit.setDate(self._safe_qdate(acilis_value))

        durusma_bos = bool(state.get("durusma_bos", False))
        self.durusma_bos_checkbox.setChecked(durusma_bos)
        durusma_value = state.get("durusma_tarihi")
        if durusma_value:
            self.durusma_tarih_edit.setDate(self._safe_qdate(durusma_value))
        elif not durusma_bos:
            self.durusma_tarih_edit.setDate(QDate.currentDate())

        self.dava_durumu_combo.setCurrentText(
            str(state.get("dava_durumu", "") or "")
        )
        self._set_job_date_value("is_tarihi", state.get("is_tarihi"))
        self.aciklama_edit.setPlainText(str(state.get("aciklama", "") or ""))
        self.tekrar_dava_durumu_combo.setCurrentText(
            str(state.get("tekrar_dava_durumu_2", "") or "")
        )
        self._set_job_date_value("is_tarihi_2", state.get("is_tarihi_2"))
        self.aciklama2_edit.setPlainText(str(state.get("aciklama_2", "") or ""))
        assignees = state.get("assignees")
        if isinstance(assignees, (list, tuple, set)):
            try:
                ids = [int(value) for value in assignees]
            except (TypeError, ValueError):
                ids = []
            self._select_assignees(ids)
        custom_tabs = state.get("custom_tabs")
        if isinstance(custom_tabs, (list, tuple, set)):
            try:
                tab_ids = [int(value) for value in custom_tabs]
            except (TypeError, ValueError):
                tab_ids = []
            self._select_custom_tabs(tab_ids)
        self._block_history = False

        self.update_role_color(self.muvekkil_rolu_combo.currentText())
        self.on_durusma_bos_toggled(self.durusma_bos_checkbox.isChecked())

    def undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._apply_state(self._history[self._history_index])

    def redo(self) -> None:
        if self._history_index < 0 or self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._apply_state(self._history[self._history_index])

    def _collect_form_data(self) -> Optional[dict[str, object]]:
        if not self.muvekkil_ad_edit.text().strip():
            QMessageBox.warning(self, "Hata", "Müvekkil Adı boş olamaz.")
            return None

        # Form değerlerini topla
        dava_durumu = self.dava_durumu_combo.currentText().strip()
        dava_durumu_2 = self.tekrar_dava_durumu_combo.currentText().strip()
        is_tarihi = self._get_job_date_value("is_tarihi")
        is_tarihi_2 = self._get_job_date_value("is_tarihi_2")

        # KURAL: Dava durumu boşsa is_tarihi olamaz
        # Burada doğrudan temizliyoruz - daha güvenilir
        if not dava_durumu:
            is_tarihi = None
        if not dava_durumu_2:
            is_tarihi_2 = None

        data: dict[str, object] = {
            "dosya_esas_no": self.esas_no_edit.text().strip(),
            "muvekkil_adi": self.muvekkil_ad_edit.text().strip(),
            "muvekkil_rolu": self.muvekkil_rolu_combo.currentText(),
            "karsi_taraf": self.karsi_taraf_edit.text().strip(),
            "dosya_konusu": self.dosya_konusu_edit.text().strip(),
            "mahkeme_adi": self.mahkeme_adi_edit.text().strip(),
            "dava_acilis_tarihi": tr_to_iso(self.dava_acilis_tarih_edit.text()),
            "durusma_tarihi": None
            if self.durusma_bos_checkbox.isChecked()
            else tr_to_iso(self.durusma_tarih_edit.text()),
            "dava_durumu": dava_durumu,
            "is_tarihi": is_tarihi,
            "aciklama": self.aciklama_edit.toPlainText().strip(),
            "tekrar_dava_durumu_2": dava_durumu_2,
            "is_tarihi_2": is_tarihi_2,
            "aciklama_2": self.aciklama2_edit.toPlainText().strip(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return data

    def _persist_record(
        self, data: dict[str, object], *, original_tracked_state: dict[str, object] | None = None
    ) -> tuple[bool, bool]:
        was_new = self.is_new
        try:
            if was_new:
                data["buro_takip_no"] = get_next_buro_takip_no()
                data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.dosya_id = add_dosya(data)
            else:
                if self.dosya_id is None:
                    raise RuntimeError("Düzenlenecek dosya bulunamadı.")
                user_name = (
                    self.current_user.get("username")
                    or self.current_user.get("kullanici_adi")
                    or ""
                )
                changed = update_dosya_with_auto_timeline(
                    self.dosya_id,
                    data,
                    user_name,
                    original_state=dict(original_tracked_state or {}),
                )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Hata", str(exc))
            return False, False
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hata",
                f"Kayıt kaydedilirken bir hata oluştu:\n{exc}",
            )
            return False, False

        assigned_ids: list[int] = list(self._initial_assignee_ids)
        if self.can_edit_assignments:
            assigned_ids = self._get_selected_assignee_ids()
        elif was_new and self.current_user_id is not None:
            assigned_ids = [int(self.current_user_id)]

        if self.dosya_id is not None:
            try:
                set_dosya_assignees(self.dosya_id, assigned_ids)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Hata", str(exc))
                return False, False

        tab_ids = self._get_selected_custom_tab_ids()
        if self.dosya_id is not None:
            conn = get_connection()
            try:
                set_tab_assignments_for_dosya(conn, self.dosya_id, tab_ids)
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                QMessageBox.critical(
                    self,
                    "Hata",
                    f"Sekme atamaları güncellenemedi:\n{exc}",
                )
                return False, False
            finally:
                conn.close()

        self._initial_assignee_ids = assigned_ids
        self._initial_custom_tab_ids = tab_ids
        if was_new:
            self.is_new = False
        self._update_timeline_inputs_state()
        if self.dosya_id is not None and self.attachments_panel is not None:
            self.attachments_panel.set_dosya_id(self.dosya_id)
            if self._tab_initialized.get(self._attachments_tab_index):
                self.attachments_panel.refresh()
        return True, bool(locals().get("changed"))

    def save(self) -> None:
        data = self._collect_form_data()
        if data is None:
            return

        old_state = dict(getattr(self, "_original_record", {}) or {})

        # Dava durumu değişikliklerini kontrol et (sadece mevcut kayıtlar için)
        if not self.is_new and self.dosya_id is not None:
            self._handle_status_change(data, old_state)

        new_state = self._capture_tracked_state()
        success, timeline_changed = self._persist_record(
            data, original_tracked_state=old_state
        )
        if not success:
            return
        if timeline_changed:
            self._load_timeline_entries()
        self._original_tracked_state = new_state
        self._original_record = dict(new_state)
        parent = self.parent()
        if parent is not None and hasattr(parent, "refresh_custom_tab_filters"):
            try:
                parent.refresh_custom_tab_filters()
            except Exception:
                pass
        self.accept()

    def _handle_status_change(self, data: dict, old_state: dict) -> None:
        """Dava durumu değiştiğinde veya silindiğinde is_tarihi'yi sıfırla.

        Kurallar:
        - Dava durumu silindiyse → is_tarihi sıfırlanır
        - Dava durumu değiştiyse → eski görev tamamlandı olarak kaydedilir, is_tarihi sıfırlanır

        NOT: old_state yerine doğrudan veritabanından okuyoruz -
        widget senkronizasyon sorunlarından kaçınmak için.
        """
        # Doğrudan veritabanından mevcut durumu oku (en güvenilir kaynak)
        db_record = get_dosya(self.dosya_id) if self.dosya_id else None
        if not db_record:
            return  # Kayıt bulunamadı, işlem yapma

        user_name = (
            self.current_user.get("username")
            or self.current_user.get("kullanici_adi")
            or ""
        )

        # Veritabanından okunan değerler
        db_dava_durumu = (db_record.get("dava_durumu") or "").strip()
        db_dava_durumu_2 = (db_record.get("tekrar_dava_durumu_2") or "").strip()
        db_is_tarihi = (db_record.get("is_tarihi") or "").strip()
        db_is_tarihi_2 = (db_record.get("is_tarihi_2") or "").strip()

        # Form'dan gelen yeni değerler
        new_dava_durumu = (data.get("dava_durumu") or "").strip()
        new_dava_durumu_2 = (data.get("tekrar_dava_durumu_2") or "").strip()
        new_is_tarihi = (data.get("is_tarihi") or "").strip() if data.get("is_tarihi") else ""
        new_is_tarihi_2 = (data.get("is_tarihi_2") or "").strip() if data.get("is_tarihi_2") else ""

        # ============================================================
        # DAVA DURUMU 1 KONTROLÜ
        # ============================================================
        # Kural 1: Dava durumu boşsa is_tarihi olamaz
        if not new_dava_durumu and new_is_tarihi:
            data["is_tarihi"] = None
            self._set_job_date_value("is_tarihi", None)
        # Kural 2: Dava durumu değiştiyse (ve eskisi doluydu), eski görevi kaydet ve is_tarihi'yi temizle
        elif db_dava_durumu != new_dava_durumu and db_dava_durumu:
            if db_is_tarihi:
                try:
                    insert_completed_task(
                        tarih=db_is_tarihi,
                        konu=db_dava_durumu,
                        aciklama=f"Dava durumu değişti: {db_dava_durumu} → {new_dava_durumu or '(boş)'}",
                        olusturan_kullanici=user_name,
                        gorev_turu="IS_TARIHI",
                        dosya_id=self.dosya_id,
                    )
                except Exception:
                    pass
            data["is_tarihi"] = None
            self._set_job_date_value("is_tarihi", None)

        # ============================================================
        # DAVA DURUMU 2 KONTROLÜ
        # ============================================================
        # Kural 1: Dava durumu 2 boşsa is_tarihi_2 olamaz
        if not new_dava_durumu_2 and new_is_tarihi_2:
            data["is_tarihi_2"] = None
            self._set_job_date_value("is_tarihi_2", None)
        # Kural 2: Dava durumu 2 değiştiyse (ve eskisi doluydu), eski görevi kaydet ve is_tarihi_2'yi temizle
        elif db_dava_durumu_2 != new_dava_durumu_2 and db_dava_durumu_2:
            if db_is_tarihi_2:
                try:
                    insert_completed_task(
                        tarih=db_is_tarihi_2,
                        konu=db_dava_durumu_2,
                        aciklama=f"Dava durumu 2 değişti: {db_dava_durumu_2} → {new_dava_durumu_2 or '(boş)'}",
                        olusturan_kullanici=user_name,
                        gorev_turu="IS_TARIHI_2",
                        dosya_id=self.dosya_id,
                    )
                except Exception:
                    pass
            data["is_tarihi_2"] = None
            self._set_job_date_value("is_tarihi_2", None)

    def archive_record(self) -> None:
        if not self.is_admin:
            QMessageBox.warning(
                self,
                "Yetki",
                "Arşive ekleme yetkisi sadece admin kullanıcısına verilmiştir.",
            )
            return

        if self.is_new or self.dosya_id is None:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Arşive göndermek için önce dosyayı kaydedin.",
            )
            return
        data = self._collect_form_data()
        if data is None:
            return
        data["is_archived"] = 1
        success, _ = self._persist_record(data)
        if not success:
            return
        self.was_archived = True
        self.is_archived = True
        QMessageBox.information(self, "Bilgi", "Dosya arşive gönderildi.")
        self.accept()

    def hard_delete_record(self) -> None:
        if self.dosya_id is None:
            return

        if not self.can_hard_delete:
            QMessageBox.warning(self, "Yetki", "Bu işlem için yetkiniz yok.")
            return

        reply = QMessageBox.question(
            self,
            "Kalıcı Sil",
            "Bu dosyayı kalıcı olarak silmek istediğinize emin misiniz?\n"
            "Bu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        text, ok = QInputDialog.getText(
            self,
            "Kalıcı Sil",
            "İşlemi onaylamak için BÜYÜK harflerle 'SİL' yazınız:",
        )
        if not ok:
            return
        if text.strip() != "SİL":
            QMessageBox.warning(
                self,
                "Uyarı",
                "Onay metni doğru girilmedi. Silme işlemi iptal edildi.",
            )
            return

        conn = None
        try:
            conn = get_connection()
            delete_case_hard(conn, int(self.dosya_id))
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(
                self,
                "Veritabanı hatası",
                f"Silme sırasında hata oluştu:\n{type(exc).__name__}: {exc}",
            )
            return
        finally:
            if conn is not None:
                conn.close()

        self.was_hard_deleted = True
        self.hard_deleted_id = int(self.dosya_id)
        QMessageBox.information(self, "Tamam", "Dosya kalıcı olarak silindi.")

        parent = self.parent()
        if parent is not None:
            if hasattr(parent, "refresh_table"):
                parent.refresh_table()
            if hasattr(parent, "refresh_finance_table"):
                parent.refresh_finance_table()

        self.accept()
