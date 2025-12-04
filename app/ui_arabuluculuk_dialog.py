# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional, Any

from PyQt6.QtCore import QDate, QTime, QSettings
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

try:  # pragma: no cover - runtime import guard
    from app.models import (
        get_arabuluculuk_by_id,
        insert_arabuluculuk,
        update_arabuluculuk,
        delete_arabuluculuk,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        get_arabuluculuk_by_id,
        insert_arabuluculuk,
        update_arabuluculuk,
        delete_arabuluculuk,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import user_has_hard_delete
except ModuleNotFoundError:  # pragma: no cover
    from utils import user_has_hard_delete


class ArabuluculukDialog(QDialog):
    """Yeni veya mevcut arabuluculuk kaydını düzenleyen diyalog."""

    def __init__(
        self,
        parent=None,
        *,
        record_id: Optional[int] = None,
        current_user: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.record_id = record_id
        self.is_new = record_id is None
        self.last_action: Optional[str] = None
        self.was_deleted = False
        if current_user is not None:
            self.current_user = current_user
        elif parent is not None and hasattr(parent, "current_user"):
            self.current_user = getattr(parent, "current_user")
        else:
            self.current_user = {}

        self.setWindowTitle("Yeni Arabuluculuk" if self.is_new else "Arabuluculuk Düzenle")

        self._build_ui()
        self._load_existing()
        self._restore_dialog_size()

    def _restore_dialog_size(self) -> None:
        """Kaydedilmiş pencere boyutunu yükle."""
        settings = QSettings("LexTakip", "LexTakip")
        size = settings.value("ArabuluculukDialog/size")
        if size:
            self.resize(size)

    def closeEvent(self, event) -> None:
        """Pencere boyutunu kaydet ve kapat."""
        settings = QSettings("LexTakip", "LexTakip")
        settings.setValue("ArabuluculukDialog/size", self.size())
        super().closeEvent(event)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.davaci_edit = QLineEdit()
        form.addRow("Davacı", self.davaci_edit)

        self.davali_edit = QLineEdit()
        form.addRow("Davalı", self.davali_edit)

        self.arb_adi_edit = QLineEdit()
        form.addRow("Arb. adı", self.arb_adi_edit)

        self.arb_tel_edit = QLineEdit()
        form.addRow("Arb tel no", self.arb_tel_edit)

        self.toplanti_tarih_edit = QDateEdit()
        self.toplanti_tarih_edit.setDisplayFormat("dd.MM.yyyy")
        self.toplanti_tarih_edit.setCalendarPopup(True)
        self.toplanti_tarih_edit.setDate(QDate.currentDate())
        form.addRow("Toplantı tarihi", self.toplanti_tarih_edit)

        self.toplanti_saat_edit = QTimeEdit()
        self.toplanti_saat_edit.setDisplayFormat("HH:mm")
        self.toplanti_saat_edit.setTime(QTime.currentTime())
        form.addRow("Toplantı saati", self.toplanti_saat_edit)

        self.konu_edit = QTextEdit()
        form.addRow("Konu", self.konu_edit)

        layout.addLayout(form)

        self.button_box = QDialogButtonBox()
        save_btn = self.button_box.addButton("Kaydet", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = self.button_box.addButton("Çık", QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)

        self.delete_button = QPushButton("Kaydı Sil")
        self.delete_button.setObjectName("btnDeleteArabuluculuk")
        self.delete_button.clicked.connect(self._delete_record)
        can_delete = (not self.is_new) and self._has_hard_delete()
        self.delete_button.setVisible(can_delete)
        self.delete_button.setEnabled(can_delete)

        button_row = QHBoxLayout()
        button_row.addWidget(self.delete_button)
        button_row.addStretch()
        button_row.addWidget(self.button_box)
        layout.addLayout(button_row)

    # -------------------------------------------------------------- Helpers --
    def _load_existing(self) -> None:
        if self.record_id is None:
            return
        record = get_arabuluculuk_by_id(int(self.record_id))
        if not record:
            QMessageBox.warning(self, "Uyarı", "Kayıt bulunamadı.")
            return

        self.davaci_edit.setText(record.get("davaci", "") or "")
        self.davali_edit.setText(record.get("davali", "") or "")
        self.arb_adi_edit.setText(record.get("arb_adi", "") or "")
        self.arb_tel_edit.setText(record.get("arb_tel", "") or "")
        self._set_qdate(self.toplanti_tarih_edit, record.get("toplanti_tarihi"))
        self._set_qtime(self.toplanti_saat_edit, record.get("toplanti_saati"))
        self.konu_edit.setPlainText(record.get("konu", "") or "")

    @staticmethod
    def _set_qdate(widget: QDateEdit, iso: Optional[str]) -> None:
        if not iso:
            widget.setDate(QDate.currentDate())
            return
        try:
            year, month, day = [int(part) for part in iso.split("-")]
        except (ValueError, AttributeError):
            widget.setDate(QDate.currentDate())
            return
        widget.setDate(QDate(year, month, day))

    @staticmethod
    def _set_qtime(widget: QTimeEdit, hhmm: Optional[str]) -> None:
        if not hhmm:
            widget.setTime(QTime.currentTime())
            return
        try:
            hour, minute = [int(part) for part in hhmm.split(":")]
        except (ValueError, AttributeError):
            widget.setTime(QTime.currentTime())
            return
        widget.setTime(QTime(hour, minute))

    def _qdate_iso(self, widget: QDateEdit) -> str:
        qdate = widget.date()
        return f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"

    def _qtime_hhmm(self, widget: QTimeEdit) -> str:
        qtime = widget.time()
        return f"{qtime.hour():02d}:{qtime.minute():02d}"

    # -------------------------------------------------------------- Actions --
    def _save(self) -> None:
        davaci = self.davaci_edit.text().strip()
        davali = self.davali_edit.text().strip()
        arb_adi = self.arb_adi_edit.text().strip()
        if not davaci or not davali or not arb_adi:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Davacı, Davalı ve Arb. adı alanları boş bırakılamaz.",
            )
            return

        payload = {
            "davaci": davaci,
            "davali": davali,
            "arb_adi": arb_adi,
            "arb_tel": self.arb_tel_edit.text().strip(),
            "toplanti_tarihi": self._qdate_iso(self.toplanti_tarih_edit),
            "toplanti_saati": self._qtime_hhmm(self.toplanti_saat_edit),
            "konu": self.konu_edit.toPlainText().strip(),
        }

        try:
            if self.record_id is None:
                new_id = insert_arabuluculuk(payload)
                self.record_id = new_id
                self.last_action = "insert"
            else:
                payload["id"] = self.record_id
                update_arabuluculuk(payload)
                self.last_action = "update"
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Kayıt kaydedilemedi:\n{exc}")
            return
        self.accept()

    # ------------------------------------------------------------ Deletion --
    def _has_hard_delete(self) -> bool:
        try:
            return bool(user_has_hard_delete(self.current_user))
        except Exception:
            perms = (self.current_user or {}).get("permissions") or {}
            if isinstance(perms, dict):
                return bool(
                    perms.get("hard_delete")
                    or perms.get("can_hard_delete")
                    or perms.get("HARD_DELETE")
                )
            if isinstance(perms, set):
                return "hard_delete" in perms or "HARD_DELETE" in perms
            return False

    def _delete_record(self) -> None:
        if self.record_id is None:
            QMessageBox.information(self, "Bilgi", "Yeni kayıt silinemez.")
            return
        if not self._has_hard_delete():
            QMessageBox.warning(self, "Yetki Yok", "Bu işlemi yapma yetkiniz yok.")
            return

        reply = QMessageBox.question(
            self,
            "Onay",
            "Bu Arabuluculuk kaydını kalıcı olarak silmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_arabuluculuk(int(self.record_id))
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Kayıt silinemedi:\n{exc}")
            return

        self.last_action = "delete"
        self.was_deleted = True
        self.accept()
