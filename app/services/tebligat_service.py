# -*- coding: utf-8 -*-
"""
Tebligat CRUD işlemleri.
"""

from services.base import *

__all__ = [
    "get_tebligatlar_list",
    "get_tebligat_by_id",
    "insert_tebligat",
    "update_tebligat",
    "delete_tebligat",
    "mark_tebligat_complete",
]


def _clean_tebligat_text(value: Any) -> Optional[str]:
    """Tebligat metin alanlarını temizle."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_tebligatlar_list() -> List[Dict[str, Any]]:
    """Tüm tebligat kayıtlarını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, dosya_no, kurum, geldigi_tarih, teblig_tarihi, is_son_gunu, icerik,
               COALESCE(tamamlandi, 0) as tamamlandi
        FROM tebligatlar
        ORDER BY id DESC
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_tebligat_by_id(tebligat_id: int) -> Optional[Dict[str, Any]]:
    """Belirtilen ID'ye sahip tebligat kaydını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, dosya_no, kurum, geldigi_tarih, teblig_tarihi, is_son_gunu, icerik,
               COALESCE(tamamlandi, 0) as tamamlandi
        FROM tebligatlar
        WHERE id = ?
        """,
        (tebligat_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def insert_tebligat(rec: Dict[str, Any]) -> int:
    """Yeni tebligat kaydı oluşturur."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tebligatlar (
            dosya_no,
            kurum,
            geldigi_tarih,
            teblig_tarihi,
            is_son_gunu,
            icerik,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            _clean_tebligat_text(rec.get("dosya_no")),
            _clean_tebligat_text(rec.get("kurum")),
            normalize_iso_date(rec.get("geldigi_tarih")),
            normalize_iso_date(rec.get("teblig_tarihi")),
            normalize_iso_date(rec.get("is_son_gunu")),
            _clean_tebligat_text(rec.get("icerik")),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return int(new_id)


def update_tebligat(rec: Dict[str, Any]) -> None:
    """Tebligat kaydını günceller."""
    tebligat_id = rec.get("id")
    if not tebligat_id:
        raise ValueError("Güncellenecek tebligat kimliği belirtilmedi")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE tebligatlar
           SET dosya_no = ?,
               kurum = ?,
               geldigi_tarih = ?,
               teblig_tarihi = ?,
               is_son_gunu = ?,
               icerik = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            _clean_tebligat_text(rec.get("dosya_no")),
            _clean_tebligat_text(rec.get("kurum")),
            normalize_iso_date(rec.get("geldigi_tarih")),
            normalize_iso_date(rec.get("teblig_tarihi")),
            normalize_iso_date(rec.get("is_son_gunu")),
            _clean_tebligat_text(rec.get("icerik")),
            int(tebligat_id),
        ),
    )
    conn.commit()
    conn.close()


def delete_tebligat(tebligat_id: int) -> None:
    """Tebligat kaydını siler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tebligatlar WHERE id = ?", (tebligat_id,))
    conn.commit()
    conn.close()


def mark_tebligat_complete(tebligat_id: int, completed: bool) -> None:
    """Tebligat kaydını tamamlandı olarak işaretler veya işareti kaldırır."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE tebligatlar
           SET tamamlandi = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (1 if completed else 0, tebligat_id),
    )
    conn.commit()
    conn.close()
