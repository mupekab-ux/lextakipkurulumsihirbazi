# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from functools import partial
import sqlite3
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

try:  # pragma: no cover - runtime import guard
    from app.models import (
        harici_generate_installments,
        harici_get_contract,
        harici_get_expenses,
        harici_get_payment_plan,
        harici_get_payments,
        harici_insert_payment_from_installment,
        harici_delete_payment_by_installment,
        harici_insert_payment_from_kasadan,
        harici_delete_payment_from_kasadan,
        harici_delete_payment,
        harici_delete_expense,
        harici_delete_expense_by_kasa_avans,
        harici_recalculate_totals,
        harici_reset_payment_plan,
        harici_save_expenses,
        harici_save_payment_plan,
        harici_save_payments,
        harici_update_contract,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (  # type: ignore
        harici_generate_installments,
        harici_get_contract,
        harici_get_expenses,
        harici_get_payment_plan,
        harici_get_payments,
        harici_insert_payment_from_installment,
        harici_delete_payment_by_installment,
        harici_insert_payment_from_kasadan,
        harici_delete_payment_from_kasadan,
        harici_delete_payment,
        harici_delete_expense,
        harici_delete_expense_by_kasa_avans,
        harici_recalculate_totals,
        harici_reset_payment_plan,
        harici_save_expenses,
        harici_save_payment_plan,
        harici_save_payments,
        harici_update_contract,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import format_tl, tl_to_cents
except ModuleNotFoundError:  # pragma: no cover
    from utils import format_tl, tl_to_cents  # type: ignore

try:  # pragma: no cover - runtime import guard
    from app.db import (
        add_harici_finans_timeline_entry,
        get_harici_finans_timeline,
        get_harici_muvekkil_kasasi_entries,
        insert_harici_muvekkil_kasasi_entry,
        update_harici_muvekkil_kasasi_entry,
        delete_harici_muvekkil_kasasi_entry,
    )
except ModuleNotFoundError:  # pragma: no cover
    from db import (
        add_harici_finans_timeline_entry,
        get_harici_finans_timeline,
        get_harici_muvekkil_kasasi_entries,
        insert_harici_muvekkil_kasasi_entry,
        update_harici_muvekkil_kasasi_entry,
        delete_harici_muvekkil_kasasi_entry,
    )

INSTALLMENT_STATUS_OPTIONS = ["Ödenecek", "Ödendi", "Gecikmiş"]
EXPENSE_STATUS_OPTIONS = ["Bekliyor", "Tahsil Edildi"]
PAYMENT_SOURCE_OPTIONS = ["Kasadan", "Büro"]


class FinansHariciDialog(QDialog):
    """Harici finans kayıtlarını FinanceDialog ile aynı UX'te yönetir."""

    @property
    def _current_username(self) -> str | None:
        """Mevcut kullanıcının kullanıcı adını döndür."""
        return self.current_user.get("username") if hasattr(self, "current_user") else None

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

    def __init__(
        self,
        parent=None,
        *,
        conn=None,
        harici_id: int | None = None,
        current_user: dict | None = None,
    ) -> None:
        super().__init__(parent)
        if conn is None or harici_id is None:
            raise ValueError("Harici finans kaydı için bağlantı ve kimlik gereklidir.")
        self.conn = conn
        self.harici_id = harici_id
        self.current_user = current_user or {}
        self.setWindowTitle("Harici Finans")
        self.resize(960, 640)

        self.finans: dict[str, Any] = {}
        self._plan_table_updating = False
        data_loaded = self._load_finans_data()

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Kayıt sonrası bildirim için küçük durum etiketi
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
        """Başarılı işlemler için kısa mesaj gösterir."""

        self.status_label.setText(text)
        QTimer.singleShot(timeout_ms, lambda: self.status_label.setText(""))

    # ------------------------------------------------------------------
    # Veri yükleme / yenileme
    # ------------------------------------------------------------------
    def _load_finans_data(self) -> bool:
        try:
            finans = harici_get_contract(self.conn, self.harici_id)
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Finans verisi yüklenemedi:\n{exc}")
            return False
        if not finans:
            finans = {}
        defaults = {
            "harici_bn": "",
            "harici_muvekkil": "",
            "harici_esas_no": "",
            "sabit_ucret_cents": 0,
            "yuzde_orani": 0.0,
            "tahsil_hedef_cents": 0,
            "yuzde_is_sonu": 0,
            "notlar": "",
            "toplam_ucret_cents": 0,
            "tahsil_edilen_cents": 0,
            "masraf_toplam_cents": 0,
            "masraf_tahsil_cents": 0,
            "kalan_bakiye_cents": 0,
        }
        for key, value in defaults.items():
            finans.setdefault(key, value)
        self.finans = finans
        return True

    def refresh_finance_data(self) -> None:
        if not self._load_finans_data():
            return
        try:
            harici_recalculate_totals(self.conn, self.harici_id)
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Finans verisi güncellenemedi:\n{exc}")
            return
        if not self._load_finans_data():
            return
        self.load_contract()
        self.refresh_summary()

    # ------------------------------------------------------------------
    # Sözleşme / Anlaşma Sekmesi
    # ------------------------------------------------------------------
    def _build_contract_tab(self) -> None:
        self.contract_tab = QWidget()
        layout = QVBoxLayout(self.contract_tab)

        form = QFormLayout()
        self.bn_input = QLineEdit()
        form.addRow("BN", self.bn_input)
        self.client_input = QLineEdit()
        form.addRow("Müvekkil", self.client_input)
        self.esas_input = QLineEdit()
        form.addRow("Esas No", self.esas_input)

        self.fixed_amount = self._create_amount_spinbox()
        form.addRow("Sabit Ücret", self.fixed_amount)

        self.percent_rate = self._create_amount_spinbox(max_value=100.0, suffix=" %")
        form.addRow("Yüzde Oranı", self.percent_rate)

        self.percent_target = self._create_amount_spinbox()
        form.addRow("Yüzde Baz Tutarı", self.percent_target)

        self.percent_deferred_checkbox = QCheckBox(
            "Yüzde meblağ iş sonunda alınacak (taksitlere yansıtılmaz)"
        )
        form.addRow("", self.percent_deferred_checkbox)

        self.contract_total_label = QLabel("0,00 ₺")
        form.addRow("Hesaplanan Toplam Ücret", self.contract_total_label)

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
        self.bn_input.setText(self.finans.get("harici_bn") or "")
        self.client_input.setText(self.finans.get("harici_muvekkil") or "")
        self.esas_input.setText(self.finans.get("harici_esas_no") or "")
        self.fixed_amount.setValue((self.finans.get("sabit_ucret_cents") or 0) / 100)
        self.percent_rate.setValue(float(self.finans.get("yuzde_orani") or 0))
        self.percent_target.setValue((self.finans.get("tahsil_hedef_cents") or 0) / 100)
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
            (toplam * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        self.contract_total_label.setText(format_tl(cents))

    def save_contract(self) -> None:
        try:
            harici_update_contract(
                self.conn,
                self.harici_id,
                sabit_ucret_cents=tl_to_cents(self.fixed_amount.value()),
                yuzde_orani=float(self.percent_rate.value()),
                tahsil_hedef_cents=tl_to_cents(self.percent_target.value()),
                yuzde_is_sonu=1 if self.percent_deferred_checkbox.isChecked() else 0,
                notlar=self.contract_notes.toPlainText().strip() or None,
                harici_bn=self.bn_input.text().strip() or None,
                harici_muvekkil=self.client_input.text().strip() or None,
                harici_esas_no=self.esas_input.text().strip() or None,
            )
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Sözleşme kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Sözleşme bilgileri güncellendi.")
        add_harici_finans_timeline_entry(self.harici_id, "Sözleşme bilgileri güncellendi.", self._current_username)
        self.refresh_finance_data()

    # ------------------------------------------------------------------
    # Ödeme Planı Sekmesi
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

        button_row = QHBoxLayout()
        self.plan_generate_button = QPushButton("Plan Oluştur")
        button_row.addWidget(self.plan_generate_button)

        self.plan_reset_button = QPushButton("Sıfırla")
        self.plan_reset_button.setStyleSheet("color: #c0392b;")
        reset_menu = QMenu(self)
        reset_menu.addAction("Tamamen Sıfırla", self._reset_plan_all)
        reset_menu.addAction("Ödenmemiş Taksitleri Sil", self._reset_plan_unpaid)
        self.plan_reset_button.setMenu(reset_menu)
        button_row.addWidget(self.plan_reset_button)

        button_row.addStretch()
        self.plan_save_button = QPushButton("Kaydet")
        button_row.addWidget(self.plan_save_button)
        layout.addLayout(button_row)

        self.plan_table = QTableWidget(0, 6)
        self.plan_table.setHorizontalHeaderLabels(
            ["Sıra", "Vade Tarihi", "Tutar", "Durum", "Ödeme Tarihi", "Açıklama"]
        )
        self.plan_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.plan_table)

        self.plan_info_label = QLabel("")
        self.plan_info_label.setWordWrap(True)
        self.plan_info_label.setStyleSheet("color:#555;font-style:italic;")
        self.plan_info_label.hide()
        layout.addWidget(self.plan_info_label)

        self.plan_generate_button.clicked.connect(self.generate_plan)
        self.plan_save_button.clicked.connect(self.save_plan)

        self.tab_widget.addTab(self.plan_tab, "Ödeme Planı")

    def load_plan(self) -> None:
        plan, taksitler = harici_get_payment_plan(self.conn, self.harici_id)
        if plan:
            self.installment_count.setValue(int(plan.get("taksit_sayisi") or 0))
            self.installment_period.setCurrentText(plan.get("periyot") or "Ay")
            self.installment_day.setValue(int(plan.get("vade_gunu") or 1))
            if plan.get("baslangic_tarihi"):
                parsed = QDate.fromString(plan.get("baslangic_tarihi"), "yyyy-MM-dd")
                if parsed and parsed.isValid():
                    self.installment_start.setDate(parsed)
            self.plan_description.setText(plan.get("aciklama") or "")
        self.populate_plan_table(taksitler or [])

    def populate_plan_table(self, taksitler: list[dict[str, Any]]) -> None:
        self._plan_table_updating = True
        self.plan_table.setRowCount(0)
        try:
            for item in taksitler:
                row = self.plan_table.rowCount()
                self.plan_table.insertRow(row)

                order_item = QTableWidgetItem(str(item.get("sira") or row + 1))
                order_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                order_item.setData(Qt.ItemDataRole.UserRole, item.get("id"))
                self.plan_table.setItem(row, 0, order_item)

                due_edit = self._create_date_edit(item.get("vade_tarihi"))
                due_edit.setProperty("taksit_id", item.get("id"))
                self.plan_table.setCellWidget(row, 1, due_edit)

                amount_spin = self._create_amount_spinbox()
                amount_spin.setValue((item.get("tutar_cents") or 0) / 100)
                self.plan_table.setCellWidget(row, 2, amount_spin)

                status_combo = QComboBox()
                status_combo.addItems(INSTALLMENT_STATUS_OPTIONS)
                current_status = item.get("durum") or "Ödenecek"
                status_combo.setCurrentText(current_status)
                status_combo.setProperty("prev_status", current_status)
                self.plan_table.setCellWidget(row, 3, status_combo)

                paid_edit = self._create_date_edit(item.get("odeme_tarihi"), allow_blank=True)
                self.plan_table.setCellWidget(row, 4, paid_edit)
                status_combo.currentTextChanged.connect(
                    lambda value, edit=paid_edit, combo=status_combo: self.on_plan_status_changed(combo, edit, value)
                )

                desc_item = QTableWidgetItem(item.get("aciklama") or "")
                self.plan_table.setItem(row, 5, desc_item)
        finally:
            self._plan_table_updating = False

    def on_plan_status_changed(
        self, status_widget: QComboBox | None, date_edit: QDateEdit | None, value: str
    ) -> None:
        if not isinstance(date_edit, QDateEdit):
            return
        # Tarih alanını güncelle
        if value == "Ödendi" and date_edit.date() == date_edit.minimumDate():
            date_edit.setDate(QDate.currentDate())
        elif value != "Ödendi":
            date_edit.setDate(date_edit.minimumDate())

        if getattr(self, "_plan_table_updating", False):
            return

        # Önceki durumu al
        prev_status = status_widget.property("prev_status") if status_widget else None

        # Durum "Ödendi" ise otomatik ödeme oluştur
        if value == "Ödendi":
            row_index = self._plan_row_for_widget(status_widget)
            if row_index >= 0:
                self._auto_create_payment_for_installment(row_index)
        # Durum "Ödendi"den başka bir şeye değiştiyse ödemeyi sil
        elif prev_status == "Ödendi" and value != "Ödendi":
            row_index = self._plan_row_for_widget(status_widget)
            if row_index >= 0:
                self._auto_delete_payment_for_installment(row_index)

        # Yeni durumu kaydet
        if status_widget:
            status_widget.setProperty("prev_status", value)

        # Planı kaydet ve yenile
        if not self._persist_plan(sync_payments=True, show_errors=True):
            return
        self.load_plan()
        self.load_payments()
        self.refresh_finance_data()

    def _persist_plan(self, *, sync_payments: bool, show_errors: bool = True) -> bool:
        try:
            harici_save_payment_plan(
                self.conn,
                self.harici_id,
                {
                    "taksit_sayisi": self.installment_count.value(),
                    "periyot": self.installment_period.currentText(),
                    "vade_gunu": self.installment_day.value(),
                    "baslangic_tarihi": self.installment_start.date().toString("yyyy-MM-dd"),
                    "aciklama": self.plan_description.text().strip() or None,
                },
                self._collect_plan_rows(),
            )
            return True
        except Exception as exc:
            if show_errors:
                QMessageBox.critical(self, "Hata", f"Plan kaydedilemedi:\n{exc}")
            return False

    def _plan_row_for_widget(self, widget: QComboBox | None) -> int:
        if widget is None or self.plan_table is None:
            return -1
        for row in range(self.plan_table.rowCount()):
            if self.plan_table.cellWidget(row, 3) is widget:
                return row
        return -1

    # NOTE: mirrors bound-finance auto payment creation when an installment is paid
    def _auto_create_payment_for_installment(self, row_index: int) -> None:
        if row_index < 0 or self.plan_table is None:
            return
        due_edit = self.plan_table.cellWidget(row_index, 1)
        amount_spin = self.plan_table.cellWidget(row_index, 2)
        desc_item = self.plan_table.item(row_index, 5)
        if not isinstance(due_edit, QDateEdit):
            return
        taksit_id = due_edit.property("taksit_id")
        if taksit_id in (None, "", 0):
            return
        due_date = None
        if due_edit.date() != due_edit.minimumDate():
            due_date = due_edit.date().toString("yyyy-MM-dd")
        amount_cents = 0
        if isinstance(amount_spin, QDoubleSpinBox):
            amount_cents = tl_to_cents(amount_spin.value())
        desc_text = desc_item.text().strip() if isinstance(desc_item, QTableWidgetItem) else ""
        installment = {
            "id": taksit_id,
            "vade_tarihi": due_date,
            "tutar_cents": amount_cents,
            "aciklama": desc_text,
        }
        try:
            created = harici_insert_payment_from_installment(
                self.conn,
                self.harici_id,
                installment,
            )
        except Exception as exc:  # pragma: no cover - GUI feedback
            QMessageBox.warning(
                self,
                "Uyarı",
                f"Taksit ödemesi otomatik eklenemedi:\n{exc}",
            )
            return
        if not created:
            return
        self.load_payments()
        self.refresh_finance_data()

    def _auto_delete_payment_for_installment(self, row_index: int) -> None:
        """Taksit durumu 'Ödendi'den değişince otomatik oluşturulan ödemeyi siler."""
        if row_index < 0 or self.plan_table is None:
            return
        due_edit = self.plan_table.cellWidget(row_index, 1)
        if not isinstance(due_edit, QDateEdit):
            return
        taksit_id = due_edit.property("taksit_id")
        if taksit_id in (None, "", 0):
            return
        try:
            deleted = harici_delete_payment_by_installment(
                self.conn,
                self.harici_id,
                int(taksit_id),
            )
        except Exception as exc:  # pragma: no cover - GUI feedback
            QMessageBox.warning(
                self,
                "Uyarı",
                f"Taksit ödemesi silinemedi:\n{exc}",
            )
            return
        if deleted:
            self.load_payments()
            self.refresh_finance_data()

    def generate_plan(self) -> None:
        taksit_sayisi = int(self.installment_count.value())
        if taksit_sayisi <= 0:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir taksit sayısı giriniz.")
            return
        installments = harici_generate_installments(
            self.conn,
            self.harici_id,
            taksit_sayisi,
            self.installment_period.currentText(),
            int(self.installment_day.value()),
            self.installment_start.date().toPyDate(),
        )
        if not installments:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Plan oluşturmak için sözleşme verilerini doldurun.",
            )
            return
        self.populate_plan_table(installments)
        self.plan_info_label.hide()

    def _collect_plan_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.plan_table.rowCount()):
            order_item = self.plan_table.item(row, 0)
            due_edit = self.plan_table.cellWidget(row, 1)
            amount_spin = self.plan_table.cellWidget(row, 2)
            status_combo = self.plan_table.cellWidget(row, 3)
            paid_edit = self.plan_table.cellWidget(row, 4)
            desc_item = self.plan_table.item(row, 5)
            if not isinstance(due_edit, QDateEdit) or not isinstance(amount_spin, QDoubleSpinBox):
                continue
            taksit_id = due_edit.property("taksit_id")
            rows.append(
                {
                    "id": taksit_id,
                    "sira": int(order_item.text()) if order_item else row + 1,
                    "vade_tarihi": due_edit.date().toString("yyyy-MM-dd"),
                    "tutar_cents": tl_to_cents(amount_spin.value()),
                    "durum": status_combo.currentText() if isinstance(status_combo, QComboBox) else "Ödenecek",
                    "odeme_tarihi": None
                    if not isinstance(paid_edit, QDateEdit)
                    or paid_edit.date() == paid_edit.minimumDate()
                    else paid_edit.date().toString("yyyy-MM-dd"),
                    "aciklama": desc_item.text() if desc_item else "",
                }
            )
        return rows

    def save_plan(self) -> None:
        try:
            harici_save_payment_plan(
                self.conn,
                self.harici_id,
                {
                    "taksit_sayisi": self.installment_count.value(),
                    "periyot": self.installment_period.currentText(),
                    "vade_gunu": self.installment_day.value(),
                    "baslangic_tarihi": self.installment_start.date().toString("yyyy-MM-dd"),
                    "aciklama": self.plan_description.text().strip() or None,
                },
                self._collect_plan_rows(),
            )
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Ödeme planı kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Ödeme planı kaydedildi.")
        add_harici_finans_timeline_entry(self.harici_id, "Ödeme planı kaydedildi.", self._current_username)
        self.load_plan()
        self.load_payments()
        self.refresh_finance_data()

    def _reset_plan_all(self) -> None:
        """Tüm ödeme planını sıfırla."""
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
            deleted = harici_reset_payment_plan(self.conn, self.harici_id, keep_paid=False)
            self.show_status_message(f"{deleted} taksit silindi.")
            add_harici_finans_timeline_entry(self.harici_id, f"Ödeme planı tamamen sıfırlandı ({deleted} taksit).", self._current_username)
            self.load_plan()
            self.load_payments()
            self.refresh_finance_data()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Plan sıfırlanamadı:\n{exc}")

    def _reset_plan_unpaid(self) -> None:
        """Sadece ödenmemiş taksitleri sil."""
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
            deleted = harici_reset_payment_plan(self.conn, self.harici_id, keep_paid=True)
            self.show_status_message(f"{deleted} ödenmemiş taksit silindi.")
            add_harici_finans_timeline_entry(self.harici_id, f"Ödenmemiş taksitler silindi ({deleted} taksit).", self._current_username)
            self.load_plan()
            self.load_payments()
            self.refresh_finance_data()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Taksitler silinemedi:\n{exc}")

    # ------------------------------------------------------------------
    # Ödemeler Sekmesi
    # ------------------------------------------------------------------
    def _build_payments_tab(self) -> None:
        self.payments_tab = QWidget()
        layout = QVBoxLayout(self.payments_tab)

        button_row = QHBoxLayout()
        self.payment_add_button = QPushButton("Ekle")
        self.payment_remove_button = QPushButton("Sil")
        self.payment_save_button = QPushButton("Kaydet")
        button_row.addWidget(self.payment_add_button)
        button_row.addWidget(self.payment_remove_button)
        button_row.addStretch()
        button_row.addWidget(self.payment_save_button)
        layout.addLayout(button_row)

        self.payments_table = QTableWidget(0, 4)
        self.payments_table.setHorizontalHeaderLabels(
            ["Tarih", "Tutar", "Yöntem", "Açıklama"]
        )
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

        date_source = record.get("tahsil_tarihi") or record.get("tarih")
        date_edit = self._create_date_edit(date_source)
        date_edit.setProperty("payment_id", record.get("id"))
        if record.get("plan_taksit_id") is not None:
            date_edit.setProperty("plan_taksit_id", record.get("plan_taksit_id"))
        self.payments_table.setCellWidget(row, 0, date_edit)

        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue((record.get("tutar_cents") or 0) / 100)
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
                        harici_delete_payment(int(payment_id))
                    except Exception as exc:
                        QMessageBox.warning(self, "Uyarı", f"Ödeme silinemedi:\n{exc}")
                        return
            self.payments_table.removeRow(row)
            # Finans toplamlarını güncelle
            self.refresh_finance_data()

    def load_payments(self) -> None:
        self.payments_table.setRowCount(0)
        for record in harici_get_payments(self.conn, self.harici_id):
            self.add_payment_row(record)

    def _collect_payments(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.payments_table.rowCount()):
            date_edit = self.payments_table.cellWidget(row, 0)
            amount_spin = self.payments_table.cellWidget(row, 1)
            method_item = self.payments_table.item(row, 2)
            desc_item = self.payments_table.item(row, 3)
            if not isinstance(date_edit, QDateEdit) or not isinstance(amount_spin, QDoubleSpinBox):
                continue
            tarih_iso = None
            if date_edit.date() != date_edit.minimumDate():
                tarih_iso = date_edit.date().toString("yyyy-MM-dd")
            plan_taksit_id = date_edit.property("plan_taksit_id")
            rows.append(
                {
                    "id": date_edit.property("payment_id"),
                    "tarih": tarih_iso,
                    "tahsil_tarihi": tarih_iso,
                    "tutar_cents": tl_to_cents(amount_spin.value()),
                    "yontem": method_item.text() if method_item else None,
                    "aciklama": desc_item.text() if desc_item else None,
                    "tahsil_durumu": "Ödendi",
                    "plan_taksit_id": plan_taksit_id,
                }
            )
        return rows

    def save_payments(self) -> None:
        try:
            harici_save_payments(self.conn, self.harici_id, self._collect_payments())
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Ödemeler kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Ödeme kayıtları kaydedildi.")
        add_harici_finans_timeline_entry(self.harici_id, "Ödeme kayıtları güncellendi.", self._current_username)
        self.load_payments()
        self.refresh_finance_data()

    # ------------------------------------------------------------------
    # Masraflar Sekmesi
    # ------------------------------------------------------------------
    def _build_expenses_tab(self) -> None:
        self.expenses_tab = QWidget()
        layout = QVBoxLayout(self.expenses_tab)

        # Müvekkil kasası bakiye bilgisi
        balance_layout = QHBoxLayout()
        self.expense_kasa_balance_label = QLabel("Müvekkil Kasası Bakiye: 0,00 ₺")
        self.expense_kasa_balance_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        balance_layout.addWidget(self.expense_kasa_balance_label)
        balance_layout.addStretch()
        layout.addLayout(balance_layout)

        button_row = QHBoxLayout()
        self.expense_add_button = QPushButton("Ekle")
        self.expense_remove_button = QPushButton("Sil")
        self.expense_save_button = QPushButton("Kaydet")
        button_row.addWidget(self.expense_add_button)
        button_row.addWidget(self.expense_remove_button)
        button_row.addStretch()
        button_row.addWidget(self.expense_save_button)
        layout.addLayout(button_row)

        self.expenses_table = QTableWidget(0, 7)
        self.expenses_table.setHorizontalHeaderLabels(
            ["Kalem", "Tutar", "Ödeme Kaynağı", "Tarih", "Tahsil Durumu", "Tahsil Tarihi", "Açıklama"]
        )
        self.expenses_table.horizontalHeader().setStretchLastSection(True)
        self.expenses_table.setColumnWidth(2, 100)
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
        name_item = QTableWidgetItem(record.get("kalem") or "")
        if record.get("id"):
            name_item.setData(Qt.ItemDataRole.UserRole, record["id"])
        self.expenses_table.setItem(row, 0, name_item)

        # Sütun 1: Tutar
        amount_spin = self._create_amount_spinbox()
        amount_spin.setValue((record.get("tutar_cents") or 0) / 100)
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
        # Kasadan ödendiyse tahsil durumu devre dışı
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
        desc_item = QTableWidgetItem(record.get("aciklama") or "")
        self.expenses_table.setItem(row, 6, desc_item)

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

    def on_expense_status_changed(self, status_combo: QComboBox, date_edit: QDateEdit, value: str) -> None:
        if value == "Tahsil Edildi" and date_edit.date() == date_edit.minimumDate():
            date_edit.setDate(QDate.currentDate())
        elif value != "Tahsil Edildi":
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
                            date_edit = self.expenses_table.cellWidget(row, 3)
                            amount_spin = self.expenses_table.cellWidget(row, 1)
                            if isinstance(date_edit, QDateEdit) and isinstance(amount_spin, QDoubleSpinBox):
                                tarih = date_edit.date().toString("yyyy-MM-dd") if date_edit.date() != date_edit.minimumDate() else ""
                                tutar_kurus = tl_to_cents(amount_spin.value())
                                if self.harici_id and tarih and tutar_kurus > 0:
                                    try:
                                        harici_delete_expense_by_kasa_avans(None, self.harici_id, tarih, tutar_kurus)
                                    except Exception:
                                        pass
                        harici_delete_expense(int(expense_id))
                    except Exception as exc:
                        QMessageBox.warning(self, "Uyarı", f"Masraf silinemedi:\n{exc}")
                        return
            self.expenses_table.removeRow(row)
            # Finans toplamlarını güncelle
            self.refresh_finance_data()

    def load_expenses(self) -> None:
        self.expenses_table.setRowCount(0)
        for record in harici_get_expenses(self.conn, self.harici_id):
            self.add_expense_row(record)
        self._update_expense_kasa_balance()

    def _update_expense_kasa_balance(self) -> None:
        """Müvekkil kasası bakiyesini masraflar sekmesinde göster."""
        try:
            raw_entries = get_harici_muvekkil_kasasi_entries(self.harici_id)
            entries = [dict(e) for e in raw_entries]
        except Exception:
            entries = []
        # Giriş türleri
        giris_turleri = {"Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Alınan Masraf", "GELEN"}
        # Çıkış türleri
        cikis_turleri = {"Kullanılan Avans", "Ödenen Masraf", "Müvekkile Ödeme", "MUVEKKILE_ODEME"}
        gelen = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in giris_turleri)
        giden = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in cikis_turleri)
        kalan = gelen - giden
        self.expense_kasa_balance_label.setText(f"Müvekkil Kasası Bakiye: {format_tl(kalan)}")

    def _collect_expenses(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.expenses_table.rowCount()):
            name_item = self.expenses_table.item(row, 0)
            amount_spin = self.expenses_table.cellWidget(row, 1)
            source_combo = self.expenses_table.cellWidget(row, 2)
            date_edit = self.expenses_table.cellWidget(row, 3)
            status_combo = self.expenses_table.cellWidget(row, 4)
            collected_edit = self.expenses_table.cellWidget(row, 5)
            desc_item = self.expenses_table.item(row, 6)
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
                    "aciklama": desc_item.text() if desc_item else "",
                }
            )
        return rows

    def save_expenses(self) -> None:
        try:
            harici_save_expenses(self.conn, self.harici_id, self._collect_expenses())
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Masraflar kaydedilemedi:\n{exc}")
            return
        self.show_status_message("Masraf kayıtları kaydedildi.")
        add_harici_finans_timeline_entry(self.harici_id, "Masraf kayıtları güncellendi.", self._current_username)
        self.load_expenses()
        self.load_client_cash()  # Kasadan masrafları müvekkil kasasına ekleniyor olabilir
        self.refresh_finance_data()

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
        widths = settings.value("HariciFinansDialog/client_cash_widths", None)
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
        settings.setValue("HariciFinansDialog/client_cash_widths", widths)

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
                    delete_harici_muvekkil_kasasi_entry(int(entry_id))
                except Exception as exc:
                    QMessageBox.warning(self, "Uyarı", f"Kayıt silinemedi:\n{exc}")
                    return

                # Otomatik oluşturulan kayıtları da sil
                if self.harici_id and tarih and tutar_kurus > 0:
                    if islem_turu == "Sözleşme Ödemesi":
                        try:
                            harici_delete_payment_from_kasadan(None, self.harici_id, tarih, tutar_kurus)
                        except Exception:
                            pass  # Ödeme kaydı silinmese de devam et
                    elif islem_turu == "Kullanılan Avans":
                        try:
                            harici_delete_expense_by_kasa_avans(None, self.harici_id, tarih, tutar_kurus)
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
        try:
            entries = get_harici_muvekkil_kasasi_entries(self.harici_id)
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
                    update_harici_muvekkil_kasasi_entry(
                        int(entry_id),
                        row["tarih"],
                        row["tutar_kurus"],
                        islem_turu,
                        row.get("aciklama"),
                    )
                    saved_count += 1
                else:
                    new_id = insert_harici_muvekkil_kasasi_entry(
                        self.harici_id,
                        row["tarih"],
                        row["tutar_kurus"],
                        islem_turu,
                        row.get("aciklama"),
                    )
                    order_item = self.client_cash_table.item(idx, 0)
                    if isinstance(order_item, QTableWidgetItem):
                        order_item.setData(Qt.ItemDataRole.UserRole, new_id)
                    add_harici_finans_timeline_entry(
                        self.harici_id,
                        f"Müvekkil kasası: {format_tl(row['tutar_kurus'])} {islem_turu} kaydı eklendi.",
                        self._current_username,
                    )
                    saved_count += 1
                    # Sözleşme Ödemesi ise ödemeler sekmesine de ekle
                    if islem_turu == "Sözleşme Ödemesi":
                        try:
                            harici_insert_payment_from_kasadan(
                                None,
                                self.harici_id,
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
    # Özet Sekmesi
    # ------------------------------------------------------------------
    def _build_summary_tab(self) -> None:
        self.summary_tab = QWidget()
        layout = QVBoxLayout(self.summary_tab)

        # Büro Alacağı grubu
        buro_group = QGroupBox("Büro Alacağı")
        buro_form = QFormLayout(buro_group)
        self.summary_total = QLabel("0,00 ₺")
        self.summary_collected = QLabel("0,00 ₺")
        self.summary_expenses = QLabel("0,00 ₺")
        self.summary_expenses.setToolTip("Sadece Büro tarafından ödenen masraflar")
        self.summary_expenses_collected = QLabel("0,00 ₺")
        self.summary_balance = QLabel("0,00 ₺")
        self.summary_balance.setStyleSheet("font-weight: bold;")
        buro_form.addRow("Toplam Ücret:", self.summary_total)
        buro_form.addRow("Tahsil Edilen:", self.summary_collected)
        buro_form.addRow("Büro Masrafları:", self.summary_expenses)
        buro_form.addRow("Masraf Tahsil:", self.summary_expenses_collected)
        buro_form.addRow("Büro Alacağı:", self.summary_balance)
        layout.addWidget(buro_group)

        # Müvekkil Kasası grubu
        kasa_group = QGroupBox("Müvekkil Kasası")
        kasa_form = QFormLayout(kasa_group)
        self.summary_kasa_giris = QLabel("0,00 ₺")
        self.summary_kasa_kullanilan = QLabel("0,00 ₺")
        self.summary_kasa_kullanilan.setToolTip("Kasadan ödenen masraflar")
        self.summary_kasa_cikis = QLabel("0,00 ₺")
        self.summary_kasa_bakiye = QLabel("0,00 ₺")
        self.summary_kasa_bakiye.setStyleSheet("font-weight: bold; color: #0066cc;")
        kasa_form.addRow("Toplam Giriş:", self.summary_kasa_giris)
        kasa_form.addRow("Kullanılan Avans:", self.summary_kasa_kullanilan)
        kasa_form.addRow("Diğer Çıkışlar:", self.summary_kasa_cikis)
        kasa_form.addRow("Kalan Bakiye:", self.summary_kasa_bakiye)
        layout.addWidget(kasa_group)

        # Müvekkile Gönderilecek grubu
        muvekkil_group = QGroupBox("Müvekkile Gönderilecek")
        muvekkil_form = QFormLayout(muvekkil_group)
        self.summary_muvekkile_gonderilecek = QLabel("0,00 ₺")
        self.summary_muvekkile_gonderilecek.setStyleSheet("font-weight: bold; color: #cc6600;")
        self.summary_muvekkile_gonderilecek.setToolTip("Kasa Bakiyesi - Büro Alacağı (pozitifse müvekkile gönderilecek)")
        muvekkil_form.addRow("Toplam:", self.summary_muvekkile_gonderilecek)
        layout.addWidget(muvekkil_group)

        layout.addStretch()
        self.tab_widget.addTab(self.summary_tab, "Özet")

    def refresh_summary(self) -> None:
        total = int(self.finans.get("toplam_ucret_cents") or 0)
        tahsil = int(self.finans.get("tahsil_edilen_cents") or 0)
        masraf = int(self.finans.get("masraf_toplam_cents") or 0)
        masraf_tahsil = int(self.finans.get("masraf_tahsil_cents") or 0)
        kalan = int(self.finans.get("kalan_bakiye_cents") or 0)

        self.summary_total.setText(format_tl(total))
        self.summary_collected.setText(format_tl(tahsil))
        self.summary_expenses.setText(format_tl(masraf))
        self.summary_expenses_collected.setText(format_tl(masraf_tahsil))
        self.summary_balance.setText(format_tl(kalan))

        # Müvekkil kasası özeti
        try:
            raw_entries = get_harici_muvekkil_kasasi_entries(self.harici_id)
            entries = [dict(e) for e in raw_entries]
        except Exception:
            entries = []
        giris_turleri = {"Dosya Geliri", "Avans Masrafı", "Masraf Geliri", "Alınan Masraf", "GELEN"}
        kullanilan_turleri = {"Kullanılan Avans"}
        sozlesme_odemesi_turleri = {"Sözleşme Ödemesi"}
        diger_cikis_turleri = {"Ödenen Masraf", "Müvekkile Ödeme", "MUVEKKILE_ODEME"}

        toplam_giris = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in giris_turleri)
        kullanilan_avans = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in kullanilan_turleri)
        sozlesme_odemesi = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in sozlesme_odemesi_turleri)
        diger_cikis = sum(int(e.get("tutar_kurus") or 0) for e in entries if e.get("islem_turu") in diger_cikis_turleri)
        kasa_bakiye = toplam_giris - kullanilan_avans - sozlesme_odemesi - diger_cikis

        self.summary_kasa_giris.setText(format_tl(toplam_giris))
        self.summary_kasa_kullanilan.setText(format_tl(kullanilan_avans))
        self.summary_kasa_cikis.setText(format_tl(diger_cikis))
        self.summary_kasa_bakiye.setText(format_tl(kasa_bakiye))

        # Müvekkile Gönderilecek: Kasa bakiyesi - Büro alacağı
        # kalan = büro alacağı (pozitif ise büroya borç, negatif ise müvekkile borç)
        # (Yüzde tutarı zaten toplam ücrete dahil, kalan içinde)
        muvekkile_gonderilecek = kasa_bakiye - kalan
        if muvekkile_gonderilecek > 0:
            self.summary_muvekkile_gonderilecek.setText(format_tl(muvekkile_gonderilecek))
            self.summary_muvekkile_gonderilecek.setStyleSheet("font-weight: bold; color: #009900;")
        elif muvekkile_gonderilecek < 0:
            self.summary_muvekkile_gonderilecek.setText(f"-{format_tl(abs(muvekkile_gonderilecek))}")
            self.summary_muvekkile_gonderilecek.setStyleSheet("font-weight: bold; color: #cc0000;")
        else:
            self.summary_muvekkile_gonderilecek.setText("0,00 ₺")
            self.summary_muvekkile_gonderilecek.setStyleSheet("font-weight: bold; color: #666666;")

    def _refresh_summary_labels(self) -> None:
        if not self._load_finans_data():
            return
        self.refresh_summary()

    # ------------------------------------------------------------------
    # Zaman Çizgisi sekmesi (harici finans)
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
        """Harici finans zaman çizgisine manuel not ekle."""
        note_text = self.finance_timeline_input.text().strip()
        if not note_text:
            QMessageBox.warning(self, "Uyarı", "Not alanı boş bırakılamaz.")
            return
        try:
            add_harici_finans_timeline_entry(self.harici_id, note_text, self._current_username)
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
        try:
            rows = get_harici_finans_timeline(self.harici_id)
        except Exception:
            rows = []
        for entry in rows:
            self.finance_timeline_list.addItem(self._format_finance_timeline_row(entry))

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    def _create_date_edit(
        self,
        iso_value: str | None,
        *,
        allow_blank: bool = False,
        default_to_today: bool = True,
    ) -> QDateEdit:
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        if allow_blank:
            date_edit.setSpecialValueText("-")
            date_edit.setDateRange(QDate(1900, 1, 1), QDate(7999, 12, 31))
            date_edit.setDate(date_edit.minimumDate())
        if iso_value:
            parsed = QDate.fromString(iso_value, "yyyy-MM-dd")
            if parsed and parsed.isValid():
                date_edit.setDate(parsed)
            elif default_to_today and not allow_blank:
                date_edit.setDate(QDate.currentDate())
        elif default_to_today and not allow_blank:
            date_edit.setDate(QDate.currentDate())
        return date_edit
