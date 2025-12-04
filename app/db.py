# -*- coding: utf-8 -*-
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # pragma: no cover - runtime import guard
    from app.utils import hash_password, iso_to_tr, normalize_hex, get_attachments_dir
except ModuleNotFoundError:  # pragma: no cover
    from utils import hash_password, iso_to_tr, normalize_hex, get_attachments_dir

DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "LexTakip")
os.makedirs(DOCS_DIR, exist_ok=True)
DB_PATH = os.path.join(DOCS_DIR, "data.db")


def timed_query(conn, sql, params=()):
    import time

    t0 = time.perf_counter()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    dt = (time.perf_counter() - t0) * 1000
    print(f"[perf] SQL took {dt:.1f} ms  -- {sql[:80]}...")
    try:
        plan = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        print("[perf] PLAN:", plan)
    except Exception:
        pass
    return rows

DEFAULT_STATUSES = [
    # SARI
    *(
        (name, "FFD700", "SARI")
        for name in [
            "BAŞVURU YAPILACAK",
            "DAVA AÇILACAK",
            "VEKALET SUNULACAK",
            "DAVA DİLEKÇESİ VERİLECEK",
            "CEVAP YAZILACAK",
            "CEVABA CEVAP YAZILACAK",
            "2. CEVAP VERİLECEK",
            "BEYAN DİLEKÇESİ YAZILACAK",
            "SAVUNMA DİLEKÇESİ YAZILACAK",
            "DELİLLER TOPLANACAK",
            "TANIK LİSTESİ YAZILACAK",
            "TALEPTE BULUNULACAK",
            "ÖN İNCELEME DURUŞMASINA GİDİLECEK",
            "İCRAYA KONULACAK",
            "ÖDEME EMRİ GÖNDERİLECEK",
            "İTİRAZ EDİLECEK",
            "TAKİP TALEBİ",
            "HACİZ TALEBİ",
            "SATIŞ TALEBİ",
            "CEZAEVİNE GİDİLECEK",
            "HAKİMLE GÖRÜŞÜLECEK",
            "MEMURLA GÖRÜŞÜLECEK",
            "SUÇ DUYURUSU YAPILACAK",
            "İFADE VERİLECEK",
            "SAVCIYLA GÖRÜŞÜLECEK",
            "GÖRÜŞME YAPILACAK",
            "İSTİNAFA BAŞVURULACAK",
            "TEMYİZE BAŞVURULACAK",
            "AYM BAŞVURULACAK",
            "DEĞİŞİK İŞ",
            # Yeni eklenenler
            "ISLAH YAPILACAK",
            "BİLİRKİŞİYE İTİRAZ EDİLECEK",
            "KARAR DÜZELTME BAŞVURUSU YAPILACAK",
            "FERAGAT DİLEKÇESİ VERİLECEK",
            "ARABULUCULUĞA BAŞVURULACAK",
            "TEDBİR TALEBİ YAPILACAK",
            "MÜDAHALE DİLEKÇESİ VERİLECEK",
            "MASRAF AVANSI YATIRILACAK",
            "İHTİYATİ HACİZ TALEBİ",
            "TEMİNAT YATIRILACAK",
            "HARÇ YATIRILACAK",
            "ŞİKAYET DİLEKÇESİ VERİLECEK",
            "UZLAŞMA TEKLİFİ YAPILACAK",
            "MAĞDUR VEKİLİ BEYANI",
            "İPTAL DAVASI AÇILACAK",
            "TAM YARGI DAVASI AÇILACAK",
            "YÜRÜTMEYİ DURDURMA TALEBİ",
            "DOSYA İNCELENECEK",
            "HESAPLAMA YAPILACAK",
            "PROTOKOL HAZIRLANACAK",
            "RAPOR HAZIRLANACAK",
            "DOSYA DEVİR ALINACAK",
            "DOSYA DEVREDİLECEK",
            "DURUŞMAYA GİDİLECEK",
            "MAZERET BİLDİRİLECEK",
            "BEYANDA BULUNULACAK",
            "UYAP'TAN TAKİP EDİLECEK",
        ]
    ),
    # TURUNCU
    *(
        (name, "FF8C00", "TURUNCU")
        for name in [
            "DURUŞMA BEKLENİYOR",
            "GEREKÇELİ KARAR BEKLENİYOR",
            "BİLİRKİŞİ RAPORU BEKLENİYOR",
            "KEŞİF BEKLENİYOR",
            "MÜZEKKERE BEKLENİYOR",
            "KESİNLEŞME SÜRESİNDE",
            "TEBLİĞ AŞAMASINDA",
            "TEMYİZ EDİLDİ",
            "İSTİNAF EDİLDİ",
            "TAHKİMDE",
            "PAYLAŞTIRMA BEKLENİYOR",
            # Yeni eklenenler
            "KARAR BEKLENİYOR",
            "ARABULUCULUK AŞAMASINDA",
            "UZLAŞMA AŞAMASINDA",
            "TEDBİR KARARI BEKLENİYOR",
            "İHTİYATİ HACİZ KARARI BEKLENİYOR",
            "DURUŞMA GÜNÜ VERİLECEK",
            "YÜRÜTMEYİ DURDURMA KARARI BEKLENİYOR",
            "SIRA CETVELİ BEKLENİYOR",
            "ARA KARAR BEKLENİYOR",
            "ESAS KARAR BEKLENİYOR",
            "TEVZİ BEKLENİYOR",
        ]
    ),
    # GARIP_TURUNCU
    *(
        (name, "CD853F", "GARIP_TURUNCU")
        for name in [
            "CEVAP BEKLENİYOR",
            "CEVABA CEVAP BEKLENİYOR",
            "SAVUNMA DİLEKÇESİ BEKLENİYOR",
            "SİGORTAYA BAŞVURULDU",
            "EKSPERTİZ BEKLENİYOR",
            # Yeni eklenenler
            "MÜVEKKİLDEN BELGE BEKLENİYOR",
            "KURUMDAN CEVAP BEKLENİYOR",
            "ÜÇÜNCÜ KİŞİDEN CEVAP BEKLENİYOR",
            "PROTOKOL İMZASI BEKLENİYOR",
            "VEKALETNAME BEKLENİYOR",
        ]
    ),
    # KIRMIZI
    ("DOSYA KAPANDI", "FF0000", "KIRMIZI"),
]


def is_case_closed(row: dict | sqlite3.Row | None) -> bool:
    """Return True when a case row is marked as closed in either status field."""

    if not row:
        return False

    def _normalize(value: Any) -> str:
        return str(value).strip().upper() if value not in (None, "") else ""

    def _value(key: str) -> Any:
        if hasattr(row, "get"):
            try:
                return row.get(key)  # type: ignore[call-arg]
            except Exception:
                pass
        try:
            return row[key]  # type: ignore[index]
        except Exception:
            return getattr(row, key, None)

    status_primary = _normalize(_value("dava_durumu"))
    status_secondary = _normalize(_value("dava_durumu_2"))
    if not status_secondary:
        status_secondary = _normalize(_value("tekrar_dava_durumu_2"))

    closed_value = "DOSYA KAPANDI"
    return status_primary == closed_value or status_secondary == closed_value


# Zaman Çizgisi: finans için ortak zaman damgası üretimi
def _finance_timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")

ATTACHMENTS_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_id INTEGER NOT NULL,
    original_name TEXT,
    stored_path TEXT,
    mime TEXT,
    size_bytes INTEGER,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
"""

ATTACHMENTS_COLUMNS = [
    ("dosya_id", "INTEGER"),
    ("original_name", "TEXT"),
    ("stored_path", "TEXT"),
    ("mime", "TEXT"),
    ("size_bytes", "INTEGER"),
    ("added_at", "TEXT"),
]

DOSYA_TIMELINE_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    user TEXT,
    type TEXT,
    title TEXT,
    body TEXT,
    FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
"""

DOSYA_TIMELINE_COLUMNS = [
    ("created_at", "TEXT"),
    ("user", "TEXT"),
    ("type", "TEXT"),
    ("title", "TEXT"),
    ("body", "TEXT"),
]

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {
        "view_all_cases": True,
        "manage_users": True,
        "can_view_finance": True,
        "can_hard_delete": True,
        "can_manage_backups": True,
    },
    "yonetici_avukat": {
        "view_all_cases": True,
        "manage_users": False,
        "can_view_finance": True,
        "can_hard_delete": False,
        "can_manage_backups": False,
    },
    "avukat": {
        "view_all_cases": False,
        "manage_users": False,
        "can_view_finance": False,
        "can_hard_delete": False,
        "can_manage_backups": False,
    },
    "stajyer": {
        "view_all_cases": False,
        "manage_users": False,
        "can_view_finance": False,
        "can_hard_delete": False,
        "can_manage_backups": False,
    },
}

PERMISSION_ACTIONS: list[str] = [
    "view_all_cases",
    "manage_users",
    "can_view_finance",
    "can_hard_delete",
    "can_manage_backups",
]

FINANS_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_id INTEGER UNIQUE,
    sozlesme_ucreti REAL,
    sozlesme_yuzdesi REAL,
    sozlesme_ucreti_cents INTEGER,
    tahsil_hedef_cents INTEGER NOT NULL DEFAULT 0,
    tahsil_edilen_cents INTEGER NOT NULL DEFAULT 0,
    masraf_toplam_cents INTEGER NOT NULL DEFAULT 0,
    masraf_tahsil_cents INTEGER NOT NULL DEFAULT 0,
    notlar TEXT,
    yuzde_is_sonu INTEGER NOT NULL DEFAULT 0,
    son_guncelleme DATETIME,
    FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
"""

FINANS_COLUMNS = [
    ("sozlesme_ucreti", "REAL"),
    ("sozlesme_yuzdesi", "REAL"),
    ("sozlesme_ucreti_cents", "INTEGER"),
    ("tahsil_hedef_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("tahsil_edilen_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("masraf_toplam_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("masraf_tahsil_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("notlar", "TEXT"),
    ("yuzde_is_sonu", "INTEGER NOT NULL DEFAULT 0"),
    ("son_guncelleme", "DATETIME"),
]

ODEME_PLAN_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finans_id INTEGER NOT NULL UNIQUE,
    taksit_sayisi INTEGER NOT NULL DEFAULT 0,
    periyot TEXT NOT NULL DEFAULT 'Ay',
    vade_gunu INTEGER NOT NULL DEFAULT 7,
    baslangic_tarihi DATE,
    aciklama TEXT,
    FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE
"""

ODEME_PLAN_COLUMNS = [
    ("taksit_sayisi", "INTEGER NOT NULL DEFAULT 0"),
    ("periyot", "TEXT NOT NULL DEFAULT 'Ay'"),
    ("vade_gunu", "INTEGER NOT NULL DEFAULT 7"),
    ("baslangic_tarihi", "DATE"),
    ("aciklama", "TEXT"),
]

MUVEKKIL_KASASI_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_id INTEGER NOT NULL,
    tarih TEXT NOT NULL,
    tutar_kurus INTEGER NOT NULL,
    islem_turu TEXT NOT NULL,
    aciklama TEXT,
    FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
"""

HARICI_MUVEKKIL_KASASI_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    harici_finans_id INTEGER NOT NULL,
    tarih TEXT NOT NULL,
    tutar_kurus INTEGER NOT NULL,
    islem_turu TEXT NOT NULL,
    aciklama TEXT,
    FOREIGN KEY(harici_finans_id) REFERENCES finans_harici(id) ON DELETE CASCADE
"""

FINANS_TIMELINE_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL,
    user TEXT,
    FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
"""

HARICI_FINANS_TIMELINE_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    harici_finans_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL,
    user TEXT,
    FOREIGN KEY(harici_finans_id) REFERENCES finans_harici(id) ON DELETE CASCADE
"""

TAKSITLER_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finans_id INTEGER NOT NULL,
    vade_tarihi DATE NOT NULL,
    tutar_cents INTEGER NOT NULL DEFAULT 0,
    durum TEXT NOT NULL DEFAULT 'Ödenecek',
    odeme_tarihi DATE,
    aciklama TEXT,
    FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE
"""

TAKSITLER_COLUMNS = [
    ("vade_tarihi", "DATE NOT NULL"),
    ("tutar_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("durum", "TEXT NOT NULL DEFAULT 'Ödenecek'"),
    ("odeme_tarihi", "DATE"),
    ("aciklama", "TEXT"),
]

ODEME_KAYIT_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finans_id INTEGER NOT NULL,
    tarih DATE NOT NULL,
    tutar_cents INTEGER NOT NULL,
    yontem TEXT,
    aciklama TEXT,
    taksit_id INTEGER,
    FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE,
    FOREIGN KEY(taksit_id) REFERENCES taksitler(id) ON DELETE CASCADE
"""

ODEME_KAYIT_COLUMNS = [
    ("tarih", "DATE NOT NULL"),
    ("tutar_cents", "INTEGER NOT NULL"),
    ("yontem", "TEXT"),
    ("aciklama", "TEXT"),
    ("taksit_id", "INTEGER"),
]

MASRAFLAR_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finans_id INTEGER NOT NULL,
    kalem TEXT NOT NULL,
    tutar_cents INTEGER NOT NULL,
    tarih DATE,
    odeme_kaynagi TEXT NOT NULL DEFAULT 'Büro',
    tahsil_durumu TEXT NOT NULL DEFAULT 'Bekliyor',
    tahsil_tarihi DATE,
    aciklama TEXT,
    FOREIGN KEY(finans_id) REFERENCES finans(id) ON DELETE CASCADE
"""

MASRAFLAR_COLUMNS = [
    ("kalem", "TEXT NOT NULL"),
    ("tutar_cents", "INTEGER NOT NULL"),
    ("tarih", "DATE"),
    ("odeme_kaynagi", "TEXT NOT NULL DEFAULT 'Büro'"),
    ("tahsil_durumu", "TEXT NOT NULL DEFAULT 'Bekliyor'"),
    ("tahsil_tarihi", "DATE"),
    ("aciklama", "TEXT"),
]

DOSYALAR_TABLE_SCHEMA = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buro_takip_no INTEGER UNIQUE,
    dosya_esas_no TEXT,
    muvekkil_adi TEXT,
    muvekkil_rolu TEXT,
    karsi_taraf TEXT,
    dosya_konusu TEXT,
    mahkeme_adi TEXT,
    dava_acilis_tarihi DATE,
    durusma_tarihi DATE,
    dava_durumu TEXT,
    is_tarihi DATE,
    aciklama TEXT,
    tekrar_dava_durumu_2 TEXT,
    is_tarihi_2 DATE,
    aciklama_2 TEXT,
    is_archived INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
"""

DOSYALAR_CREATE_SQL = f"CREATE TABLE IF NOT EXISTS dosyalar ({DOSYALAR_TABLE_SCHEMA})"
DOSYALAR_CREATE_SQL_NO_IF = f"CREATE TABLE dosyalar ({DOSYALAR_TABLE_SCHEMA})"

DOSYALAR_COLUMN_LIST = (
    "id",
    "buro_takip_no",
    "dosya_esas_no",
    "muvekkil_adi",
    "muvekkil_rolu",
    "karsi_taraf",
    "dosya_konusu",
    "mahkeme_adi",
    "dava_acilis_tarihi",
    "durusma_tarihi",
    "dava_durumu",
    "is_tarihi",
    "aciklama",
    "tekrar_dava_durumu_2",
    "is_tarihi_2",
    "aciklama_2",
    "is_archived",
    "created_at",
    "updated_at",
)

DOSYALAR_OPTIONAL_COLUMNS = [
    ("is_tarihi", "DATE"),
    ("is_tarihi_2", "DATE"),
]

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    pragmas = [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA temp_store=MEMORY",
        "PRAGMA cache_size=-200000",
        "PRAGMA mmap_size=268435456",
        "PRAGMA wal_autocheckpoint=1000",
        "PRAGMA journal_size_limit=67108864",
    ]
    for pragma in pragmas:
        try:
            conn.execute(pragma)
        except sqlite3.DatabaseError:
            continue
    return conn


def _ensure_table_columns(
    cur: sqlite3.Cursor,
    table_name: str,
    columns: list[tuple[str, str]],
) -> None:
    cur.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cur.fetchall()}
    for column, definition in columns:
        if column not in existing:
            cur.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column} {definition}"
            )


def _migrate_finans_contract_fields(cur: sqlite3.Cursor) -> None:
    """Geçmiş ``finans`` kayıtlarını yeni sözleşme alanlarına taşır."""

    cur.execute("PRAGMA table_info(finans)")
    info = cur.fetchall()
    existing = {row[1] for row in info}
    if "sozlesme_ucreti" not in existing:
        cur.execute("ALTER TABLE finans ADD COLUMN sozlesme_ucreti REAL")
        existing.add("sozlesme_ucreti")
    if "sozlesme_ucreti_cents" not in existing:
        cur.execute("ALTER TABLE finans ADD COLUMN sozlesme_ucreti_cents INTEGER")
        existing.add("sozlesme_ucreti_cents")
    if "sozlesme_yuzdesi" not in existing:
        cur.execute("ALTER TABLE finans ADD COLUMN sozlesme_yuzdesi REAL")
        existing.add("sozlesme_yuzdesi")
    if "yuzde_is_sonu" not in existing:
        cur.execute(
            "ALTER TABLE finans ADD COLUMN yuzde_is_sonu INTEGER NOT NULL DEFAULT 0"
        )
        existing.add("yuzde_is_sonu")

    if "ucret_sabit_cents" in existing:
        cur.execute(
            """
            UPDATE finans
            SET sozlesme_ucreti_cents = ucret_sabit_cents
            WHERE (sozlesme_ucreti_cents IS NULL OR sozlesme_ucreti_cents = 0)
              AND COALESCE(ucret_sabit_cents, 0) != 0
            """
        )
        cur.execute(
            """
            UPDATE finans
            SET sozlesme_ucreti = ucret_sabit_cents / 100.0
            WHERE (sozlesme_ucreti IS NULL OR ABS(sozlesme_ucreti) < 1e-9)
              AND COALESCE(ucret_sabit_cents, 0) != 0
            """
        )

    if "sozlesme_ucreti" in existing and "sozlesme_ucreti_cents" in existing:
        cur.execute(
            """
            UPDATE finans
            SET sozlesme_ucreti = sozlesme_ucreti_cents / 100.0
            WHERE sozlesme_ucreti IS NULL AND sozlesme_ucreti_cents IS NOT NULL
            """
        )
    if "yuzde_orani" in existing:
        cur.execute(
            """
            UPDATE finans
            SET sozlesme_yuzdesi = yuzde_orani
            WHERE (sozlesme_yuzdesi IS NULL OR ABS(sozlesme_yuzdesi) < 1e-9)
              AND COALESCE(yuzde_orani, 0) != 0
            """
        )

    if "yuzde_is_sonu" in existing:
        cur.execute(
            "UPDATE finans SET yuzde_is_sonu = 0 WHERE yuzde_is_sonu IS NULL"
        )


def ensure_gorevler_columns(conn: sqlite3.Connection) -> None:
    """Ensure gorevler table has all required columns for to-do system."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(gorevler)")
    columns = {row[1] for row in cur.fetchall()}

    with conn:
        if "tamamlandi" not in columns:
            cur.execute("ALTER TABLE gorevler ADD COLUMN tamamlandi INTEGER NOT NULL DEFAULT 0")
        if "tamamlanma_zamani" not in columns:
            cur.execute("ALTER TABLE gorevler ADD COLUMN tamamlanma_zamani TEXT")
        if "dosya_id" not in columns:
            cur.execute("ALTER TABLE gorevler ADD COLUMN dosya_id INTEGER")
        if "gorev_turu" not in columns:
            cur.execute("ALTER TABLE gorevler ADD COLUMN gorev_turu TEXT")


def _mark_automatic_task_completed(
    conn: sqlite3.Connection,
    dosya_id: int,
    old_state: dict[str, Any],
    user_name: str,
    task_type: str = "IS_TARIHI",
) -> None:
    """
    Dava durumu değiştiğinde otomatik görevi tamamlandı olarak işaretle.

    Bu fonksiyon, görevler tablosuna tamamlanmış bir kayıt ekler.

    Args:
        task_type: "IS_TARIHI" veya "IS_TARIHI_2"
    """
    # Eski is_tarihi, dava_durumu ve aciklama bilgilerini al
    if task_type == "IS_TARIHI_2":
        is_tarihi = old_state.get("is_tarihi_2")
        dava_durumu = old_state.get("dava_durumu_2", "")
        dosya_aciklama = old_state.get("aciklama_2", "")
        type_label = "İş Tarihi 2"
    else:
        is_tarihi = old_state.get("is_tarihi")
        dava_durumu = old_state.get("dava_durumu", "")
        dosya_aciklama = old_state.get("aciklama", "")
        type_label = "İş Tarihi"

    # Eğer is_tarihi yoksa, tamamlanacak bir görev de yok
    if not is_tarihi:
        return

    # Dava durumu çok kısa ise (yarım yazılmış) görev oluşturma
    # Bu, kullanıcının yazarken ara kayıtların görev oluşturmasını önler
    if len((dava_durumu or "").strip()) < 3:
        return

    # Dosya bilgilerini al (BN ve müvekkil için)
    cur = conn.cursor()
    cur.execute(
        "SELECT dosya_esas_no, muvekkil_adi FROM dosyalar WHERE id = ?",
        (dosya_id,),
    )
    dosya_row = cur.fetchone()
    bn = dosya_row[0] if dosya_row else ""
    muvekkil = dosya_row[1] if dosya_row else ""

    # Tamamlanmış görev kaydını oluştur
    now_str = datetime.now().isoformat(timespec="seconds")
    meta = {
        "bn": bn,
        "muvekkil": muvekkil,
        "type": type_label,
        "notes": f"Dava durumu değişti: {dava_durumu}",
        "icerik": dosya_aciklama or "",  # Dosyadaki açıklama görevin içeriğine
        "source": "auto_completed",
    }
    aciklama = f"__META__{json.dumps(meta, ensure_ascii=False)}"

    cur.execute(
        """
        INSERT INTO gorevler (
            tarih, konu, aciklama, atanan_kullanicilar, olusturan_kullanici,
            olusturma_zamani, tamamlandi, tamamlanma_zamani, dosya_id, gorev_turu
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """,
        (
            is_tarihi,
            dava_durumu or f"{type_label} Tamamlandı",
            aciklama,
            None,
            user_name,
            now_str,
            now_str,
            dosya_id,
            task_type,
        ),
    )


def ensure_finans_timestamps(conn: sqlite3.Connection) -> None:
    """Ensure the finance table exposes creation/update timestamps."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(finans)")
    columns = {row[1] for row in cur.fetchall()}
    with conn:
        if "created_at" not in columns:
            cur.execute("ALTER TABLE finans ADD COLUMN created_at DATETIME")
            cur.execute(
                "UPDATE finans SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
        if "updated_at" not in columns:
            cur.execute("ALTER TABLE finans ADD COLUMN updated_at DATETIME")
        cur.execute(
            "UPDATE finans SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
        )


def ensure_finans_harici_columns(conn: sqlite3.Connection) -> None:
    """Guarantee essential columns exist on ``finans_harici``."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(finans_harici)")
    columns_info = cur.fetchall()
    if not columns_info:
        return

    existing = {info[1] for info in columns_info}

    def _add_column(column: str, ddl: str) -> None:
        if column in existing:
            return
        conn.execute(f"ALTER TABLE finans_harici ADD COLUMN {column} {ddl}")

    with conn:
        if "sabit_ucret_cents" not in existing:
            conn.execute(
                "ALTER TABLE finans_harici ADD COLUMN sabit_ucret_cents INTEGER NOT NULL DEFAULT 0"
            )
            if "sozlesme_ucreti_cents" in existing:
                conn.execute(
                    "UPDATE finans_harici SET sabit_ucret_cents = COALESCE(sozlesme_ucreti_cents, 0)"
                )
            elif "sozlesme_ucreti" in existing:
                conn.execute(
                    "UPDATE finans_harici SET sabit_ucret_cents = CAST(ROUND(COALESCE(sozlesme_ucreti, 0) * 100) AS INTEGER)"
                )
        else:
            conn.execute(
                "UPDATE finans_harici SET sabit_ucret_cents = COALESCE(sabit_ucret_cents, 0)"
            )
            if "sozlesme_ucreti_cents" in existing:
                conn.execute(
                    """
                    UPDATE finans_harici
                       SET sabit_ucret_cents = COALESCE(sozlesme_ucreti_cents, 0)
                     WHERE sabit_ucret_cents = 0 AND COALESCE(sozlesme_ucreti_cents, 0) > 0
                    """
                )
            elif "sozlesme_ucreti" in existing:
                conn.execute(
                    """
                    UPDATE finans_harici
                       SET sabit_ucret_cents = CAST(ROUND(COALESCE(sozlesme_ucreti, 0) * 100) AS INTEGER)
                     WHERE sabit_ucret_cents = 0 AND ABS(COALESCE(sozlesme_ucreti, 0)) > 0
                    """
                )

        if "masraf_toplam_cents" not in existing:
            conn.execute(
                "ALTER TABLE finans_harici ADD COLUMN masraf_toplam_cents INTEGER NOT NULL DEFAULT 0"
            )
        else:
            conn.execute(
                "UPDATE finans_harici SET masraf_toplam_cents = COALESCE(masraf_toplam_cents, 0)"
            )

        if "masraf_tahsil_cents" not in existing:
            conn.execute(
                "ALTER TABLE finans_harici ADD COLUMN masraf_tahsil_cents INTEGER NOT NULL DEFAULT 0"
            )
        else:
            conn.execute(
                "UPDATE finans_harici SET masraf_tahsil_cents = COALESCE(masraf_tahsil_cents, 0)"
            )

        _add_column("tahsil_hedef_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column("yuzde_is_sonu", "INTEGER NOT NULL DEFAULT 0")
        _add_column("toplam_ucret_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column("kalan_bakiye_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column("has_overdue_installment", "INTEGER NOT NULL DEFAULT 0")
        _add_column("plan_taksit_sayisi", "INTEGER NOT NULL DEFAULT 0")
        _add_column("plan_periyot", "TEXT")
        _add_column("plan_vade_gunu", "INTEGER NOT NULL DEFAULT 0")
        _add_column("plan_baslangic_tarihi", "TEXT")
        _add_column("plan_aciklama", "TEXT")

        if "notlar" not in existing:
            conn.execute("ALTER TABLE finans_harici ADD COLUMN notlar TEXT")

        if "updated_at" not in existing:
            conn.execute("ALTER TABLE finans_harici ADD COLUMN updated_at DATETIME")

        conn.execute(
            "UPDATE finans_harici SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
        )


def ensure_odeme_plani_harici_columns(conn: sqlite3.Connection) -> None:
    """Ensure optional fields exist on ``odeme_plani_harici``."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(odeme_plani_harici)")
    columns_info = cur.fetchall()
    if not columns_info:
        return

    existing = {info[1] for info in columns_info}
    with conn:
        if "sira" not in existing:
            conn.execute("ALTER TABLE odeme_plani_harici ADD COLUMN sira INTEGER")
        if "odeme_tarihi" not in existing:
            conn.execute("ALTER TABLE odeme_plani_harici ADD COLUMN odeme_tarihi TEXT")
        if "aciklama" not in existing:
            conn.execute("ALTER TABLE odeme_plani_harici ADD COLUMN aciklama TEXT")
        conn.execute(
            "UPDATE odeme_plani_harici SET durum = COALESCE(NULLIF(TRIM(durum), ''), 'Ödenecek')"
        )


def ensure_masraflar_harici_columns(conn: sqlite3.Connection) -> None:
    """Ensure optional fields exist on ``masraflar_harici``."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(masraflar_harici)")
    columns_info = cur.fetchall()
    if not columns_info:
        return

    existing = {info[1] for info in columns_info}
    with conn:
        if "tahsil_durumu" not in existing:
            conn.execute(
                "ALTER TABLE masraflar_harici ADD COLUMN tahsil_durumu TEXT DEFAULT 'Bekliyor'"
            )
        if "tahsil_tarihi" not in existing:
            conn.execute("ALTER TABLE masraflar_harici ADD COLUMN tahsil_tarihi TEXT")
        if "odeme_kaynagi" not in existing:
            conn.execute(
                "ALTER TABLE masraflar_harici ADD COLUMN odeme_kaynagi TEXT DEFAULT 'Büro'"
            )
        conn.execute(
            "UPDATE masraflar_harici SET tahsil_durumu = COALESCE(NULLIF(TRIM(tahsil_durumu), ''), 'Bekliyor')"
        )


def ensure_odemeler_harici_columns(conn: sqlite3.Connection) -> None:
    """Ensure payment rows keep the expected nullable columns."""

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(odemeler_harici)")
    columns_info = cur.fetchall()
    if not columns_info:
        return

    existing = {info[1] for info in columns_info}
    with conn:
        if "tarih" not in existing:
            conn.execute("ALTER TABLE odemeler_harici ADD COLUMN tarih TEXT")
        if "yontem" not in existing:
            conn.execute("ALTER TABLE odemeler_harici ADD COLUMN yontem TEXT")
        if "aciklama" not in existing:
            conn.execute("ALTER TABLE odemeler_harici ADD COLUMN aciklama TEXT")
        if "tahsil_durumu" not in existing:
            conn.execute(
                "ALTER TABLE odemeler_harici ADD COLUMN tahsil_durumu TEXT DEFAULT 'Bekliyor'"
            )
        if "tahsil_tarihi" not in existing:
            conn.execute("ALTER TABLE odemeler_harici ADD COLUMN tahsil_tarihi TEXT")
        if "plan_taksit_id" not in existing:
            conn.execute("ALTER TABLE odemeler_harici ADD COLUMN plan_taksit_id INTEGER")


def ensure_tebligatlar_columns(conn: sqlite3.Connection) -> None:
    """Ensure tebligatlar table has tamamlandi column."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tebligatlar)")
    columns = {row[1] for row in cur.fetchall()}

    with conn:
        if "tamamlandi" not in columns:
            cur.execute("ALTER TABLE tebligatlar ADD COLUMN tamamlandi INTEGER DEFAULT 0")


def ensure_arabuluculuk_columns(conn: sqlite3.Connection) -> None:
    """Ensure arabuluculuk table has tamamlandi column."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(arabuluculuk)")
    columns = {row[1] for row in cur.fetchall()}

    with conn:
        if "tamamlandi" not in columns:
            cur.execute("ALTER TABLE arabuluculuk ADD COLUMN tamamlandi INTEGER DEFAULT 0")


def setup_tebligat_gorev_triggers(conn: sqlite3.Connection) -> None:
    """Setup triggers to sync tebligatlar with gorevler table."""
    cur = conn.cursor()

    # Tebligat INSERT trigger - görev oluştur
    cur.execute("DROP TRIGGER IF EXISTS tr_tebligat_insert_gorev")
    cur.execute("""
        CREATE TRIGGER tr_tebligat_insert_gorev
        AFTER INSERT ON tebligatlar
        WHEN NEW.is_son_gunu IS NOT NULL AND NEW.is_son_gunu != ''
        BEGIN
            INSERT INTO gorevler (tarih, konu, aciklama, kaynak_turu, olusturan_kullanici, olusturma_zamani, tamamlandi, gorev_turu)
            VALUES (
                NEW.is_son_gunu,
                'Tebligat',
                '__META__' || json_object('tebligat_id', NEW.id, 'dosya_no', NEW.dosya_no, 'icerik', NEW.icerik, 'bn', NEW.kurum, 'type', 'Tebligat'),
                'TEBLIGAT',
                'system',
                datetime('now'),
                COALESCE(NEW.tamamlandi, 0),
                'TEBLIGAT'
            );
        END
    """)

    # Tebligat UPDATE trigger - görev güncelle
    cur.execute("DROP TRIGGER IF EXISTS tr_tebligat_update_gorev")
    cur.execute("""
        CREATE TRIGGER tr_tebligat_update_gorev
        AFTER UPDATE ON tebligatlar
        BEGIN
            UPDATE gorevler
            SET tarih = NEW.is_son_gunu,
                konu = 'Tebligat',
                aciklama = '__META__' || json_object('tebligat_id', NEW.id, 'dosya_no', NEW.dosya_no, 'icerik', NEW.icerik, 'bn', NEW.kurum, 'type', 'Tebligat'),
                tamamlandi = COALESCE(NEW.tamamlandi, 0)
            WHERE gorev_turu = 'TEBLIGAT'
              AND (aciklama LIKE '%"tebligat_id":' || OLD.id || ',%'
                   OR aciklama LIKE '%"tebligat_id": ' || OLD.id || ',%');
        END
    """)

    # Tebligat DELETE trigger - görev sil
    cur.execute("DROP TRIGGER IF EXISTS tr_tebligat_delete_gorev")
    cur.execute("""
        CREATE TRIGGER tr_tebligat_delete_gorev
        AFTER DELETE ON tebligatlar
        BEGIN
            DELETE FROM gorevler
            WHERE gorev_turu = 'TEBLIGAT'
              AND (aciklama LIKE '%"tebligat_id":' || OLD.id || ',%'
                   OR aciklama LIKE '%"tebligat_id": ' || OLD.id || ',%');
        END
    """)

    conn.commit()


def setup_arabuluculuk_gorev_triggers(conn: sqlite3.Connection) -> None:
    """Setup triggers to sync arabuluculuk with gorevler table."""
    cur = conn.cursor()

    # Arabuluculuk INSERT trigger - görev oluştur
    cur.execute("DROP TRIGGER IF EXISTS tr_arabuluculuk_insert_gorev")
    cur.execute("""
        CREATE TRIGGER tr_arabuluculuk_insert_gorev
        AFTER INSERT ON arabuluculuk
        WHEN NEW.toplanti_tarihi IS NOT NULL AND NEW.toplanti_tarihi != ''
        BEGIN
            INSERT INTO gorevler (tarih, konu, aciklama, kaynak_turu, olusturan_kullanici, olusturma_zamani, tamamlandi, gorev_turu)
            VALUES (
                NEW.toplanti_tarihi,
                'Arabuluculuk',
                '__META__' || json_object('arabuluculuk_id', NEW.id, 'davaci', NEW.davaci, 'davali', NEW.davali, 'konu', NEW.konu, 'saat', NEW.toplanti_saati, 'bn', NEW.davaci, 'type', 'Arabuluculuk'),
                'ARABULUCULUK',
                'system',
                datetime('now'),
                COALESCE(NEW.tamamlandi, 0),
                'ARABULUCULUK'
            );
        END
    """)

    # Arabuluculuk UPDATE trigger - görev güncelle
    cur.execute("DROP TRIGGER IF EXISTS tr_arabuluculuk_update_gorev")
    cur.execute("""
        CREATE TRIGGER tr_arabuluculuk_update_gorev
        AFTER UPDATE ON arabuluculuk
        BEGIN
            UPDATE gorevler
            SET tarih = NEW.toplanti_tarihi,
                konu = 'Arabuluculuk',
                aciklama = '__META__' || json_object('arabuluculuk_id', NEW.id, 'davaci', NEW.davaci, 'davali', NEW.davali, 'konu', NEW.konu, 'saat', NEW.toplanti_saati, 'bn', NEW.davaci, 'type', 'Arabuluculuk'),
                tamamlandi = COALESCE(NEW.tamamlandi, 0)
            WHERE gorev_turu = 'ARABULUCULUK'
              AND (aciklama LIKE '%"arabuluculuk_id":' || OLD.id || ',%'
                   OR aciklama LIKE '%"arabuluculuk_id": ' || OLD.id || ',%');
        END
    """)

    # Arabuluculuk DELETE trigger - görev sil
    cur.execute("DROP TRIGGER IF EXISTS tr_arabuluculuk_delete_gorev")
    cur.execute("""
        CREATE TRIGGER tr_arabuluculuk_delete_gorev
        AFTER DELETE ON arabuluculuk
        BEGIN
            DELETE FROM gorevler
            WHERE gorev_turu = 'ARABULUCULUK'
              AND (aciklama LIKE '%"arabuluculuk_id":' || OLD.id || ',%'
                   OR aciklama LIKE '%"arabuluculuk_id": ' || OLD.id || ',%');
        END
    """)

    conn.commit()


def migrate_existing_tebligatlar_to_gorevler(conn: sqlite3.Connection) -> None:
    """Migrate existing tebligatlar to gorevler table."""
    cur = conn.cursor()

    # Sadece henüz migrate edilmemiş tebligatları al
    cur.execute("""
        SELECT t.id, t.is_son_gunu, t.kurum, t.dosya_no, t.icerik, COALESCE(t.tamamlandi, 0)
        FROM tebligatlar t
        WHERE t.is_son_gunu IS NOT NULL AND t.is_son_gunu != ''
          AND NOT EXISTS (
              SELECT 1 FROM gorevler g
              WHERE g.gorev_turu = 'TEBLIGAT'
                AND g.aciklama LIKE '%"tebligat_id":' || t.id || ',%'
          )
    """)

    rows = cur.fetchall()
    for row in rows:
        teb_id, tarih, kurum, dosya_no, icerik, tamamlandi = row
        import json
        # separators ile boşluksuz format (SQLite json_object ile uyumlu)
        meta = json.dumps({"tebligat_id": teb_id, "dosya_no": dosya_no, "icerik": icerik, "bn": kurum, "type": "Tebligat"}, separators=(',', ':'))
        cur.execute("""
            INSERT INTO gorevler (tarih, konu, aciklama, kaynak_turu, olusturan_kullanici, olusturma_zamani, tamamlandi, gorev_turu)
            VALUES (?, ?, ?, 'TEBLIGAT', 'migration', datetime('now'), ?, 'TEBLIGAT')
        """, (tarih, 'Tebligat', '__META__' + meta, tamamlandi))

    conn.commit()


def migrate_existing_arabuluculuk_to_gorevler(conn: sqlite3.Connection) -> None:
    """Migrate existing arabuluculuk to gorevler table."""
    cur = conn.cursor()

    # Sadece henüz migrate edilmemiş arabuluculukları al
    cur.execute("""
        SELECT a.id, a.toplanti_tarihi, a.arb_adi, a.davaci, a.davali, a.konu, a.toplanti_saati, COALESCE(a.tamamlandi, 0)
        FROM arabuluculuk a
        WHERE a.toplanti_tarihi IS NOT NULL AND a.toplanti_tarihi != ''
          AND NOT EXISTS (
              SELECT 1 FROM gorevler g
              WHERE g.gorev_turu = 'ARABULUCULUK'
                AND g.aciklama LIKE '%"arabuluculuk_id":' || a.id || ',%'
          )
    """)

    rows = cur.fetchall()
    for row in rows:
        arb_id, tarih, arb_adi, davaci, davali, konu, saat, tamamlandi = row
        import json
        # separators ile boşluksuz format (SQLite json_object ile uyumlu)
        meta = json.dumps({"arabuluculuk_id": arb_id, "davaci": davaci, "davali": davali, "konu": konu, "saat": saat, "bn": davaci, "type": "Arabuluculuk"}, separators=(',', ':'))
        cur.execute("""
            INSERT INTO gorevler (tarih, konu, aciklama, kaynak_turu, olusturan_kullanici, olusturma_zamani, tamamlandi, gorev_turu)
            VALUES (?, ?, ?, 'ARABULUCULUK', 'migration', datetime('now'), ?, 'ARABULUCULUK')
        """, (tarih, 'Arabuluculuk', '__META__' + meta, tamamlandi))

    conn.commit()


def cleanup_orphaned_gorevler(conn: sqlite3.Connection) -> None:
    """Kaynak tablosunda karşılığı olmayan görevleri temizle."""
    cur = conn.cursor()

    # Tebligat görevleri - tebligatlar tablosunda karşılığı olmayanları sil
    cur.execute("""
        DELETE FROM gorevler
        WHERE gorev_turu = 'TEBLIGAT'
          AND NOT EXISTS (
              SELECT 1 FROM tebligatlar t
              WHERE gorevler.aciklama LIKE '%"tebligat_id":' || t.id || ',%'
                 OR gorevler.aciklama LIKE '%"tebligat_id": ' || t.id || ',%'
          )
    """)

    # Arabuluculuk görevleri - arabuluculuk tablosunda karşılığı olmayanları sil
    cur.execute("""
        DELETE FROM gorevler
        WHERE gorev_turu = 'ARABULUCULUK'
          AND NOT EXISTS (
              SELECT 1 FROM arabuluculuk a
              WHERE gorevler.aciklama LIKE '%"arabuluculuk_id":' || a.id || ',%'
                 OR gorevler.aciklama LIKE '%"arabuluculuk_id": ' || a.id || ',%'
          )
    """)

    # Kısa/anlamsız konu ile oluşturulmuş hatalı görevleri temizle
    # (Kullanıcı dava durumu yazarken ara kayıtlardan oluşan görevler)
    cur.execute("""
        DELETE FROM gorevler
        WHERE tamamlandi = 1
          AND gorev_turu IS NULL
          AND LENGTH(TRIM(konu)) < 3
          AND aciklama LIKE '%"source": "auto_completed"%'
    """)

    conn.commit()


def update_existing_gorevler_format(conn: sqlite3.Connection) -> None:
    """Mevcut TEBLIGAT ve ARABULUCULUK görevlerinin konu ve bn alanlarını güncelle."""
    import json as json_module
    cur = conn.cursor()

    # Tebligat görevlerini güncelle - konu alanını "Tebligat" yap
    cur.execute("""
        UPDATE gorevler SET konu = 'Tebligat'
        WHERE gorev_turu = 'TEBLIGAT' AND konu != 'Tebligat'
    """)

    # Arabuluculuk görevlerini güncelle - konu alanını "Arabuluculuk" yap
    cur.execute("""
        UPDATE gorevler SET konu = 'Arabuluculuk'
        WHERE gorev_turu = 'ARABULUCULUK' AND konu != 'Arabuluculuk'
    """)

    # Tebligat görevlerinin meta JSON'una bn alanı ekle
    cur.execute("""
        SELECT g.id, g.aciklama, t.kurum
        FROM gorevler g
        JOIN tebligatlar t ON g.aciklama LIKE '%"tebligat_id":' || t.id || ',%'
                          OR g.aciklama LIKE '%"tebligat_id": ' || t.id || ',%'
        WHERE g.gorev_turu = 'TEBLIGAT'
          AND g.aciklama NOT LIKE '%"bn":%'
    """)
    for row in cur.fetchall():
        gorev_id, aciklama, kurum = row
        if aciklama and aciklama.startswith("__META__"):
            try:
                meta = json_module.loads(aciklama[8:])
                meta["bn"] = kurum
                new_aciklama = "__META__" + json_module.dumps(meta, separators=(',', ':'))
                cur.execute("UPDATE gorevler SET aciklama = ? WHERE id = ?", (new_aciklama, gorev_id))
            except (json_module.JSONDecodeError, ValueError):
                pass

    # Arabuluculuk görevlerinin meta JSON'una bn alanı ekle
    cur.execute("""
        SELECT g.id, g.aciklama, a.davaci
        FROM gorevler g
        JOIN arabuluculuk a ON g.aciklama LIKE '%"arabuluculuk_id":' || a.id || ',%'
                           OR g.aciklama LIKE '%"arabuluculuk_id": ' || a.id || ',%'
        WHERE g.gorev_turu = 'ARABULUCULUK'
          AND g.aciklama NOT LIKE '%"bn":%'
    """)
    for row in cur.fetchall():
        gorev_id, aciklama, davaci = row
        if aciklama and aciklama.startswith("__META__"):
            try:
                meta = json_module.loads(aciklama[8:])
                meta["bn"] = davaci
                new_aciklama = "__META__" + json_module.dumps(meta, separators=(',', ':'))
                cur.execute("UPDATE gorevler SET aciklama = ? WHERE id = ?", (new_aciklama, gorev_id))
            except (json_module.JSONDecodeError, ValueError):
                pass

    conn.commit()


def migrate_harici_finans(conn: sqlite3.Connection) -> None:
    """Create the standalone finance tables if they do not exist."""

    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finans_harici (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                harici_bn TEXT,
                harici_muvekkil TEXT,
                harici_esas_no TEXT,
                sabit_ucret_cents INTEGER NOT NULL DEFAULT 0,
                yuzde_orani REAL DEFAULT 0,
                tahsil_edilen_cents INTEGER DEFAULT 0,
                masraf_toplam_cents INTEGER DEFAULT 0,
                masraf_tahsil_cents INTEGER DEFAULT 0,
                tahsil_hedef_cents INTEGER NOT NULL DEFAULT 0,
                yuzde_is_sonu INTEGER NOT NULL DEFAULT 0,
                toplam_ucret_cents INTEGER NOT NULL DEFAULT 0,
                kalan_bakiye_cents INTEGER NOT NULL DEFAULT 0,
                has_overdue_installment INTEGER NOT NULL DEFAULT 0,
                notlar TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odeme_plani_harici (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                harici_finans_id INTEGER NOT NULL,
                vade_tarihi TEXT,
                tutar_cents INTEGER NOT NULL DEFAULT 0,
                durum TEXT DEFAULT 'bekliyor',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(harici_finans_id) REFERENCES finans_harici(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odemeler_harici (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                harici_finans_id INTEGER NOT NULL,
                tarih TEXT,
                tutar_cents INTEGER NOT NULL DEFAULT 0,
                tahsil_durumu TEXT DEFAULT 'Bekliyor',
                tahsil_tarihi TEXT,
                yontem TEXT,
                aciklama TEXT,
                plan_taksit_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(harici_finans_id) REFERENCES finans_harici(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "UPDATE finans_harici SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "UPDATE finans_harici SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "UPDATE odeme_plani_harici SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "UPDATE odeme_plani_harici SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "UPDATE odemeler_harici SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "UPDATE odemeler_harici SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
        )


def ensure_tebligatlar_table(cur_or_conn: sqlite3.Cursor | sqlite3.Connection) -> None:
    """Ensure that the ``tebligatlar`` table and indexes exist."""

    if isinstance(cur_or_conn, sqlite3.Connection):
        cursor = cur_or_conn.cursor()
    else:
        cursor = cur_or_conn

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tebligatlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_no TEXT,
            kurum TEXT,
            geldigi_tarih TEXT,
            teblig_tarihi TEXT,
            is_son_gunu TEXT,
            icerik TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tebligatlar_tarih ON tebligatlar(is_son_gunu)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tebligatlar_dosya ON tebligatlar(dosya_no)"
    )


def ensure_arabuluculuk_table(cur_or_conn: sqlite3.Cursor | sqlite3.Connection) -> None:
    """Ensure that the ``arabuluculuk`` table and indexes exist."""

    if isinstance(cur_or_conn, sqlite3.Connection):
        cursor = cur_or_conn.cursor()
    else:
        cursor = cur_or_conn

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS arabuluculuk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            davaci TEXT,
            davali TEXT,
            arb_adi TEXT,
            arb_tel TEXT,
            toplanti_tarihi TEXT,
            toplanti_saati TEXT,
            konu TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_arb_tarih ON arabuluculuk(toplanti_tarihi)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_arb_ad ON arabuluculuk(arb_adi)"
    )

def _ensure_dosyalar_schema(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    """Ensure the ``dosyalar`` tablosu, ``muvekkil_rolu`` alanında kısıt olmadan oluşturulmuş olsun."""

    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='dosyalar'"
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(DOSYALAR_CREATE_SQL)
    else:
        existing_sql = row[0] or ""
        if "CHECK" in existing_sql.upper() and "MUVEKKIL_ROLU" in existing_sql.upper():
            columns = ", ".join(DOSYALAR_COLUMN_LIST)
            conn.execute("PRAGMA foreign_keys=OFF")
            try:
                cur.execute("ALTER TABLE dosyalar RENAME TO dosyalar_old")
                cur.execute(DOSYALAR_CREATE_SQL_NO_IF)
                cur.execute(
                    f"INSERT INTO dosyalar ({columns}) SELECT {columns} FROM dosyalar_old"
                )
                cur.execute("DROP TABLE dosyalar_old")
            finally:
                conn.execute("PRAGMA foreign_keys=ON")

    cur.execute("PRAGMA table_info(dosyalar)")
    columns = {info[1] for info in cur.fetchall()}
    if "is_archived" not in columns:
        cur.execute("ALTER TABLE dosyalar ADD COLUMN is_archived INTEGER DEFAULT 0")


def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    _ensure_dosyalar_schema(conn, cur)
    _ensure_table_columns(cur, "dosyalar", DOSYALAR_OPTIONAL_COLUMNS)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ayarlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        )
        """
    )

    cur.execute(
        "DELETE FROM ayarlar WHERE key = ?",
        ("allow_lawyers_finance_tab",),
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT UNIQUE,
            color_hex TEXT,
            owner TEXT
        )
        """
    )

    cur.execute(f"CREATE TABLE IF NOT EXISTS attachments ({ATTACHMENTS_TABLE_SCHEMA})")
    _ensure_table_columns(cur, "attachments", ATTACHMENTS_COLUMNS)

    try:
        cur.execute("PRAGMA table_info(attachments)")
        columns = {row[1] for row in cur.fetchall()}
        if "path" in columns:
            migrate_cursor = cur.execute(
                "SELECT id, path, stored_path, original_name FROM attachments"
            )
            base_dir = get_attachments_dir()
            updates: list[tuple[str, str, int]] = []
            name_updates: list[tuple[str, int]] = []
            for row_id, path_value, stored_path, original_name in migrate_cursor.fetchall():
                new_stored = stored_path
                if (not new_stored) and path_value:
                    try:
                        relative = _normalize_attachment_path(base_dir, path_value)
                    except Exception:
                        relative = path_value
                    new_stored = relative
                new_name = original_name
                if (not new_name) and path_value:
                    new_name = os.path.basename(path_value)
                if new_stored and new_stored != stored_path:
                    updates.append((new_stored, new_name or "", int(row_id)))
                elif new_name and new_name != original_name:
                    name_updates.append((new_name, int(row_id)))
            for stored_value, original_name, row_id in updates:
                cur.execute(
                    "UPDATE attachments SET stored_path = ?, original_name = ? WHERE id = ?",
                    (stored_value, original_name, row_id),
                )
            for original_name, row_id in name_updates:
                cur.execute(
                    "UPDATE attachments SET original_name = ? WHERE id = ?",
                    (original_name, row_id),
                )
    except Exception:
        # Sessizce yoksay – eski kolonlar yine de okunabilir durumda kalacak.
        pass

    cur.execute("PRAGMA table_info(custom_tabs)")
    if not cur.fetchall():
        cur.execute(
            """
            CREATE TABLE custom_tabs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    cur.execute("PRAGMA table_info(custom_tabs_dosyalar)")
    if not cur.fetchall():
        cur.execute(
            """
            CREATE TABLE custom_tabs_dosyalar (
                custom_tab_id INTEGER NOT NULL,
                dosya_id INTEGER NOT NULL,
                PRIMARY KEY (custom_tab_id, dosya_id),
                FOREIGN KEY(custom_tab_id) REFERENCES custom_tabs(id) ON DELETE CASCADE,
                FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE
            )
            """
        )

    cur.execute(
        f"CREATE TABLE IF NOT EXISTS dosya_timeline ({DOSYA_TIMELINE_TABLE_SCHEMA})"
    )
    _ensure_table_columns(cur, "dosya_timeline", DOSYA_TIMELINE_COLUMNS)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_dosya_timeline_dosya_id ON dosya_timeline(dosya_id)"
    )

    cur.execute(f"CREATE TABLE IF NOT EXISTS finans ({FINANS_TABLE_SCHEMA})")
    _ensure_table_columns(cur, "finans", FINANS_COLUMNS)
    _migrate_finans_contract_fields(cur)

    cur.execute(f"CREATE TABLE IF NOT EXISTS odeme_plani ({ODEME_PLAN_TABLE_SCHEMA})")
    _ensure_table_columns(cur, "odeme_plani", ODEME_PLAN_COLUMNS)

    cur.execute(f"CREATE TABLE IF NOT EXISTS taksitler ({TAKSITLER_TABLE_SCHEMA})")
    _ensure_table_columns(cur, "taksitler", TAKSITLER_COLUMNS)

    cur.execute(
        f"CREATE TABLE IF NOT EXISTS odeme_kayitlari ({ODEME_KAYIT_TABLE_SCHEMA})"
    )
    _ensure_table_columns(cur, "odeme_kayitlari", ODEME_KAYIT_COLUMNS)

    cur.execute(f"CREATE TABLE IF NOT EXISTS masraflar ({MASRAFLAR_TABLE_SCHEMA})")
    _ensure_table_columns(cur, "masraflar", MASRAFLAR_COLUMNS)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS masraflar_harici(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            harici_finans_id INTEGER NOT NULL,
            tarih TEXT,
            kalem TEXT,
            tutar_cents INTEGER,
            tahsil_cents INTEGER,
            aciklama TEXT,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(harici_finans_id) REFERENCES finans_harici(id) ON DELETE CASCADE
        )
        """
    )

    ensure_tebligatlar_table(cur)
    ensure_arabuluculuk_table(cur)
    cur.execute(f"CREATE TABLE IF NOT EXISTS muvekkil_kasasi ({MUVEKKIL_KASASI_TABLE_SCHEMA})")
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS harici_muvekkil_kasasi ({HARICI_MUVEKKIL_KASASI_TABLE_SCHEMA})"
    )
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS finans_timeline ({FINANS_TIMELINE_TABLE_SCHEMA})"
    )
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS harici_finans_timeline ({HARICI_FINANS_TIMELINE_TABLE_SCHEMA})"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gorevler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            konu TEXT NOT NULL,
            aciklama TEXT,
            atanan_kullanicilar TEXT,
            kaynak_turu TEXT NOT NULL DEFAULT 'MANUEL',
            olusturan_kullanici TEXT,
            olusturma_zamani TEXT NOT NULL,
            tamamlandi INTEGER NOT NULL DEFAULT 0,
            tamamlanma_zamani TEXT,
            dosya_id INTEGER,
            gorev_turu TEXT
        )
        """
    )
    ensure_gorevler_columns(conn)
    ensure_finans_timestamps(conn)
    migrate_harici_finans(conn)
    ensure_finans_harici_columns(conn)
    ensure_odeme_plani_harici_columns(conn)
    ensure_masraflar_harici_columns(conn)
    ensure_odemeler_harici_columns(conn)

    # Tebligatlar ve Arabuluculuk tamamlandi sütunları
    ensure_tebligatlar_columns(conn)
    ensure_arabuluculuk_columns(conn)

    # Görev senkronizasyonu için trigger'lar
    setup_tebligat_gorev_triggers(conn)
    setup_arabuluculuk_gorev_triggers(conn)

    # Mevcut verileri görevlere migrate et
    migrate_existing_tebligatlar_to_gorevler(conn)
    migrate_existing_arabuluculuk_to_gorevler(conn)

    # Artık kaynak kaydı olmayan görevleri temizle
    cleanup_orphaned_gorevler(conn)

    # Mevcut görevlerin konu ve bn alanlarını güncelle
    update_existing_gorevler_format(conn)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            allowed INTEGER NOT NULL,
            UNIQUE(role, action)
        )
        """
    )

    for role, actions in DEFAULT_ROLE_PERMISSIONS.items():
        for action, allowed in actions.items():
            cur.execute(
                """
                INSERT OR IGNORE INTO permissions (role, action, allowed)
                VALUES (?, ?, ?)
                """,
                (role, action, 1 if allowed else 0),
            )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dosya_atamalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dosya_id, user_id),
            FOREIGN KEY(dosya_id) REFERENCES dosyalar(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            target_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    cur.executemany(
        "INSERT OR IGNORE INTO statuses (ad, color_hex, owner) VALUES (?, ?, ?)",
        [
            (name, normalize_hex(color) or color, owner)
            for name, color, owner in DEFAULT_STATUSES
        ],
    )

    cur.execute(
        "INSERT OR IGNORE INTO finans (dosya_id) SELECT id FROM dosyalar"
    )

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, 1)",
            ("admin", hash_password("admin"), "admin"),
        )

    # Eski sistem görevlerini temizle (IS_TARIHI, IS_TARIHI_2, DURUSMA)
    # Bu görevler artık dosyalar tablosundan okunuyor, gorevler tablosunda tutulmamalı
    cur.execute(
        """
        DELETE FROM gorevler
        WHERE gorev_turu IN ('IS_TARIHI', 'IS_TARIHI_2', 'DURUSMA')
            AND (tamamlandi = 0 OR tamamlandi IS NULL)
        """
    )

    # Change log tablosu - değişiklik tespiti için
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Dosyalar tablosu trigger'ları
    cur.execute("DROP TRIGGER IF EXISTS tr_dosyalar_insert")
    cur.execute("DROP TRIGGER IF EXISTS tr_dosyalar_update")
    cur.execute("DROP TRIGGER IF EXISTS tr_dosyalar_delete")
    cur.execute(
        """
        CREATE TRIGGER tr_dosyalar_insert AFTER INSERT ON dosyalar
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('dosyalar');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_dosyalar_update AFTER UPDATE ON dosyalar
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('dosyalar');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_dosyalar_delete AFTER DELETE ON dosyalar
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('dosyalar');
        END
        """
    )

    # Gorevler tablosu trigger'ları
    cur.execute("DROP TRIGGER IF EXISTS tr_gorevler_insert")
    cur.execute("DROP TRIGGER IF EXISTS tr_gorevler_update")
    cur.execute("DROP TRIGGER IF EXISTS tr_gorevler_delete")
    cur.execute(
        """
        CREATE TRIGGER tr_gorevler_insert AFTER INSERT ON gorevler
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('gorevler');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_gorevler_update AFTER UPDATE ON gorevler
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('gorevler');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_gorevler_delete AFTER DELETE ON gorevler
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('gorevler');
        END
        """
    )

    # Finans tablosu trigger'ları
    cur.execute("DROP TRIGGER IF EXISTS tr_finans_insert")
    cur.execute("DROP TRIGGER IF EXISTS tr_finans_update")
    cur.execute("DROP TRIGGER IF EXISTS tr_finans_delete")
    cur.execute(
        """
        CREATE TRIGGER tr_finans_insert AFTER INSERT ON finans
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('finans');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_finans_update AFTER UPDATE ON finans
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('finans');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER tr_finans_delete AFTER DELETE ON finans
        BEGIN
            INSERT INTO change_log (table_name) VALUES ('finans');
        END
        """
    )

    # ADIM 1: Dava durumu boşsa is_tarihi ve aciklama sıfırla (uygulama başlangıcında)
    # Mevcut tutarsız verileri düzelt
    cur.execute(
        """
        UPDATE dosyalar
        SET is_tarihi = NULL, aciklama = NULL
        WHERE (dava_durumu IS NULL OR dava_durumu = '')
        AND (is_tarihi IS NOT NULL OR aciklama IS NOT NULL)
        """
    )
    cur.execute(
        """
        UPDATE dosyalar
        SET is_tarihi_2 = NULL, aciklama_2 = NULL
        WHERE (tekrar_dava_durumu_2 IS NULL OR tekrar_dava_durumu_2 = '')
        AND (is_tarihi_2 IS NOT NULL OR aciklama_2 IS NOT NULL)
        """
    )

    conn.commit()
    conn.close()


def _normalize_attachment_path(base_dir: Path, path_value: str) -> str:
    """Normalize stored attachment path to be relative to the base directory."""

    candidate = Path(path_value)
    try:
        candidate = candidate.resolve()
    except Exception:
        candidate = Path(path_value)
    base_dir = base_dir.resolve()
    try:
        relative = candidate.relative_to(base_dir)
    except ValueError:
        relative = candidate.name if not candidate.is_dir() else candidate.as_posix()
    return relative.as_posix() if isinstance(relative, Path) else str(relative)


def get_timeline_for_dosya(dosya_id: int) -> list[dict]:
    """Fetch timeline entries for ``dosya_id`` ordered by creation time."""

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT id, dosya_id, created_at, user, type, title, body
              FROM dosya_timeline
             WHERE dosya_id = ?
             ORDER BY COALESCE(created_at, ''), id
            """,
            (dosya_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_timeline_entry(
    dosya_id: int,
    user: str,
    entry_type: str,
    title: str,
    body: str,
    created_at: Any | None = None,
) -> None:
    """Insert a timeline entry for ``dosya_id``."""

    normalized_timestamp = _normalize_timeline_timestamp(created_at)
    conn = get_connection()
    try:
        with conn:
            if normalized_timestamp is None:
                conn.execute(
                    """
                    INSERT INTO dosya_timeline (dosya_id, user, type, title, body)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (dosya_id, user, entry_type, title or "", body or ""),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO dosya_timeline (
                        dosya_id,
                        user,
                        type,
                        title,
                        body,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dosya_id,
                        user,
                        entry_type,
                        title or "",
                        body or "",
                        normalized_timestamp,
                    ),
                )
    finally:
        conn.close()


def add_auto_timeline_entry_for_changes(
    conn,
    dosya_id: int,
    user_name: str,
    changes: list[tuple[str, Any, Any]],
) -> None:
    """Append an automatic timeline entry describing tracked field changes."""

    if not changes:
        return

    field_labels: dict[str, tuple[str, bool]] = {
        "dava_durumu": ("Dava durumu", False),
        "dava_durumu_2": ("Dava durumu 2", False),
        "aciklama": ("Açıklama", False),
        "aciklama_2": ("Açıklama 2", False),
        "is_tarihi": ("İş tarihi", True),
        "is_tarihi_2": ("İş tarihi 2", True),
        "durusma_tarihi": ("Duruşma tarihi", True),
    }

    def _format_value(value: Any, is_date: bool) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                return ""
            if is_date:
                return iso_to_tr(trimmed) or trimmed
            return trimmed
        return str(value)

    timestamp = datetime.now()
    normalized_ts = _normalize_timeline_timestamp(timestamp)

    needs_close = conn is None
    local_conn = conn or get_connection()
    try:
        with local_conn:
            for key, old_val, new_val in changes:
                label, is_date = field_labels.get(key, (key, False))
                old_text = _format_value(old_val, is_date)
                new_text = _format_value(new_val, is_date)
                if (old_text or "") == (new_text or ""):
                    continue

                if old_text and new_text:
                    old_repr = old_text if is_date else f'"{old_text}"'
                    new_repr = new_text if is_date else f'"{new_text}"'
                    description = f"{label} {old_repr} → {new_repr} olarak güncellendi."
                elif not old_text and new_text:
                    new_repr = new_text if is_date else f'"{new_text}"'
                    description = f"{label} {new_repr} olarak ayarlandı."
                elif old_text and not new_text:
                    description = f"{label} temizlendi."
                else:
                    continue

                local_conn.execute(
                    """
                    INSERT INTO dosya_timeline (dosya_id, user, type, title, body, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dosya_id,
                        user_name or "",
                        "auto",
                        description,
                        "",
                        normalized_ts,
                    ),
                )
    finally:
        if needs_close:
            local_conn.close()


TRACKED_DOSYA_FIELD_ALIASES: dict[str, str] = {
    "dava_durumu": "dava_durumu",
    "tekrar_dava_durumu_2": "dava_durumu_2",
    "aciklama": "aciklama",
    "aciklama_2": "aciklama_2",
    "is_tarihi": "is_tarihi",
    "is_tarihi_2": "is_tarihi_2",
    "durusma_tarihi": "durusma_tarihi",
}


def update_dosya_with_auto_timeline(
    dosya_id: int,
    data: dict[str, Any],
    user_name: str,
    *,
    original_state: dict[str, Any] | None = None,
) -> bool:
    """
    Update ``dosyalar`` with ``data`` and log automatic timeline entries.

    Returns ``True`` when at least one tracked change was logged.
    """

    if not data:
        return False

    normalized_data = dict(data)
    # DÜZELTME: Sadece MEVCUT anahtarları normalize et, yeni anahtar EKLEME!
    for date_field in ("durusma_tarihi", "is_tarihi", "is_tarihi_2"):
        if date_field in normalized_data and normalized_data[date_field] in ("", None):
            normalized_data[date_field] = None

    tracked_keys = tuple(TRACKED_DOSYA_FIELD_ALIASES.values())
    tracked_state = dict(original_state or {})

    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if not tracked_state:
            cur.execute(
                """
                SELECT
                    dava_durumu,
                    tekrar_dava_durumu_2 AS dava_durumu_2,
                    aciklama,
                    aciklama_2,
                    is_tarihi,
                    is_tarihi_2,
                    durusma_tarihi
                FROM dosyalar
                WHERE id = ?
                """,
                (dosya_id,),
            )
            row = cur.fetchone()
            tracked_state = dict(row) if row else {}

        columns = ", ".join(f"{key} = ?" for key in normalized_data.keys())
        values = list(normalized_data.values()) + [dosya_id]

        with conn:
            cur.execute(f"UPDATE dosyalar SET {columns} WHERE id = ?", values)

            # ADIM 1: Dava durumu boşsa is_tarihi ve aciklama otomatik sıfırla
            cur.execute(
                """
                UPDATE dosyalar
                SET is_tarihi = NULL, aciklama = NULL
                WHERE id = ? AND (dava_durumu IS NULL OR dava_durumu = '')
                AND (is_tarihi IS NOT NULL OR aciklama IS NOT NULL)
                """,
                (dosya_id,),
            )
            cur.execute(
                """
                UPDATE dosyalar
                SET is_tarihi_2 = NULL, aciklama_2 = NULL
                WHERE id = ? AND (tekrar_dava_durumu_2 IS NULL OR tekrar_dava_durumu_2 = '')
                AND (is_tarihi_2 IS NOT NULL OR aciklama_2 IS NOT NULL)
                """,
                (dosya_id,),
            )

            new_state = dict(tracked_state)
            for key, value in normalized_data.items():
                alias = TRACKED_DOSYA_FIELD_ALIASES.get(key)
                if alias:
                    new_state[alias] = value

            changes: list[tuple[str, Any, Any]] = []
            for key in tracked_keys:
                old_value = tracked_state.get(key)
                new_value = new_state.get(key)
                if (old_value or "") != (new_value or ""):
                    changes.append((key, old_value, new_value))

            # ADIM 2: Dava durumu değiştiyse is_tarihi ve aciklama sıfırla
            # ADIM 3: Eski görevi tamamlandı olarak işaretle
            # (Eski değer doluydu ve yeni değer farklı bir şey olduysa)
            for key, old_val, new_val in changes:
                if key == "dava_durumu" and old_val:
                    # ADIM 3: Eski görevi tamamlandı olarak işaretle
                    _mark_automatic_task_completed(
                        conn, dosya_id, tracked_state, user_name, "IS_TARIHI"
                    )
                    # ADIM 2: is_tarihi ve aciklama sıfırla
                    cur.execute(
                        "UPDATE dosyalar SET is_tarihi = NULL, aciklama = NULL WHERE id = ?",
                        (dosya_id,),
                    )
                elif key == "dava_durumu_2" and old_val:
                    # ADIM 3: Eski görevi tamamlandı olarak işaretle
                    _mark_automatic_task_completed(
                        conn, dosya_id, tracked_state, user_name, "IS_TARIHI_2"
                    )
                    # ADIM 2: is_tarihi_2 ve aciklama_2 sıfırla
                    cur.execute(
                        "UPDATE dosyalar SET is_tarihi_2 = NULL, aciklama_2 = NULL WHERE id = ?",
                        (dosya_id,),
                    )

            if changes:
                add_auto_timeline_entry_for_changes(
                    conn, dosya_id, user_name, changes
                )

            # NOT: Dava durumu değişikliğinde is_tarihi temizleme işlemi
            # ADIM 1 ve ADIM 2 ile bu fonksiyonda yapılıyor.

        return bool(changes)
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise RuntimeError(
            "Dosya güncellenirken veritabanı hatası oluştu. Lütfen girdileri kontrol edin."
        ) from exc
    finally:
        conn.close()


def _normalize_timeline_timestamp(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip()
    return text or None


# --------------------------------------------------------------
# Müvekkil kasası kayıtları
# --------------------------------------------------------------
def get_muvekkil_kasasi_entries(dosya_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM muvekkil_kasasi WHERE dosya_id = ? ORDER BY tarih DESC, id DESC",
        (dosya_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_muvekkil_kasasi_entry(
    dosya_id: int, tarih: str, tutar_kurus: int, islem_turu: str, aciklama: str | None
) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO muvekkil_kasasi (dosya_id, tarih, tutar_kurus, islem_turu, aciklama)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dosya_id, tarih, tutar_kurus, islem_turu, aciklama),
        )
    conn.close()
    return int(cur.lastrowid)


def update_muvekkil_kasasi_entry(
    entry_id: int, tarih: str, tutar_kurus: int, islem_turu: str, aciklama: str | None
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE muvekkil_kasasi
            SET tarih = ?, tutar_kurus = ?, islem_turu = ?, aciklama = ?
            WHERE id = ?
            """,
            (tarih, tutar_kurus, islem_turu, aciklama, entry_id),
        )
    conn.close()


def delete_muvekkil_kasasi_entry(entry_id: int) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM muvekkil_kasasi WHERE id = ?", (entry_id,))
    conn.close()


def get_harici_muvekkil_kasasi_entries(harici_finans_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT * FROM harici_muvekkil_kasasi
        WHERE harici_finans_id = ?
        ORDER BY tarih DESC, id DESC
        """,
        (harici_finans_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_harici_muvekkil_kasasi_entry(
    harici_finans_id: int,
    tarih: str,
    tutar_kurus: int,
    islem_turu: str,
    aciklama: str | None,
) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO harici_muvekkil_kasasi (harici_finans_id, tarih, tutar_kurus, islem_turu, aciklama)
            VALUES (?, ?, ?, ?, ?)
            """,
            (harici_finans_id, tarih, tutar_kurus, islem_turu, aciklama),
        )
    conn.close()
    return int(cur.lastrowid)


def update_harici_muvekkil_kasasi_entry(
    entry_id: int, tarih: str, tutar_kurus: int, islem_turu: str, aciklama: str | None
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE harici_muvekkil_kasasi
            SET tarih = ?, tutar_kurus = ?, islem_turu = ?, aciklama = ?
            WHERE id = ?
            """,
            (tarih, tutar_kurus, islem_turu, aciklama, entry_id),
        )
    conn.close()


def delete_harici_muvekkil_kasasi_entry(entry_id: int) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM harici_muvekkil_kasasi WHERE id = ?", (entry_id,))
    conn.close()


# --------------------------------------------------------------
# Finans timeline
# --------------------------------------------------------------
def add_finans_timeline_entry(dosya_id: int, message: str, user: str | None = None) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO finans_timeline (dosya_id, timestamp, message, user) VALUES (?, ?, ?, ?)",
            (dosya_id, _finance_timestamp(), message, user),
        )
    conn.close()


def get_finans_timeline(dosya_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM finans_timeline WHERE dosya_id = ? ORDER BY timestamp DESC, id DESC",
        (dosya_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_harici_finans_timeline_entry(
    harici_finans_id: int, message: str, user: str | None = None
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO harici_finans_timeline (harici_finans_id, timestamp, message, user)
            VALUES (?, ?, ?, ?)
            """,
            (harici_finans_id, _finance_timestamp(), message, user),
        )
    conn.close()


def get_harici_finans_timeline(harici_finans_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT * FROM harici_finans_timeline
        WHERE harici_finans_id = ?
        ORDER BY timestamp DESC, id DESC
        """,
        (harici_finans_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# --------------------------------------------------------------
# Görevler (To-Do System)
# --------------------------------------------------------------


def get_manual_tasks_between(start_date: str, end_date: str) -> list[sqlite3.Row]:
    """Tarih aralığındaki manuel görevleri getir.

    Takvimde gösterilmek için:
    - Tamamlanmamış olmalı (tamamlandi = 0 veya NULL)
    - Sistem tarafından oluşturulmuş otomatik görevler hariç (IS_TARIHI, IS_TARIHI_2, DURUSMA)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT g.*,
            (SELECT GROUP_CONCAT(u.username, ', ')
             FROM dosya_atamalar da
             JOIN users u ON u.id = da.user_id
             WHERE da.dosya_id = g.dosya_id) AS dosya_atanan_kullanicilar
        FROM gorevler g
        WHERE g.tarih BETWEEN ? AND ?
            AND (g.tamamlandi = 0 OR g.tamamlandi IS NULL)
            AND (g.gorev_turu IS NULL OR g.gorev_turu NOT IN ('IS_TARIHI', 'IS_TARIHI_2', 'DURUSMA'))
        ORDER BY g.tarih ASC, g.id ASC
        """,
        (start_date, end_date),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_manual_tasks() -> list[sqlite3.Row]:
    """Tüm manuel görevleri getir (tamamlanmamış olanlar önce)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT g.*,
            (SELECT GROUP_CONCAT(u.username, ', ')
             FROM dosya_atamalar da
             JOIN users u ON u.id = da.user_id
             WHERE da.dosya_id = g.dosya_id) AS dosya_atanan_kullanicilar
        FROM gorevler g
        ORDER BY g.tamamlandi ASC, g.tarih ASC NULLS LAST, g.id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_pending_tasks() -> list[sqlite3.Row]:
    """Tamamlanmamış görevleri getir."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT g.*,
            (SELECT GROUP_CONCAT(u.username, ', ')
             FROM dosya_atamalar da
             JOIN users u ON u.id = da.user_id
             WHERE da.dosya_id = g.dosya_id) AS dosya_atanan_kullanicilar
        FROM gorevler g
        WHERE g.tamamlandi = 0
        ORDER BY g.tarih ASC NULLS LAST, g.id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_completed_tasks(limit: int = 50) -> list[sqlite3.Row]:
    """Tamamlanmış görevleri getir."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT g.*,
            (SELECT GROUP_CONCAT(u.username, ', ')
             FROM dosya_atamalar da
             JOIN users u ON u.id = da.user_id
             WHERE da.dosya_id = g.dosya_id) AS dosya_atanan_kullanicilar
        FROM gorevler g
        WHERE g.tamamlandi = 1
        ORDER BY g.tamamlanma_zamani DESC, g.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_manual_task(
    tarih: str | None,
    konu: str,
    aciklama: str | None,
    atanan_kullanicilar: str | None,
    olusturan_kullanici: str | None,
    gorev_turu: str | None = None,
    dosya_id: int | None = None,
) -> int:
    """Manuel görev ekle. tarih None olabilir (tarihsiz görev)."""
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO gorevler (tarih, konu, aciklama, atanan_kullanicilar,
                                  olusturan_kullanici, olusturma_zamani, gorev_turu, dosya_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tarih,
                konu,
                aciklama,
                atanan_kullanicilar,
                olusturan_kullanici,
                datetime.now().isoformat(timespec="seconds"),
                gorev_turu,
                dosya_id,
            ),
        )
    conn.close()
    return int(cur.lastrowid)


def insert_completed_task(
    tarih: str | None,
    konu: str,
    aciklama: str | None,
    olusturan_kullanici: str | None,
    gorev_turu: str | None = None,
    dosya_id: int | None = None,
) -> int:
    """Tamamlanmış görev ekle (dava durumu değiştiğinde kullanılır)."""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            """
            INSERT INTO gorevler (tarih, konu, aciklama, atanan_kullanicilar,
                                  olusturan_kullanici, olusturma_zamani, gorev_turu, dosya_id,
                                  tamamlandi, tamamlanma_zamani)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                tarih,
                konu,
                aciklama,
                None,  # atanan_kullanicilar
                olusturan_kullanici,
                now,
                gorev_turu,
                dosya_id,
                now,  # tamamlanma_zamani
            ),
        )
    conn.close()
    return int(cur.lastrowid)


def cleanup_orphan_system_tasks() -> int:
    """Eski sistem görevlerini temizle.

    Tamamlanmamış IS_TARIHI, IS_TARIHI_2, DURUSMA görevlerini siler.
    Bu görevler artık dosyalar tablosundan doğrudan okunuyor,
    gorevler tablosunda tutulmamalı.

    Returns:
        Silinen kayıt sayısı
    """
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            DELETE FROM gorevler
            WHERE gorev_turu IN ('IS_TARIHI', 'IS_TARIHI_2', 'DURUSMA')
                AND (tamamlandi = 0 OR tamamlandi IS NULL)
            """
        )
        deleted_count = cur.rowcount
    conn.close()
    return deleted_count


def update_manual_task(
    task_id: int,
    tarih: str | None,
    konu: str,
    aciklama: str | None,
    atanan_kullanicilar: str | None,
    gorev_turu: str | None = None,
) -> None:
    """Manuel görevi güncelle. tarih None olabilir."""
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE gorevler
            SET tarih = ?, konu = ?, aciklama = ?, atanan_kullanicilar = ?, gorev_turu = ?
            WHERE id = ?
            """,
            (tarih, konu, aciklama, atanan_kullanicilar, gorev_turu, task_id),
        )
    conn.close()


def mark_task_complete(task_id: int, completed: bool = True) -> None:
    """Görevi tamamlandı/tamamlanmadı olarak işaretle.

    TEBLIGAT veya ARABULUCULUK görevleri için kaynak tablodaki
    tamamlandi alanını da günceller.
    """
    import json as json_module
    conn = get_connection()

    # Önce görev bilgisini al
    cur = conn.cursor()
    cur.execute("SELECT gorev_turu, aciklama FROM gorevler WHERE id = ?", (task_id,))
    row = cur.fetchone()
    gorev_turu = row[0] if row else None
    aciklama = row[1] if row else None

    with conn:
        if completed:
            conn.execute(
                """
                UPDATE gorevler
                SET tamamlandi = 1, tamamlanma_zamani = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(timespec="seconds"), task_id),
            )
        else:
            conn.execute(
                """
                UPDATE gorevler
                SET tamamlandi = 0, tamamlanma_zamani = NULL
                WHERE id = ?
                """,
                (task_id,),
            )

        # Kaynak tabloyu da güncelle (TEBLIGAT veya ARABULUCULUK için)
        if gorev_turu and aciklama and aciklama.startswith("__META__"):
            try:
                meta = json_module.loads(aciklama[8:])
                if gorev_turu == "TEBLIGAT" and "tebligat_id" in meta:
                    conn.execute(
                        "UPDATE tebligatlar SET tamamlandi = ? WHERE id = ?",
                        (1 if completed else 0, meta["tebligat_id"])
                    )
                elif gorev_turu == "ARABULUCULUK" and "arabuluculuk_id" in meta:
                    conn.execute(
                        "UPDATE arabuluculuk SET tamamlandi = ? WHERE id = ?",
                        (1 if completed else 0, meta["arabuluculuk_id"])
                    )
            except (json_module.JSONDecodeError, ValueError, KeyError):
                pass

    conn.close()


def delete_manual_task(task_id: int) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM gorevler WHERE id = ?", (task_id,))
    conn.close()


# --------------------------------------------------------------
# Change Log (Değişiklik Takip Sistemi)
# --------------------------------------------------------------


def get_pending_changes() -> dict[str, bool]:
    """Bekleyen değişiklikleri kontrol et ve temizle.

    Returns:
        {"dosyalar": bool, "gorevler": bool, "finans": bool}
    """
    conn = get_connection()
    cur = conn.cursor()

    # Hangi tablolarda değişiklik var?
    cur.execute("SELECT DISTINCT table_name FROM change_log")
    changed_tables = {row[0] for row in cur.fetchall()}

    # Log'u temizle
    cur.execute("DELETE FROM change_log")
    conn.commit()
    conn.close()

    return {
        "dosyalar": "dosyalar" in changed_tables,
        "gorevler": "gorevler" in changed_tables,
        "finans": "finans" in changed_tables,
    }


def clear_change_log() -> None:
    """Change log tablosunu temizle."""
    conn = get_connection()
    conn.execute("DELETE FROM change_log")
    conn.commit()
    conn.close()


def get_case_tasks_between(
    start_date: str, end_date: str, only_for_user: str | None = None
) -> list[dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            d.id AS dosya_id,
            d.dosya_esas_no,
            d.muvekkil_adi,
            d.durusma_tarihi,
            d.is_tarihi,
            d.is_tarihi_2,
            d.dava_durumu,
            d.tekrar_dava_durumu_2 AS dava_durumu_2,
            s1.color_hex AS dava_durumu_color,
            s2.color_hex AS dava_durumu_2_color,
            (SELECT GROUP_CONCAT(u.username, ', ')
             FROM dosya_atamalar da
             JOIN users u ON u.id = da.user_id
             WHERE da.dosya_id = d.id) AS dosya_atanan_kullanicilar
        FROM dosyalar d
        LEFT JOIN statuses s1 ON TRIM(s1.ad) = TRIM(d.dava_durumu)
        LEFT JOIN statuses s2 ON TRIM(s2.ad) = TRIM(d.tekrar_dava_durumu_2)
        WHERE (d.durusma_tarihi BETWEEN ? AND ? OR d.is_tarihi BETWEEN ? AND ? OR d.is_tarihi_2 BETWEEN ? AND ?)
            AND d.is_archived = 0
        """,
        (
            start_date,
            end_date,
            start_date,
            end_date,
            start_date,
            end_date,
        ),
    )
    rows = cur.fetchall()
    tasks: list[dict[str, Any]] = []
    for row in rows:
        atanan = row["dosya_atanan_kullanicilar"] or ""
        # Duruşma tarihi - dava durumundan bağımsız
        if row["durusma_tarihi"]:
            tasks.append(
                {
                    "task_id": f"{row['dosya_id']}-durusma",
                    "type": "DURUSMA",
                    "date": row["durusma_tarihi"],
                    "dosya_id": row["dosya_id"],
                    "bn": row["dosya_esas_no"],
                    "muvekkil_adi": row["muvekkil_adi"],
                    "description": "Duruşma",
                    "dava_durumu": row["dava_durumu"],
                    "dava_durumu_color": row["dava_durumu_color"],
                    "atanan_kullanicilar": atanan,
                }
            )
        # İş tarihi - sadece dava_durumu varsa göster
        dava_durumu = (row["dava_durumu"] or "").strip()
        if row["is_tarihi"] and dava_durumu:
            tasks.append(
                {
                    "task_id": f"{row['dosya_id']}-is1",
                    "type": "IS_TARIHI",
                    "date": row["is_tarihi"],
                    "dosya_id": row["dosya_id"],
                    "bn": row["dosya_esas_no"],
                    "muvekkil_adi": row["muvekkil_adi"],
                    "description": "İş Tarihi",
                    "dava_durumu": dava_durumu,
                    "dava_durumu_color": row["dava_durumu_color"],
                    "atanan_kullanicilar": atanan,
                }
            )
        # İş tarihi 2 - sadece dava_durumu_2 varsa göster
        dava_durumu_2 = (row["dava_durumu_2"] or "").strip()
        if row["is_tarihi_2"] and dava_durumu_2:
            tasks.append(
                {
                    "task_id": f"{row['dosya_id']}-is2",
                    "type": "IS_TARIHI_2",
                    "date": row["is_tarihi_2"],
                    "dosya_id": row["dosya_id"],
                    "bn": row["dosya_esas_no"],
                    "muvekkil_adi": row["muvekkil_adi"],
                    "description": "İş Tarihi 2",
                    "dava_durumu": dava_durumu_2,
                    "dava_durumu_color": row["dava_durumu_2_color"],
                    "atanan_kullanicilar": atanan,
                }
            )
    conn.close()
    return tasks


# --------------------------------------------------------- Yedekleme --
BACKUP_DIR = os.path.join(DOCS_DIR, "yedekler")


def get_backup_dir() -> str:
    """Yedekleme dizinini döndürür, yoksa oluşturur."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def create_backup(custom_path: str | None = None) -> str | None:
    """
    Veritabanının yedeğini alır.

    Args:
        custom_path: Özel yedek yolu (None ise varsayılan dizine kaydeder)

    Returns:
        Yedek dosyasının yolu veya hata durumunda None
    """
    import shutil

    if not os.path.exists(DB_PATH):
        return None

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_path:
            backup_path = custom_path
        else:
            backup_dir = get_backup_dir()
            backup_path = os.path.join(backup_dir, f"data_backup_{timestamp}.db")

        # SQLite WAL modunda güvenli yedekleme için bağlantı kullan
        source_conn = sqlite3.connect(DB_PATH)
        dest_conn = sqlite3.connect(backup_path)

        with dest_conn:
            source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()

        return backup_path
    except Exception as e:
        print(f"Yedekleme hatası: {e}")
        return None


def list_backups() -> list[dict[str, Any]]:
    """
    Mevcut yedekleri listeler.

    Returns:
        Yedek bilgilerini içeren sözlük listesi
    """
    backup_dir = get_backup_dir()
    backups = []

    try:
        for filename in os.listdir(backup_dir):
            if filename.startswith("data_backup_") and filename.endswith(".db"):
                filepath = os.path.join(backup_dir, filename)
                stat = os.stat(filepath)
                backups.append({
                    "filename": filename,
                    "filepath": filepath,
                    "size_bytes": stat.st_size,
                    "size_display": _format_size(stat.st_size),
                    "created_at": datetime.fromtimestamp(stat.st_mtime),
                    "created_display": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                })

        # En yeniden eskiye sırala
        backups.sort(key=lambda x: x["created_at"], reverse=True)
    except Exception as e:
        print(f"Yedek listeleme hatası: {e}")

    return backups


def _format_size(size_bytes: int) -> str:
    """Dosya boyutunu okunabilir formata çevirir."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# --------------------------------------------------------- Ana Veri Koruma Sistemi --

# Minimum yedek sayısı - bu sayının altına asla düşülmez
MINIMUM_BACKUP_COUNT = 3


def is_main_database(file_path: str) -> bool:
    """
    Verilen dosya yolunun ana veritabanı olup olmadığını kontrol eder.

    Bu fonksiyon, ana data.db dosyasının yanlışlıkla silinmesini engellemek için kullanılır.

    Args:
        file_path: Kontrol edilecek dosya yolu

    Returns:
        Ana veritabanı ise True
    """
    try:
        # Normalize paths for comparison
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        normalized_db_path = os.path.normpath(os.path.abspath(DB_PATH))
        return normalized_path == normalized_db_path
    except Exception:
        # Hata durumunda güvenli tarafta kal
        return True


def safe_delete_file(file_path: str) -> tuple[bool, str]:
    """
    Dosyayı güvenli bir şekilde siler. Ana veritabanını SİLMEZ.

    Args:
        file_path: Silinecek dosya yolu

    Returns:
        (başarılı, mesaj) tuple
    """
    if is_main_database(file_path):
        return False, "HATA: Ana veritabanı (data.db) asla silinemez!"

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True, "Dosya silindi."
        return False, "Dosya bulunamadı."
    except Exception as e:
        return False, f"Silme hatası: {e}"


def get_backup_count() -> int:
    """Mevcut yedek sayısını döndürür."""
    return len(list_backups())


def cleanup_old_backups(keep_count: int = 10) -> int:
    """
    Eski yedekleri siler, son N tanesini tutar.

    ÖNEMLİ: Minimum yedek sayısının (3) altına asla düşülmez.

    Args:
        keep_count: Tutulacak yedek sayısı

    Returns:
        Silinen yedek sayısı
    """
    backups = list_backups()
    deleted = 0

    # Minimum yedek garantisi - en az MINIMUM_BACKUP_COUNT yedek tutulmalı
    effective_keep = max(keep_count, MINIMUM_BACKUP_COUNT)

    if len(backups) <= effective_keep:
        return 0

    # En yeni effective_keep kadarını tut, gerisini sil
    to_delete = backups[effective_keep:]

    for backup in to_delete:
        # Ana veritabanı kontrolü (paranoyak güvenlik)
        if is_main_database(backup["filepath"]):
            print(f"UYARI: Ana veritabanı silinmesi engellendi!")
            continue

        try:
            os.remove(backup["filepath"])
            deleted += 1
        except Exception as e:
            print(f"Yedek silme hatası: {backup['filename']} - {e}")

    return deleted


def restore_backup(backup_path: str) -> tuple[bool, str]:
    """
    Yedekten geri yükleme yapar.

    GÜVENLİK:
    1. Yedek dosyası var mı kontrol edilir
    2. Yedek dosyası doğrulanır
    3. Mevcut veritabanı yedeklenir (pre_restore)
    4. Pre-restore yedeği doğrulanır
    5. Ancak bundan sonra geri yükleme yapılır
    6. Geri yükleme sonrası doğrulama yapılır
    7. Başarısız olursa pre-restore'dan geri dönülür

    Args:
        backup_path: Yedek dosyasının yolu

    Returns:
        (başarılı, mesaj) tuple
    """
    # 1. Yedek dosyası var mı?
    if not os.path.exists(backup_path):
        return False, "Yedek dosyası bulunamadı."

    # 2. Ana veritabanını geri yüklemeye çalışmayı engelle (paranoyak güvenlik)
    if is_main_database(backup_path):
        return False, "HATA: Ana veritabanı kendisine geri yüklenemez!"

    # 3. Yedek dosyasını doğrula
    is_valid, validation_msg = validate_backup_file(backup_path)
    if not is_valid:
        return False, f"Yedek dosyası geçersiz: {validation_msg}"

    pre_restore_backup = None

    try:
        # 4. Mevcut veritabanını yedekle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = os.path.join(get_backup_dir(), f"pre_restore_{timestamp}.db")

        source_conn = sqlite3.connect(DB_PATH)
        pre_conn = sqlite3.connect(pre_restore_backup)
        with pre_conn:
            source_conn.backup(pre_conn)
        source_conn.close()
        pre_conn.close()

        # 5. Pre-restore yedeğini doğrula
        pre_valid, pre_msg = validate_backup_file(pre_restore_backup)
        if not pre_valid:
            return False, f"Güvenlik yedeği oluşturulamadı: {pre_msg}"

        # 6. Yedeği geri yükle
        backup_conn = sqlite3.connect(backup_path)
        dest_conn = sqlite3.connect(DB_PATH)
        with dest_conn:
            backup_conn.backup(dest_conn)
        backup_conn.close()
        dest_conn.close()

        # 7. Geri yüklenen veritabanını doğrula
        restored_valid, restored_msg = validate_backup_file(DB_PATH)
        if not restored_valid:
            # Geri yükleme başarısız - pre-restore'dan geri dön
            print(f"Geri yükleme sonrası doğrulama başarısız: {restored_msg}")
            print("Pre-restore yedeğinden geri dönülüyor...")

            rollback_conn = sqlite3.connect(pre_restore_backup)
            rollback_dest = sqlite3.connect(DB_PATH)
            with rollback_dest:
                rollback_conn.backup(rollback_dest)
            rollback_conn.close()
            rollback_dest.close()

            return False, f"Geri yükleme başarısız, önceki durum geri yüklendi. Hata: {restored_msg}"

        return True, "Geri yükleme başarılı."

    except Exception as e:
        # Hata durumunda pre-restore'dan geri dönmeyi dene
        if pre_restore_backup and os.path.exists(pre_restore_backup):
            try:
                print(f"Hata oluştu: {e}")
                print("Pre-restore yedeğinden geri dönülüyor...")

                rollback_conn = sqlite3.connect(pre_restore_backup)
                rollback_dest = sqlite3.connect(DB_PATH)
                with rollback_dest:
                    rollback_conn.backup(rollback_dest)
                rollback_conn.close()
                rollback_dest.close()

                return False, f"Geri yükleme hatası, önceki durum geri yüklendi: {e}"
            except Exception as rollback_error:
                return False, f"KRİTİK HATA: Geri yükleme ve geri dönüş başarısız! {e} / {rollback_error}"

        return False, f"Geri yükleme hatası: {e}"


def auto_backup_on_startup(keep_count: int = 10) -> str | None:
    """
    Uygulama başlangıcında otomatik yedekleme yapar.

    Args:
        keep_count: Tutulacak maksimum yedek sayısı

    Returns:
        Oluşturulan yedek yolu veya None
    """
    backup_path = create_backup()
    if backup_path:
        cleanup_old_backups(keep_count)
    return backup_path


# --------------------------------------------------------- Yedekleme Güvenlik Kontrolleri --


def get_database_size() -> int:
    """
    Mevcut veritabanı dosyasının boyutunu döndürür.

    Returns:
        Dosya boyutu (bayt cinsinden)
    """
    if os.path.exists(DB_PATH):
        return os.path.getsize(DB_PATH)
    return 0


def check_disk_space(target_path: str, required_bytes: int | None = None) -> tuple[bool, str]:
    """
    Hedef dizinde yeterli disk alanı olup olmadığını kontrol eder.

    Args:
        target_path: Hedef dizin veya dosya yolu
        required_bytes: Gereken alan (None ise veritabanı boyutunun 2 katı alınır)

    Returns:
        (yeterli_alan_var, mesaj) tuple
    """
    try:
        # Dizin yoksa üst dizini kontrol et
        check_path = target_path
        while not os.path.exists(check_path) and check_path != os.path.dirname(check_path):
            check_path = os.path.dirname(check_path)

        if not os.path.exists(check_path):
            return False, "Hedef dizin bulunamadı."

        # Cross-platform disk alanı kontrolü (shutil.disk_usage)
        try:
            usage = shutil.disk_usage(check_path)
            free_bytes = usage.free
        except (OSError, AttributeError):
            # Fallback: disk alanı kontrol edilemezse devam et
            return True, "Disk alanı kontrol edilemedi, yedekleme denenecek."

        if required_bytes is None:
            required_bytes = get_database_size() * 2  # Güvenlik için 2x

        if required_bytes == 0:
            required_bytes = 10 * 1024 * 1024  # Minimum 10 MB

        if free_bytes < required_bytes:
            free_mb = free_bytes / (1024 * 1024)
            required_mb = required_bytes / (1024 * 1024)
            return False, f"Yetersiz disk alanı: {free_mb:.1f} MB mevcut, {required_mb:.1f} MB gerekli."

        free_gb = free_bytes / (1024 * 1024 * 1024)
        return True, f"Disk alanı yeterli ({free_gb:.1f} GB boş)."
    except Exception as e:
        # Hata durumunda da devam etmeye izin ver (ama uyar)
        return True, f"Disk alanı kontrol edilemedi ({e}), yedekleme denenecek."


def validate_backup_file(backup_path: str) -> tuple[bool, str]:
    """
    Yedek dosyasının geçerli bir SQLite veritabanı olduğunu kontrol eder.

    Args:
        backup_path: Yedek dosyasının yolu

    Returns:
        (geçerli, mesaj) tuple
    """
    if not os.path.exists(backup_path):
        return False, "Dosya bulunamadı."

    if os.path.getsize(backup_path) == 0:
        return False, "Dosya boş."

    try:
        # SQLite header kontrolü (ilk 16 byte)
        with open(backup_path, "rb") as f:
            header = f.read(16)
            if not header.startswith(b"SQLite format 3"):
                return False, "Geçerli bir SQLite veritabanı değil."

        # Veritabanına bağlanmayı dene
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()

        # integrity_check çalıştır
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] != "ok":
            conn.close()
            return False, f"Veritabanı bütünlük hatası: {result[0]}"

        # Temel tabloları kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {"dosyalar", "users"}  # En az bu tablolar olmalı
        missing = required_tables - tables

        conn.close()

        if missing:
            return False, f"Eksik tablolar: {', '.join(missing)}"

        return True, "Yedek dosyası geçerli."
    except sqlite3.Error as e:
        return False, f"SQLite hatası: {e}"
    except Exception as e:
        return False, f"Doğrulama hatası: {e}"


def get_backup_info(backup_path: str) -> dict[str, Any] | None:
    """
    Yedek dosyası hakkında detaylı bilgi döndürür.

    Args:
        backup_path: Yedek dosyasının yolu

    Returns:
        Bilgi sözlüğü veya hata durumunda None
    """
    if not os.path.exists(backup_path):
        return None

    try:
        stat = os.stat(backup_path)

        # Veritabanındaki kayıt sayılarını al
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM dosyalar")
        dosya_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        conn.close()

        return {
            "filepath": backup_path,
            "filename": os.path.basename(backup_path),
            "size_bytes": stat.st_size,
            "size_display": _format_size(stat.st_size),
            "created_at": datetime.fromtimestamp(stat.st_mtime),
            "created_display": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
            "dava_count": dosya_count,
            "user_count": user_count,
        }
    except Exception:
        return None


# --------------------------------------------------------- Dosya Klasör Yönetimi --

# Ana dosyalar klasörü (Documents/LexTakip Dosyaları)
CASE_FILES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "LexTakip Dosyaları")


def get_case_files_root() -> str:
    """
    Dosya klasörlerinin ana dizinini döndürür ve yoksa oluşturur.

    Returns:
        Ana klasör yolu
    """
    os.makedirs(CASE_FILES_DIR, exist_ok=True)
    return CASE_FILES_DIR


def sanitize_folder_name(name: str) -> str:
    """
    Klasör adı için güvenli karakter dönüşümü yapar.

    - Türkçe karakterleri ASCII'ye çevirir
    - Geçersiz karakterleri kaldırır
    - Uzunluğu sınırlar

    Args:
        name: Orijinal isim

    Returns:
        Güvenli klasör adı
    """
    if not name:
        return ""

    # Türkçe karakter dönüşümü
    tr_map = {
        'ş': 's', 'Ş': 'S',
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ö': 'o', 'Ö': 'O',
        'ı': 'i', 'İ': 'I',
        'ç': 'c', 'Ç': 'C',
    }

    result = name
    for tr_char, ascii_char in tr_map.items():
        result = result.replace(tr_char, ascii_char)

    # Geçersiz karakterleri kaldır (Windows için)
    # Yasak: \ / : * ? " < > |
    invalid_chars = r'\/:*?"<>|'
    for char in invalid_chars:
        result = result.replace(char, '')

    # Çoklu boşlukları tek boşluğa indir
    result = ' '.join(result.split())

    # Başında/sonunda nokta veya boşluk olmasın
    result = result.strip('. ')

    # Maksimum uzunluk (Windows yol limiti için güvenli)
    max_len = 80
    if len(result) > max_len:
        result = result[:max_len].strip()

    return result


def generate_case_folder_name(buro_takip_no: int | str | None,
                               esas_no: str | None,
                               muvekkil: str | None) -> str:
    """
    Dava için klasör adı oluşturur.

    Format: [BN001] [2024-123 E] [Ali Veli]

    Args:
        buro_takip_no: Büro takip numarası
        esas_no: Esas numarası
        muvekkil: Müvekkil adı

    Returns:
        Klasör adı
    """
    parts = []

    # BN numarası
    if buro_takip_no:
        bn_str = str(buro_takip_no).zfill(3)  # 1 -> 001
        parts.append(f"[BN{bn_str}]")

    # Esas no
    if esas_no:
        safe_esas = sanitize_folder_name(esas_no)
        if safe_esas:
            parts.append(f"[{safe_esas}]")

    # Müvekkil adı
    if muvekkil:
        safe_muvekkil = sanitize_folder_name(muvekkil)
        if safe_muvekkil:
            parts.append(f"[{safe_muvekkil}]")

    if not parts:
        return "[Isimsiz Dosya]"

    return " ".join(parts)


def get_case_folder_path(dosya_id: int) -> str | None:
    """
    Belirli bir dava için klasör yolunu döndürür.

    Args:
        dosya_id: Dava ID'si

    Returns:
        Klasör yolu veya None (dava bulunamazsa)
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT buro_takip_no, dosya_esas_no, muvekkil_adi FROM dosyalar WHERE id = ?",
            (dosya_id,)
        )
        row = cur.fetchone()
        if not row:
            return None

        buro_takip_no, esas_no, muvekkil = row
        folder_name = generate_case_folder_name(buro_takip_no, esas_no, muvekkil)

        return os.path.join(get_case_files_root(), folder_name)
    finally:
        conn.close()


def ensure_case_folder(dosya_id: int) -> str | None:
    """
    Dava için klasör oluşturur (yoksa).

    Args:
        dosya_id: Dava ID'si

    Returns:
        Klasör yolu veya None (hata durumunda)
    """
    folder_path = get_case_folder_path(dosya_id)
    if not folder_path:
        return None

    try:
        os.makedirs(folder_path, exist_ok=True)
        return folder_path
    except Exception as e:
        print(f"Klasör oluşturma hatası: {e}")
        return None


def get_unique_filename(folder_path: str, original_name: str) -> str:
    """
    Klasörde benzersiz dosya adı döndürür.

    Eğer dosya varsa numara ekler: belge.pdf -> belge_2.pdf

    Args:
        folder_path: Hedef klasör
        original_name: Orijinal dosya adı

    Returns:
        Benzersiz dosya adı
    """
    if not os.path.exists(os.path.join(folder_path, original_name)):
        return original_name

    name, ext = os.path.splitext(original_name)
    counter = 2

    while True:
        new_name = f"{name}_{counter}{ext}"
        if not os.path.exists(os.path.join(folder_path, new_name)):
            return new_name
        counter += 1

        # Sonsuz döngüyü önle
        if counter > 1000:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{name}_{timestamp}{ext}"


def add_case_attachment(dosya_id: int, source_path: str, description: str = "") -> dict[str, Any] | None:
    """
    Davaya dosya ekler (kopyalar, taşımaz).

    1. Kaynak dosya kontrol edilir
    2. Disk alanı kontrol edilir
    3. Dosya klasöre kopyalanır
    4. Kopya doğrulanır
    5. Veritabanına kayıt eklenir

    Args:
        dosya_id: Dava ID'si
        source_path: Kaynak dosya yolu
        description: Açıklama (opsiyonel)

    Returns:
        Ek bilgisi dict veya None (hata durumunda)
    """
    import shutil
    import mimetypes

    # 1. Kaynak dosya kontrolü
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source_path}")

    if not os.path.isfile(source_path):
        raise ValueError("Yalnızca dosyalar eklenebilir, klasör eklenemez.")

    source_size = os.path.getsize(source_path)
    if source_size == 0:
        raise ValueError("Boş dosya eklenemez.")

    # 2. Disk alanı kontrolü
    space_ok, space_msg = check_disk_space(get_case_files_root(), source_size * 2)
    if not space_ok:
        raise IOError(f"Yetersiz disk alanı: {space_msg}")

    # 3. Hedef klasörü oluştur
    folder_path = ensure_case_folder(dosya_id)
    if not folder_path:
        raise ValueError("Dava klasörü oluşturulamadı.")

    # 4. Benzersiz dosya adı al
    original_name = os.path.basename(source_path)
    safe_name = sanitize_folder_name(os.path.splitext(original_name)[0])
    ext = os.path.splitext(original_name)[1]
    safe_filename = safe_name + ext if safe_name else original_name

    unique_name = get_unique_filename(folder_path, safe_filename)
    dest_path = os.path.join(folder_path, unique_name)

    # 5. Dosyayı kopyala
    try:
        shutil.copy2(source_path, dest_path)
    except Exception as e:
        raise IOError(f"Dosya kopyalama hatası: {e}")

    # 6. Kopyayı doğrula (boyut kontrolü)
    dest_size = os.path.getsize(dest_path)
    if dest_size != source_size:
        os.remove(dest_path)  # Hatalı kopyayı sil
        raise IOError("Dosya kopyalama doğrulaması başarısız - boyut uyuşmuyor.")

    # 7. MIME type belirle
    mime_type, _ = mimetypes.guess_type(dest_path)
    mime_type = mime_type or "application/octet-stream"

    # 8. Veritabanına kaydet
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO attachments (dosya_id, original_name, stored_path, mime, size_bytes, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (dosya_id, original_name, unique_name, mime_type, dest_size,
             datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
        attachment_id = cur.lastrowid

        return {
            "id": attachment_id,
            "dosya_id": dosya_id,
            "original_name": original_name,
            "stored_name": unique_name,
            "stored_path": dest_path,
            "mime": mime_type,
            "size_bytes": dest_size,
            "size_display": _format_size(dest_size),
        }
    except Exception as e:
        # DB hatası durumunda kopyalanan dosyayı sil
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise e
    finally:
        conn.close()


def get_case_attachments(dosya_id: int) -> list[dict[str, Any]]:
    """
    Davaya ait ekleri listeler.

    Args:
        dosya_id: Dava ID'si

    Returns:
        Ek listesi
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, original_name, stored_path, mime, size_bytes, added_at
            FROM attachments
            WHERE dosya_id = ?
            ORDER BY added_at DESC
            """,
            (dosya_id,)
        )

        folder_path = get_case_folder_path(dosya_id)
        attachments = []

        for row in cur.fetchall():
            att_id, original_name, stored_name, mime, size_bytes, added_at = row

            # Tam dosya yolunu oluştur
            full_path = os.path.join(folder_path, stored_name) if folder_path else ""
            file_exists = os.path.exists(full_path) if full_path else False

            attachments.append({
                "id": att_id,
                "original_name": original_name or stored_name,
                "stored_name": stored_name,
                "full_path": full_path,
                "mime": mime,
                "size_bytes": size_bytes or 0,
                "size_display": _format_size(size_bytes or 0),
                "added_at": added_at,
                "added_display": added_at[:10] if added_at else "",
                "exists": file_exists,
            })

        return attachments
    finally:
        conn.close()


def remove_case_attachment(attachment_id: int, delete_file: bool = True) -> bool:
    """
    Eki siler.

    Args:
        attachment_id: Ek ID'si
        delete_file: Dosyayı da silsin mi?

    Returns:
        Başarılı ise True
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # Önce ek bilgisini al
        cur.execute(
            "SELECT dosya_id, stored_path FROM attachments WHERE id = ?",
            (attachment_id,)
        )
        row = cur.fetchone()
        if not row:
            return False

        dosya_id, stored_name = row

        # Dosyayı sil (istenirse)
        if delete_file and stored_name:
            folder_path = get_case_folder_path(dosya_id)
            if folder_path:
                full_path = os.path.join(folder_path, stored_name)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                    except Exception as e:
                        print(f"Dosya silme hatası: {e}")

        # Veritabanından sil
        cur.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()

        return True
    finally:
        conn.close()


def open_case_folder(dosya_id: int) -> bool:
    """
    Dava klasörünü dosya yöneticisinde açar.

    Args:
        dosya_id: Dava ID'si

    Returns:
        Başarılı ise True
    """
    import subprocess
    import platform

    folder_path = ensure_case_folder(dosya_id)
    if not folder_path:
        return False

    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(folder_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", folder_path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", folder_path], check=True)
        return True
    except Exception as e:
        print(f"Klasör açma hatası: {e}")
        return False


def open_attachment_file(attachment_id: int) -> bool:
    """
    Ek dosyasını varsayılan uygulama ile açar.

    Args:
        attachment_id: Ek ID'si

    Returns:
        Başarılı ise True
    """
    import subprocess
    import platform

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dosya_id, stored_path FROM attachments WHERE id = ?",
            (attachment_id,)
        )
        row = cur.fetchone()
        if not row:
            return False

        dosya_id, stored_name = row
        folder_path = get_case_folder_path(dosya_id)
        if not folder_path:
            return False

        full_path = os.path.join(folder_path, stored_name)
        if not os.path.exists(full_path):
            return False

        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(full_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", full_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", full_path], check=True)
            return True
        except Exception as e:
            print(f"Dosya açma hatası: {e}")
            return False
    finally:
        conn.close()
