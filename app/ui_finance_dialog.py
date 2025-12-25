# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
import sqlite3
from functools import partial
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

from PyQt6.QtCore import Qt, QDate, QTimer, QLocale, QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import logging

try:  # pragma: no cover - runtime import guard
    from app.models import (
        get_finans_for_dosya,
        get_finans_by_id,
        update_finans_contract,
        generate_installments,
        get_payment_plan,
        save_payment_plan,
        reset_payment_plan,
        insert_payment_from_installment,
        delete_payment_by_installment,
        insert_payment_from_kasadan,
        delete_payment_from_kasadan,
        delete_payment,
        delete_expense,
        delete_expense_by_kasa_avans,
        get_payments,
        save_payments as store_payment_records,
        get_expenses,
        save_expenses as store_expense_records,
        recalculate_finans_totals,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        get_finans_for_dosya,
        get_finans_by_id,
        update_finans_contract,
        generate_installments,
        get_payment_plan,
        save_payment_plan,
        reset_payment_plan,
        insert_payment_from_installment,
        delete_payment_by_installment,
        insert_payment_from_kasadan,
        delete_payment_from_kasadan,
        delete_payment,
        delete_expense,
        delete_expense_by_kasa_avans,
        get_payments,
        save_payments as store_payment_records,
        get_expenses,
        save_expenses as store_expense_records,
        recalculate_finans_totals,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import format_tl, tl_to_cents
except ModuleNotFoundError:  # pragma: no cover
    from utils import format_tl, tl_to_cents

try:  # pragma: no cover - runtime import guard
    from app.db import (
        add_finans_timeline_entry,
        get_connection,
        get_finans_timeline,
        get_muvekkil_kasasi_entries,
        insert_muvekkil_kasasi_entry,
        update_muvekkil_kasasi_entry,
        delete_muvekkil_kasasi_entry,
    )
except ModuleNotFoundError:  # pragma: no cover
    from db import (
        add_finans_timeline_entry,
        get_connection,
        get_finans_timeline,
        get_muvekkil_kasasi_entries,
        insert_muvekkil_kasasi_entry,
        update_muvekkil_kasasi_entry,
        delete_muvekkil_kasasi_entry,
    )

INSTALLMENT_STATUS_OPTIONS = ["Ödenecek", "Ödendi", "Gecikmiş"]
EXPENSE_STATUS_OPTIONS = ["Bekliyor", "Tahsil Edildi"]
PAYMENT_SOURCE_OPTIONS = ["Kasadan", "Büro"]


logger = logging.getLogger(__name__)


class FinanceDialog(QDialog):
    """Bir dosya için finansal takip detaylarını gösterir."""

    @property
    def _current_username(self) -> str | None:
        """Mevcut kullanıcının kullanıcı adını döndür."""
        return self.current_user.get("username") if hasattr(self, "current_user") else None

    def _empty_finans_dict(self) -> dict[str, Any]:
        return {
            "dosya_id": self.dosya_id,
            "id": None,
            "finans_id": None,
            "sozlesme_ucreti": 0.0,
            "sozlesme_yuzdesi": 0.0,
            "tahsil_hedef_cents": 0,
            "notlar": "",
            "yuzde_is_sonu": 0,
            "tahsil_edilen_cents": 0,
            "masraf_toplam_cents": 0,
            "masraf_tahsil_cents": 0,
            "toplam_ucret_cents": 0,
            "kalan_bakiye_cents": 0,
        }

    def _to_float(self, value: Any) -> float:
        if value in (None, "", False):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return float(Decimal(str(value)))
            except (InvalidOperation, ValueError, TypeError):
                return 0.0

    def _to_int(self, value: Any) -> int:
        if value in (None, "", False):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(Decimal(str(value)))
            except (InvalidOperation, ValueError, TypeError):
                return 0

    def _create_amount_spinbox(self, max_value: float = 1_000_000_000, suffix: str = " ₺") -> QDoubleSpinBox:
        """Türk para formatında (binlik ayraçlı) tutar girişi için spinbox oluşturur."""
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setMaximum(max_value)
        spin.setSuffix(suffix)
        # Türk locale: binlik ayraç nokta, ondalık ayraç virgül
        turkish_locale = QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey)
        spin.setLocale(turkish_locale)
        return spin

    def _log_and_fix_finance_schema(self) -> None:
        try:
            conn = get_connection()
        except Exception as exc:  # pragma: no cover - defensive
            print("[FinanceDialog] Veritabanı bağlantısı alınamadı:", exc)
            return
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(finans)")
            info = cur.fetchall()
            print("[FinanceDialog] PRAGMA table_info(finans):", info)
            existing = {row[1] for row in info}
            altered = False
            if "sozlesme_ucreti" not in existing:
                print("[FinanceDialog] Eksik kolon sozlesme_ucreti eklenecek")
                cur.execute("ALTER TABLE finans ADD COLUMN sozlesme_ucreti REAL")
                altered = True
            if "sozlesme_yuzdesi" not in existing:
                print("[FinanceDialog] Eksik kolon sozlesme_yuzdesi eklenecek")
                cur.execute("ALTER TABLE finans ADD COLUMN sozlesme_yuzdesi REAL")
                altered = True
            if "yuzde_is_sonu" not in existing:
                print("[FinanceDialog] Eksik kolon yuzde_is_sonu eklenecek")
                cur.execute(
                    "ALTER TABLE finans ADD COLUMN yuzde_is_sonu INTEGER NOT NULL DEFAULT 0"
                )
                altered = True
            if altered:
                conn.commit()
        except Exception as exc:
            import traceback

            print("[FinanceDialog] Finans tablosu kolon kontrolü sırasında hata:", exc)
            print(traceback.format_exc())
        finally:
            conn.close()

    def _load_finans_data(self) -> bool:
        self._log_and_fix_finance_schema()
        try:
            if self.finans_id is not None:
                finans = get_finans_by_id(self.finans_id)
            elif self.dosya_id is not None:
                finans = get_finans_for_dosya(self.dosya_id)
            else:
                finans = {}
            if not finans:
                finans = self._empty_finans_dict()
            finans.setdefault("dosya_id", self.dosya_id)
            finans_id_value = finans.get("id") or finans.get("finans_id")
            if finans_id_value is not None:
                try:
                    self.finans_id = int(finans_id_value)
                except (TypeError, ValueError):
                    self.finans_id = None
            dosya_value = finans.get("dosya_id")
            if dosya_value not in (None, "", 0):
                try:
                    self.dosya_id = int(dosya_value)
                except (TypeError, ValueError):
                    self.dosya_id = dosya_value
            raw_fixed = finans.get("sozlesme_ucreti")
            finans["sozlesme_ucreti"] = self._to_float(raw_fixed)
            raw_percent = finans.get("sozlesme_yuzdesi")
            finans["sozlesme_yuzdesi"] = self._to_float(raw_percent)
            for key in (
                "tahsil_hedef_cents",
                "tahsil_edilen_cents",
                "masraf_toplam_cents",
                "masraf_tahsil_cents",
                "toplam_ucret_cents",
                "kalan_bakiye_cents",
            ):
                finans[key] = self._to_int(finans.get(key))
            finans["yuzde_is_sonu"] = int(bool(finans.get("yuzde_is_sonu")))
            self.finans = finans
            return True
        except Exception as exc:
            import traceback

            print("Finans düzenleme hata:", exc)
            print(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Hata",
                f"Finans verisi yüklenemedi:\n{exc}",
            )
            self.finans = self._empty_finans_dict()
            self.finans_id = None
            return False

    def __init__(
        self,
        parent=None,
        *,
        dosya_id: int | None = None,
        finans_id: int | None = None,
        dosya_info: dict | None = None,
        current_user: dict | None = None,
    ):
        super().__init__(parent)
        if dosya_id is None and finans_id is None:
            raise ValueError("Finans diyaloğu için kimlik belirtilmelidir.")
        self._restore_dialog_size()
        self.dosya_id = dosya_id
        self.finans_id = finans_id
        self.dosya_info = dosya_info or {}
        self.current_user = current_user or {}
        self.finans: dict[str, Any] = {}
        self.finans = self._empty_finans_dict()
        data_loaded = self._load_finans_data()
        self.setWindowTitle("Finansal Takip")
        self._loading_plan = False

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Kayıt sonrası durum mesajı için etiket
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self._build_contract_tab()
        self._build_plan_tab()
        self._build_payments_tab()
        self._build_expenses_tab()
        self._build_client_cash_tab()
        self._build_summary_tab()
        self._build_finance_timeline_tab()

        if not data_loaded:
            self.tab_widget.setEnabled(False)
            QTimer.singleShot(0, self.reject)
            return

        self.load_contract()
        self.load_plan()
        self.load_payments()
        self.load_expenses()
        self.load_client_cash()
        self.refresh_summary()
        self.load_finance_timeline()

    def show_status_message(self, text: str, timeout_ms: int = 2000) -> None:
        """Kısa süreli durum mesajını alt kısımda gösterir."""

        self.status_label.setText(text)
        QTimer.singleShot(timeout_ms, lambda: self.status_label.setText(""))

    def _restore_dialog_size(self) -> None:
        """Kaydedilmiş pencere boyutunu yükle."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        size = settings.value("FinanceDialog/size")
        if size:
            self.resize(size)
        else:
            self.resize(960, 640)

    def closeEvent(self, event) -> None:
        """Pencere boyutunu kaydet ve kapat."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        settings.setValue("FinanceDialog/size", self.size())
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Sözleşme/Anlaşma sekmesi
    # ------------------------------------------------------------------

    def _build_contract_tab(self) -> None:
        self.contract_tab = QWidget()
        layout = QVBoxLayout(self.contract_tab)

        form = QFormLayout()

        self.fixed_amount = self._create_amount_spinbox()
        form.addRow("Sabit Ücret", self.fixed_amount)

        self.percent_rate = self._create_amount_spinbox(max_value=100.0, suffix=" %")
        form.addRow("Yüzde Oranı", self.percent_rate)

        self.percent_target = self._create_amount_spinbox()
        form.addRow("Yüzde Baz Tutarı", self.percent_target)

        self.percent_deferred_checkbox = QCheckBox(
            "Yüzde meblağ iş sonunda alınacak (taksitlere yansıtılmaz)"
        )
        self.percent_deferred_checkbox.setObjectName("chkYuzdeIsSonu")
        form.addRow("", self.percent_deferred_checkbox)

        self.contract_total_label = QLabel("0,00 ₺")
        form.addRow("Hesaplanan Toplam Ücret", self.contract_total_label)

        # Karşı taraf vekalet ücreti - mahkeme lehimize sonuçlandığında karşı taraftan alınır
        self.karsi_vekalet_amount = self._create_amount_spinbox()
        self.karsi_vekalet_amount.setToolTip(
            "Mahkeme lehimize sonuçlandığında karşı taraftan hükmedilen vekalet ücreti.\n"
            "Bu tutar müvekkilin borcundan düşülmez, doğrudan büro geliridir."
        )
        form.addRow("Karşı Vekalet Ücreti", self.karsi_vekalet_amount)

        self.contract_notes = QTextEdit()
        form.addRow("Notlar", self.contract_notes)

        layout.addLayout(form)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.contract_save_button = QPushButton("Kaydet")
        button_layout.addWidget(self.contract_save_button)
        layout.addLayout(button_layout)

        self.contract_save_button.clicked.connect(self.save_contract)
        self.fixed_amount.valueChanged.connect(self._update_contract_total)
        self.percent_rate.valueChanged.connect(self._update_contract_total)
        self.percent_target.valueChanged.connect(self._update_contract_total)

        self.tab_widget.addTab(self.contract_tab, "Sözleşme/Anlaşma")

    def load_contract(self) -> None:
        self.fixed_amount.setValue(self._to_float(self.finans.get("sozlesme_ucreti")))
        self.percent_rate.setValue(self._to_float(self.finans.get("sozlesme_yuzdesi")))
        target_cents = self._to_int(self.finans.get("tahsil_hedef_cents"))
        self.percent_target.setValue(target_cents / 100)
        karsi_vekalet_cents = self._to_int(self.finans.get("karsi_vekalet_ucreti_cents"))
        self.karsi_vekalet_amount.setValue(karsi_vekalet_cents / 100)
        self.contract_notes.setPlainText(self.finans.get("notlar") or "")
        self.percent_deferred_checkbox.setChecked(
            bool(self.finans.get("yuzde_is_sonu"))
        )
        self._update_contract_total()

    def _update_contract_total(self) -> None:
        fixed = Decimal(str(self.fixed_amount.value()))
        hedef = Decimal(str(self.percent_target.value()))
        oran = Decimal(str(self.percent_rate.value()))
        toplam = fixed
        if oran and hedef:
            toplam += (hedef * oran) / Decimal("100")
        cents = int(
            (toplam * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        self.contract_total_label.setText(format_tl(cents))

    def save_contract(self) -> None:
        try:
            fixed_value = float(self.fixed_amount.value())
            percent_value = round(float(self.percent_rate.value()), 2)
            karsi_vekalet_cents = tl_to_cents(self.karsi_vekalet_amount.value())
            success = update_finans_contract(
                self.dosya_id,
                finans_id=self.finans_id,
                sozlesme_ucreti=fixed_value,
                sozlesme_yuzdesi=percent_value,
                tahsil_hedef_cents=tl_to_cents(self.percent_target.value()),
                notlar=self.contract_notes.toPlainText().strip() or None,
                yuzde_is_sonu=self.percent_deferred_checkbox.isChecked(),
                karsi_vekalet_ucreti_cents=karsi_vekalet_cents,
            )
            self.refresh_finance_data()
            if success:
                self.show_status_message("Finans bilgileri güncellendi.")
                add_finans_timeline_entry(self.dosya_id, "Sözleşme bilgileri güncellendi.", self._current_username)
            else:
                QMessageBox.warning(
                    self,
                    "Uyarı",
                    "Finans kaydı bulunamadı; herhangi bir değişiklik yapılmadı.",
                )
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            logger.exception("Finans sözleşmesi kaydedilemedi")
            QMessageBox.critical(self, "Hata", f"Bilgiler kaydedilemedi:\n{exc}")

    # ------------------------------------------------------------------
    # Ödeme Planı sekmesi
    # ------------------------------------------------------------------
    def _build_plan_tab(self) -> None:
        self.plan_tab = QWidget()
        layout = QVBoxLayout(self.plan_tab)

        form = QFormLayout()
        self.installment_count = QSpinBox()
        self.installment_count.setRange(0, 200)
        form.addRow("Taksit Sayısı", self.installment_count)

        self.installment_period = QComboBox()
        self.installment_period.addItems(["Ay", "Hafta"])
        form.addRow("Periyot", self.installment_period)

        self.installment_day = QSpinBox()
        self.installment_day.setRange(1, 28)
        form.addRow("Vade Günü", self.installment_day)

        self.installment_start = QDateEdit()
        self.installment_start.setCalendarPopup(True)
        self.installment_start.setDisplayFormat("dd.MM.yyyy")
        self.installment_start.setDate(QDate.currentDate())
        form.addRow("Başlangıç Tarihi", self.installment_start)

        self.plan_description = QLineEdit()
        form.addRow("Açıklama", self.plan_description)

        layout.addLayout(form)

        plan_buttons = QHBoxLayout()
        self.plan_generate_button = QPushButton("Plan Oluştur")
        plan_buttons.addWidget(self.plan_generate_button)

        self.plan_reset_button = QPushButton("Sıfırla")
        self.plan_reset_button.setStyleSheet("color: #c0392b;")
        reset_menu = QMenu(self)
        reset_menu.addAction("Tamamen Sıfırla", self._reset_plan_all)
        reset_menu.addAction("Ödenmemiş Taksitleri Sil", self._reset_plan_unpaid)
        self.plan_reset_button.setMenu(reset_menu)
        plan_buttons.addWidget(self.plan_reset_button)

        plan_buttons.addStretch()
        self.plan_save_button = QPushButton("Kaydet")
        plan_buttons.addWidget(self.plan_save_button)
        layout.addLayout(plan_buttons)

        self.plan_table = QTableWidget(0, 6)
        self.plan_table.setHorizontalHeaderLabels(
            [
                "Sıra",
                "Vade Tarihi",
                "Tutar",
                "Durum",
                "Ödeme Tarihi",
                "Açıklama",
            ]
        )
        self.plan_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.plan_table)

        self.plan_info_label = QLabel("")
        self.plan_info_label.setWordWrap(True)
        self.plan_info_label.setStyleSheet("color: #555555; font-style: italic;")
        self.plan_info_label.hide()
        layout.addWidget(self.plan_info_label)

        self.plan_generate_button.clicked.connect(self.generate_plan)
        self.plan_save_button.clicked.connect(self.save_plan)

        self._update_plan_hint()
        self.tab_widget.addTab(self.plan_tab, "Ödeme Planı")

    def load_plan(self) -> None:
        if not self.finans_id:
            self.installment_count.setValue(0)
            self.installment_period.setCurrentText("Ay")
            self.installment_day.setValue(max(1, self.installment_day.minimum()))
            self.installment_start.setDate(QDate.currentDate())
            self.plan_description.clear()
            self.populate_plan_table([])
            self._update_plan_hint()
            return
        plan, taksitler = get_payment_plan(self.finans_id)
        if plan:
            self.installment_count.setValue(int(plan.get("taksit_sayisi") or 0))
            self.installment_period.setCurrentText(plan.get("periyot") or "Ay")
            self.installment_day.setValue(int(plan.get("vade_gunu") or 7))
            if plan.get("baslangic_tarihi"):
                qdate = QDate.fromString(plan["baslangic_tarihi"], "yyyy-MM-dd")
                if qdate.isValid():
                    self.installment_start.setDate(qdate)
            self.plan_description.setText(plan.get("aciklama") or "")
        else:
            self.installment_count.setValue(0)
            self.plan_description.clear()
        self.populate_plan_table(taksitler)
        self._update_plan_hint()

    def populate_plan_table(self, taksitler: list[dict]) -> None:
        self._loading_plan = True
        try:
            self.plan_table.setRowCount(0)
            for item in taksitler:
                self.add_plan_row(item)
        finally:
            self._loading_plan = False

    def _update_plan_hint(self) -> None:
        if not hasattr(self, "plan_info_label"):
            return
        if bool(self.finans.get("yuzde_is_sonu")):
            self.plan_info_label.setText(
                "% meblağ iş sonu alınacak; taksitlere dahil edilmez."
            )
            self.plan_info_label.show()
        else:
            self.plan_info_label.clear()
            self.plan_info_label.hide()

    def _create_date_edit(
        self,
        value: str | None,
        allow_blank: bool = False,
        *,
        default_to_today: bool = False,
    ) -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        if allow_blank:
            edit.setSpecialValueText("—")
            edit.setMinimumDate(QDate(1900, 1, 1))
            if value:
                qdate = QDate.fromString(value, "yyyy-MM-dd")
                if qdate.isValid():
                    edit.setDate(qdate)
                    return edit
            if default_to_today:
                edit.setDate(QDate.currentDate())
            else:
                edit.setDate(edit.minimumDate())
        else:
            if value:
                qdate = QDate.fromString(value, "yyyy-MM-dd")
                if qdate.isValid():
                    edit.setDate(qdate)
                    return edit
            edit.setDate(QDate.currentDate())
        return edit

    def add_plan_row(self, item: dict | None = None) -> None:
        item = item or {}
        row = self.plan_table.rowCount()
        self.plan_table.insertRow(row)

        order_item = QTableWidgetItem(str(item.get("sira", row + 1) if item else row + 1))
        order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        order_item.setData(Qt.ItemDataRole.UserRole, item.get("id"))
        self.plan_table.setItem(row, 0, order_item)

        due_edit = self._create_date_edit(item.get("vade_tarihi"))
        self.plan_table.setCellWidget(row, 1, due_edit)

        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue(item.get("tutar_cents", 0) / 100)
        self.plan_table.setCellWidget(row, 2, amount_spin)

        status_combo = QComboBox()
        status_combo.addItems(INSTALLMENT_STATUS_OPTIONS)
        current_status = item.get("durum") or "Ödenecek"
        status_combo.setCurrentText(current_status)
        status_combo.setProperty("prev_status", current_status)
        status_combo.currentTextChanged.connect(
            lambda value, combo=status_combo: self.on_installment_status_changed(combo, value)
        )
        self.plan_table.setCellWidget(row, 3, status_combo)

        has_paid_date = bool(item and item.get("odeme_tarihi"))
        paid_edit = self._create_date_edit(
            item.get("odeme_tarihi"),
            allow_blank=True,
            default_to_today=not has_paid_date,
        )
        paid_edit.setProperty("installment_id", item.get("id"))
        self.plan_table.setCellWidget(row, 4, paid_edit)

        note = QTableWidgetItem(item.get("aciklama") or "")
        self.plan_table.setItem(row, 5, note)

    def generate_plan(self) -> None:
        if not self.finans_id:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Plan oluşturmak için geçerli bir finans kaydı bulunamadı.",
            )
            return
        taksit_sayisi = int(self.installment_count.value())
        if taksit_sayisi <= 0:
            QMessageBox.warning(self, "Uyarı", "Taksit sayısı 0 olamaz.")
            return
        start_qdate = self.installment_start.date()
        if not start_qdate.isValid():
            QMessageBox.warning(self, "Uyarı", "Başlangıç tarihi seçiniz.")
            return
        vade_gunu = int(self.installment_day.value())
        if not 1 <= vade_gunu <= 28:
            QMessageBox.warning(self, "Uyarı", "Vade günü 1 ile 28 arasında olmalıdır.")
            return
        start_date = start_qdate.toPyDate()
        taksitler = generate_installments(
            self.finans_id,
            taksit_sayisi,
            self.installment_period.currentText(),
            vade_gunu,
            start_date,
        )
        if not taksitler:
            QMessageBox.warning(self, "Uyarı", "Plan oluşturulamadı. Ücret bilgilerini kontrol edin.")
            return
        self.populate_plan_table(taksitler)

    def _collect_plan_rows(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.plan_table.rowCount()):
            order_item = self.plan_table.item(row, 0)
            due_edit = self.plan_table.cellWidget(row, 1)
            amount_spin = self.plan_table.cellWidget(row, 2)
            status_combo = self.plan_table.cellWidget(row, 3)
            paid_edit = self.plan_table.cellWidget(row, 4)
            note_item = self.plan_table.item(row, 5)
            if not isinstance(due_edit, QDateEdit) or not isinstance(amount_spin, QDoubleSpinBox):
                continue
            due_iso = due_edit.date().toString("yyyy-MM-dd")
            paid_iso = None
            if isinstance(paid_edit, QDateEdit):
                if paid_edit.date() != paid_edit.minimumDate():
                    paid_iso = paid_edit.date().toString("yyyy-MM-dd")
            installment_id = None
            if isinstance(order_item, QTableWidgetItem):
                data = order_item.data(Qt.ItemDataRole.UserRole)
                if data not in (None, ""):
                    try:
                        installment_id = int(data)
                    except (TypeError, ValueError):
                        installment_id = None
            rows.append(
                {
                    "id": installment_id,
                    "sira": row + 1,
                    "vade_tarihi": due_iso,
                    "tutar_cents": tl_to_cents(amount_spin.value()),
                    "durum": status_combo.currentText() if isinstance(status_combo, QComboBox) else "Ödenecek",
                    "odeme_tarihi": paid_iso,
                    "aciklama": note_item.text() if note_item else "",
                }
            )
        return rows

    def _persist_plan(self, *, sync_payments: bool, show_errors: bool = True) -> bool:
        if not self.finans_id:
            return False
        taksitler = self._collect_plan_rows()
        plan_data = {
            "taksit_sayisi": self.installment_count.value(),
            "periyot": self.installment_period.currentText(),
            "vade_gunu": self.installment_day.value(),
            "baslangic_tarihi": self.installment_start.date().toString("yyyy-MM-dd"),
            "aciklama": self.plan_description.text().strip() or None,
        }
        try:
            save_payment_plan(
                self.finans_id,
                plan_data,
                taksitler,
                sync_payments=sync_payments,
            )
            return True
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            if show_errors:
                QMessageBox.critical(self, "Hata", f"Plan kaydedilemedi:\n{exc}")
            return False

    def save_plan(self) -> None:
        if not self._persist_plan(sync_payments=True, show_errors=True):
            return
        self.show_status_message("Ödeme planı kaydedildi.")
        add_finans_timeline_entry(self.dosya_id, "Ödeme planı kaydedildi.", self._current_username)
        self.load_plan()
        self.load_payments()
        self._refresh_summary_labels()

    def _reset_plan_all(self) -> None:
        """Tüm ödeme planını sıfırla."""
        if not self.finans_id:
            QMessageBox.warning(self, "Uyarı", "Önce finans kaydı oluşturulmalıdır.")
            return

        reply = QMessageBox.question(
            self,
            "Onay",
            "Tüm ödeme planı silinecek. Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = reset_payment_plan(self.finans_id, keep_paid=False)
            self.show_status_message(f"{deleted} taksit silindi.")
            add_finans_timeline_entry(self.dosya_id, f"Ödeme planı tamamen sıfırlandı ({deleted} taksit).", self._current_username)
            self.load_plan()
            self.load_payments()
            self._refresh_summary_labels()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Plan sıfırlanamadı:\n{exc}")

    def _reset_plan_unpaid(self) -> None:
        """Sadece ödenmemiş taksitleri sil."""
        if not self.finans_id:
            QMessageBox.warning(self, "Uyarı", "Önce finans kaydı oluşturulmalıdır.")
            return

        reply = QMessageBox.question(
            self,
            "Onay",
            "Ödenmemiş taksitler silinecek. Ödenen taksitler korunacak. Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = reset_payment_plan(self.finans_id, keep_paid=True)
            self.show_status_message(f"{deleted} ödenmemiş taksit silindi.")
            add_finans_timeline_entry(self.dosya_id, f"Ödenmemiş taksitler silindi ({deleted} taksit).", self._current_username)
            self.load_plan()
            self.load_payments()
            self._refresh_summary_labels()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Taksitler silinemedi:\n{exc}")

    def on_installment_status_changed(self, combo: QComboBox, value: str) -> None:
        if self._loading_plan:
            return
        row = self.plan_table.indexAt(combo.pos()).row()
        if row < 0:
            for idx in range(self.plan_table.rowCount()):
                if self.plan_table.cellWidget(idx, 3) is combo:
                    row = idx
                    break
        if row < 0:
            return

        # Önceki durumu al
        prev_status = combo.property("prev_status")

        paid_edit = self.plan_table.cellWidget(row, 4)
        if isinstance(paid_edit, QDateEdit):
            if value == "Ödendi":
                if paid_edit.date() == paid_edit.minimumDate():
                    paid_edit.setDate(QDate.currentDate())
            else:
                paid_edit.setDate(paid_edit.minimumDate())

        # Durum "Ödendi" ise otomatik ödeme oluştur
        if value == "Ödendi":
            self._auto_create_payment_for_installment(row)
        # Durum "Ödendi"den başka bir şeye değiştiyse ödemeyi sil
        elif prev_status == "Ödendi" and value != "Ödendi":
            self._auto_delete_payment_for_installment(row)

        # Yeni durumu kaydet
        combo.setProperty("prev_status", value)

        if not self._persist_plan(sync_payments=True, show_errors=True):
            return
        self.load_plan()
        self.load_payments()
        self._refresh_summary_labels()

    def _auto_create_payment_for_installment(self, row_index: int) -> None:
        if row_index < 0 or not self.finans_id:
            return
        order_item = self.plan_table.item(row_index, 0)
        if not isinstance(order_item, QTableWidgetItem):
            return
        raw_id = order_item.data(Qt.ItemDataRole.UserRole)
        try:
            installment_id = int(raw_id)
        except (TypeError, ValueError):
            return
        due_edit = self.plan_table.cellWidget(row_index, 1)
        amount_spin = self.plan_table.cellWidget(row_index, 2)
        note_item = self.plan_table.item(row_index, 5)
        due_value = None
        if isinstance(due_edit, QDateEdit):
            qdate = due_edit.date()
            if qdate and qdate.isValid():
                due_value = qdate.toString("yyyy-MM-dd")
        amount_cents = 0
        if isinstance(amount_spin, QDoubleSpinBox):
            amount_cents = tl_to_cents(amount_spin.value())
        note_text = note_item.text().strip() if isinstance(note_item, QTableWidgetItem) else ""
        installment = {
            "id": installment_id,
            "vade_tarihi": due_value,
            "tutar_cents": amount_cents,
            "aciklama": note_text,
        }
        try:
            created = insert_payment_from_installment(
                None,
                self.finans_id,
                installment,
            )
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.warning(
                self,
                "Uyarı",
                f"Taksit ödemesi otomatik eklenemedi:\n{exc}",
            )
            return
        if not created:
            return
        self.load_payments()
        self._refresh_summary_labels()

    def _auto_delete_payment_for_installment(self, row_index: int) -> None:
        """Taksit durumu 'Ödendi'den değişince otomatik oluşturulan ödemeyi siler."""
        if row_index < 0 or not self.finans_id:
            return
        order_item = self.plan_table.item(row_index, 0)
        if not isinstance(order_item, QTableWidgetItem):
            return
        raw_id = order_item.data(Qt.ItemDataRole.UserRole)
        try:
            installment_id = int(raw_id)
        except (TypeError, ValueError):
            return
        try:
            deleted = delete_payment_by_installment(
                None,
                self.finans_id,
                installment_id,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Uyarı", f"Taksit ödemesi silinemedi:\n{exc}")
            return
        if deleted:
            self.load_payments()
            self._refresh_summary_labels()

    # ------------------------------------------------------------------
    # Ödemeler sekmesi
    # ------------------------------------------------------------------
    def _build_payments_tab(self) -> None:
        self.payments_tab = QWidget()
        layout = QVBoxLayout(self.payments_tab)

        button_layout = QHBoxLayout()
        self.payment_add_button = QPushButton("Ekle")
        self.payment_remove_button = QPushButton("Sil")
        self.payment_save_button = QPushButton("Kaydet")
        button_layout.addWidget(self.payment_add_button)
        button_layout.addWidget(self.payment_remove_button)
        button_layout.addStretch()
        button_layout.addWidget(self.payment_save_button)
        layout.addLayout(button_layout)

        self.payments_table = QTableWidget(0, 4)
        self.payments_table.setHorizontalHeaderLabels(["Tarih", "Tutar", "Yöntem", "Açıklama"])
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.payments_table)

        self.payment_add_button.clicked.connect(self.add_payment_row)
        self.payment_remove_button.clicked.connect(self.remove_payment_row)
        self.payment_save_button.clicked.connect(self.save_payments)

        self.tab_widget.addTab(self.payments_tab, "Ödemeler")

    def add_payment_row(self, record: dict | None = None) -> None:
        record = record or {}
        row = self.payments_table.rowCount()
        self.payments_table.insertRow(row)

        date_edit = self._create_date_edit(record.get("tarih"))
        date_edit.setProperty("payment_id", record.get("id"))
        date_edit.setProperty("taksit_id", record.get("taksit_id"))
        self.payments_table.setCellWidget(row, 0, date_edit)

        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue(record.get("tutar_cents", 0) / 100)
        self.payments_table.setCellWidget(row, 1, amount_spin)

        method_item = QTableWidgetItem(record.get("yontem") or "")
        self.payments_table.setItem(row, 2, method_item)

        desc_item = QTableWidgetItem(record.get("aciklama") or "")
        self.payments_table.setItem(row, 3, desc_item)

    def remove_payment_row(self) -> None:
        row = self.payments_table.currentRow()
        if row >= 0:
            # Kasadan veya Taksit ödemeler silinemez
            method_item = self.payments_table.item(row, 2)
            if method_item:
                yontem = method_item.text()
                if yontem in ("Kasadan", "Taksit"):
                    QMessageBox.warning(
                        self,
                        "Uyarı",
                        f"'{yontem}' yöntemiyle oluşturulan ödemeler buradan silinemez.\n"
                        f"Bu ödemeyi silmek için {'müvekkil kasasından' if yontem == 'Kasadan' else 'ödeme planından'} silin.",
                    )
                    return
            # Ödeme ID'sini al ve veritabanından sil
            date_edit = self.payments_table.cellWidget(row, 0)
            if isinstance(date_edit, QDateEdit):
                payment_id = date_edit.property("payment_id")
                if payment_id:
                    try:
                        delete_payment(int(payment_id))
                    except Exception as exc:
                        QMessageBox.warning(self, "Uyarı", f"Ödeme silinemedi:\n{exc}")
                        return
            self.payments_table.removeRow(row)
            # Finans toplamlarını güncelle
            self.refresh_finance_data()

    def load_payments(self) -> None:
        self.payments_table.setRowCount(0)
        if not self.finans_id:
            return
        for record in get_payments(self.finans_id):
            self.add_payment_row(record)

    def _collect_payments(self) -> list[dict]:
        records: list[dict] = []
        for row in range(self.payments_table.rowCount()):
            date_edit = self.payments_table.cellWidget(row, 0)
            amount_spin = self.payments_table.cellWidget(row, 1)
            method_item = self.payments_table.item(row, 2)
            desc_item = self.payments_table.item(row, 3)
            if not isinstance(date_edit, QDateEdit) or not isinstance(amount_spin, QDoubleSpinBox):
                continue
            records.append(
                {
                    "id": date_edit.property("payment_id"),
                    "tarih": date_edit.date().toString("yyyy-MM-dd"),
                    "tutar_cents": tl_to_cents(amount_spin.value()),
                    "yontem": method_item.text() if method_item else None,
                    "aciklama": desc_item.text() if desc_item else None,
                    "taksit_id": date_edit.property("taksit_id"),
                }
            )
        return records

    def save_payments(self) -> None:
        if not self.finans_id:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Ödemeleri kaydetmek için geçerli bir finans kaydı bulunamadı.",
            )
            return
        try:
            store_payment_records(self.finans_id, self._collect_payments())
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Ödemeler kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Ödeme kayıtları kaydedildi.")
        add_finans_timeline_entry(self.dosya_id, "Ödeme kayıtları güncellendi.", self._current_username)
        self.refresh_finance_data()
        self.load_payments()

    # ------------------------------------------------------------------
    # Masraflar sekmesi
    # ------------------------------------------------------------------
    def _build_expenses_tab(self) -> None:
        self.expenses_tab = QWidget()
        layout = QVBoxLayout(self.expenses_tab)

        # Müvekkil kasası bakiyesi bilgisi
        kasa_info_layout = QHBoxLayout()
        self.expense_kasa_bakiye_label = QLabel("Müvekkil Kasası Bakiyesi: 0,00 ₺")
        self.expense_kasa_bakiye_label.setStyleSheet("font-weight: bold; color: #0066cc; padding: 4px;")
        kasa_info_layout.addWidget(self.expense_kasa_bakiye_label)
        kasa_info_layout.addStretch()
        layout.addLayout(kasa_info_layout)

        button_layout = QHBoxLayout()
        self.expense_add_button = QPushButton("Ekle")
        self.expense_remove_button = QPushButton("Sil")
        self.expense_save_button = QPushButton("Kaydet")
        button_layout.addWidget(self.expense_add_button)
        button_layout.addWidget(self.expense_remove_button)
        button_layout.addStretch()
        button_layout.addWidget(self.expense_save_button)
        layout.addLayout(button_layout)

        self.expenses_table = QTableWidget(0, 7)
        self.expenses_table.setHorizontalHeaderLabels(
            ["Kalem", "Tutar", "Ödeme Kaynağı", "Tarih", "Tahsil Durumu", "Tahsil Tarihi", "Açıklama"]
        )
        self.expenses_table.horizontalHeader().setStretchLastSection(True)
        self.expenses_table.setColumnWidth(2, 100)  # Ödeme Kaynağı sütunu
        layout.addWidget(self.expenses_table)

        self.expense_add_button.clicked.connect(self.add_expense_row)
        self.expense_remove_button.clicked.connect(self.remove_expense_row)
        self.expense_save_button.clicked.connect(self.save_expenses)

        self.tab_widget.addTab(self.expenses_tab, "Masraflar")

    def add_expense_row(self, record: dict | None = None) -> None:
        record = record or {}
        row = self.expenses_table.rowCount()
        self.expenses_table.insertRow(row)

        # Sütun 0: Kalem (ID'yi UserRole olarak sakla)
        item_name = QTableWidgetItem(record.get("kalem") or "")
        if record.get("id"):
            item_name.setData(Qt.ItemDataRole.UserRole, record["id"])
        self.expenses_table.setItem(row, 0, item_name)

        # Sütun 1: Tutar
        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue(record.get("tutar_cents", 0) / 100)
        self.expenses_table.setCellWidget(row, 1, amount_spin)

        # Sütun 2: Ödeme Kaynağı
        source_combo = QComboBox()
        source_combo.addItems(PAYMENT_SOURCE_OPTIONS)
        source_text = record.get("odeme_kaynagi") or "Büro"
        source_combo.setCurrentText(source_text)
        self.expenses_table.setCellWidget(row, 2, source_combo)

        # Ödeme kaynağı değiştiğinde tahsil durumunu güncelle
        source_combo.currentTextChanged.connect(
            partial(self.on_expense_source_changed, row, source_combo)
        )

        # Sütun 3: Tarih
        has_existing_date = bool(record and record.get("tarih"))
        date_edit = self._create_date_edit(
            record.get("tarih"),
            allow_blank=True,
            default_to_today=not has_existing_date,
        )
        self.expenses_table.setCellWidget(row, 3, date_edit)

        # Sütun 4: Tahsil Durumu
        status_combo = QComboBox()
        status_combo.addItems(EXPENSE_STATUS_OPTIONS)
        # Kasadan ödendiyse tahsil durumu "-" olmalı
        if source_text == "Kasadan":
            status_combo.setEnabled(False)
            status_combo.setCurrentText("Bekliyor")
        else:
            status_text = record.get("tahsil_durumu") or "Bekliyor"
            status_combo.setCurrentText(status_text)
        self.expenses_table.setCellWidget(row, 4, status_combo)

        # Sütun 5: Tahsil Tarihi
        collected_edit = self._create_date_edit(
            record.get("tahsil_tarihi"),
            allow_blank=True,
            default_to_today=(record.get("tahsil_durumu") == "Tahsil Edildi" and not record.get("tahsil_tarihi")),
        )
        if source_text == "Kasadan":
            collected_edit.setEnabled(False)
        self.expenses_table.setCellWidget(row, 5, collected_edit)

        status_combo.currentTextChanged.connect(
            partial(self.on_expense_status_changed, status_combo, collected_edit)
        )

        # Sütun 6: Açıklama
        note_item = QTableWidgetItem(record.get("aciklama") or "")
        self.expenses_table.setItem(row, 6, note_item)

    def on_expense_source_changed(self, row: int, source_combo: QComboBox, value: str) -> None:
        """Ödeme kaynağı değiştiğinde tahsil durumu ve tarih alanlarını güncelle."""
        status_combo = self.expenses_table.cellWidget(row, 4)
        collected_edit = self.expenses_table.cellWidget(row, 5)

        if value == "Kasadan":
            # Kasadan ödendiyse tahsil durumu ve tarihi devre dışı
            if isinstance(status_combo, QComboBox):
                status_combo.setCurrentText("Bekliyor")
                status_combo.setEnabled(False)
            if isinstance(collected_edit, QDateEdit):
                collected_edit.setDate(collected_edit.minimumDate())
                collected_edit.setEnabled(False)
        else:
            # Büro ödediyse tahsil alanları aktif
            if isinstance(status_combo, QComboBox):
                status_combo.setEnabled(True)
            if isinstance(collected_edit, QDateEdit):
                collected_edit.setEnabled(True)

    def on_expense_status_changed(
        self, _combo: QComboBox, date_edit: QDateEdit, value: str
    ) -> None:
        if not isinstance(date_edit, QDateEdit):
            return
        if value == "Tahsil Edildi":
            if date_edit.date() == date_edit.minimumDate():
                date_edit.setDate(QDate.currentDate())
        else:
            date_edit.setDate(date_edit.minimumDate())

    def remove_expense_row(self) -> None:
        row = self.expenses_table.currentRow()
        if row >= 0:
            # Masraf ID'sini al ve veritabanından sil
            name_item = self.expenses_table.item(row, 0)
            if isinstance(name_item, QTableWidgetItem):
                expense_id = name_item.data(Qt.ItemDataRole.UserRole)
                if expense_id:
                    try:
                        # Kasadan masraf ise müvekkil kasasından da sil
                        source_combo = self.expenses_table.cellWidget(row, 2)
                        if isinstance(source_combo, QComboBox) and source_combo.currentText() == "Kasadan":
                            # Kasadan masrafı silmek için müvekkil kasasındaki ilgili kaydı da sil
                            date_edit = self.expenses_table.cellWidget(row, 3)
                            amount_spin = self.expenses_table.cellWidget(row, 1)
                            if isinstance(date_edit, QDateEdit) and isinstance(amount_spin, QDoubleSpinBox):
                                tarih = date_edit.date().toString("yyyy-MM-dd") if date_edit.date() != date_edit.minimumDate() else ""
                                tutar_kurus = tl_to_cents(amount_spin.value())
                                if self.dosya_id and tarih and tutar_kurus > 0:
                                    try:
                                        delete_expense_by_kasa_avans(None, self.finans_id, tarih, tutar_kurus)
                                    except Exception:
                                        pass
                        delete_expense(int(expense_id))
                    except Exception as exc:
                        QMessageBox.warning(self, "Uyarı", f"Masraf silinemedi:\n{exc}")
                        return
            self.expenses_table.removeRow(row)
            # Finans toplamlarını güncelle
            self.refresh_finance_data()

    def load_expenses(self) -> None:
        self.expenses_table.setRowCount(0)
        self._update_expense_kasa_bakiye()
        if not self.finans_id:
            return
        for record in get_expenses(self.finans_id):
            self.add_expense_row(record)

    def _update_expense_kasa_bakiye(self) -> None:
        """Masraflar sekmesindeki kasa bakiyesi etiketini günceller."""
        if not self.dosya_id:
            self.expense_kasa_bakiye_label.setText("Müvekkil Kasası Bakiyesi: 0,00 ₺")
            return

        kasa_giris = 0
        kasa_cikis = 0
        kasa_entries = get_muvekkil_kasasi_entries(self.dosya_id)
        for entry in kasa_entries:
            entry_dict = dict(entry) if hasattr(entry, "keys") else entry
            tutar = self._to_int(entry_dict.get("tutar_kurus") if isinstance(entry_dict, dict) else entry["tutar_kurus"])
            islem_turu = (entry_dict.get("islem_turu") if isinstance(entry_dict, dict) else entry["islem_turu"]) or ""
            if islem_turu in ("Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Alınan Masraf", "GELEN"):
                kasa_giris += tutar
            elif islem_turu in ("Kullanılan Avans", "Ödenen Masraf", "Müvekkile Ödeme", "MUVEKKILE_ODEME"):
                kasa_cikis += tutar

        kasa_bakiye = kasa_giris - kasa_cikis
        self.expense_kasa_bakiye_label.setText(f"Müvekkil Kasası Bakiyesi: {format_tl(kasa_bakiye)}")

    def _collect_expenses(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.expenses_table.rowCount()):
            name_item = self.expenses_table.item(row, 0)
            amount_spin = self.expenses_table.cellWidget(row, 1)
            source_combo = self.expenses_table.cellWidget(row, 2)
            date_edit = self.expenses_table.cellWidget(row, 3)
            status_combo = self.expenses_table.cellWidget(row, 4)
            collected_edit = self.expenses_table.cellWidget(row, 5)
            note_item = self.expenses_table.item(row, 6)
            if not isinstance(amount_spin, QDoubleSpinBox):
                continue
            tarih_iso = None
            if isinstance(date_edit, QDateEdit) and date_edit.date() != date_edit.minimumDate():
                tarih_iso = date_edit.date().toString("yyyy-MM-dd")
            tahsil_iso = None
            if isinstance(collected_edit, QDateEdit) and collected_edit.date() != collected_edit.minimumDate():
                tahsil_iso = collected_edit.date().toString("yyyy-MM-dd")
            odeme_kaynagi = source_combo.currentText() if isinstance(source_combo, QComboBox) else "Büro"
            rows.append(
                {
                    "kalem": name_item.text() if name_item else "",
                    "tutar_cents": tl_to_cents(amount_spin.value()),
                    "odeme_kaynagi": odeme_kaynagi,
                    "tarih": tarih_iso,
                    "tahsil_durumu": status_combo.currentText() if isinstance(status_combo, QComboBox) else "Bekliyor",
                    "tahsil_tarihi": tahsil_iso,
                    "aciklama": note_item.text() if note_item else "",
                }
            )
        return rows

    def save_expenses(self) -> None:
        if not self.finans_id:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Masrafları kaydetmek için geçerli bir finans kaydı bulunamadı.",
            )
            return
        try:
            store_expense_records(self.finans_id, self._collect_expenses())
        except Exception as exc:  # pragma: no cover - GUI güvenliği
            QMessageBox.critical(self, "Hata", f"Masraflar kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Masraf kayıtları kaydedildi.")
        add_finans_timeline_entry(self.dosya_id, "Masraf kayıtları güncellendi.", self._current_username)
        self.refresh_finance_data()
        self.load_expenses()
        self.load_client_cash()  # Kasadan masraflar müvekkil kasasına ekleniyor

    # ------------------------------------------------------------------
    # Müvekkil Kasası sekmesi
    # ------------------------------------------------------------------
    def _build_client_cash_tab(self) -> None:
        self.client_cash_tab = QWidget()
        layout = QVBoxLayout(self.client_cash_tab)

        summary_layout = QHBoxLayout()
        self.client_cash_in_label = QLabel("Toplam Gelen: 0,00 ₺")
        self.client_cash_out_label = QLabel("Müvekkile Ödenen: 0,00 ₺")
        self.client_cash_balance_label = QLabel("Kalan (Müvekkil Alacağı): 0,00 ₺")
        summary_layout.addWidget(self.client_cash_in_label)
        summary_layout.addWidget(self.client_cash_out_label)
        summary_layout.addWidget(self.client_cash_balance_label)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        button_layout = QHBoxLayout()
        self.client_cash_add_button = QPushButton("Ekle")
        self.client_cash_remove_button = QPushButton("Sil")
        self.client_cash_save_button = QPushButton("Kaydet")
        button_layout.addWidget(self.client_cash_add_button)
        button_layout.addWidget(self.client_cash_remove_button)
        button_layout.addStretch()
        button_layout.addWidget(self.client_cash_save_button)
        layout.addLayout(button_layout)

        self.client_cash_table = QTableWidget(0, 5)
        self.client_cash_table.setHorizontalHeaderLabels(
            ["Sıra", "Tarih", "Tutar", "İşlem Türü", "Açıklama"]
        )
        self.client_cash_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.client_cash_table)

        self.client_cash_add_button.clicked.connect(self.add_client_cash_row)
        self.client_cash_remove_button.clicked.connect(self.remove_client_cash_row)
        self.client_cash_save_button.clicked.connect(self.save_client_cash)

        # Sütun genişliklerini yükle
        self._client_cash_col_save_timer = QTimer(self)
        self._client_cash_col_save_timer.setSingleShot(True)
        self._client_cash_col_save_timer.timeout.connect(self._save_client_cash_column_widths)
        self._load_client_cash_column_widths()
        self.client_cash_table.horizontalHeader().sectionResized.connect(self._on_client_cash_column_resized)

        self.tab_widget.addTab(self.client_cash_tab, "Müvekkil Kasası")

    def _load_client_cash_column_widths(self) -> None:
        """Müvekkil kasası sütun genişliklerini QSettings'den yükle."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        widths = settings.value("FinansDialog/client_cash_widths", None)
        if widths:
            header = self.client_cash_table.horizontalHeader()
            for i, w in enumerate(widths):
                if i < header.count() - 1:  # Son sütun stretch olduğu için atla
                    try:
                        header.resizeSection(i, int(w))
                    except (ValueError, TypeError):
                        pass

    def _save_client_cash_column_widths(self) -> None:
        """Müvekkil kasası sütun genişliklerini QSettings'e kaydet."""
        header = self.client_cash_table.horizontalHeader()
        widths = [header.sectionSize(i) for i in range(header.count() - 1)]  # Son sütun stretch
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        settings.setValue("FinansDialog/client_cash_widths", widths)

    def _on_client_cash_column_resized(self, index: int, old_size: int, new_size: int) -> None:
        """Sütun genişliği değiştiğinde debounced kaydet."""
        self._client_cash_col_save_timer.start(500)

    def add_client_cash_row(self, record: dict | None = None) -> None:
        record = record or {}
        row = self.client_cash_table.rowCount()
        self.client_cash_table.insertRow(row)

        order_item = QTableWidgetItem(str(row + 1))
        order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        order_item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
        self.client_cash_table.setItem(row, 0, order_item)

        date_edit = self._create_date_edit(record.get("tarih"), allow_blank=False, default_to_today=True)
        self.client_cash_table.setCellWidget(row, 1, date_edit)

        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue((record.get("tutar_kurus") or 0) / 100)
        self.client_cash_table.setCellWidget(row, 2, amount_spin)

        type_combo = QComboBox()
        # Giriş: Dosya Geliri, Avans Masrafı, Masraf Geliri
        # Çıkış: Ödenen Masraf, Müvekkile Ödeme, Sözleşme Ödemesi
        # Not: Kullanılan Avans otomatik oluşturulur (masraflardan), kullanıcı seçemez
        type_combo.addItems(["Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Ödenen Masraf", "Müvekkile Ödeme", "Sözleşme Ödemesi"])
        # Eski değerleri yeni değerlere eşle
        old_to_new = {"GELEN": "Dosya Geliri", "MUVEKKILE_ODEME": "Müvekkile Ödeme", "Alınan Masraf": "Avans Masrafı"}
        old_value = record.get("islem_turu") or "Dosya Geliri"
        mapped_value = old_to_new.get(old_value, old_value)
        # Kullanılan Avans varsa (eski kayıt) göster ama düzenlenemez yap
        if mapped_value == "Kullanılan Avans":
            type_combo.addItem("Kullanılan Avans")
            type_combo.setCurrentText("Kullanılan Avans")
            type_combo.setEnabled(False)  # Otomatik oluşturulan kayıt değiştirilemez
        else:
            type_combo.setCurrentText(mapped_value)
        self.client_cash_table.setCellWidget(row, 3, type_combo)

        desc_item = QTableWidgetItem(record.get("aciklama") or "")
        self.client_cash_table.setItem(row, 4, desc_item)

    def remove_client_cash_row(self) -> None:
        row = self.client_cash_table.currentRow()
        if row >= 0:
            # Satır verilerini al
            order_item = self.client_cash_table.item(row, 0)
            date_edit = self.client_cash_table.cellWidget(row, 1)
            amount_spin = self.client_cash_table.cellWidget(row, 2)
            type_combo = self.client_cash_table.cellWidget(row, 3)

            entry_id = None
            tarih = ""
            tutar_kurus = 0
            islem_turu = ""

            if isinstance(order_item, QTableWidgetItem):
                entry_id = order_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(date_edit, QDateEdit):
                tarih = date_edit.date().toString("yyyy-MM-dd")
            if isinstance(amount_spin, QDoubleSpinBox):
                tutar_kurus = tl_to_cents(amount_spin.value())
            if isinstance(type_combo, QComboBox):
                islem_turu = type_combo.currentText()

            # Veritabanından sil
            if entry_id:
                try:
                    delete_muvekkil_kasasi_entry(int(entry_id))
                except Exception as exc:
                    QMessageBox.warning(self, "Uyarı", f"Kayıt silinemedi:\n{exc}")
                    return

                # Otomatik oluşturulan kayıtları da sil
                if self.finans_id and tarih and tutar_kurus > 0:
                    if islem_turu == "Sözleşme Ödemesi":
                        try:
                            delete_payment_from_kasadan(None, self.finans_id, tarih, tutar_kurus)
                        except Exception:
                            pass  # Ödeme kaydı silinmese de devam et
                    elif islem_turu == "Kullanılan Avans":
                        try:
                            delete_expense_by_kasa_avans(None, self.finans_id, tarih, tutar_kurus)
                        except Exception:
                            pass  # Masraf kaydı güncellenemese de devam et

            self.client_cash_table.removeRow(row)
            self._update_client_cash_ordering()
            self.refresh_client_cash_summary()
            # Diğer sekmeleri de yenile
            self.load_payments()
            self.load_expenses()
            # Finans toplamlarını yeniden hesapla ve güncelle
            self.refresh_finance_data()

    def _update_client_cash_ordering(self) -> None:
        for idx in range(self.client_cash_table.rowCount()):
            order_item = self.client_cash_table.item(idx, 0)
            if isinstance(order_item, QTableWidgetItem):
                order_item.setText(str(idx + 1))

    def load_client_cash(self) -> None:
        if not self.dosya_id:
            self.client_cash_table.setRowCount(0)
            return
        try:
            entries = get_muvekkil_kasasi_entries(self.dosya_id)
        except Exception:
            entries = []
        self.client_cash_table.setRowCount(0)
        for entry in entries:
            self.add_client_cash_row(dict(entry))
        self.refresh_client_cash_summary()

    def _collect_client_cash_rows(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.client_cash_table.rowCount()):
            order_item = self.client_cash_table.item(row, 0)
            date_edit = self.client_cash_table.cellWidget(row, 1)
            amount_spin = self.client_cash_table.cellWidget(row, 2)
            type_combo = self.client_cash_table.cellWidget(row, 3)
            desc_item = self.client_cash_table.item(row, 4)
            if not isinstance(date_edit, QDateEdit) or not isinstance(amount_spin, QDoubleSpinBox):
                continue
            rows.append(
                {
                    "id": order_item.data(Qt.ItemDataRole.UserRole) if isinstance(order_item, QTableWidgetItem) else None,
                    "tarih": date_edit.date().toString("yyyy-MM-dd"),
                    "tutar_kurus": tl_to_cents(amount_spin.value()),
                    "islem_turu": type_combo.currentText() if isinstance(type_combo, QComboBox) else "GELEN",
                    "aciklama": desc_item.text() if isinstance(desc_item, QTableWidgetItem) else None,
                }
            )
        return rows

    def save_client_cash(self) -> None:
        """Müvekkil kasası kayıtlarını kaydeder ve tabloyu yeniler."""
        if not self.dosya_id:
            return
        try:
            rows = self._collect_client_cash_rows()
            if not rows:
                self.show_status_message("Kaydedilecek kayıt yok.")
                return

            saved_count = 0
            for idx, row in enumerate(rows):
                entry_id = row.get("id")
                islem_turu = row["islem_turu"]
                if entry_id:
                    update_muvekkil_kasasi_entry(
                        int(entry_id),
                        row["tarih"],
                        row["tutar_kurus"],
                        islem_turu,
                        row.get("aciklama"),
                    )
                    saved_count += 1
                else:
                    new_id = insert_muvekkil_kasasi_entry(
                        self.dosya_id,
                        row["tarih"],
                        row["tutar_kurus"],
                        islem_turu,
                        row.get("aciklama"),
                    )
                    order_item = self.client_cash_table.item(idx, 0)
                    if isinstance(order_item, QTableWidgetItem):
                        order_item.setData(Qt.ItemDataRole.UserRole, new_id)
                    add_finans_timeline_entry(
                        self.dosya_id,
                        f"Müvekkil kasası: {format_tl(row['tutar_kurus'])} {islem_turu} kaydı eklendi.",
                        self._current_username,
                    )
                    saved_count += 1
                    # Sözleşme Ödemesi ise ödemeler sekmesine de ekle
                    if islem_turu == "Sözleşme Ödemesi" and self.finans_id:
                        try:
                            insert_payment_from_kasadan(
                                None,
                                self.finans_id,
                                row["tarih"],
                                row["tutar_kurus"],
                                row.get("aciklama") or "Kasadan sözleşme ödemesi",
                            )
                        except Exception:
                            pass  # Ödeme ekleme başarısız olsa da kasa kaydı yapıldı

            # Tüm verileri yenile
            self.load_client_cash()
            self.load_payments()
            self.refresh_finance_data()
            self.show_status_message(f"Müvekkil kasası kaydedildi ({saved_count} kayıt).")
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Müvekkil kasası kaydedilemedi:\n{exc}")

    def refresh_client_cash_summary(self) -> None:
        rows = self._collect_client_cash_rows()
        # Giriş: Dosya Geliri, Avans Masrafı, Masraf Geliri (ve eski GELEN, Alınan Masraf)
        giris_turleri = {"Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Alınan Masraf", "GELEN"}
        # Çıkış: Kullanılan Avans, Ödenen Masraf, Müvekkile Ödeme, Sözleşme Ödemesi (ve eski MUVEKKILE_ODEME)
        cikis_turleri = {"Kullanılan Avans", "Ödenen Masraf", "Müvekkile Ödeme", "Sözleşme Ödemesi", "MUVEKKILE_ODEME"}
        gelen = sum(r.get("tutar_kurus", 0) for r in rows if r.get("islem_turu") in giris_turleri)
        giden = sum(r.get("tutar_kurus", 0) for r in rows if r.get("islem_turu") in cikis_turleri)
        kalan = gelen - giden
        self.client_cash_in_label.setText(f"Toplam Giriş: {format_tl(gelen)}")
        self.client_cash_out_label.setText(f"Toplam Çıkış: {format_tl(giden)}")
        self.client_cash_balance_label.setText(f"Kalan Bakiye: {format_tl(kalan)}")

    # ------------------------------------------------------------------
    # Özet sekmesi
    # ------------------------------------------------------------------
    def _build_summary_tab(self) -> None:
        self.summary_tab = QWidget()
        layout = QVBoxLayout(self.summary_tab)
        layout.setSpacing(12)

        # 1. ÜCRET BÖLÜMÜ
        ucret_group = QGroupBox("ÜCRET")
        ucret_form = QFormLayout(ucret_group)
        self.summary_total = QLabel("0,00 ₺")
        self.summary_collected = QLabel("0,00 ₺")
        self.summary_ucret_kalan = QLabel("0,00 ₺")
        ucret_form.addRow("Sözleşme Ücreti:", self.summary_total)
        ucret_form.addRow("Tahsil Edilen:", self.summary_collected)
        ucret_form.addRow("Kalan Ücret Alacağı:", self.summary_ucret_kalan)
        layout.addWidget(ucret_group)

        # 2. MASRAFLAR BÖLÜMÜ
        masraf_group = QGroupBox("MASRAFLAR")
        masraf_form = QFormLayout(masraf_group)
        self.summary_masraf_toplam = QLabel("0,00 ₺")
        self.summary_masraf_kasadan = QLabel("0,00 ₺")
        self.summary_masraf_cepten = QLabel("0,00 ₺")
        self.summary_masraf_tahsil = QLabel("0,00 ₺")
        self.summary_masraf_alacak = QLabel("0,00 ₺")
        masraf_form.addRow("Toplam Masraf:", self.summary_masraf_toplam)
        masraf_form.addRow("Kasadan Ödenen:", self.summary_masraf_kasadan)
        masraf_form.addRow("Büro Ödedi:", self.summary_masraf_cepten)
        masraf_form.addRow("Müvekkilden Tahsil:", self.summary_masraf_tahsil)
        masraf_form.addRow("Büro Alacağı:", self.summary_masraf_alacak)
        layout.addWidget(masraf_group)

        # 3. KASA DURUMU BÖLÜMÜ
        kasa_group = QGroupBox("MÜVEKKİL KASASI")
        kasa_form = QFormLayout(kasa_group)
        self.summary_kasa_giris = QLabel("0,00 ₺")
        self.summary_kasa_kullanilan_avans = QLabel("0,00 ₺")
        self.summary_kasa_cikis = QLabel("0,00 ₺")
        self.summary_kasa_bakiye = QLabel("0,00 ₺")
        kasa_form.addRow("Toplam Giriş (Avans):", self.summary_kasa_giris)
        kasa_form.addRow("Kullanılan Avans:", self.summary_kasa_kullanilan_avans)
        kasa_form.addRow("Diğer Çıkışlar:", self.summary_kasa_cikis)
        kasa_form.addRow("Kasa Bakiyesi:", self.summary_kasa_bakiye)
        layout.addWidget(kasa_group)

        # 4. NET DURUM BÖLÜMÜ
        net_group = QGroupBox("NET DURUM")
        net_form = QFormLayout(net_group)
        self.summary_muvekkilden_alinacak = QLabel("0,00 ₺")
        self.summary_muvekkile_verilecek = QLabel("0,00 ₺")
        self.summary_net_alacak = QLabel("0,00 ₺")
        self.summary_net_alacak.setStyleSheet("font-weight: bold; font-size: 14px;")
        net_form.addRow("Müvekkilden Alınacak:", self.summary_muvekkilden_alinacak)
        net_form.addRow("Müvekkile Verilecek:", self.summary_muvekkile_verilecek)
        net_form.addRow("NET ALACAK:", self.summary_net_alacak)
        layout.addWidget(net_group)

        layout.addStretch()
        self.tab_widget.addTab(self.summary_tab, "Özet")

    def refresh_finance_data(self) -> None:
        if not self._load_finans_data():
            return
        if self.finans_id:
            try:
                recalculate_finans_totals(self.finans_id)
            except Exception as exc:  # pragma: no cover - GUI güvenliği
                QMessageBox.critical(
                    self,
                    "Hata",
                    f"Finans verisi güncellenemedi:\n{exc}",
                )
                return
            if not self._load_finans_data():
                return
        self.load_contract()
        self._update_plan_hint()
        self.refresh_summary()

    def refresh_summary(self) -> None:
        # 1. ÜCRET HESAPLAMALARI
        total = self._to_int(self.finans.get("toplam_ucret_cents"))
        tahsil = self._to_int(self.finans.get("tahsil_edilen_cents"))
        ucret_kalan = total - tahsil

        self.summary_total.setText(format_tl(total))
        self.summary_collected.setText(format_tl(tahsil))
        self.summary_ucret_kalan.setText(format_tl(ucret_kalan))

        # 2. MASRAF HESAPLAMALARI
        masraf_toplam = 0
        masraf_kasadan = 0
        masraf_cepten = 0
        masraf_tahsil = 0

        if self.finans_id:
            expenses = get_expenses(self.finans_id)
            for exp in expenses:
                tutar = self._to_int(exp.get("tutar_cents"))
                masraf_toplam += tutar
                odeme_kaynagi = exp.get("odeme_kaynagi") or "Büro"
                if odeme_kaynagi == "Kasadan":
                    masraf_kasadan += tutar
                else:
                    masraf_cepten += tutar
                    # Sadece cepten ödenenlerin tahsil durumunu takip et
                    if exp.get("tahsil_durumu") == "Tahsil Edildi":
                        masraf_tahsil += tutar

        masraf_alacak = masraf_cepten - masraf_tahsil  # Büro ödedi ama müvekkilden tahsil edilmemiş

        self.summary_masraf_toplam.setText(format_tl(masraf_toplam))
        self.summary_masraf_kasadan.setText(format_tl(masraf_kasadan))
        self.summary_masraf_cepten.setText(format_tl(masraf_cepten))
        self.summary_masraf_tahsil.setText(format_tl(masraf_tahsil))
        self.summary_masraf_alacak.setText(format_tl(masraf_alacak))

        # 3. KASA HESAPLAMALARI
        kasa_giris = 0
        kasa_kullanilan_avans = 0
        kasa_diger_cikis = 0

        if self.dosya_id:
            kasa_entries = get_muvekkil_kasasi_entries(self.dosya_id)
            for entry in kasa_entries:
                # sqlite3.Row -> dict dönüşümü
                entry_dict = dict(entry) if hasattr(entry, "keys") else entry
                tutar = self._to_int(entry_dict.get("tutar_kurus") if isinstance(entry_dict, dict) else entry["tutar_kurus"])
                islem_turu = (entry_dict.get("islem_turu") if isinstance(entry_dict, dict) else entry["islem_turu"]) or ""
                if islem_turu in ("Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Alınan Masraf", "GELEN"):
                    kasa_giris += tutar
                elif islem_turu == "Kullanılan Avans":
                    kasa_kullanilan_avans += tutar
                elif islem_turu in ("Ödenen Masraf", "Müvekkile Ödeme", "Sözleşme Ödemesi", "MUVEKKILE_ODEME"):
                    kasa_diger_cikis += tutar

        kasa_toplam_cikis = kasa_kullanilan_avans + kasa_diger_cikis
        kasa_bakiye = kasa_giris - kasa_toplam_cikis

        self.summary_kasa_giris.setText(format_tl(kasa_giris))
        self.summary_kasa_kullanilan_avans.setText(format_tl(kasa_kullanilan_avans))
        self.summary_kasa_cikis.setText(format_tl(kasa_diger_cikis))
        self.summary_kasa_bakiye.setText(format_tl(kasa_bakiye))

        # 4. NET DURUM HESAPLAMALARI
        # Müvekkilden alınacak = Kalan ücret alacağı + Büro masraf alacağı
        # (Yüzde tutarı zaten toplam ücrete dahil, ucret_kalan içinde)
        muvekkilden_alinacak = ucret_kalan + masraf_alacak
        # Müvekkile verilecek = Kasa bakiyesi (müvekkilin parası kasada)
        muvekkile_verilecek = kasa_bakiye if kasa_bakiye > 0 else 0
        # Net alacak = Alınacak - Verilecek
        net_alacak = muvekkilden_alinacak - muvekkile_verilecek

        self.summary_muvekkilden_alinacak.setText(format_tl(muvekkilden_alinacak))
        self.summary_muvekkile_verilecek.setText(format_tl(muvekkile_verilecek))

        # Net alacak rengini ayarla
        if net_alacak > 0:
            self.summary_net_alacak.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")
            self.summary_net_alacak.setText(f"+{format_tl(net_alacak)}")
        elif net_alacak < 0:
            self.summary_net_alacak.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")
            self.summary_net_alacak.setText(format_tl(net_alacak))
        else:
            self.summary_net_alacak.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.summary_net_alacak.setText(format_tl(0))

    def _refresh_summary_labels(self) -> None:
        if not self._load_finans_data():
            return
        self.refresh_summary()

    # ------------------------------------------------------------------
    # Zaman Çizgisi sekmesi (finans)
    # ------------------------------------------------------------------
    def _build_finance_timeline_tab(self) -> None:
        self.finance_timeline_tab = QWidget()
        layout = QVBoxLayout(self.finance_timeline_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.finance_timeline_list = QListWidget()
        self.finance_timeline_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.finance_timeline_list, 1)

        # Yeni not ekleme formu
        form_group = QGroupBox("Yeni Not Ekle")
        form_layout = QFormLayout(form_group)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(6)

        self.finance_timeline_input = QLineEdit()
        self.finance_timeline_input.setPlaceholderText("Not ekle...")
        form_layout.addRow("Not", self.finance_timeline_input)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.finance_timeline_add_btn = QPushButton("Ekle")
        self.finance_timeline_add_btn.clicked.connect(self._on_finance_timeline_add)
        button_row.addWidget(self.finance_timeline_add_btn)
        form_layout.addRow(button_row)

        layout.addWidget(form_group)
        self.tab_widget.addTab(self.finance_timeline_tab, "Zaman Çizgisi")

    def _on_finance_timeline_add(self) -> None:
        """Finans zaman çizgisine manuel not ekle."""
        note_text = self.finance_timeline_input.text().strip()
        if not note_text:
            QMessageBox.warning(self, "Uyarı", "Not alanı boş bırakılamaz.")
            return
        if not self.dosya_id:
            return
        try:
            add_finans_timeline_entry(self.dosya_id, note_text, self._current_username)
            self.finance_timeline_input.clear()
            self.load_finance_timeline()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Not eklenemedi:\n{exc}")

    def _format_finance_timeline_row(self, row: sqlite3.Row | dict) -> str:
        timestamp = (row.get("timestamp") if hasattr(row, "get") else row["timestamp"]).replace("T", " ")
        message = row.get("message") if hasattr(row, "get") else row["message"]
        user = row.get("user") if hasattr(row, "get") else row.get("user", "") if isinstance(row, dict) else row["user"]
        user_suffix = f" - {user}" if user else ""
        return f"[{timestamp}] {message}{user_suffix}"

    def load_finance_timeline(self) -> None:
        self.finance_timeline_list.clear()
        if not self.dosya_id:
            return
        try:
            rows = get_finans_timeline(self.dosya_id)
        except Exception:
            rows = []
        for entry in rows:
            self.finance_timeline_list.addItem(self._format_finance_timeline_row(entry))
