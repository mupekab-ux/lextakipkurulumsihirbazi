# -*- coding: utf-8 -*-
"""
Dosya/Dava CRUD işlemleri ve arama fonksiyonları.
"""

from services.base import *

__all__ = [
    "add_dosya",
    "list_dosyalar",
    "get_next_buro_takip_no",
    "get_dosya",
    "update_dosya",
    "delete_case_hard",
    "get_dosya_assignees",
    "set_dosya_assignees",
    "set_archive_status",
    "fetch_dosyalar_by_color_hex",
    "get_all_dosyalar",
    "search_dosyalar",
]


def add_dosya(data: Dict[str, Any]) -> int:
    """Yeni dosya kaydı oluşturur ve finans kaydını da ekler."""
    for date_field in ("durusma_tarihi", "is_tarihi", "is_tarihi_2"):
        if data.get(date_field) in ("", None):
            data[date_field] = None
    data.setdefault("is_archived", 0)

    conn = get_connection()
    try:
        cur = conn.cursor()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = list(data.values())
        cur.execute(
            f"INSERT INTO dosyalar ({columns}) VALUES ({placeholders})",
            values,
        )
        dosya_id = cur.lastrowid
        cur.execute(
            "INSERT OR IGNORE INTO finans (dosya_id) VALUES (?)",
            (dosya_id,),
        )
        conn.commit()
        return dosya_id
    except sqlite3.Error as exc:
        conn.rollback()
        logger.exception("Dosya eklenirken hata: %s", exc)
        raise RuntimeError(
            "Dosya kaydedilirken veritabanı hatası oluştu. Lütfen girdiğiniz bilgileri kontrol edin."
        ) from exc
    finally:
        conn.close()


def list_dosyalar() -> List[sqlite3.Row]:
    """Tüm dosya kayıtlarını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM dosyalar")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_next_buro_takip_no() -> int:
    """Bir sonraki uygun büro takip numarasını döndürür."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(buro_takip_no), 0) + 1 FROM dosyalar")
    value = cur.fetchone()[0]
    conn.close()
    return int(value)


def get_dosya(dosya_id: int) -> Optional[Dict[str, Any]]:
    """Belirtilen kimliğe sahip tek bir dosya kaydını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM dosyalar WHERE id = ?", (dosya_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_dosya(dosya_id: int, data: Dict[str, Any]) -> None:
    """Belirtilen dosya kaydını günceller."""
    if not data:
        return
    # DÜZELTME: Sadece MEVCUT anahtarları normalize et, yeni anahtar EKLEME!
    for date_field in ("durusma_tarihi", "is_tarihi", "is_tarihi_2"):
        if date_field in data and data[date_field] in ("", None):
            data[date_field] = None

    conn = get_connection()
    try:
        cur = conn.cursor()
        columns = ", ".join(f"{key} = ?" for key in data.keys())
        values = list(data.values()) + [dosya_id]
        cur.execute(f"UPDATE dosyalar SET {columns} WHERE id = ?", values)
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.exception("Dosya güncellenirken hata: %s", exc)
        raise RuntimeError(
            "Dosya güncellenirken veritabanı hatası oluştu. Lütfen girdileri kontrol edin."
        ) from exc
    finally:
        conn.close()


def delete_case_hard(conn: sqlite3.Connection, dosya_id: int) -> bool:
    """İlişkili tüm kayıtlarla birlikte dosyayı kalıcı olarak siler."""

    def table_exists(name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    try:
        conn.execute("BEGIN")

        finans_id = None
        if table_exists("finans"):
            row = conn.execute(
                "SELECT id FROM finans WHERE dosya_id=?",
                (dosya_id,),
            ).fetchone()
            finans_id = row[0] if row else None

        if finans_id is not None:
            if table_exists("taksitler"):
                conn.execute("DELETE FROM taksitler WHERE finans_id=?", (finans_id,))
            if table_exists("odeme_kayitlari"):
                conn.execute("DELETE FROM odeme_kayitlari WHERE finans_id=?", (finans_id,))
            if table_exists("masraflar"):
                conn.execute("DELETE FROM masraflar WHERE finans_id=?", (finans_id,))
            if table_exists("odeme_plani"):
                conn.execute("DELETE FROM odeme_plani WHERE finans_id=?", (finans_id,))
            conn.execute("DELETE FROM finans WHERE id=?", (finans_id,))
        elif table_exists("finans"):
            conn.execute("DELETE FROM finans WHERE dosya_id=?", (dosya_id,))

        if table_exists("attachments"):
            conn.execute("DELETE FROM attachments WHERE dosya_id=?", (dosya_id,))
        if table_exists("dosya_kullanicilari"):
            conn.execute("DELETE FROM dosya_kullanicilari WHERE dosya_id=?", (dosya_id,))

        conn.execute("DELETE FROM dosyalar WHERE id=?", (dosya_id,))
        conn.commit()
        return True
    except sqlite3.Error as exc:
        conn.rollback()
        logger.exception("Dosya silinirken hata: %s", exc)
        raise


def get_dosya_assignees(dosya_id: int) -> List[Dict[str, Any]]:
    """Belirtilen dosyaya atanmış kullanıcıları döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.id, u.username, u.role, u.active
        FROM dosya_atamalar da
        JOIN users u ON u.id = da.user_id
        WHERE da.dosya_id = ?
        ORDER BY LOWER(u.username)
        """,
        (dosya_id,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def set_dosya_assignees(dosya_id: int, user_ids: Iterable[int]) -> None:
    """Dosyaya atanmış kullanıcı listesini günceller."""
    desired: Set[int] = {int(uid) for uid in user_ids if uid is not None}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM dosya_atamalar WHERE dosya_id = ?",
            (dosya_id,),
        )
        existing = {row[0] for row in cur.fetchall()}

        to_remove = existing - desired
        to_add = desired - existing

        if to_remove:
            cur.executemany(
                "DELETE FROM dosya_atamalar WHERE dosya_id = ? AND user_id = ?",
                [(dosya_id, uid) for uid in to_remove],
            )

        if to_add:
            cur.executemany(
                "INSERT OR IGNORE INTO dosya_atamalar (dosya_id, user_id) VALUES (?, ?)",
                [(dosya_id, uid) for uid in to_add],
            )

        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.exception("Atama güncellenirken hata: %s", exc)
        raise RuntimeError(
            "Atama bilgileri güncellenirken veritabanı hatası oluştu."
        ) from exc
    finally:
        conn.close()


def set_archive_status(dosya_id: int, archived: bool) -> None:
    """Dosyanın arşiv durumunu günceller."""
    update_dosya(
        dosya_id,
        {
            "is_archived": 1 if archived else 0,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def fetch_dosyalar_by_color_hex(
    hex6: str | None,
    search_text: str | None = None,
    open_only: bool | None = None,
    other_filters: Optional[Dict[str, Any]] = None,
    archived: bool = False,
    assigned_user_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Renk koduna, arama parametrelerine ve arşiv durumuna göre kayıtları döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dosya_durumlari'"
    )
    has_history = cur.fetchone() is not None

    params: Dict[str, Any] = {"is_archived": 1 if archived else 0}
    where_clauses: List[str] = ["d.is_archived = :is_archived"]

    if assigned_user_id is not None:
        params["assigned_user_id"] = int(assigned_user_id)
        where_clauses.append(
            "EXISTS (SELECT 1 FROM dosya_atamalar da WHERE da.dosya_id = d.id AND da.user_id = :assigned_user_id)"
        )

    if hex6:
        params["hex6"] = hex6
        where_clauses.append(
            "(UPPER(REPLACE(sd1.color_hex,'#','')) = :hex6 "
            "OR UPPER(REPLACE(sd2.color_hex,'#','')) = :hex6 "
            "OR UPPER(REPLACE(sa.color_hex,'#','')) = :hex6)"
        )

    durusma_period = None
    if other_filters:
        durusma_period = other_filters.get("durusma_period")

    if open_only and not archived:
        where_clauses.append(
            "NOT ("
            "UPPER(COALESCE(NULLIF(d.dava_durumu,''),'')) = 'DOSYA KAPANDI' "
            "OR UPPER(COALESCE(NULLIF(d.tekrar_dava_durumu_2,''),'')) = 'DOSYA KAPANDI'"
            ")"
        )

    if durusma_period:
        today = date.today()
        start: Optional[date] = None
        end: Optional[date] = None
        if durusma_period == "bu_hafta":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif durusma_period == "gelecek_hafta":
            start = today + timedelta(days=7 - today.weekday())
            end = start + timedelta(days=6)
        elif durusma_period == "bu_ay":
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
        if start and end:
            where_clauses.append("d.durusma_tarihi BETWEEN :durusma_start AND :durusma_end")
            params["durusma_start"] = start.isoformat()
            params["durusma_end"] = end.isoformat()

    if has_history:
        base_query = """
        WITH last_status AS (
            SELECT dd.dosya_id,
                   dd.durum AS aktif_durum,
                   MAX(dd.created_at) AS max_ts
            FROM dosya_durumlari dd
            GROUP BY dd.dosya_id
        )
        SELECT d.*,
               ls.aktif_durum AS aktif_durum,
               sa.color_hex AS status_color,
               sd1.owner AS dava_durumu_owner,
               sd2.owner AS tekrar_dava_durumu_2_owner,
               sd1.color_hex AS dava_durumu_color,
               sd2.color_hex AS tekrar_dava_durumu_2_color
        FROM dosyalar d
        LEFT JOIN last_status ls ON ls.dosya_id = d.id
        LEFT JOIN statuses sa ON sa.ad = ls.aktif_durum
        LEFT JOIN statuses sd1 ON sd1.ad = d.dava_durumu
        LEFT JOIN statuses sd2 ON sd2.ad = d.tekrar_dava_durumu_2
        """
    else:
        base_query = """
        SELECT d.*,
               COALESCE(NULLIF(d.tekrar_dava_durumu_2,''), d.dava_durumu) AS aktif_durum,
               sa.color_hex AS status_color,
               sd1.owner AS dava_durumu_owner,
               sd2.owner AS tekrar_dava_durumu_2_owner,
               sd1.color_hex AS dava_durumu_color,
               sd2.color_hex AS tekrar_dava_durumu_2_color
        FROM dosyalar d
        LEFT JOIN statuses sd1 ON sd1.ad = d.dava_durumu
        LEFT JOIN statuses sd2 ON sd2.ad = d.tekrar_dava_durumu_2
        LEFT JOIN statuses sa
          ON sa.ad = COALESCE(NULLIF(d.tekrar_dava_durumu_2,''), d.dava_durumu)
        """

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)

    base_query += " ORDER BY d.buro_takip_no"

    rows = timed_query(conn, base_query, params)
    rows_prepared: list[sqlite3.Row] = list(rows)
    result = []
    normalized_search = normalize_str(search_text) if search_text else None

    for row in rows_prepared:
        record = dict(row)
        record["status_color"] = normalize_hex(record.get("status_color"))
        record["dava_durumu_color"] = normalize_hex(record.get("dava_durumu_color"))
        record["tekrar_dava_durumu_2_color"] = normalize_hex(
            record.get("tekrar_dava_durumu_2_color")
        )
        record["dava_durumu_owner"] = resolve_owner_label(
            record.get("dava_durumu_owner"), record.get("dava_durumu_color")
        )
        record["tekrar_dava_durumu_2_owner"] = resolve_owner_label(
            record.get("tekrar_dava_durumu_2_owner"),
            record.get("tekrar_dava_durumu_2_color"),
        )
        if normalized_search:
            hay_fields = [
                "dosya_esas_no", "muvekkil_adi", "karsi_taraf", "dosya_konusu",
                "mahkeme_adi", "dava_durumu", "aciklama", "tekrar_dava_durumu_2", "aciklama_2",
            ]
            haystack = " ".join(
                normalize_str(str(record.get(field, ""))) for field in hay_fields
            )
            if normalized_search not in haystack:
                continue
        result.append(record)

    conn.close()
    return result


def get_all_dosyalar(
    archived: bool = False, assigned_user_id: int | None = None
) -> List[Dict[str, Any]]:
    """Tüm dosya kayıtlarını döndürür."""
    return fetch_dosyalar_by_color_hex(
        None,
        archived=archived,
        assigned_user_id=assigned_user_id,
    )


def search_dosyalar(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Verilen filtre sözlüğüne göre dosya kayıtlarını döndürür."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    base_query = (
        "SELECT id, buro_takip_no, dosya_esas_no, muvekkil_adi, muvekkil_rolu, "
        "karsi_taraf, dosya_konusu, mahkeme_adi, dava_acilis_tarihi, "
        "durusma_tarihi, dava_durumu, is_tarihi, aciklama, tekrar_dava_durumu_2, "
        "is_tarihi_2, aciklama_2 FROM dosyalar"
    )

    conditions: List[str] = ["is_archived = 0"]
    params: List[Any] = []

    q = filters.get("query")
    if q:
        like = f"%{q.lower()}%"
        text_fields = [
            "dosya_esas_no", "muvekkil_adi", "karsi_taraf", "dosya_konusu",
            "mahkeme_adi", "dava_durumu", "aciklama", "tekrar_dava_durumu_2", "aciklama_2",
        ]
        conditions.append(
            "(" + " OR ".join(f"LOWER({field}) LIKE ?" for field in text_fields) + ")"
        )
        params.extend([like] * len(text_fields))

    rol = filters.get("rol")
    if rol:
        conditions.append("muvekkil_rolu = ?")
        params.append(rol)

    status = filters.get("status")
    if status:
        conditions.append("dava_durumu = ?")
        params.append(status)

    period = filters.get("durusma_period")
    if period:
        today = date.today()
        start = end = None
        if period == "bu_hafta":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period == "gelecek_hafta":
            start = today + timedelta(days=7 - today.weekday())
            end = start + timedelta(days=6)
        elif period == "bu_ay":
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
        if start and end:
            conditions.append("durusma_tarihi BETWEEN ? AND ?")
            params.extend([start.isoformat(), end.isoformat()])

    if filters.get("only_open"):
        conditions.append("dava_durumu <> 'Kapandı'")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY buro_takip_no"

    cur.execute(base_query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows
