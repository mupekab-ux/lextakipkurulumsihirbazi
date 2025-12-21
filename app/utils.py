"""Yardımcı fonksiyonlar."""

import os
import re
import sys
import unicodedata
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping
import bcrypt
from PyQt6.QtCore import Qt, QSettings, QSortFilterProxyModel, QStringListModel
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QCompleter, QLineEdit


ROLE_CHOICES: list[tuple[str, str]] = [
    ("Davacı", "DVC"),
    ("Davalı", "DVL"),
    ("Davalı-Davacı", "DAD"),
    ("Müdahil", "MUD"),
    ("Sanık", "SNK"),
    ("Katılan / Şikâyetçi", "KAT"),
    ("Mağdur", "MDR"),
    ("Alacaklı", "ALC"),
    ("Borçlu", "BOR"),
    ("Üçüncü Kişi", "UCK"),
]

ROLE_NAMES: list[str] = [name for name, _ in ROLE_CHOICES]

ROLE_ABBREVIATIONS: dict[str, str] = {name: abbr for name, abbr in ROLE_CHOICES}

ROLE_COLOR_MAP: dict[str, str] = {
    "Davacı": "#CCFFCC",
    "Davalı": "#CCE5FF",
}

DEFAULT_ROLE_COLOR = "#FFFFFF"


USER_ROLE_CHOICES: list[tuple[str, str]] = [
    ("admin", "Kurucu Avukat"),
    ("yonetici_avukat", "Yönetici Avukat"),
    ("avukat", "Avukat"),
    ("stajyer", "Stajyer"),
]

USER_ROLE_LABELS: dict[str, str] = {
    value: label for value, label in USER_ROLE_CHOICES
}

ASSIGNMENT_EDIT_ROLES: set[str] = {"admin", "yonetici_avukat"}


HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


def normalize_hex(hex_str: str | None) -> str | None:
    """Renk kodlarını karşılaştırma için normalize eder."""

    if not hex_str:
        return None
    h = hex_str.strip()
    if h.startswith("#"):
        h = h[1:]
    return h.upper() if h else None


COLOR_MAP = {
    "Bizde": "FFD700",
    "Mahkemede / Kurumda": "FF8C00",
    "Karşı Tarafta / Üçüncü Kişide": "CD853F",
    "Arşiv / Kapandı": "FF0000",
}


STANDARD_STATUS_HEXES: set[str] = {
    normalize_hex(code)
    for code in COLOR_MAP.values()
    if normalize_hex(code)
}


THEME_DEFAULT = "Varsayılan (Açık Tema)"
THEME_DARK = "Koyu Tema"
THEME_BLUE = "Mavi Ton"
THEME_PASTEL = "Pastel Tema"
THEME_DARK_GREY = "Koyu Gri"
THEME_DARK_BLUE = "Koyu Mavi"

THEME_SETTINGS_ORG = "TakibiEsasi"
THEME_SETTINGS_APP = "TakibiEsasiApp"
THEME_SETTINGS_KEY = "ui/theme"

THEME_MAP: dict[str, str] = {
    THEME_DEFAULT: "default.qss",
    THEME_DARK: "dark.qss",
    THEME_BLUE: "blue.qss",
    THEME_PASTEL: "pastel.qss",
    THEME_DARK_GREY: "darkgrey.qss",
    THEME_DARK_BLUE: "darkblue.qss",
}

_THEME_ALIASES: dict[str, str] = {
    "Varsayılan": THEME_DEFAULT,
    "Açık Tema": THEME_DEFAULT,
}

_THEME_CACHE: dict[str, str] = {}


def resource_path(relative_path: str) -> str:
    """PyInstaller veya Nuitka paketlerinde kaynak dosyaları güvenle çözümler."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller
        base = Path(sys._MEIPASS)
    elif '__nuitka_binary_dir' in dir():
        # Nuitka onefile - geçici klasör
        base = Path(__nuitka_binary_dir)  # noqa: F821
    elif getattr(sys, 'frozen', False) or '__compiled__' in dir():
        # Nuitka standalone veya diğer frozen durumlar
        base = Path(sys.executable).parent
    else:
        # Geliştirme ortamı - app klasörünün bir üst dizini
        base = Path(__file__).resolve().parent.parent
    return str((base / relative_path).resolve())


def normalize_theme_label(theme_label: str | None) -> str:
    """Tema adını bilinen etiketlere dönüştürür."""

    if not theme_label:
        return THEME_DEFAULT
    label = _THEME_ALIASES.get(str(theme_label), str(theme_label))
    if label not in THEME_MAP:
        return THEME_DEFAULT
    return label


def _load_stylesheet(theme_label: str) -> str:
    normalized = normalize_theme_label(theme_label)
    cached = _THEME_CACHE.get(normalized)
    if cached is not None:
        return cached
    filename = THEME_MAP[normalized]
    path = Path(resource_path(f"themes/{filename}"))
    stylesheet = path.read_text(encoding="utf-8")
    _THEME_CACHE[normalized] = stylesheet
    return stylesheet


def apply_theme(theme_label: str | None) -> None:
    """Verilen tema etiketini uygular; hata durumunda varsayılanı kullanır."""

    app = QApplication.instance()
    if app is None:
        return
    normalized = normalize_theme_label(theme_label)
    try:
        stylesheet = _load_stylesheet(normalized)
    except Exception:
        try:
            stylesheet = _load_stylesheet(THEME_DEFAULT)
        except Exception:
            stylesheet = ""
    app.setStyleSheet(stylesheet)
    for widget in app.topLevelWidgets():
        refresh = getattr(widget, "refresh_finance_colors", None)
        if callable(refresh):
            refresh()


def load_theme_from_settings_and_apply() -> str:
    """Kaydedilen temayı yükler, uygular ve kullanılan etiketi döndürür."""

    settings = QSettings(THEME_SETTINGS_ORG, THEME_SETTINGS_APP)
    saved = settings.value(THEME_SETTINGS_KEY, THEME_DEFAULT)
    normalized = normalize_theme_label(saved)
    if normalized != saved:
        settings.setValue(THEME_SETTINGS_KEY, normalized)
        settings.sync()
    apply_theme(normalized)
    return normalized


def save_theme_to_settings(theme_label: str) -> None:
    """Temayı normalize edip ayarlara kaydeder."""

    settings = QSettings(THEME_SETTINGS_ORG, THEME_SETTINGS_APP)
    normalized = normalize_theme_label(theme_label)
    settings.setValue(THEME_SETTINGS_KEY, normalized)
    settings.sync()


def setting_to_bool(value: str | None) -> bool:
    """Ayar değerini (1/true gibi) booleana çevirir."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def user_has_hard_delete(current_user: Mapping[str, Any] | None) -> bool:
    """Return True when the given user can perform hard delete operations."""

    if not current_user:
        return False
    if current_user.get("role") == "admin":
        return True
    permissions = current_user.get("permissions") or {}
    if isinstance(permissions, Mapping):
        return bool(permissions.get("can_hard_delete"))
    getter = getattr(permissions, "get", None)
    if callable(getter):
        try:
            return bool(getter("can_hard_delete"))
        except Exception:  # pragma: no cover - güvenlik
            return False
    return False


def tr_to_iso(date_str: str) -> str:
    """GG.AA.YYYY formatındaki tarihi YYYY-MM-DD formatına çevirir."""
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def iso_to_tr(date_str: str) -> str:
    """YYYY-MM-DD formatındaki tarihi GG.AA.YYYY formatına çevirir."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_str


def parse_date_auto(value: str | None) -> date | None:
    """Bilinen formatlardaki tarihleri ``date`` nesnesine çevirir."""

    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if "-" in text:
            return datetime.strptime(text, "%Y-%m-%d").date()
        if "." in text:
            return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None
    return None


def parse_date_auto_to_date(value: str | None) -> date | None:
    """``parse_date_auto`` için kullanıcı dostu bir takma ad."""

    return parse_date_auto(value)


def hex_to_qcolor(hex_code: str) -> QColor:
    """RRGGBB biçimindeki renk kodundan QColor üretir."""
    normalized = normalize_hex(hex_code)
    if not normalized or not HEX_COLOR_RE.fullmatch(normalized):
        return QColor()
    return QColor("#" + normalized)


def tl_to_cents(value: str | float | int | None) -> int:
    """Verilen Türk Lirası değerini kuruş cinsine çevirir."""

    if value is None:
        return 0
    if isinstance(value, (int, float)):
        decimal_value = Decimal(str(value))
    else:
        text = str(value).strip()
        if not text:
            return 0
        cleaned = (
            text.replace("₺", "")
            .replace("TRY", "")
            .replace(" ", "")
            .replace("\u00A0", "")
        )
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", ".")
        try:
            decimal_value = Decimal(cleaned)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Geçersiz para değeri: {value}") from exc
    cents = (decimal_value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_tl(value: int | float | Decimal | None) -> float:
    """Kuruş cinsinden değeri Türk Lirası (float) olarak döndürür."""

    if value in (None, ""):
        return 0.0
    decimal_value = Decimal(str(value))
    tl_value = decimal_value / Decimal("100")
    return float(tl_value)


def format_tl(value: int | float | Decimal | None) -> str:
    """Kuruş cinsinden değeri '12.345,67 ₺' biçiminde formatlar."""

    decimal_value = Decimal(str(value or 0)) / Decimal("100")
    formatted = f"{decimal_value:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{formatted} ₺"


def is_valid_hex(color: str) -> bool:
    """RRGGBB biçimindeki renk kodunu doğrular."""
    normalized = normalize_hex(color)
    return bool(normalized and HEX_COLOR_RE.fullmatch(normalized))


def get_status_text_color(bg_hex: str | None) -> str:
    """Statü rengine göre yazı rengini döndürür."""

    normalized = normalize_hex(bg_hex)
    if not normalized:
        return "#000000"
    return "#000000" if normalized in STANDARD_STATUS_HEXES else "#FFFFFF"


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri doğru şekilde küçük harfe çevirir.

    Python'un varsayılan lower() metodu Türkçe karakterleri doğru işlemez:
    - 'İ'.lower() = 'i̇' (yanlış, 'i' olmalı)
    - 'I'.lower() = 'i' (yanlış, 'ı' olmalı)
    """
    result = text.replace("İ", "i").replace("I", "ı")
    return result.lower()


def turkish_casefold(text: str) -> str:
    """Türkçe karakter destekli case-insensitive karşılaştırma için normalize eder."""
    result = text.replace("İ", "i").replace("I", "ı").replace("ı", "i")
    return result.casefold()


class TurkishFilterProxyModel(QSortFilterProxyModel):
    """Türkçe karakter destekli filtreleme için QSortFilterProxyModel.

    Qt'nin varsayılan case-insensitive filtrelemesi Türkçe i/İ ve ı/I
    karakterlerini doğru eşleştirmez. Bu sınıf turkish_casefold kullanarak
    sorunu çözer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        """Filtreleme metnini ayarlar ve modeli yeniler."""
        self._filter_text = turkish_casefold(text) if text else ""
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Satırın filtreye uyup uymadığını kontrol eder."""
        if not self._filter_text:
            return True
        source_model = self.sourceModel()
        if source_model is None:
            return True
        index = source_model.index(source_row, 0, source_parent)
        item_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        # Türkçe case-insensitive karşılaştırma (contains)
        return self._filter_text in turkish_casefold(item_text)


class TurkishCompleter(QCompleter):
    """Türkçe karakter destekli QCompleter.

    Varsayılan QCompleter Türkçe i/İ ve ı/I karakterlerini doğru eşleştirmez.
    Bu sınıf custom TurkishFilterProxyModel ile bu sorunu çözer ve
    QCompleter'ın kendi prefix matching'ini bypass eder.
    """

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items
        self._current_filter = ""
        # Kaynak model - string listesi
        self._source_model = QStringListModel(items, self)
        # Türkçe filtreli proxy model
        self._proxy_model = TurkishFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        # Completer'a proxy modeli ata
        self.setModel(self._proxy_model)
        # Qt'nin kendi filtrelemesini devre dışı bırak
        self.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def setCompletionPrefix(self, prefix: str) -> None:
        """Override: Türkçe filtrelemeyi uygula ve Qt'nin filtrelemesini bypass et."""
        self._current_filter = prefix
        self._proxy_model.set_filter_text(prefix)
        # Qt'ye boş prefix ver ki kendi filtrelemesini yapmasın
        super().setCompletionPrefix("")

    def splitPath(self, path: str) -> list[str]:
        """Filtreleme için kullanılan metni döndürür."""
        return [""]  # Qt'nin prefix matching yapmaması için boş döndür

    def pathFromIndex(self, index) -> str:
        """Seçilen öğenin metnini döndürür."""
        return index.data(Qt.ItemDataRole.DisplayRole) or ""


def setup_autocomplete(lineedit: QLineEdit, items: list[str]) -> QCompleter:
    """Verilen QLineEdit için Türkçe karakter destekli otomatik tamamlama ayarlar."""
    completer = TurkishCompleter(items)
    lineedit.setCompleter(completer)
    # LineEdit text değiştiğinde completer'ı güncelle
    lineedit.textChanged.connect(completer.setCompletionPrefix)
    return completer


def normalize_str(value: str) -> str:
    """Karşılaştırma için küçük harfe çevirip Unicode normalizasyonu uygular."""
    return unicodedata.normalize("NFKD", value).casefold()


def get_attachments_dir() -> Path:
    """Ek dosyalarının saklandığı klasörü döndürür ve yoksa oluşturur.

    Depo talimatlarına uygun şekilde kullanıcı ``Documents/TakibiEsasi``
    dizini altındaki ``attachments`` klasörü tercih edilir. Eğer sistemde
    ``Documents`` klasörü bulunmuyorsa kullanıcının ana dizinine
    yedeklenir.
    """

    home = Path.home()
    documents_dir = home / "Documents"
    try:
        documents_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Windows dışındaki kurulumlarda ``Documents`` klasörü olmayabilir.
        documents_dir = home

    base_path = documents_dir / "TakibiEsasi"
    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Yazma izni yoksa uygulama dizinine geri düş.
        fallback = Path(__file__).resolve().parent.parent
        base_path = fallback / "attachments"
        base_path.mkdir(parents=True, exist_ok=True)
        return base_path

    attachments_dir = base_path / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    return attachments_dir


# Modül yüklendiğinde ek klasörünün mevcut olduğundan emin ol.
_ = get_attachments_dir()


COLOR_TO_OWNER: dict[str, str] = {
    normalize_hex(code): label for label, code in COLOR_MAP.items()
}

OWNER_ALIAS_MAP: dict[str, str] = {}
for label in COLOR_MAP.keys():
    OWNER_ALIAS_MAP[normalize_str(label)] = label

_OWNER_EXTRA_ALIASES = {
    "Bizde": "Bizde",
    "BİZDE": "Bizde",
    "BIZDE": "Bizde",
    "Sarı": "Bizde",
    "Sari": "Bizde",
    "Mahkemede": "Mahkemede / Kurumda",
    "Turuncu": "Mahkemede / Kurumda",
    "Mahkemede / Kurumda": "Mahkemede / Kurumda",
    "Karşı Tarafta / Üçüncü Kişide": "Karşı Tarafta / Üçüncü Kişide",
    "Karsi Tarafta / Ucuncu Kiside": "Karşı Tarafta / Üçüncü Kişide",
    "Garip Turuncu": "Karşı Tarafta / Üçüncü Kişide",
    "Garip_Turuncu": "Karşı Tarafta / Üçüncü Kişide",
    "Arşiv / Kapandı": "Arşiv / Kapandı",
    "Arsiv / Kapandi": "Arşiv / Kapandı",
    "Kırmızı": "Arşiv / Kapandı",
    "Kirmizi": "Arşiv / Kapandı",
}
for alias, canonical in _OWNER_EXTRA_ALIASES.items():
    OWNER_ALIAS_MAP[normalize_str(alias)] = canonical


def resolve_owner_label(owner: str | None, color_hex: str | None = None) -> str | None:
    """Statü sahibi metnini standart dört kategoriden birine dönüştürür."""

    if owner:
        normalized_owner = normalize_str(owner)
        mapped = OWNER_ALIAS_MAP.get(normalized_owner)
        if mapped:
            return mapped

    normalized_hex = normalize_hex(color_hex)
    if normalized_hex:
        mapped = COLOR_TO_OWNER.get(normalized_hex)
        if mapped:
            return mapped

    if owner and owner.strip():
        return owner.strip()
    return None


def hash_password(password: str) -> str:
    """Parolayı bcrypt ile özetleyip döndürür."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verilen parolayı bcrypt özetiyle karşılaştırır."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), (hashed or "").encode("utf-8"))
    except ValueError:
        return False


def get_durusma_color(date_str: str):
    """Duruşma tarihine göre uygun renkleri döndürür.

    ``date_str`` parametresi ``YYYY-MM-DD`` biçiminde olmalıdır. Geçersiz ya da
    boşsa ``None`` döner. Geçerli bir tarih olduğunda aşağıdaki kurallar
    uygulanır ve ``{"bg": "#RRGGBB", "fg": "#RRGGBB"}`` biçiminde bir sözlük
    döndürülür:

    - Bugün              -> yeşil (#4CAF50)   / metin beyaz
    - Yarın              -> sarı (#FFEB3B)    / metin siyah
    - Bu hafta (yarın hariç) -> turuncu (#FF9800) / metin beyaz
    - Gelecek hafta      -> koyu mavi (#1565C0) / metin beyaz
    - Diğer durumlar     -> renksiz (``None``)
    - Geçmiş tarihler    -> renksiz (``None``)
    """

    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return None

    today = date.today()
    if d < today:
        return None

    if d == today:
        return {"bg": "#4CAF50", "fg": "#FFFFFF"}

    tomorrow = today + timedelta(days=1)
    if d == tomorrow:
        return {"bg": "#FFEB3B", "fg": "#000000"}

    if d.isocalendar()[:2] == today.isocalendar()[:2] and d > tomorrow:
        return {"bg": "#FF9800", "fg": "#FFFFFF"}

    next_week = today + timedelta(days=7)
    if d.isocalendar()[:2] == next_week.isocalendar()[:2]:
        return {"bg": "#1565C0", "fg": "#FFFFFF"}

    return None


def get_task_color_by_date(date_obj: date | None, is_completed: bool = False) -> dict | None:
    """Görev tarihine göre renkleri döndürür.

    Dosyalar sekmesindeki iş tarihi renklendirmesine benzer mantık kullanır.
    Tamamlanmış görevler için gri döner.

    - Tamamlandı         -> gri (#e8e8e8)     / metin gri
    - Geçmiş             -> kırmızı (#ff4d4d) / metin beyaz
    - Bugün              -> yeşil (#4caf50)   / metin beyaz
    - 1-3 gün içinde     -> sarı (#ffeb3b)    / metin siyah
    - 4-7 gün içinde     -> turuncu (#ff9800) / metin beyaz
    - 8-14 gün içinde    -> mavi (#2196f3)    / metin beyaz
    - Daha uzak          -> açık gri (#f5f5f5)/ metin siyah
    """
    if is_completed:
        return {"bg": "#e8e8e8", "fg": "#888888"}

    if date_obj is None:
        return {"bg": "#f5f5f5", "fg": "#666666"}

    today = date.today()
    delta = (date_obj - today).days

    if delta < 0:
        return {"bg": "#ff4d4d", "fg": "#FFFFFF"}
    if delta == 0:
        return {"bg": "#4caf50", "fg": "#FFFFFF"}
    if delta <= 3:
        return {"bg": "#ffeb3b", "fg": "#000000"}
    if delta <= 7:
        return {"bg": "#ff9800", "fg": "#FFFFFF"}
    if delta <= 14:
        return {"bg": "#2196f3", "fg": "#FFFFFF"}

    return {"bg": "#f5f5f5", "fg": "#333333"}


VEKALET_DIRNAME = "vekaletler"


def get_base_dir() -> str:
    """Return the writable base directory used by the application."""

    try:
        try:
            from app.db import DOCS_DIR  # type: ignore
        except ModuleNotFoundError:
            from db import DOCS_DIR  # type: ignore

        if DOCS_DIR:
            return os.path.abspath(DOCS_DIR)
    except Exception:
        pass

    try:
        return os.path.abspath(os.path.dirname(sys.executable))
    except Exception:
        return os.path.abspath(os.path.dirname(__file__))


def get_vekalet_dir() -> str:
    """Return the absolute path to the vekaletler directory."""

    return os.path.join(get_base_dir(), VEKALET_DIRNAME)


def ensure_vekalet_dir_exists() -> str:
    """Ensure that the vekaletler directory exists and return its path."""

    path = get_vekalet_dir()
    os.makedirs(path, exist_ok=True)
    return path


def human_size(num_bytes: int) -> str:
    """Convert a byte count to a human-readable string."""

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:,.0f} {unit}".replace(",", ".")
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"
