# -*- coding: utf-8 -*-
"""Finans güncelleme işlemleri için doğrulamalar."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "bcrypt" not in sys.modules:
    fake_bcrypt = types.ModuleType("bcrypt")

    _FAKE_SALT = b"testsalt"

    def _ensure_bytes(value: str | bytes) -> bytes:
        return value if isinstance(value, bytes) else value.encode("utf-8")

    def gensalt() -> bytes:  # type: ignore[override]
        return _FAKE_SALT

    def hashpw(password: bytes, salt: bytes) -> bytes:  # type: ignore[override]
        pwd = _ensure_bytes(password)
        slt = _ensure_bytes(salt)
        return base64.b64encode(slt + pwd)

    def checkpw(password: bytes, hashed: bytes) -> bool:  # type: ignore[override]
        pwd = _ensure_bytes(password)
        hashed_bytes = _ensure_bytes(hashed)
        try:
            decoded = base64.b64decode(hashed_bytes)
        except Exception:  # pragma: no cover - savunma amaçlı
            return False
        expected_salt = decoded[: len(_FAKE_SALT)]
        stored = decoded[len(_FAKE_SALT) :]
        return expected_salt == _FAKE_SALT and stored == pwd

    fake_bcrypt.gensalt = gensalt  # type: ignore[attr-defined]
    fake_bcrypt.hashpw = hashpw  # type: ignore[attr-defined]
    fake_bcrypt.checkpw = checkpw  # type: ignore[attr-defined]
    sys.modules["bcrypt"] = fake_bcrypt

if "PyQt6" not in sys.modules:
    qt_package = types.ModuleType("PyQt6")
    qt_core = types.ModuleType("PyQt6.QtCore")
    qt_gui = types.ModuleType("PyQt6.QtGui")
    qt_widgets = types.ModuleType("PyQt6.QtWidgets")

    class _CaseSensitivity:
        CaseInsensitive = object()

    class DummyQt:
        CaseSensitivity = _CaseSensitivity()

    class DummyQSettings:
        def __init__(self, *args, **kwargs):
            self._values: dict[str, str] = {}

        def value(self, key: str, default: str | None = None) -> str | None:
            return self._values.get(key, default)

        def setValue(self, key: str, value: str) -> None:
            self._values[key] = value

    class DummyQColor:
        def __init__(self, *_args, **_kwargs):
            pass

    class DummyQApplication:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def instance():
            return None

    class DummyQCompleter:
        def __init__(self, *args, **kwargs):
            pass

        def setModel(self, *_args, **_kwargs):
            pass

        def setCaseSensitivity(self, *_args, **_kwargs):
            pass

    class DummyQLineEdit:
        def __init__(self, *args, **kwargs):
            pass

    class DummyQDate:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def currentDate():
            return DummyQDate()

        def toString(self, *_args, **_kwargs) -> str:
            return ""

        @staticmethod
        def fromString(*_args, **_kwargs):  # pragma: no cover - sadece import için
            return DummyQDate()

    qt_core.Qt = DummyQt()  # type: ignore[attr-defined]
    qt_core.QSettings = DummyQSettings  # type: ignore[attr-defined]
    qt_core.QDate = DummyQDate  # type: ignore[attr-defined]
    qt_gui.QColor = DummyQColor  # type: ignore[attr-defined]
    qt_widgets.QApplication = DummyQApplication  # type: ignore[attr-defined]
    qt_widgets.QCompleter = DummyQCompleter  # type: ignore[attr-defined]
    qt_widgets.QLineEdit = DummyQLineEdit  # type: ignore[attr-defined]

    qt_package.QtCore = qt_core  # type: ignore[attr-defined]
    qt_package.QtGui = qt_gui  # type: ignore[attr-defined]
    qt_package.QtWidgets = qt_widgets  # type: ignore[attr-defined]

    sys.modules["PyQt6"] = qt_package
    sys.modules["PyQt6.QtCore"] = qt_core
    sys.modules["PyQt6.QtGui"] = qt_gui
    sys.modules["PyQt6.QtWidgets"] = qt_widgets

if "openpyxl" not in sys.modules:
    openpyxl_module = types.ModuleType("openpyxl")

    class DummyWorkbook:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    openpyxl_module.Workbook = DummyWorkbook  # type: ignore[attr-defined]
    sys.modules["openpyxl"] = openpyxl_module

if "docx" not in sys.modules:
    docx_module = types.ModuleType("docx")
    docx_oxml = types.ModuleType("docx.oxml")
    docx_ns = types.ModuleType("docx.oxml.ns")
    docx_shared = types.ModuleType("docx.shared")
    docx_enum_section = types.ModuleType("docx.enum.section")

    class DummyDocument:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    def OxmlElement(*_args, **_kwargs):  # type: ignore[override]
        return object()

    def qn(name: str) -> str:  # type: ignore[override]
        return name

    class RGBColor:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    class Pt:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    class Mm:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    class WD_ORIENT:  # pragma: no cover - sadece import için
        PORTRAIT = 0
        LANDSCAPE = 1

    class WD_SECTION:  # pragma: no cover - sadece import için
        NEW_PAGE = 0

    docx_module.Document = DummyDocument  # type: ignore[attr-defined]
    docx_oxml.OxmlElement = OxmlElement  # type: ignore[attr-defined]
    docx_ns.qn = qn  # type: ignore[attr-defined]
    docx_shared.RGBColor = RGBColor  # type: ignore[attr-defined]
    docx_shared.Pt = Pt  # type: ignore[attr-defined]
    docx_shared.Mm = Mm  # type: ignore[attr-defined]
    docx_enum_section.WD_ORIENT = WD_ORIENT  # type: ignore[attr-defined]
    docx_enum_section.WD_SECTION = WD_SECTION  # type: ignore[attr-defined]

    sys.modules["docx"] = docx_module
    sys.modules["docx.oxml"] = docx_oxml
    sys.modules["docx.oxml.ns"] = docx_ns
    sys.modules["docx.shared"] = docx_shared
    sys.modules["docx.enum.section"] = docx_enum_section

if "pandas" not in sys.modules:
    pandas_module = types.ModuleType("pandas")

    class DummyDataFrame:  # pragma: no cover - sadece import için
        def __init__(self, *args, **kwargs):
            pass

    pandas_module.DataFrame = DummyDataFrame  # type: ignore[attr-defined]
    pandas_module.Series = DummyDataFrame  # type: ignore[attr-defined]
    sys.modules["pandas"] = pandas_module

from app import db, models


class FinanceUpdateTestCase(unittest.TestCase):
    """``update_finans_*`` fonksiyonlarının davranışlarını doğrular."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        self._orig_docs_dir = db.DOCS_DIR
        self._orig_models_db_path = models.DB_PATH
        self._orig_models_get_connection = models.get_connection

        temp_docs = Path(self._temp_dir.name)
        db.DOCS_DIR = str(temp_docs)
        os.makedirs(db.DOCS_DIR, exist_ok=True)
        db.DB_PATH = str(temp_docs / "data.db")
        models.DB_PATH = db.DB_PATH
        models.get_connection = db.get_connection

        db.initialize_database()

    def tearDown(self) -> None:  # pragma: no cover - test cleanup
        models.get_connection = self._orig_models_get_connection
        models.DB_PATH = self._orig_models_db_path
        db.DB_PATH = self._orig_db_path
        db.DOCS_DIR = self._orig_docs_dir
        self._temp_dir.cleanup()

    def _create_case(self, buro_no: int = 1) -> int:
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO dosyalar (buro_takip_no, muvekkil_adi) VALUES (?, ?)",
                (buro_no, "Test Müvekkil"),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def test_update_finans_contract_persists_changes(self) -> None:
        dosya_id = self._create_case(buro_no=101)

        success = models.update_finans_contract(
            dosya_id,
            sozlesme_ucreti=1250.75,
            sozlesme_yuzdesi=10.5,
            tahsil_hedef_cents=500_000,
            notlar="Deneme kaydı",
            yuzde_is_sonu=True,
        )

        self.assertTrue(success)
        conn = db.get_connection()
        try:
            row = conn.execute(
                """
                SELECT sozlesme_ucreti, sozlesme_ucreti_cents, sozlesme_yuzdesi,
                       tahsil_hedef_cents, notlar, yuzde_is_sonu
                FROM finans
                WHERE dosya_id=?
                """,
                (dosya_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        assert row is not None  # Tip denetimi için
        self.assertAlmostEqual(row["sozlesme_ucreti"], 1250.75)
        self.assertEqual(row["sozlesme_ucreti_cents"], 125075)
        self.assertAlmostEqual(row["sozlesme_yuzdesi"], 10.5)
        self.assertEqual(row["tahsil_hedef_cents"], 500_000)
        self.assertEqual(row["notlar"], "Deneme kaydı")
        self.assertEqual(row["yuzde_is_sonu"], 1)

    def test_update_finans_terms_updates_existing_row(self) -> None:
        dosya_id = self._create_case(buro_no=202)
        initial_success = models.update_finans_contract(
            dosya_id,
            sozlesme_ucreti=100.0,
            sozlesme_yuzdesi=5.0,
            tahsil_hedef_cents=1000,
            notlar=None,
            yuzde_is_sonu=False,
        )
        self.assertTrue(initial_success)

        conn = db.get_connection()
        try:
            finans_row = conn.execute(
                "SELECT id FROM finans WHERE dosya_id=?",
                (dosya_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(finans_row)
        finans_id = int(finans_row["id"])  # type: ignore[index]

        success = models.update_finans_terms(
            None,
            finans_id=finans_id,
            sozlesme_ucreti=777.25,
            sozlesme_yuzdesi=12.0,
        )
        self.assertTrue(success)

        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT sozlesme_ucreti, sozlesme_ucreti_cents, sozlesme_yuzdesi FROM finans WHERE id=?",
                (finans_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertAlmostEqual(row["sozlesme_ucreti"], 777.25)
        self.assertEqual(row["sozlesme_ucreti_cents"], 77725)
        self.assertAlmostEqual(row["sozlesme_yuzdesi"], 12.0)

    def test_update_finans_contract_without_identifier_raises(self) -> None:
        with self.assertRaises(ValueError):
            models.update_finans_contract(
                None,
                sozlesme_ucreti=10.0,
                sozlesme_yuzdesi=1.0,
                tahsil_hedef_cents=0,
                notlar=None,
                yuzde_is_sonu=False,
            )

    def test_update_finans_contract_missing_row_returns_false(self) -> None:
        success = models.update_finans_contract(
            None,
            finans_id=9_999,
            sozlesme_ucreti=50.0,
            sozlesme_yuzdesi=0.0,
            tahsil_hedef_cents=0,
            notlar=None,
            yuzde_is_sonu=False,
        )
        self.assertFalse(success)

    def test_update_finans_terms_requires_identifier(self) -> None:
        with self.assertRaises(ValueError):
            models.update_finans_terms(
                None,
                sozlesme_ucreti=20.0,
                sozlesme_yuzdesi=1.0,
            )


if __name__ == "__main__":  # pragma: no cover - manuel çalıştırma
    unittest.main()
