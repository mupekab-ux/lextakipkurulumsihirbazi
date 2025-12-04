# -*- coding: utf-8 -*-
"""
Finans işlemleri - dosya bazlı ve harici finans kayıtları.
Bu modül, models.py'deki finans fonksiyonlarını re-export eder.
Geriye dönük uyumluluk için models.py'deki fonksiyonlar korunur.
"""

from services.base import *

# QDate için import
try:
    from PyQt6.QtCore import QDate
except ImportError:
    QDate = None

__all__ = [
    # Yardımcı fonksiyonlar
    "tl_to_cents",
    "cents_to_tl",
    "calculate_finance_total",
    "calculate_finance_balance",
    "calculate_harici_total",
    "calculate_harici_balance",
    # Finans CRUD
    "ensure_finans_record",
    "get_finans_for_dosya",
    "get_finans_by_id",
    "list_finance_overview",
    "get_finans_master_list_bound_only",
    "summarize_finance_by_ids",
    "summarize_harici_finance_by_ids",
    # Finans güncelleme
    "update_finans_contract",
    "update_finans_terms",
    "recalculate_finans_totals",
    "delete_finans_record",
    # Taksit işlemleri
    "generate_installments",
    "mark_next_installment_paid",
    "add_partial_payment",
    # Ödeme planı
    "get_payment_plan",
    "save_payment_plan",
    "get_payments",
    "save_payments",
    "get_expenses",
    "save_expenses",
    # Harici finans
    "harici_create",
    "harici_get_contract",
    "harici_update_contract",
    "harici_generate_installments",
    "harici_get_payment_plan",
    "harici_save_payment_plan",
    "harici_get_payments",
    "harici_save_payments",
    "harici_get_expenses",
    "harici_save_expenses",
    "harici_recalculate_totals",
    "harici_get_master_list",
    "harici_update_quick_info",
    # Custom tabs
    "list_custom_tabs",
    "create_custom_tab",
    "rename_custom_tab",
    "delete_custom_tab",
    "get_dosya_ids_for_tab",
    "get_tab_assignments_for_dosya",
    "set_tab_assignments_for_dosya",
    # Attachment wrappers
    "get_attachments",
    "add_attachment",
    "delete_attachment",
    "delete_attachment_with_file",
    "update_attachment_path",
    "export_attachment",
]


def _row_value(row: Dict[str, Any] | sqlite3.Row, key: str) -> Any:
    """sqlite3.Row veya dict'ten güvenli değer al."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def calculate_finance_total(finans_row: Dict[str, Any] | sqlite3.Row | None) -> int:
    """Finans kaydının toplam ücretini hesaplar (kuruş cinsinden)."""
    if finans_row is None:
        return 0

    fixed_cents = safe_int(_row_value(finans_row, "sozlesme_ucreti_cents"))
    percent_rate = Decimal(str(_row_value(finans_row, "sozlesme_yuzdesi") or 0))
    target_cents = safe_int(_row_value(finans_row, "tahsil_hedef_cents"))
    deferred = safe_int(_row_value(finans_row, "yuzde_is_sonu"))

    try:
        percent_decimal = (Decimal(target_cents) * percent_rate / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    except Exception:
        percent_decimal = Decimal("0")

    if deferred:
        return fixed_cents

    try:
        target_decimal = Decimal(str(target_cents))
    except Exception:
        target_decimal = Decimal("0")

    return fixed_cents + int(min(percent_decimal, target_decimal))


def calculate_finance_balance(finans_row: Dict[str, Any] | sqlite3.Row | None) -> int:
    """Finans kaydının kalan bakiyesini hesaplar (kuruş cinsinden)."""
    if finans_row is None:
        return 0

    total_cents = calculate_finance_total(finans_row)
    collected = safe_int(_row_value(finans_row, "tahsil_edilen_cents"))
    expense = safe_int(_row_value(finans_row, "masraf_toplam_cents"))
    expense_collected = safe_int(_row_value(finans_row, "masraf_tahsil_cents"))
    return total_cents + expense - collected - expense_collected


def calculate_harici_total(record: Dict[str, Any] | sqlite3.Row | None) -> int:
    """Harici finans kaydının toplam ücretini hesaplar."""
    if record is None:
        return 0

    fixed_cents = safe_int(_row_value(record, "sabit_ucret_cents"))
    percent_rate = Decimal(str(_row_value(record, "yuzde_orani") or 0))
    target_cents = safe_int(_row_value(record, "tahsil_hedef_cents"))

    try:
        percent_rate = Decimal(str(percent_rate or 0))
    except Exception:
        percent_rate = Decimal("0")

    percent_cents = 0
    # Yüzde tutarı her zaman toplama dahil (yuzde_is_sonu sadece taksitleri etkiler)
    if percent_rate and target_cents:
        percent_cents = int(
            (Decimal(target_cents) * percent_rate / Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    return fixed_cents + percent_cents


def calculate_harici_balance(record: Dict[str, Any] | sqlite3.Row | None) -> int:
    """Harici finans kaydının kalan bakiyesini hesaplar."""
    if record is None:
        return 0

    total = calculate_harici_total(record)
    collected = safe_int(_row_value(record, "tahsil_edilen_cents"))
    expense = safe_int(_row_value(record, "masraf_toplam_cents"))
    expense_collected = safe_int(_row_value(record, "masraf_tahsil_cents"))
    return total + expense - collected - expense_collected


# Aşağıdaki fonksiyonlar models.py'den import edilecek
# Geriye dönük uyumluluk için placeholder olarak tanımlanıyor

def ensure_finans_record(dosya_id: int, cur: sqlite3.Cursor | None = None) -> int:
    """Verilen dosya için finans kaydı oluşturur veya mevcut olanı döndürür."""
    owns_connection = cur is None
    conn: sqlite3.Connection | None = None
    if owns_connection:
        conn = get_connection()
        cur = conn.cursor()
    assert cur is not None
    cur.execute("INSERT OR IGNORE INTO finans (dosya_id) VALUES (?)", (dosya_id,))
    cur.execute("SELECT id FROM finans WHERE dosya_id = ?", (dosya_id,))
    row = cur.fetchone()
    finans_id = int(row[0]) if row else 0
    if owns_connection and conn is not None:
        conn.commit()
        conn.close()
    return finans_id


def get_finans_master_list_bound_only(
    conn: sqlite3.Connection | None = None,
    *,
    include_archived: bool = False,
) -> List[sqlite3.Row]:
    """Dosyaya bağlı finans kayıtlarını döndürür."""
    owns_conn = False
    if conn is None:
        conn = get_connection()
        owns_conn = True
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            WITH next_due AS (
                SELECT finans_id, MIN(vade_tarihi) AS next_due_date
                FROM taksitler
                WHERE durum != 'Ödendi'
                GROUP BY finans_id
            ),
            overdue AS (
                SELECT finans_id
                FROM taksitler
                WHERE durum != 'Ödendi' AND vade_tarihi < DATE('now')
                GROUP BY finans_id
            ),
            assignments AS (
                SELECT dosya_id, GROUP_CONCAT(user_id) AS user_ids
                FROM dosya_atamalar
                GROUP BY dosya_id
            )
            SELECT
                f.id AS finans_id,
                f.dosya_id,
                f.sozlesme_ucreti,
                f.sozlesme_ucreti_cents,
                f.sozlesme_yuzdesi,
                f.tahsil_hedef_cents,
                f.tahsil_edilen_cents,
                f.masraf_toplam_cents,
                f.masraf_tahsil_cents,
                f.yuzde_is_sonu,
                d.buro_takip_no,
                d.dosya_esas_no,
                d.muvekkil_adi,
                d.is_archived,
                next_due.next_due_date,
                CASE WHEN overdue.finans_id IS NOT NULL THEN 1 ELSE 0 END AS has_overdue_installment,
                assignments.user_ids AS assigned_user_ids
            FROM finans f
            JOIN dosyalar d ON d.id = f.dosya_id
            LEFT JOIN next_due ON next_due.finans_id = f.id
            LEFT JOIN overdue ON overdue.finans_id = f.id
            LEFT JOIN assignments ON assignments.dosya_id = f.dosya_id
            WHERE (? = 1 OR COALESCE(d.is_archived, 0) = 0)
            ORDER BY f.id DESC
            """,
            (1 if include_archived else 0,),
        )
        return cur.fetchall()
    finally:
        if owns_conn:
            conn.close()


# Custom tabs fonksiyonları
def list_custom_tabs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Özel sekmeleri döndürür."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, created_at FROM custom_tabs ORDER BY name COLLATE NOCASE"
    )
    rows = cur.fetchall()
    return [
        {"id": int(row[0]), "name": row[1], "created_at": row[2]}
        for row in rows
    ]


def create_custom_tab(conn: sqlite3.Connection, name: str) -> int:
    """Yeni özel sekme oluşturur."""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Sekme adı boş olamaz")
    cur = conn.cursor()
    cur.execute("INSERT INTO custom_tabs (name) VALUES (?)", (cleaned,))
    conn.commit()
    return int(cur.lastrowid)


def rename_custom_tab(conn: sqlite3.Connection, tab_id: int, new_name: str) -> None:
    """Özel sekme adını günceller."""
    cleaned = new_name.strip()
    if not cleaned:
        raise ValueError("Sekme adı boş olamaz")
    cur = conn.cursor()
    cur.execute("UPDATE custom_tabs SET name = ? WHERE id = ?", (cleaned, tab_id))
    conn.commit()


def delete_custom_tab(conn: sqlite3.Connection, tab_id: int) -> None:
    """Özel sekmeyi siler."""
    cur = conn.cursor()
    cur.execute("DELETE FROM custom_tabs WHERE id = ?", (tab_id,))
    conn.commit()


def get_dosya_ids_for_tab(conn: sqlite3.Connection, tab_id: int) -> Set[int]:
    """Sekmeye atanmış dosya ID'lerini döndürür."""
    cur = conn.cursor()
    cur.execute(
        "SELECT dosya_id FROM custom_tabs_dosyalar WHERE custom_tab_id = ?",
        (tab_id,),
    )
    return {int(row[0]) for row in cur.fetchall()}


def get_tab_assignments_for_dosya(conn: sqlite3.Connection, dosya_id: int) -> Set[int]:
    """Dosyanın atandığı sekme ID'lerini döndürür."""
    cur = conn.cursor()
    cur.execute(
        "SELECT custom_tab_id FROM custom_tabs_dosyalar WHERE dosya_id = ?",
        (dosya_id,),
    )
    return {int(row[0]) for row in cur.fetchall()}


def set_tab_assignments_for_dosya(
    conn: sqlite3.Connection, dosya_id: int, tab_ids: Iterable[int]
) -> None:
    """Dosyanın sekme atamalarını günceller."""
    desired_ids = {int(tab_id) for tab_id in tab_ids}
    cur = conn.cursor()
    current_ids = get_tab_assignments_for_dosya(conn, dosya_id)

    to_remove = current_ids - desired_ids
    to_add = desired_ids - current_ids

    if to_remove:
        cur.executemany(
            "DELETE FROM custom_tabs_dosyalar WHERE custom_tab_id = ? AND dosya_id = ?",
            ((tab_id, dosya_id) for tab_id in to_remove),
        )
    if to_add:
        cur.executemany(
            "INSERT OR IGNORE INTO custom_tabs_dosyalar (custom_tab_id, dosya_id) VALUES (?, ?)",
            ((tab_id, dosya_id) for tab_id in to_add),
        )
    conn.commit()


# Attachment wrapper'ları - models.py'den import edilecek
# Şimdilik placeholder

def get_attachments(dosya_id: int) -> List[Dict[str, Any]]:
    """Dosya eklerini döndürür."""
    try:
        from app.attachments import list_attachments
    except ModuleNotFoundError:
        from attachments import list_attachments
    return list(list_attachments(dosya_id))


def add_attachment(dosya_id: int, path: str) -> int:
    """Dosyaya ek ekler."""
    try:
        from app.attachments import add_attachments
    except ModuleNotFoundError:
        from attachments import add_attachments
    ids = add_attachments(dosya_id, [path])
    return ids[0] if ids else 0


def delete_attachment(attachment_id: int) -> None:
    """Ek kaydını siler."""
    try:
        from app.attachments import delete_attachment as _del
    except ModuleNotFoundError:
        from attachments import delete_attachment as _del
    _del(attachment_id)


def delete_attachment_with_file(attachment_id: int) -> None:
    """Ek kaydını ve dosyayı siler."""
    try:
        from app.attachments import delete_attachment as _del
    except ModuleNotFoundError:
        from attachments import delete_attachment as _del
    _del(attachment_id, remove_file=True)


def update_attachment_path(attachment_id: int, source_path: str) -> None:
    """Ek yolunu günceller."""
    try:
        from app.attachments import update_attachment_source
    except ModuleNotFoundError:
        from attachments import update_attachment_source
    update_attachment_source(attachment_id, source_path)


def export_attachment(attachment_id: int, target_directory: str):
    """Eki dışa aktarır."""
    try:
        from app.attachments import export_attachment as _exp
    except ModuleNotFoundError:
        from attachments import export_attachment as _exp
    return _exp(attachment_id, target_directory)


# Aşağıdaki fonksiyonlar büyük ve karmaşık olduğundan
# models.py'de kalacak ve oradan import edilecek.
# Burada sadece placeholder olarak tanımlanıyor.

def get_finans_for_dosya(dosya_id: int) -> Dict[str, Any]:
    """Dosya için finans kaydını döndürür - models.py'den import edilecek."""
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def get_finans_by_id(finans_id: int) -> Dict[str, Any]:
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def list_finance_overview(include_archived: bool = False) -> List[Dict[str, Any]]:
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def summarize_finance_by_ids(finance_ids: Iterable[int]) -> Dict[str, int]:
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def summarize_harici_finance_by_ids(finance_ids: Iterable[int]) -> Dict[str, int]:
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def update_finans_contract(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def update_finans_terms(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def recalculate_finans_totals(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def delete_finans_record(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def generate_installments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def mark_next_installment_paid(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def add_partial_payment(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def get_payment_plan(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def save_payment_plan(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def get_payments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def save_payments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def get_expenses(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def save_expenses(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_create(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_get_contract(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_update_contract(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_generate_installments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_get_payment_plan(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_save_payment_plan(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_get_payments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_save_payments(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_get_expenses(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_save_expenses(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_recalculate_totals(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_get_master_list(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")

def harici_update_quick_info(*args, **kwargs):
    raise NotImplementedError("Bu fonksiyon models.py'den import edilmeli")
