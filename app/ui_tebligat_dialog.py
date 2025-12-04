# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta, date
from typing import Any, Dict, Optional

from PyQt6.QtCore import QDate, QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

try:  # pragma: no cover - runtime import guard
    from app.models import (
        delete_tebligat,
        get_tebligat_by_id,
        insert_tebligat,
        update_tebligat,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        delete_tebligat,
        get_tebligat_by_id,
        insert_tebligat,
        update_tebligat,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import user_has_hard_delete
except ModuleNotFoundError:  # pragma: no cover
    from utils import user_has_hard_delete


class TebligatDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        tebligat_id: Optional[int] = None,
        current_user: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.tebligat_id = tebligat_id
        self.current_user = current_user or {}
        self.user_id = self.current_user.get("id")
        self.is_new = tebligat_id is None
        self.was_deleted = False
        self.last_action: Optional[str] = None

        self.setWindowTitle("Yeni Tebligat" if self.is_new else "Tebligat Düzenle")

        self._build_ui()
        self._load_existing()
        self._restore_dialog_size()

    def _restore_dialog_size(self) -> None:
        """Kaydedilmiş pencere boyutunu yükle."""
        settings = QSettings("LexTakip", "LexTakip")
        size = settings.value("TebligatDialog/size")
        if size:
            self.resize(size)

    def closeEvent(self, event) -> None:
        """Pencere boyutunu kaydet ve kapat."""
        settings = QSettings("LexTakip", "LexTakip")
        settings.setValue("TebligatDialog/size", self.size())
        super().closeEvent(event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.dosya_no_edit = QLineEdit()
        form_layout.addRow("Dosya No", self.dosya_no_edit)

        self.kurum_edit = QLineEdit()
        form_layout.addRow("Kurum", self.kurum_edit)

        self.geldigi_tarih_edit = self._create_date_edit()
        form_layout.addRow("Geldiği Tarih", self.geldigi_tarih_edit)

        self.teblig_tarihi_edit = self._create_date_edit()
        form_layout.addRow("Tebliğ Tarihi", self.teblig_tarihi_edit)

        self.chk_e_teblig = QCheckBox("E-Tebligat")
        self.chk_e_teblig.toggled.connect(self._handle_e_teblig_toggle)
        form_layout.addRow("", self.chk_e_teblig)

        self.is_son_gunu_edit = self._create_date_edit()
        form_layout.addRow("İşin Son Günü", self.is_son_gunu_edit)

        self.icerik_edit = QTextEdit()
        form_layout.addRow("İçerik", self.icerik_edit)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.button_box = QDialogButtonBox()
        save_btn = self.button_box.addButton("Kaydet", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = self.button_box.addButton("Çık", QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        self.delete_button = QPushButton("Tebligatı Sil")
        self.delete_button.setObjectName("btnDeleteTebligat")
        self.delete_button.clicked.connect(self._hard_delete)
        can_delete = user_has_hard_delete(self.current_user)
        self.delete_button.setVisible(not self.is_new and can_delete)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)

        self.geldigi_tarih_edit.dateChanged.connect(self._handle_geldigi_changed)

    def _create_date_edit(self) -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setDate(QDate.currentDate())
        return edit

    def _handle_e_teblig_toggle(self, checked: bool) -> None:
        if checked:
            self._apply_e_tebligat_date()

    def _handle_geldigi_changed(self) -> None:
        if self.chk_e_teblig.isChecked():
            self._apply_e_tebligat_date()

    def _apply_e_tebligat_date(self) -> None:
        qdate = self.geldigi_tarih_edit.date()
        if not qdate.isValid():
            return
        new_date = qdate.addDays(5)
        self.teblig_tarihi_edit.setDate(new_date)

    def _load_existing(self) -> None:
        if self.is_new or self.tebligat_id is None:
            return
        record = get_tebligat_by_id(int(self.tebligat_id))
        if not record:
            QMessageBox.warning(self, "Uyarı", "Tebligat kaydı bulunamadı.")
            return

        self.dosya_no_edit.setText(record.get("dosya_no", "") or "")
        self.kurum_edit.setText(record.get("kurum", "") or "")
        self._set_qdate(self.geldigi_tarih_edit, record.get("geldigi_tarih"))
        self._set_qdate(self.teblig_tarihi_edit, record.get("teblig_tarihi"))
        self._set_qdate(self.is_son_gunu_edit, record.get("is_son_gunu"))
        self.icerik_edit.setPlainText(record.get("icerik", "") or "")

        self._sync_e_teblig_checkbox(
            record.get("geldigi_tarih"), record.get("teblig_tarihi")
        )

    def _sync_e_teblig_checkbox(self, geldi_iso: Optional[str], teblig_iso: Optional[str]) -> None:
        self.chk_e_teblig.blockSignals(True)
        should_check = False
        if geldi_iso and teblig_iso:
            try:
                geldi_date = date.fromisoformat(geldi_iso)
                teblig_date = date.fromisoformat(teblig_iso)
                should_check = teblig_date == geldi_date + timedelta(days=5)
            except ValueError:
                should_check = False
        self.chk_e_teblig.setChecked(should_check)
        self.chk_e_teblig.blockSignals(False)

    def _save(self) -> None:
        payload = {
            "dosya_no": self.dosya_no_edit.text().strip(),
            "kurum": self.kurum_edit.text().strip(),
            "geldigi_tarih": self._qdate_iso(self.geldigi_tarih_edit),
            "teblig_tarihi": self._qdate_iso(self.teblig_tarihi_edit),
            "is_son_gunu": self._qdate_iso(self.is_son_gunu_edit),
            "icerik": self.icerik_edit.toPlainText().strip(),
        }
        try:
            if self.is_new or self.tebligat_id is None:
                new_id = insert_tebligat(payload)
                self.tebligat_id = new_id
                self.last_action = "insert"
            else:
                payload["id"] = self.tebligat_id
                update_tebligat(payload)
                self.last_action = "update"
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Kayıt kaydedilemedi:\n{exc}")
            return
        self.accept()

    def _hard_delete(self) -> None:
        if self.tebligat_id is None:
            return
        if not user_has_hard_delete(self.current_user):
            QMessageBox.warning(self, "Uyarı", "Bu işlem için yetkiniz yok.")
            return
        answer = QMessageBox.question(
            self,
            "Onay",
            "Bu tebligatı kalıcı olarak silmek istediğinize emin misiniz?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_tebligat(int(self.tebligat_id))
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Tebligat silinemedi:\n{exc}")
            return
        self.was_deleted = True
        self.last_action = "delete"
        self.accept()

    @staticmethod
    def _qdate_iso(widget: QDateEdit) -> Optional[str]:
        qdate = widget.date()
        if not qdate.isValid():
            return None
        return f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"

    @staticmethod
    def _set_qdate(widget: QDateEdit, iso_value: Optional[str]) -> None:
        if iso_value:
            try:
                parsed = date.fromisoformat(iso_value)
                widget.setDate(QDate(parsed.year, parsed.month, parsed.day))
                return
            except ValueError:
                pass
        widget.setDate(QDate.currentDate())
