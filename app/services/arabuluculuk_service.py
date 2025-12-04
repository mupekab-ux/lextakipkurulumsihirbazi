# -*- coding: utf-8 -*-
"""
Arabuluculuk CRUD işlemleri.
"""

from services.base import *

__all__ = [
    "get_arabuluculuk_list",
    "get_arabuluculuk_by_id",
    "insert_arabuluculuk",
    "update_arabuluculuk",
    "delete_arabuluculuk",
    "mark_arabuluculuk_complete",
]


def get_arabuluculuk_list() -> List[Dict[str, Any]]:
    """Tüm arabuluculuk kayıtlarını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, davaci, davali, arb_adi, arb_tel, toplanti_tarihi, toplanti_saati, konu,
               COALESCE(tamamlandi, 0) as tamamlandi
        FROM arabuluculuk
        ORDER BY id DESC
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_arabuluculuk_by_id(rec_id: int) -> Optional[Dict[str, Any]]:
    """Belirtilen ID'ye sahip arabuluculuk kaydını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, davaci, davali, arb_adi, arb_tel, toplanti_tarihi, toplanti_saati, konu,
               COALESCE(tamamlandi, 0) as tamamlandi
        FROM arabuluculuk
        WHERE id = ?
        """,
        (rec_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def insert_arabuluculuk(rec: Dict[str, Any]) -> int:
    """Yeni arabuluculuk kaydı oluşturur."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO arabuluculuk (
            davaci,
            davali,
            arb_adi,
            arb_tel,
            toplanti_tarihi,
            toplanti_saati,
            konu,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            (rec.get("davaci") or "").strip(),
            (rec.get("davali") or "").strip(),
            (rec.get("arb_adi") or "").strip(),
            (rec.get("arb_tel") or "").strip(),
            normalize_iso_date(rec.get("toplanti_tarihi")),
            normalize_hhmm(rec.get("toplanti_saati")) or "00:00",
            (rec.get("konu") or "").strip(),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return int(new_id)


def update_arabuluculuk(rec: Dict[str, Any]) -> None:
    """Arabuluculuk kaydını günceller."""
    rec_id = rec.get("id")
    if not rec_id:
        raise ValueError("Güncellenecek arabuluculuk kaydı bulunamadı")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE arabuluculuk
           SET davaci = ?,
               davali = ?,
               arb_adi = ?,
               arb_tel = ?,
               toplanti_tarihi = ?,
               toplanti_saati = ?,
               konu = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            (rec.get("davaci") or "").strip(),
            (rec.get("davali") or "").strip(),
            (rec.get("arb_adi") or "").strip(),
            (rec.get("arb_tel") or "").strip(),
            normalize_iso_date(rec.get("toplanti_tarihi")),
            normalize_hhmm(rec.get("toplanti_saati")) or "00:00",
            (rec.get("konu") or "").strip(),
            int(rec_id),
        ),
    )
    conn.commit()
    conn.close()


def delete_arabuluculuk(rec_id: int) -> None:
    """Arabuluculuk kaydını siler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM arabuluculuk WHERE id = ?", (rec_id,))
    conn.commit()
    conn.close()


def mark_arabuluculuk_complete(rec_id: int, completed: bool) -> None:
    """Arabuluculuk kaydını tamamlandı olarak işaretler veya işareti kaldırır."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE arabuluculuk
           SET tamamlandi = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (1 if completed else 0, rec_id),
    )
    conn.commit()
    conn.close()
