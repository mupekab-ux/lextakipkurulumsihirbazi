# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QSettings, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - runtime import guard
    from app.models import (
        get_arabuluculuk_list,
        log_action,
    )
    from app.services.arabuluculuk_service import mark_arabuluculuk_complete
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        get_arabuluculuk_list,
        log_action,
    )
    from services.arabuluculuk_service import mark_arabuluculuk_complete

try:  # pragma: no cover - runtime import guard
    from app.ui_arabuluculuk_dialog import ArabuluculukDialog
except ModuleNotFoundError:  # pragma: no cover
    from ui_arabuluculuk_dialog import ArabuluculukDialog

try:  # pragma: no cover - runtime import guard
    from app.ui_arabuluculuk_model import ArabuluculukTableModel, COL_TAMAMLANDI, COL_SIRA
except ModuleNotFoundError:  # pragma: no cover
    from ui_arabuluculuk_model import ArabuluculukTableModel, COL_TAMAMLANDI, COL_SIRA


class ArabuluculukTab(QWidget):
    def __init__(self, *, current_user: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_user = current_user or {}
        self.user_id = self.current_user.get("id")

        self.table_model = ArabuluculukTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Tüm sütunlarda ara

        self._all_records: list[Dict[str, Any]] = []
        self._alert_filter: tuple[date, date] | None = None
        self._current_filter: str = "all"

        self._build_ui()
        self.load_records()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Filtre ve arama satırı
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Tarih filtreleri
        self.filter_buttons: dict[str, QToolButton] = {}
        for key, label in (
            ("all", "Tümü"),
            ("today", "Bugün"),
            ("week", "Bu Hafta"),
            ("month", "Bu Ay"),
            ("past", "Geçmiş"),
        ):
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setMinimumWidth(70)
            btn.clicked.connect(lambda checked, k=key: self._on_filter_changed(k))
            self.filter_buttons[key] = btn
            filter_layout.addWidget(btn)
        self.filter_buttons["all"].setChecked(True)

        filter_layout.addSpacing(16)

        # Arama kutusu
        filter_layout.addWidget(QLabel("Ara:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Davacı, davalı, arabulucu veya konu ara...")
        self.search_edit.setMinimumWidth(250)
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addStretch()

        # Yeni arabuluculuk butonu
        self.new_button = QPushButton("+ Yeni Arabuluculuk")
        self.new_button.setMinimumWidth(140)
        self.new_button.clicked.connect(self.add_record)
        filter_layout.addWidget(self.new_button)

        # Yenile butonu
        self.refresh_button = QToolButton()
        self.refresh_button.setText("Yenile")
        self.refresh_button.clicked.connect(self.load_records)
        filter_layout.addWidget(self.refresh_button)

        layout.addLayout(filter_layout)

        # Tablo
        self._build_table(layout)

    def _on_filter_changed(self, key: str) -> None:
        """Filtre butonu değiştiğinde."""
        for name, btn in self.filter_buttons.items():
            btn.setChecked(name == key)
        self._current_filter = key
        self._apply_filters()

    def _on_search_changed(self, text: str) -> None:
        """Arama metni değiştiğinde."""
        self.proxy_model.setFilterFixedString(text)

    def _apply_filters(self) -> None:
        """Tarih filtrelerini uygula."""
        today = date.today()
        filtered = list(self._all_records)

        if self._current_filter == "today":
            filtered = [r for r in filtered if self._coerce_date(r.get("toplanti_tarihi")) == today]
        elif self._current_filter == "week":
            week_end = today + timedelta(days=7)
            filtered = [r for r in filtered if self._is_in_range(r, today, week_end)]
        elif self._current_filter == "month":
            month_end = today + timedelta(days=30)
            filtered = [r for r in filtered if self._is_in_range(r, today, month_end)]
        elif self._current_filter == "past":
            filtered = [r for r in filtered if self._is_past(r)]

        self.table_model.set_records(filtered)
        self.proxy_model.invalidate()

    def _is_in_range(self, record: Dict[str, Any], start: date, end: date) -> bool:
        """Kaydın tarihinin aralıkta olup olmadığını kontrol et."""
        toplanti = self._coerce_date(record.get("toplanti_tarihi"))
        if toplanti and start <= toplanti <= end:
            return True
        return False

    def _is_past(self, record: Dict[str, Any]) -> bool:
        """Kaydın geçmişte olup olmadığını kontrol et (tamamlananlar hariç)."""
        # Tamamlanan kayıtlar geçmiş filtresinde gösterilmesin
        if record.get("tamamlandi"):
            return False
        toplanti = self._coerce_date(record.get("toplanti_tarihi"))
        if toplanti and toplanti < date.today():
            return True
        return False

    def _build_table(self, layout: QVBoxLayout) -> None:
        """Tablo görünümünü oluştur."""
        self.table_view = QTableView(self)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.setWordWrap(False)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table_view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table_view.doubleClicked.connect(self._open_from_index)
        self.table_view.clicked.connect(self._on_cell_clicked)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._open_header_menu)

        # Kaydedilmiş sütun genişliklerini yükle
        self._load_column_widths()

        # Sütun genişliği değiştiğinde otomatik kaydet
        self._column_save_timer = QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.setInterval(500)
        self._column_save_timer.timeout.connect(self._save_column_widths)
        header.sectionResized.connect(self._on_section_resized)

        self._copy_shortcut = QShortcut(
            QKeySequence(QKeySequence.StandardKey.Copy), self.table_view
        )
        self._copy_shortcut.activated.connect(self._copy_selection)
        layout.addWidget(self.table_view)

    # -------------------------------------------------------------- Actions --
    def load_records(self) -> None:
        try:
            records = get_arabuluculuk_list()
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Kayıtlar yüklenemedi:\n{exc}")
            return
        self._all_records = list(records)
        self._apply_filters()

    def add_record(self) -> None:
        dialog = ArabuluculukDialog(self, current_user=self.current_user)
        if dialog.exec() == int(dialog.DialogCode.Accepted):
            if dialog.last_action == "insert" and self.user_id:
                log_action(self.user_id, "add_arabuluculuk", dialog.record_id)
            self.load_records()

    def _on_cell_clicked(self, index) -> None:
        """Hücreye tıklandığında - checkbox sütunu ise tamamlandı durumunu değiştir."""
        source_index = self.proxy_model.mapToSource(index)
        if source_index.column() == COL_TAMAMLANDI:
            id_index = self.table_model.index(source_index.row(), COL_SIRA)
            rec_id = self.table_model.data(id_index, Qt.ItemDataRole.UserRole)
            if rec_id:
                current_status = self.table_model.data(source_index, Qt.ItemDataRole.UserRole)
                new_status = not bool(current_status)
                try:
                    mark_arabuluculuk_complete(int(rec_id), new_status)
                    self.load_records()
                except Exception as exc:
                    QMessageBox.warning(self, "Hata", f"İşlem tamamlanamadı:\n{exc}")

    def _open_from_index(self, proxy_index) -> None:
        if not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        record = self.table_model.record_at(source_index.row())
        if not record:
            return
        self._edit_record(record)

    def _edit_record(self, record: Dict[str, Any]) -> None:
        rec_id = record.get("id")
        if rec_id is None:
            return
        dialog = ArabuluculukDialog(
            self,
            record_id=int(rec_id),
            current_user=self.current_user,
        )
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return
        if dialog.last_action == "update" and self.user_id:
            log_action(self.user_id, "update_arabuluculuk", int(rec_id))
        elif dialog.last_action == "delete" and self.user_id:
            log_action(self.user_id, "delete_arabuluculuk", int(rec_id))
        self.load_records()

    def _open_header_menu(self, pos) -> None:
        header = self.table_view.horizontalHeader()
        if header is None:
            return
        menu = QMenu(self.table_view)
        for visual in range(header.count()):
            logical = header.logicalIndex(visual)
            title = self.table_model.headerData(
                logical,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            label = str(title) if title else f"Sütun {logical + 1}"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(not self.table_view.isColumnHidden(logical))
            action.toggled.connect(
                lambda checked, col=logical: self.table_view.setColumnHidden(col, not checked)
            )
        menu.exec(header.mapToGlobal(pos))

    def _copy_selection(self) -> None:
        selection = self.table_view.selectionModel()
        if selection is None or not selection.hasSelection():
            return
        indexes = selection.selectedIndexes()
        if not indexes:
            return
        sorted_indexes = sorted(indexes, key=lambda idx: (idx.row(), idx.column()))
        rows: dict[int, list] = {}
        for index in sorted_indexes:
            rows.setdefault(index.row(), []).append(index)
        text_rows: list[str] = []
        for row in sorted(rows):
            columns = sorted(rows[row], key=lambda idx: idx.column())
            values = []
            for index in columns:
                data = index.data(Qt.ItemDataRole.DisplayRole)
                values.append(str(data) if data is not None else "")
            text_rows.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(text_rows))

    def apply_alert_date_filter(self, start: date, end: date) -> None:
        if end < start:
            start, end = end, start
        self._alert_filter = (start, end)
        self._apply_alert_filter()

    def clear_alert_date_filter(self) -> None:
        self._alert_filter = None
        self._apply_alert_filter()

    def _apply_alert_filter(self) -> None:
        rows = list(self._all_records)
        if self._alert_filter is not None:
            start, end = self._alert_filter
            rows = [row for row in rows if self._matches_alert_range(row, start, end)]
        self.table_model.set_records(rows)
        self.proxy_model.invalidate()

    def _matches_alert_range(self, record: Dict[str, Any], start: date, end: date) -> bool:
        for key in ("toplanti_tarihi", "toplantı_tarihi", "meeting_date"):
            row_date = self._coerce_date(record.get(key))
            if row_date is not None and start <= row_date <= end:
                return True
        return False

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    # --------------------------------------------------------- Column Widths --
    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """Sütun genişliği değiştiğinde timer'ı başlat."""
        if hasattr(self, "_column_save_timer"):
            self._column_save_timer.start()

    def _load_column_widths(self) -> None:
        """Kaydedilmiş sütun genişliklerini yükle."""
        try:
            settings = QSettings("MyCompany", "LexTakip")
            widths = settings.value("arabuluculuk/col_widths", None)
            if widths is None:
                return
            header = self.table_view.horizontalHeader()
            if header is None:
                return
            for col, width in enumerate(widths):
                if col < header.count():
                    w = int(width)
                    if w > 0:
                        header.resizeSection(col, w)
        except Exception:
            pass

    def _save_column_widths(self) -> None:
        """Sütun genişliklerini kaydet."""
        try:
            header = self.table_view.horizontalHeader()
            if header is None:
                return
            widths = [header.sectionSize(col) for col in range(header.count())]
            settings = QSettings("MyCompany", "LexTakip")
            settings.setValue("arabuluculuk/col_widths", widths)
            settings.sync()
        except Exception:
            pass
