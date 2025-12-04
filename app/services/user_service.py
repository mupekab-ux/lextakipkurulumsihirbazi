# -*- coding: utf-8 -*-
"""
Kullanıcı yönetimi, yetkilendirme, durum ve ayar işlemleri.
"""

from services.base import *
from db import DEFAULT_ROLE_PERMISSIONS, PERMISSION_ACTIONS
from utils import USER_ROLE_CHOICES

# Admin için zorunlu yetkiler
ADMIN_FORCED_PERMISSIONS = {"can_hard_delete"}

__all__ = [
    # Durum (Status) işlemleri
    "add_status",
    "get_statuses",
    "list_statuses",
    "update_status",
    "delete_status",
    "get_status_color",
    # Ayar işlemleri
    "get_settings",
    "set_settings",
    "get_setting",
    "set_setting",
    # Yetki işlemleri
    "get_permissions_for_role",
    "get_all_permissions",
    "set_permissions_for_role",
    # Kullanıcı işlemleri
    "authenticate",
    "add_user",
    "update_user",
    "delete_user",
    "get_users",
    "log_action",
    # Sabitler
    "ADMIN_FORCED_PERMISSIONS",
]


# =============================================================================
# Durum (Status) İşlemleri
# =============================================================================

def add_status(ad: str, color_hex: str, owner: str) -> int:
    """Yeni durum kaydı ekler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO statuses (ad, color_hex, owner) VALUES (?, ?, ?)",
        (ad, normalize_hex(color_hex) or color_hex, owner),
    )
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def get_statuses() -> List[Dict[str, Any]]:
    """Tüm durumları listeler."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM statuses")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# Geriye dönük uyumluluk
list_statuses = get_statuses


def update_status(status_id: int, ad: str, color_hex: str, owner: str) -> None:
    """Durum kaydını günceller."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE statuses SET ad = ?, color_hex = ?, owner = ? WHERE id = ?",
        (ad, normalize_hex(color_hex) or color_hex, owner, status_id),
    )
    conn.commit()
    conn.close()


def delete_status(status_id: int) -> None:
    """Durum kaydını siler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM statuses WHERE id = ?", (status_id,))
    conn.commit()
    conn.close()


def get_status_color(status_ad: str) -> Optional[str]:
    """Verilen statü adının hex renk kodunu döndürür."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT color_hex FROM statuses WHERE ad = ?", (status_ad,))
    row = cur.fetchone()
    conn.close()
    return normalize_hex(row[0]) if row and row[0] else None


# =============================================================================
# Ayar İşlemleri
# =============================================================================

def get_settings(key: str) -> Optional[str]:
    """Ayarlar tablosundan verilen anahtarın değerini döndürür."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM ayarlar WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_settings(key: str, value: str) -> None:
    """Ayar değerini ekler veya günceller."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ayarlar (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


# Tekil adlarla uyumlu yardımcılar
def get_setting(key: str) -> Optional[str]:
    return get_settings(key)


def set_setting(key: str, value: str) -> None:
    set_settings(key, value)


# =============================================================================
# Yetki İşlemleri
# =============================================================================

def get_permissions_for_role(role: str) -> Dict[str, bool]:
    """Verilen rol için izin haritasını döndürür."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT action, allowed FROM permissions WHERE role = ?",
        (role,),
    )
    permissions = {action: bool(allowed) for action, allowed in cur.fetchall()}
    conn.close()

    defaults = DEFAULT_ROLE_PERMISSIONS.get(role, {})
    result: Dict[str, bool] = {}
    for action in PERMISSION_ACTIONS:
        if action in permissions:
            result[action] = permissions[action]
        else:
            result[action] = bool(defaults.get(action, False))

    if role == "admin":
        for forced_action in ADMIN_FORCED_PERMISSIONS:
            result[forced_action] = True

    return result


def get_all_permissions() -> Dict[str, Dict[str, bool]]:
    """Tüm roller için izinleri döndürür."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT role, action, allowed FROM permissions")
    mapping: Dict[str, Dict[str, bool]] = {}
    for role, action, allowed in cur.fetchall():
        mapping.setdefault(role, {})[action] = bool(allowed)
    conn.close()

    for role_value, _ in USER_ROLE_CHOICES:
        role_defaults = DEFAULT_ROLE_PERMISSIONS.get(role_value, {})
        role_map = mapping.setdefault(role_value, {})
        for action in PERMISSION_ACTIONS:
            role_map.setdefault(action, bool(role_defaults.get(action, False)))
        if role_value == "admin":
            for forced_action in ADMIN_FORCED_PERMISSIONS:
                role_map[forced_action] = True
    return mapping


def set_permissions_for_role(role: str, permissions: Dict[str, bool]) -> None:
    """Belirtilen rol için izinleri günceller."""
    conn = get_connection()
    cur = conn.cursor()
    for action in PERMISSION_ACTIONS:
        if action not in permissions:
            continue
        if role == "admin" and action in ADMIN_FORCED_PERMISSIONS:
            continue
        cur.execute(
            """
            INSERT INTO permissions (role, action, allowed)
            VALUES (?, ?, ?)
            ON CONFLICT(role, action) DO UPDATE SET allowed = excluded.allowed
            """,
            (role, action, 1 if permissions[action] else 0),
        )
    conn.commit()
    conn.close()


# =============================================================================
# Kullanıcı İşlemleri
# =============================================================================

def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Kullanıcı adı ve parola ile giriş doğrulaması yapar."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
    )
    row = cur.fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        user_dict = dict(row)
        role = user_dict.get("role", "") or ""
        user_dict["permissions"] = get_permissions_for_role(role)
        return user_dict
    return None


def add_user(username: str, password: str, role: str, active: bool) -> int:
    """Yeni kullanıcı ekler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), role, 1 if active else 0),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def update_user(
    user_id: int,
    username: str,
    password: str | None = None,
    role: str | None = None,
    active: bool | None = None,
) -> None:
    """Kullanıcı bilgilerini günceller."""
    conn = get_connection()
    cur = conn.cursor()
    set_parts: List[str] = []
    params: List[Any] = []

    set_parts.append("username = ?")
    params.append(username)

    if password:
        set_parts.append("password_hash = ?")
        params.append(hash_password(password))
    if role is not None:
        set_parts.append("role = ?")
        params.append(role)
    if active is not None:
        set_parts.append("active = ?")
        params.append(1 if active else 0)

    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?"
    params.append(user_id)
    cur.execute(query, params)
    conn.commit()
    conn.close()


def delete_user(user_id: int) -> None:
    """Kullanıcıyı siler. Admin kullanıcı (id=1) silinemez."""
    if user_id == 1:
        raise ValueError("Admin kullanıcı silinemez.")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_users() -> List[Dict[str, Any]]:
    """Tüm kullanıcıları listeler."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, active, created_at, updated_at FROM users"
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def log_action(user_id: int, action: str, target_id: Optional[int] = None) -> None:
    """Audit log tablosuna bir işlem kaydı ekler."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (user_id, action, target_id) VALUES (?, ?, ?)",
        (user_id, action, target_id),
    )
    conn.commit()
    conn.close()
