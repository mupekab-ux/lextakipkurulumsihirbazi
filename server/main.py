# -*- coding: utf-8 -*-
"""
TakibiEsasi License & Admin API
FastAPI backend for license management and admin panel
"""

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import secrets
import hashlib
import json
import os
import jwt
import bcrypt
import re
import uuid

app = FastAPI(title="TakibiEsasi API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "takibiesasi_db",
    "user": "takibiesasi_user",
    "password": "TakibiEsasi2024!"
}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "TakibiAdmin2024!"
JWT_SECRET = "takibiesasi-secret-key-2024"
OFFLINE_TOKEN_SECRET = "takibiesasi-offline-token-secret-2024"
OFFLINE_TOKEN_DAYS = 30  # Offline token geçerlilik süresi

DOWNLOAD_DIR = "/var/www/takibiesasi/download"
RELEASES_FILE = "/var/www/takibiesasi/releases/latest.json"
RELEASES_HISTORY_FILE = "/var/www/takibiesasi/releases/history.json"

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(RELEASES_FILE), exist_ok=True)

# ============ DATABASE ============

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cur = conn.cursor()

    # Licenses table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id SERIAL PRIMARY KEY,
            license_key VARCHAR(50) UNIQUE NOT NULL,
            machine_id VARCHAR(100),
            user_name VARCHAR(200),
            is_active BOOLEAN DEFAULT TRUE,
            transfer_count INTEGER DEFAULT 0,
            customer_name VARCHAR(200),
            email VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            last_check TIMESTAMP
        )
    """)

    # Site settings table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS site_settings (
            id SERIAL PRIMARY KEY,
            setting_key VARCHAR(100) UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pricing plans table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pricing_plans (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            period VARCHAR(50),
            features TEXT,
            is_popular BOOLEAN DEFAULT FALSE,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Testimonials table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS testimonials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            title VARCHAR(200),
            content TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # FAQ table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Announcements table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title VARCHAR(300) NOT NULL,
            content TEXT NOT NULL,
            announcement_type VARCHAR(50) DEFAULT 'info',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Features table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id SERIAL PRIMARY KEY,
            icon VARCHAR(100) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Screenshots table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200),
            image_url VARCHAR(500) NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Media/Images table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER,
            mime_type VARCHAR(100),
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Contact messages table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Demo registrations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_registrations (
            id SERIAL PRIMARY KEY,
            email VARCHAR(200) NOT NULL UNIQUE,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(50),
            user_agent TEXT,
            converted_to_license BOOLEAN DEFAULT FALSE,
            converted_at TIMESTAMP
        )
    """)

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(200) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(200),
            phone VARCHAR(50),
            company_name VARCHAR(200),
            tax_number VARCHAR(50),
            email_verified BOOLEAN DEFAULT FALSE,
            email_verified_at TIMESTAMP,
            email_verification_token VARCHAR(255),
            password_reset_token VARCHAR(255),
            password_reset_expires TIMESTAMP,
            role VARCHAR(50) DEFAULT 'user',
            kvkk_accepted BOOLEAN DEFAULT FALSE,
            marketing_accepted BOOLEAN DEFAULT FALSE,
            last_login_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Orders table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            order_number VARCHAR(50) UNIQUE NOT NULL,
            product_type VARCHAR(50),
            product_name VARCHAR(200),
            quantity INTEGER DEFAULT 1,
            unit_price_cents INTEGER,
            subtotal_cents INTEGER,
            tax_rate INTEGER DEFAULT 20,
            tax_cents INTEGER,
            total_price_cents INTEGER,
            billing_name VARCHAR(200),
            billing_email VARCHAR(200),
            billing_phone VARCHAR(50),
            billing_address TEXT,
            billing_tax_number VARCHAR(50),
            billing_tax_office VARCHAR(100),
            customer_notes TEXT,
            payment_status VARCHAR(50) DEFAULT 'pending',
            payment_method VARCHAR(50),
            installment_count INTEGER DEFAULT 1,
            mock_card_last4 VARCHAR(10),
            mock_card_holder VARCHAR(200),
            mock_transaction_id VARCHAR(100),
            paid_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Invoices table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            order_id INTEGER REFERENCES orders(id),
            invoice_number VARCHAR(50) UNIQUE NOT NULL,
            buyer_name VARCHAR(200),
            buyer_email VARCHAR(200),
            buyer_address TEXT,
            buyer_tax_number VARCHAR(50),
            buyer_tax_office VARCHAR(100),
            subtotal_cents INTEGER,
            tax_cents INTEGER,
            total_cents INTEGER,
            status VARCHAR(50) DEFAULT 'issued',
            invoice_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Downloads table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            version VARCHAR(50),
            file_name VARCHAR(255),
            file_size_bytes BIGINT,
            ip_address VARCHAR(50),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Commit base tables first
    conn.commit()

    # Add missing columns to licenses table (for existing databases)
    # Each ALTER in its own transaction to avoid blocking on errors
    alter_statements = [
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS user_id INTEGER",
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS order_id INTEGER",
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS purchase_price_cents INTEGER",
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS purchase_date TIMESTAMP",
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual'"
    ]

    for stmt in alter_statements:
        try:
            cur.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()  # Rollback failed transaction and continue

    # Create generate_order_number function
    try:
        cur.execute("""
            CREATE OR REPLACE FUNCTION generate_order_number()
            RETURNS VARCHAR AS $$
            DECLARE
                order_num VARCHAR;
            BEGIN
                order_num := 'ORD-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || LPAD(FLOOR(RANDOM() * 10000)::TEXT, 4, '0');
                RETURN order_num;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()

    cur.close()
    conn.close()

# Initialize on startup
@app.on_event("startup")
async def startup():
    init_db()

# ============ MODELS ============

class ActivateRequest(BaseModel):
    license_key: str
    machine_id: str

class VerifyRequest(BaseModel):
    license_key: str
    machine_id: str

class TransferRequest(BaseModel):
    license_key: str
    old_machine_id: str
    new_machine_id: str

class UpdateCheckRequest(BaseModel):
    current_version: str
    machine_id: Optional[str] = None

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class CreateLicenseRequest(BaseModel):
    customer_name: Optional[str] = None
    email: Optional[str] = None

class LicenseActionRequest(BaseModel):
    license_key: str

class SetTransferRequest(BaseModel):
    license_key: str
    transfer_count: int

class SetUserNameRequest(BaseModel):
    license_key: str
    user_name: str

class ReleaseRequest(BaseModel):
    version: str
    download_url: str
    release_notes: str
    min_version: Optional[str] = None
    is_critical: bool = False

class SetCurrentReleaseRequest(BaseModel):
    version: str

class DeleteFileRequest(BaseModel):
    filename: str

class SiteSettingRequest(BaseModel):
    key: str
    value: str

class PricingPlanRequest(BaseModel):
    name: str
    price: float
    period: Optional[str] = None
    features: Optional[str] = None
    is_popular: bool = False
    sort_order: int = 0

class TestimonialRequest(BaseModel):
    name: str
    title: Optional[str] = None
    content: str
    rating: int = 5

class FAQRequest(BaseModel):
    question: str
    answer: str
    sort_order: int = 0

class AnnouncementRequest(BaseModel):
    title: str
    content: str
    announcement_type: str = "info"

class ContactMessageRequest(BaseModel):
    name: str
    email: str
    message: str

class FeatureRequest(BaseModel):
    icon: str
    title: str
    description: str
    sort_order: int = 0

class ScreenshotRequest(BaseModel):
    title: Optional[str] = None
    image_url: str
    sort_order: int = 0

class BulkSettingsRequest(BaseModel):
    settings: dict

# ============ USER AUTH MODELS ============

class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    kvkk_accepted: bool = False
    marketing_accepted: bool = False

class UserLoginRequest(BaseModel):
    email: str
    password: str

class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    token: str

# ============ ORDER/PAYMENT MODELS ============

class CreateOrderRequest(BaseModel):
    product_type: str  # individual, office_server, office_user, license (demo)
    product_name: Optional[str] = None  # Plan name from frontend
    quantity: int = 1
    unit_price_cents: Optional[int] = None  # Price from frontend for demo
    payment_method: Optional[str] = None  # card, bank
    billing_name: Optional[str] = None  # Auto-fill from user if not provided
    billing_email: Optional[str] = None  # Auto-fill from user if not provided
    billing_phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_tax_number: Optional[str] = None
    billing_tax_office: Optional[str] = None
    customer_notes: Optional[str] = None

class MockPaymentRequest(BaseModel):
    transaction_id: Optional[str] = None  # Demo mode transaction ID
    card_number: Optional[str] = None  # Mock - sadece son 4 hane saklanacak
    card_holder: Optional[str] = None
    expiry_month: Optional[str] = None
    expiry_year: Optional[str] = None
    cvv: Optional[str] = None
    installment_count: int = 1

class OrderStatusUpdateRequest(BaseModel):
    status: str  # pending, processing, completed, failed, refunded, cancelled

# ============ INVOICE MODELS ============

class CreateInvoiceRequest(BaseModel):
    order_id: int

# ============ DOWNLOAD TRACKING MODELS ============

class DownloadTrackRequest(BaseModel):
    version: str
    file_name: str
    file_size_bytes: Optional[int] = None

# ============ DEMO HEARTBEAT MODELS ============

class DemoHeartbeatRequest(BaseModel):
    machine_id: str
    machine_name: Optional[str] = None
    os_info: Optional[str] = None
    usage_minutes: int = 0

class DemoExtendRequest(BaseModel):
    demo_id: int
    days: int = 7
    notes: Optional[str] = None

# ============ HELPERS ============

def generate_license_key():
    """Generate a unique license key"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    parts = []
    for _ in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return '-'.join(parts)

def verify_admin_token(authorization: str = Header(None)):
    """Verify JWT token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace('Bearer ', '')
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============ OFFLINE TOKEN FUNCTIONS ============

def generate_offline_token(license_key: str, machine_id: str) -> dict:
    """
    Offline çalışma için JWT token oluşturur.
    Token 30 gün geçerlidir.
    """
    expires_at = datetime.utcnow() + timedelta(days=OFFLINE_TOKEN_DAYS)

    payload = {
        "license_key": license_key,
        "machine_id": machine_id,
        "issued_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
        "exp": expires_at.timestamp()  # JWT standard expiry
    }

    token = jwt.encode(payload, OFFLINE_TOKEN_SECRET, algorithm="HS256")

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "days_valid": OFFLINE_TOKEN_DAYS
    }


def verify_offline_token(token: str, machine_id: str) -> dict:
    """
    Offline token'ı doğrular.
    Returns: {"valid": bool, "error": str or None, "license_key": str or None}
    """
    try:
        payload = jwt.decode(token, OFFLINE_TOKEN_SECRET, algorithms=["HS256"])

        # Makine ID kontrolü
        if payload.get("machine_id") != machine_id:
            return {"valid": False, "error": "Token bu makine için geçerli değil", "license_key": None}

        # Token geçerli
        return {
            "valid": True,
            "error": None,
            "license_key": payload.get("license_key"),
            "expires_at": payload.get("expires_at")
        }

    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token süresi dolmuş", "license_key": None}
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Geçersiz token", "license_key": None}
    except Exception as e:
        return {"valid": False, "error": str(e), "license_key": None}


def get_current_release():
    """Get current release info"""
    try:
        with open(RELEASES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "version": "1.0.0",
            "download_url": "",
            "release_notes": "İlk sürüm",
            "release_date": datetime.now().strftime("%Y-%m-%d"),
            "is_critical": False,
            "min_version": "1.0.0"
        }

def get_releases_history():
    """Get all releases history"""
    try:
        with open(RELEASES_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_release(release_data):
    """Save release to latest.json and history"""
    # Save as current
    with open(RELEASES_FILE, 'w') as f:
        json.dump(release_data, f, indent=2)

    # Add to history
    history = get_releases_history()
    history.insert(0, release_data)
    with open(RELEASES_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# ============ USER AUTH HELPERS ============

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user_token(user_id: int, email: str) -> str:
    """Create JWT token for user"""
    return jwt.encode(
        {
            "user_id": user_id,
            "email": email,
            "type": "user",
            "exp": datetime.utcnow() + timedelta(days=7)
        },
        JWT_SECRET,
        algorithm="HS256"
    )

def verify_user_token(authorization: str = Header(None)) -> int:
    """Verify user JWT token and return user_id"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor")

    token = authorization.replace('Bearer ', '')
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "user":
            raise HTTPException(status_code=401, detail="Geçersiz token türü")
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    except:
        raise HTTPException(status_code=401, detail="Geçersiz token")

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> tuple:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalı"
    if not re.search(r'[A-Za-z]', password):
        return False, "Şifre en az bir harf içermeli"
    if not re.search(r'[0-9]', password):
        return False, "Şifre en az bir rakam içermeli"
    return True, ""

def generate_token() -> str:
    """Generate random token for email verification/password reset"""
    return str(uuid.uuid4())

# ============ PUBLIC API ============

@app.get("/")
async def root():
    return {"status": "ok", "service": "TakibiEsasi License API"}

@app.post("/api/activate")
async def activate_license(req: ActivateRequest):
    """Activate a license with machine ID"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"success": False, "error": "Geçersiz lisans anahtarı"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"success": False, "error": "Bu lisans devre dışı bırakılmış"}

    if license['machine_id'] and license['machine_id'] != req.machine_id:
        cur.close()
        conn.close()
        return {"success": False, "error": "Bu lisans başka bir cihazda aktif"}

    # Activate
    cur.execute("""
        UPDATE licenses
        SET machine_id = %s, activated_at = CURRENT_TIMESTAMP, last_check = CURRENT_TIMESTAMP
        WHERE license_key = %s
    """, (req.machine_id, req.license_key))

    conn.commit()
    cur.close()
    conn.close()

    # Offline token oluştur (30 gün geçerli)
    token_data = generate_offline_token(req.license_key, req.machine_id)

    return {
        "success": True,
        "message": "Lisans aktive edildi",
        "offline_token": token_data["token"],
        "token_expires_at": token_data["expires_at"],
        "token_days_valid": token_data["days_valid"]
    }

@app.post("/api/verify")
async def verify_license(req: VerifyRequest):
    """Verify an active license"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Geçersiz lisans"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Lisans devre dışı"}

    if license['machine_id'] != req.machine_id:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Makine ID eşleşmiyor"}

    # Update last check
    cur.execute("UPDATE licenses SET last_check = CURRENT_TIMESTAMP WHERE license_key = %s", (req.license_key,))
    conn.commit()
    cur.close()
    conn.close()

    # Yeni offline token oluştur (token yenileme - 30 gün daha)
    token_data = generate_offline_token(req.license_key, req.machine_id)

    return {
        "valid": True,
        "offline_token": token_data["token"],
        "token_expires_at": token_data["expires_at"],
        "token_days_valid": token_data["days_valid"]
    }

@app.post("/api/transfer")
async def transfer_license(req: TransferRequest):
    """Transfer license to a new machine"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"success": False, "error": "Geçersiz lisans"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"success": False, "error": "Lisans devre dışı"}

    if license['machine_id'] != req.old_machine_id:
        cur.close()
        conn.close()
        return {"success": False, "error": "Mevcut makine ID eşleşmiyor"}

    if license['transfer_count'] >= 2:
        cur.close()
        conn.close()
        return {"success": False, "error": "Transfer hakkı doldu (max 2)"}

    # Transfer
    cur.execute("""
        UPDATE licenses
        SET machine_id = %s, transfer_count = transfer_count + 1, last_check = CURRENT_TIMESTAMP
        WHERE license_key = %s
    """, (req.new_machine_id, req.license_key))

    conn.commit()
    remaining = 2 - (license['transfer_count'] + 1)
    cur.close()
    conn.close()

    return {"success": True, "remaining_transfers": remaining}

@app.post("/api/check-update")
async def check_update(req: UpdateCheckRequest):
    """Check for updates"""
    release = get_current_release()

    def parse_version(v):
        """Parse version string to tuple. Handles formats like '1.0.0', '1.0', '1'"""
        if not v:
            return (0, 0, 0)
        parts = v.strip().split('.')
        # Pad with zeros if needed
        while len(parts) < 3:
            parts.append('0')
        return tuple(int(p) for p in parts[:3])

    has_update = False
    try:
        current = parse_version(req.current_version)
        latest = parse_version(release['version'])
        has_update = latest > current
    except Exception as e:
        print(f"Version comparison error: {e}, current={req.current_version}, latest={release['version']}")
        has_update = False

    return {
        "has_update": has_update,
        "current_version": req.current_version,
        "latest_version": release['version'],
        "download_url": release.get('download_url', ''),
        "release_notes": release.get('release_notes', ''),
        "is_critical": release.get('is_critical', False)
    }

@app.get("/api/releases/latest")
async def get_latest_release():
    """Get latest release info (public)"""
    return get_current_release()

# ============ ADMIN API ============

@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest):
    """Admin login"""
    if req.username == ADMIN_USERNAME and req.password == ADMIN_PASSWORD:
        token = jwt.encode(
            {"user": req.username, "exp": datetime.utcnow() + timedelta(hours=24)},
            JWT_SECRET,
            algorithm="HS256"
        )
        return {"success": True, "token": token}
    return {"success": False, "error": "Geçersiz kullanıcı adı veya şifre"}

@app.get("/api/admin/stats")
async def admin_stats(authorization: str = Header(None)):
    """Get dashboard statistics"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Total licenses
    cur.execute("SELECT COUNT(*) as count FROM licenses")
    total = cur.fetchone()['count']

    # Active licenses
    cur.execute("SELECT COUNT(*) as count FROM licenses WHERE is_active = TRUE AND machine_id IS NOT NULL")
    active = cur.fetchone()['count']

    # Today activations
    cur.execute("SELECT COUNT(*) as count FROM licenses WHERE DATE(activated_at) = CURRENT_DATE")
    today = cur.fetchone()['count']

    # Recent activations
    cur.execute("""
        SELECT license_key, machine_id, activated_at, is_active
        FROM licenses
        WHERE activated_at IS NOT NULL
        ORDER BY activated_at DESC LIMIT 10
    """)
    recent = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    release = get_current_release()

    return {
        "total_licenses": total,
        "active_licenses": active,
        "today_activations": today,
        "current_version": release['version'],
        "recent_activations": recent
    }

@app.get("/api/admin/licenses")
async def admin_licenses(authorization: str = Header(None)):
    """Get all licenses"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses ORDER BY created_at DESC")
    licenses = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return {"licenses": licenses}


@app.get("/api/admin/users")
async def admin_list_users(authorization: str = Header(None)):
    """List all users (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get users
        cur.execute("""
            SELECT id, email, full_name, phone, company_name,
                   email_verified, role, created_at, last_login_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 100
        """)

        users = []
        for row in cur.fetchall():
            users.append({
                "id": row['id'],
                "email": row['email'],
                "full_name": row['full_name'],
                "phone": row['phone'],
                "company_name": row['company_name'],
                "email_verified": row['email_verified'],
                "role": row['role'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "last_login_at": row['last_login_at'].isoformat() if row['last_login_at'] else None
            })

        # Get stats
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE email_verified = TRUE")
        verified = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE")
        today = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE payment_status = 'completed'")
        with_orders = cur.fetchone()[0]

        return {
            "success": True,
            "users": users,
            "stats": {
                "total": total,
                "verified": verified,
                "today": today,
                "with_orders": with_orders
            }
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/license/create")
async def admin_create_license(req: CreateLicenseRequest, authorization: str = Header(None)):
    """Create a new license"""
    verify_admin_token(authorization)

    license_key = generate_license_key()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO licenses (license_key, customer_name, email)
        VALUES (%s, %s, %s)
    """, (license_key, req.customer_name, req.email))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True, "license_key": license_key}

@app.post("/api/admin/license/toggle")
async def admin_toggle_license(req: LicenseActionRequest, authorization: str = Header(None)):
    """Toggle license active status"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET is_active = NOT is_active WHERE license_key = %s", (req.license_key,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/license/reset-transfer")
async def admin_reset_transfer(req: LicenseActionRequest, authorization: str = Header(None)):
    """Reset transfer count"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET transfer_count = 0, machine_id = NULL WHERE license_key = %s", (req.license_key,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/license/set-transfer")
async def admin_set_transfer(req: SetTransferRequest, authorization: str = Header(None)):
    """Set transfer count to a specific value"""
    verify_admin_token(authorization)

    if req.transfer_count < 0:
        return {"success": False, "error": "Transfer sayısı negatif olamaz"}

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET transfer_count = %s WHERE license_key = %s", (req.transfer_count, req.license_key))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/license/set-username")
async def admin_set_username(req: SetUserNameRequest, authorization: str = Header(None)):
    """Set user name for a license"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET user_name = %s WHERE license_key = %s", (req.user_name, req.license_key))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/releases")
async def admin_releases(authorization: str = Header(None)):
    """Get all releases"""
    verify_admin_token(authorization)

    return {
        "current": get_current_release(),
        "releases": get_releases_history()
    }

@app.post("/api/admin/release/publish")
async def admin_publish_release(req: ReleaseRequest, authorization: str = Header(None)):
    """Publish a new release"""
    verify_admin_token(authorization)

    release_data = {
        "version": req.version,
        "download_url": req.download_url,
        "release_notes": req.release_notes,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "is_critical": req.is_critical,
        "min_version": req.min_version or req.version
    }

    save_release(release_data)

    return {"success": True}

@app.post("/api/admin/release/set-current")
async def admin_set_current_release(req: SetCurrentReleaseRequest, authorization: str = Header(None)):
    """Set a release as current"""
    verify_admin_token(authorization)

    history = get_releases_history()
    for release in history:
        if release['version'] == req.version:
            with open(RELEASES_FILE, 'w') as f:
                json.dump(release, f, indent=2)
            return {"success": True}

    return {"success": False, "error": "Sürüm bulunamadı"}

@app.get("/api/admin/files")
async def admin_files(authorization: str = Header(None)):
    """List uploaded files"""
    verify_admin_token(authorization)

    files = []
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    "name": filename,
                    "size": stat.st_size,
                    "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "url": f"https://takibiesasi.com/download/{filename}"
                })

    files.sort(key=lambda x: x['date'], reverse=True)
    return {"files": files}

@app.post("/api/admin/upload")
async def admin_upload(file: UploadFile = File(...), authorization: str = Header(None)):
    """Upload a file"""
    verify_admin_token(authorization)

    if not file.filename.endswith('.exe'):
        raise HTTPException(status_code=400, detail="Sadece .exe dosyaları yüklenebilir")

    filepath = os.path.join(DOWNLOAD_DIR, file.filename)

    with open(filepath, 'wb') as f:
        content = await file.read()
        f.write(content)

    return {"success": True, "filename": file.filename}

@app.post("/api/admin/file/delete")
async def admin_delete_file(req: DeleteFileRequest, authorization: str = Header(None)):
    """Delete a file"""
    verify_admin_token(authorization)

    filepath = os.path.join(DOWNLOAD_DIR, req.filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return {"success": True}

    return {"success": False, "error": "Dosya bulunamadı"}

# ============ SITE SETTINGS API ============

@app.get("/api/site/settings")
async def get_site_settings():
    """Get all site settings (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT setting_key, setting_value FROM site_settings")
    rows = cur.fetchall()

    settings = {row['setting_key']: row['setting_value'] for row in rows}

    cur.close()
    conn.close()

    return settings

@app.post("/api/admin/settings/update")
async def admin_update_setting(req: SiteSettingRequest, authorization: str = Header(None)):
    """Update a site setting"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO site_settings (setting_key, setting_value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (setting_key)
        DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
    """, (req.key, req.value, req.value))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ PRICING API ============

@app.get("/api/site/pricing")
async def get_pricing():
    """Get active pricing plans (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM pricing_plans WHERE is_active = TRUE ORDER BY sort_order")
    plans = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return plans

@app.get("/api/admin/pricing")
async def admin_get_pricing(authorization: str = Header(None)):
    """Get all pricing plans"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM pricing_plans ORDER BY sort_order")
    plans = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return plans

@app.post("/api/admin/pricing/create")
async def admin_create_pricing(req: PricingPlanRequest, authorization: str = Header(None)):
    """Create a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO pricing_plans (name, price, period, features, is_popular, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (req.name, req.price, req.period, req.features, req.is_popular, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/pricing/update/{plan_id}")
async def admin_update_pricing(plan_id: int, req: PricingPlanRequest, authorization: str = Header(None)):
    """Update a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE pricing_plans
        SET name = %s, price = %s, period = %s, features = %s, is_popular = %s, sort_order = %s
        WHERE id = %s
    """, (req.name, req.price, req.period, req.features, req.is_popular, req.sort_order, plan_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/pricing/{plan_id}")
async def admin_delete_pricing(plan_id: int, authorization: str = Header(None)):
    """Delete a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM pricing_plans WHERE id = %s", (plan_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ TESTIMONIALS API ============

@app.get("/api/site/testimonials")
async def get_testimonials():
    """Get active testimonials (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM testimonials WHERE is_active = TRUE ORDER BY created_at DESC")
    testimonials = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return testimonials

@app.get("/api/admin/testimonials")
async def admin_get_testimonials(authorization: str = Header(None)):
    """Get all testimonials"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM testimonials ORDER BY created_at DESC")
    testimonials = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return testimonials

@app.post("/api/admin/testimonials/create")
async def admin_create_testimonial(req: TestimonialRequest, authorization: str = Header(None)):
    """Create a testimonial"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO testimonials (name, title, content, rating)
        VALUES (%s, %s, %s, %s)
    """, (req.name, req.title, req.content, req.rating))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/testimonials/{testimonial_id}")
async def admin_delete_testimonial(testimonial_id: int, authorization: str = Header(None)):
    """Delete a testimonial"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM testimonials WHERE id = %s", (testimonial_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ FAQ API ============

@app.get("/api/site/faq")
async def get_faq():
    """Get active FAQ items (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM faq WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/faq")
async def admin_get_faq(authorization: str = Header(None)):
    """Get all FAQ items"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM faq ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/faq/create")
async def admin_create_faq(req: FAQRequest, authorization: str = Header(None)):
    """Create a FAQ item"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO faq (question, answer, sort_order)
        VALUES (%s, %s, %s)
    """, (req.question, req.answer, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/faq/{faq_id}")
async def admin_delete_faq(faq_id: int, authorization: str = Header(None)):
    """Delete a FAQ item"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM faq WHERE id = %s", (faq_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ ANNOUNCEMENTS API ============

@app.get("/api/site/announcements")
async def get_announcements():
    """Get active announcements (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM announcements WHERE is_active = TRUE ORDER BY created_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/announcements")
async def admin_get_announcements(authorization: str = Header(None)):
    """Get all announcements"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/announcements/create")
async def admin_create_announcement(req: AnnouncementRequest, authorization: str = Header(None)):
    """Create an announcement"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO announcements (title, content, announcement_type)
        VALUES (%s, %s, %s)
    """, (req.title, req.content, req.announcement_type))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/announcements/{announcement_id}")
async def admin_delete_announcement(announcement_id: int, authorization: str = Header(None)):
    """Delete an announcement"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ CONTACT MESSAGES API ============

@app.post("/api/contact")
async def submit_contact(req: ContactMessageRequest):
    """Submit a contact message (public)"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO contact_messages (name, email, message)
        VALUES (%s, %s, %s)
    """, (req.name, req.email, req.message))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/messages")
async def admin_get_messages(authorization: str = Header(None)):
    """Get all contact messages"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM contact_messages ORDER BY created_at DESC")
    messages = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return messages

@app.post("/api/admin/messages/read")
async def admin_mark_message_read(message_id: int, authorization: str = Header(None)):
    """Mark a message as read"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE contact_messages SET is_read = TRUE WHERE id = %s", (message_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/messages/{message_id}")
async def admin_delete_message(message_id: int, authorization: str = Header(None)):
    """Delete a message"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM contact_messages WHERE id = %s", (message_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ FEATURES API ============

@app.get("/api/site/features")
async def get_features():
    """Get active features (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM features WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/features")
async def admin_get_features(authorization: str = Header(None)):
    """Get all features"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM features ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/features/create")
async def admin_create_feature(req: FeatureRequest, authorization: str = Header(None)):
    """Create a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO features (icon, title, description, sort_order)
        VALUES (%s, %s, %s, %s)
    """, (req.icon, req.title, req.description, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/features/update/{feature_id}")
async def admin_update_feature(feature_id: int, req: FeatureRequest, authorization: str = Header(None)):
    """Update a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE features
        SET icon = %s, title = %s, description = %s, sort_order = %s
        WHERE id = %s
    """, (req.icon, req.title, req.description, req.sort_order, feature_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/features/{feature_id}")
async def admin_delete_feature(feature_id: int, authorization: str = Header(None)):
    """Delete a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM features WHERE id = %s", (feature_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ SCREENSHOTS API ============

@app.get("/api/site/screenshots")
async def get_screenshots():
    """Get active screenshots (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM screenshots WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/screenshots")
async def admin_get_screenshots(authorization: str = Header(None)):
    """Get all screenshots"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM screenshots ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/screenshots/create")
async def admin_create_screenshot(req: ScreenshotRequest, authorization: str = Header(None)):
    """Create a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO screenshots (title, image_url, sort_order)
        VALUES (%s, %s, %s)
    """, (req.title, req.image_url, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/screenshots/update/{screenshot_id}")
async def admin_update_screenshot(screenshot_id: int, req: ScreenshotRequest, authorization: str = Header(None)):
    """Update a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE screenshots
        SET title = %s, image_url = %s, sort_order = %s
        WHERE id = %s
    """, (req.title, req.image_url, req.sort_order, screenshot_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/screenshots/{screenshot_id}")
async def admin_delete_screenshot(screenshot_id: int, authorization: str = Header(None)):
    """Delete a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM screenshots WHERE id = %s", (screenshot_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ BULK SETTINGS API ============

@app.post("/api/admin/settings/bulk")
async def admin_bulk_settings(req: BulkSettingsRequest, authorization: str = Header(None)):
    """Update multiple settings at once"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    for key, value in req.settings.items():
        cur.execute("""
            INSERT INTO site_settings (setting_key, setting_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (setting_key)
            DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/settings")
async def admin_get_settings(authorization: str = Header(None)):
    """Get all site settings (admin)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT setting_key, setting_value FROM site_settings")
    rows = cur.fetchall()

    settings = {row['setting_key']: row['setting_value'] for row in rows}

    cur.close()
    conn.close()

    return settings

# ============ MEDIA UPLOAD API ============

MEDIA_DIR = "/var/www/takibiesasi/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

@app.get("/api/admin/media")
async def admin_get_media(authorization: str = Header(None)):
    """Get all uploaded media"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM media ORDER BY uploaded_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/media/upload")
async def admin_upload_media(file: UploadFile = File(...), authorization: str = Header(None)):
    """Upload a media file (image)"""
    verify_admin_token(authorization)

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Sadece resim dosyaları yüklenebilir (jpg, png, gif, webp, svg)")

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{secrets.token_hex(16)}{ext}"
    filepath = os.path.join(MEDIA_DIR, unique_name)

    # Save file
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    # Save to database
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO media (filename, original_name, file_path, file_size, mime_type)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (unique_name, file.filename, filepath, len(content), file.content_type))

    media_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {
        "success": True,
        "id": media_id,
        "filename": unique_name,
        "url": f"https://takibiesasi.com/media/{unique_name}"
    }

@app.delete("/api/admin/media/{media_id}")
async def admin_delete_media(media_id: int, authorization: str = Header(None)):
    """Delete a media file"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Get file path
    cur.execute("SELECT file_path FROM media WHERE id = %s", (media_id,))
    row = cur.fetchone()

    if row:
        # Delete file
        if os.path.exists(row['file_path']):
            os.remove(row['file_path'])

        # Delete from database
        cur.execute("DELETE FROM media WHERE id = %s", (media_id,))
        conn.commit()

    cur.close()
    conn.close()

    return {"success": True}

# ============ ADMIN PANEL ============

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve admin panel"""
    html_path = "/var/www/takibiesasi/admin.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Admin panel not found</h1>"

@app.get("/favicon.svg")
async def favicon():
    """Serve favicon"""
    favicon_path = "/var/www/takibiesasi/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/favicon.ico")
async def favicon_ico():
    """Serve favicon.ico (redirect to svg)"""
    favicon_path = "/var/www/takibiesasi/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

# ============ PUBLIC PAGES ============

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Serve demo registration page"""
    html_path = "/var/www/takibiesasi/demo.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Demo page not found</h1>"

@app.get("/gizlilik", response_class=HTMLResponse)
async def privacy_page():
    """Serve privacy policy page"""
    html_path = "/var/www/takibiesasi/gizlilik.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Privacy page not found</h1>"

@app.get("/kvkk", response_class=HTMLResponse)
async def kvkk_page():
    """Serve KVKK (Turkish data protection) page"""
    html_path = "/var/www/takibiesasi/kvkk.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>KVKK page not found</h1>"

@app.get("/kullanim-sartlari", response_class=HTMLResponse)
async def terms_page():
    """Serve terms of use page"""
    html_path = "/var/www/takibiesasi/kullanim-sartlari.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Terms page not found</h1>"

@app.get("/indir", response_class=HTMLResponse)
async def download_page():
    """Serve download page"""
    html_path = "/var/www/takibiesasi/download.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Download page not found</h1>"

@app.get("/yardim", response_class=HTMLResponse)
async def help_page():
    """Serve help center page"""
    html_path = "/var/www/takibiesasi/yardim.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Help page not found</h1>"

@app.get("/changelog", response_class=HTMLResponse)
async def changelog_page():
    """Serve changelog page"""
    html_path = "/var/www/takibiesasi/changelog.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Changelog page not found</h1>"

# ============ USER AUTH PAGES ============

@app.get("/giris", response_class=HTMLResponse)
async def login_page():
    """Serve user login page"""
    html_path = "/var/www/takibiesasi/giris.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Login page not found</h1>"

@app.get("/kayit", response_class=HTMLResponse)
async def register_page():
    """Serve user registration page"""
    html_path = "/var/www/takibiesasi/kayit.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Registration page not found</h1>"

@app.get("/hesabim", response_class=HTMLResponse)
async def account_page():
    """Serve user account/dashboard page"""
    html_path = "/var/www/takibiesasi/hesabim.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Account page not found</h1>"

@app.get("/satin-al", response_class=HTMLResponse)
async def purchase_page():
    """Serve purchase/pricing page"""
    html_path = "/var/www/takibiesasi/satin-al.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Purchase page not found</h1>"

# ============ DEMO REGISTRATION API ============

class DemoRegisterRequest(BaseModel):
    email: str

@app.post("/api/demo/register")
async def register_demo(req: DemoRegisterRequest, request: Request):
    """Register email for demo and return download link"""
    import re

    # Email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, req.email):
        raise HTTPException(status_code=400, detail="Geçersiz e-posta adresi")

    conn = get_db()
    cur = conn.cursor()

    try:
        # Get client IP
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        # Try to insert (will fail if email exists)
        cur.execute("""
            INSERT INTO demo_registrations (email, ip_address, user_agent)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                registered_at = CURRENT_TIMESTAMP,
                ip_address = EXCLUDED.ip_address
            RETURNING id, registered_at
        """, (req.email.lower().strip(), client_ip, user_agent[:500] if user_agent else None))

        result = cur.fetchone()
        conn.commit()

        return {
            "success": True,
            "message": "Demo kaydı başarılı! İndirme bağlantınız hazır.",
            "download_url": "/indir",
            "email": req.email.lower().strip(),
            "registered_at": result[1].isoformat() if result else None
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Kayıt hatası: {str(e)}")
    finally:
        cur.close()
        conn.close()

@app.get("/api/demo/stats")
async def demo_stats(authorization: str = Header(None)):
    """Get demo registration stats (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        # Total registrations
        cur.execute("SELECT COUNT(*) FROM demo_registrations")
        total = cur.fetchone()[0]

        # Today's registrations
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE DATE(registered_at) = CURRENT_DATE
        """)
        today = cur.fetchone()[0]

        # This week
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE registered_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        this_week = cur.fetchone()[0]

        # Converted to license
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE converted_to_license = TRUE
        """)
        converted = cur.fetchone()[0]

        return {
            "total": total,
            "today": today,
            "this_week": this_week,
            "converted": converted,
            "conversion_rate": round((converted / total * 100), 1) if total > 0 else 0
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/demo/status")
async def get_demo_status(authorization: str = Header(None)):
    """Get demo status for logged-in user"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get user email
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if not user:
            return {"success": False, "is_demo": False}

        # Check if user has demo registration
        cur.execute("""
            SELECT registered_at, converted_to_license
            FROM demo_registrations
            WHERE email = %s
        """, (user['email'],))
        demo = cur.fetchone()

        if demo:
            # Calculate demo expiry (14 days from registration)
            from datetime import timedelta
            expiry_date = demo['registered_at'] + timedelta(days=14)
            is_expired = datetime.now() > expiry_date
            days_left = max(0, (expiry_date - datetime.now()).days)

            return {
                "success": True,
                "is_demo": True,
                "registered_at": demo['registered_at'].isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "is_expired": is_expired,
                "days_left": days_left,
                "converted_to_license": demo['converted_to_license']
            }
        else:
            return {"success": True, "is_demo": False}

    finally:
        cur.close()
        conn.close()


@app.get("/api/licenses/my")
async def get_my_licenses(authorization: str = Header(None)):
    """Get logged-in user's licenses"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get user email first
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if not user:
            return {"success": True, "licenses": []}

        # Get licenses by user_id or email
        cur.execute("""
            SELECT id, license_key, machine_id, user_name, is_active,
                   transfer_count, customer_name, email, created_at,
                   activated_at, purchase_date, source
            FROM licenses
            WHERE user_id = %s OR email = %s
            ORDER BY created_at DESC
        """, (user_id, user['email']))

        licenses = []
        for row in cur.fetchall():
            # Mask license key for display
            key = row['license_key']
            masked_key = key[:8] + "****" + key[-4:] if len(key) > 12 else key

            licenses.append({
                "id": row['id'],
                "license_key": key,
                "masked_key": masked_key,
                "machine_id": row['machine_id'],
                "machine_name": row['user_name'],
                "is_active": row['is_active'],
                "transfer_count": row['transfer_count'],
                "transfers_remaining": max(0, 2 - (row['transfer_count'] or 0)),
                "customer_name": row['customer_name'],
                "email": row['email'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "activated_at": row['activated_at'].isoformat() if row['activated_at'] else None,
                "purchase_date": row['purchase_date'].isoformat() if row['purchase_date'] else None,
                "source": row['source'] or 'manual'
            })

        return {"success": True, "licenses": licenses}

    finally:
        cur.close()
        conn.close()


@app.get("/api/downloads/my")
async def get_my_downloads(authorization: str = Header(None)):
    """Get logged-in user's download history"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, version, file_name, file_size_bytes, created_at
            FROM downloads
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """, (user_id,))

        downloads = []
        for row in cur.fetchall():
            downloads.append({
                "id": row['id'],
                "version": row['version'],
                "file_name": row['file_name'],
                "file_size": row['file_size_bytes'],
                "downloaded_at": row['created_at'].isoformat() if row['created_at'] else None
            })

        return {"success": True, "downloads": downloads}

    finally:
        cur.close()
        conn.close()


@app.get("/api/orders/my")
async def get_my_orders_simple(authorization: str = Header(None)):
    """Get logged-in user's orders (simple endpoint)"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, order_number, product_type, product_name, quantity,
                   total_price_cents, payment_status, created_at, paid_at
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """, (user_id,))

        orders = []
        for row in cur.fetchall():
            orders.append({
                "id": row['id'],
                "order_number": row['order_number'],
                "product_type": row['product_type'],
                "product_name": row['product_name'],
                "quantity": row['quantity'],
                "total": row['total_price_cents'] / 100 if row['total_price_cents'] else 0,
                "status": row['payment_status'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "paid_at": row['paid_at'].isoformat() if row['paid_at'] else None
            })

        return {"success": True, "orders": orders}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/demo-registrations")
async def list_demo_registrations(authorization: str = Header(None)):
    """List all demo registrations (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, email, ip_address, user_agent, registered_at,
                   download_count, converted_to_license
            FROM demo_registrations
            ORDER BY registered_at DESC
            LIMIT 100
        """)
        rows = cur.fetchall()

        registrations = []
        for row in rows:
            registrations.append({
                "id": row[0],
                "email": row[1],
                "ip_address": row[2],
                "user_agent": row[3][:50] + "..." if row[3] and len(row[3]) > 50 else row[3],
                "registered_at": row[4].isoformat() if row[4] else None,
                "download_count": row[5],
                "converted": row[6]
            })

        return registrations

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/demo-registrations/{reg_id}/convert")
async def mark_demo_converted(reg_id: int, authorization: str = Header(None)):
    """Mark a demo registration as converted to license"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE demo_registrations
            SET converted_to_license = TRUE
            WHERE id = %s
        """, (reg_id,))
        conn.commit()

        return {"success": True, "message": "Demo kaydı lisansa dönüştürüldü olarak işaretlendi"}

    finally:
        cur.close()
        conn.close()


@app.delete("/api/admin/demo-registrations/{reg_id}")
async def delete_demo_registration(reg_id: int, authorization: str = Header(None)):
    """Delete a demo registration"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM demo_registrations WHERE id = %s", (reg_id,))
        conn.commit()

        return {"success": True, "message": "Demo kaydı silindi"}

    finally:
        cur.close()
        conn.close()


# ============ USER AUTH API ============

@app.post("/api/auth/register")
async def user_register(req: UserRegisterRequest, request: Request):
    """Register new user"""
    # Validate email
    if not validate_email(req.email):
        return {"success": False, "error": "Geçersiz e-posta adresi"}

    # Validate password
    is_valid, error_msg = validate_password(req.password)
    if not is_valid:
        return {"success": False, "error": error_msg}

    # Check KVKK acceptance
    if not req.kvkk_accepted:
        return {"success": False, "error": "KVKK onayı gereklidir"}

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Check if email exists
        cur.execute("SELECT id FROM users WHERE email = %s", (req.email.lower(),))
        if cur.fetchone():
            return {"success": False, "error": "Bu e-posta adresi zaten kayıtlı"}

        # Hash password
        password_hash = hash_password(req.password)

        # Generate verification token
        verification_token = generate_token()

        # Get IP address
        client_ip = request.client.host if request.client else None

        # Insert user
        cur.execute("""
            INSERT INTO users (
                email, password_hash, full_name, phone, company_name,
                kvkk_accepted, kvkk_accepted_at, kvkk_ip_address,
                marketing_accepted, marketing_accepted_at,
                email_verification_token, email_verification_sent_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                TRUE, CURRENT_TIMESTAMP, %s,
                %s, CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                %s, CURRENT_TIMESTAMP
            )
            RETURNING id, email, full_name
        """, (
            req.email.lower(), password_hash, req.full_name, req.phone, req.company_name,
            client_ip,
            req.marketing_accepted, req.marketing_accepted,
            verification_token
        ))

        user = cur.fetchone()
        conn.commit()

        # TODO: Send verification email here

        return {
            "success": True,
            "message": "Kayıt başarılı! Lütfen e-posta adresinizi doğrulayın.",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name']
            }
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Kayıt sırasında bir hata oluştu: {str(e)}"}

    finally:
        cur.close()
        conn.close()


@app.post("/api/auth/login")
async def user_login(req: UserLoginRequest, request: Request):
    """User login"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Find user
        cur.execute("""
            SELECT id, email, password_hash, full_name, is_active, email_verified, role
            FROM users WHERE email = %s
        """, (req.email.lower(),))

        user = cur.fetchone()

        if not user:
            return {"success": False, "error": "E-posta veya şifre hatalı"}

        # Verify password
        if not verify_password(req.password, user['password_hash']):
            return {"success": False, "error": "E-posta veya şifre hatalı"}

        # Check if active
        if not user['is_active']:
            return {"success": False, "error": "Hesabınız devre dışı bırakılmış"}

        # Get client IP
        client_ip = request.client.host if request.client else None

        # Update last login
        cur.execute("""
            UPDATE users SET last_login_at = CURRENT_TIMESTAMP, last_login_ip = %s
            WHERE id = %s
        """, (client_ip, user['id']))
        conn.commit()

        # Create token
        token = create_user_token(user['id'], user['email'])

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "email_verified": user['email_verified'],
                "role": user['role']
            }
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/auth/logout")
async def user_logout(authorization: str = Header(None)):
    """User logout - invalidate session"""
    try:
        payload = verify_user_token(authorization)
        # In a more robust implementation, we'd add the token to a blacklist
        # or delete the session from user_sessions table
        return {"success": True, "message": "Çıkış yapıldı"}
    except:
        return {"success": True, "message": "Çıkış yapıldı"}


@app.post("/api/auth/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verify user email with token"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Find user with token
        cur.execute("""
            SELECT id, email FROM users
            WHERE email_verification_token = %s AND email_verified = FALSE
        """, (req.token,))

        user = cur.fetchone()

        if not user:
            return {"success": False, "error": "Geçersiz veya süresi dolmuş doğrulama bağlantısı"}

        # Mark as verified
        cur.execute("""
            UPDATE users SET
                email_verified = TRUE,
                email_verified_at = CURRENT_TIMESTAMP,
                email_verification_token = NULL
            WHERE id = %s
        """, (user['id'],))
        conn.commit()

        return {"success": True, "message": "E-posta adresiniz doğrulandı!"}

    finally:
        cur.close()
        conn.close()


@app.post("/api/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Request password reset"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Find user
        cur.execute("SELECT id, email, full_name FROM users WHERE email = %s", (req.email.lower(),))
        user = cur.fetchone()

        # Always return success to prevent email enumeration
        if not user:
            return {"success": True, "message": "Eğer bu e-posta kayıtlıysa, şifre sıfırlama bağlantısı gönderildi."}

        # Generate reset token
        reset_token = generate_token()
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # Save token
        cur.execute("""
            UPDATE users SET
                password_reset_token = %s,
                password_reset_expires_at = %s
            WHERE id = %s
        """, (reset_token, expires_at, user['id']))
        conn.commit()

        # TODO: Send password reset email here

        return {"success": True, "message": "Eğer bu e-posta kayıtlıysa, şifre sıfırlama bağlantısı gönderildi."}

    finally:
        cur.close()
        conn.close()


@app.post("/api/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Reset password with token"""
    # Validate new password
    is_valid, error_msg = validate_password(req.new_password)
    if not is_valid:
        return {"success": False, "error": error_msg}

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Find user with valid token
        cur.execute("""
            SELECT id FROM users
            WHERE password_reset_token = %s
            AND password_reset_expires_at > CURRENT_TIMESTAMP
        """, (req.token,))

        user = cur.fetchone()

        if not user:
            return {"success": False, "error": "Geçersiz veya süresi dolmuş şifre sıfırlama bağlantısı"}

        # Hash new password
        password_hash = hash_password(req.new_password)

        # Update password and clear token
        cur.execute("""
            UPDATE users SET
                password_hash = %s,
                password_reset_token = NULL,
                password_reset_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (password_hash, user['id']))
        conn.commit()

        return {"success": True, "message": "Şifreniz başarıyla değiştirildi!"}

    finally:
        cur.close()
        conn.close()


@app.get("/api/user/profile")
async def get_user_profile(authorization: str = Header(None)):
    """Get current user profile"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, email, full_name, phone, company_name, tax_number,
                   email_verified, role, created_at, last_login_at
            FROM users WHERE id = %s
        """, (user_id,))

        user = cur.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

        return {
            "success": True,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "phone": user['phone'],
                "company_name": user['company_name'],
                "tax_number": user['tax_number'],
                "email_verified": user['email_verified'],
                "role": user['role'],
                "created_at": user['created_at'].isoformat() if user['created_at'] else None,
                "last_login_at": user['last_login_at'].isoformat() if user['last_login_at'] else None
            }
        }

    finally:
        cur.close()
        conn.close()


@app.put("/api/user/profile")
async def update_user_profile(req: UserProfileUpdateRequest, authorization: str = Header(None)):
    """Update user profile"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Build update query dynamically
        updates = []
        values = []

        if req.full_name is not None:
            updates.append("full_name = %s")
            values.append(req.full_name)
        if req.phone is not None:
            updates.append("phone = %s")
            values.append(req.phone)
        if req.company_name is not None:
            updates.append("company_name = %s")
            values.append(req.company_name)
        if req.tax_number is not None:
            updates.append("tax_number = %s")
            values.append(req.tax_number)

        if not updates:
            return {"success": False, "error": "Güncellenecek alan belirtilmedi"}

        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, email, full_name, phone, company_name, tax_number"

        cur.execute(query, values)
        user = cur.fetchone()
        conn.commit()

        return {
            "success": True,
            "message": "Profil güncellendi",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "phone": user['phone'],
                "company_name": user['company_name'],
                "tax_number": user['tax_number']
            }
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/user/change-password")
async def change_password(req: PasswordChangeRequest, authorization: str = Header(None)):
    """Change user password"""
    user_id = verify_user_token(authorization)

    # Validate new password
    is_valid, error_msg = validate_password(req.new_password)
    if not is_valid:
        return {"success": False, "error": error_msg}

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get current password hash
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if not user:
            return {"success": False, "error": "Kullanıcı bulunamadı"}

        # Verify current password
        if not verify_password(req.current_password, user['password_hash']):
            return {"success": False, "error": "Mevcut şifre hatalı"}

        # Hash new password
        new_hash = hash_password(req.new_password)

        # Update password
        cur.execute("""
            UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_hash, user_id))
        conn.commit()

        return {"success": True, "message": "Şifreniz başarıyla değiştirildi"}

    finally:
        cur.close()
        conn.close()


@app.post("/api/auth/resend-verification")
async def resend_verification(req: ForgotPasswordRequest):
    """Resend email verification"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Find user
        cur.execute("""
            SELECT id, email, email_verified FROM users WHERE email = %s
        """, (req.email.lower(),))

        user = cur.fetchone()

        if not user:
            return {"success": True, "message": "Eğer bu e-posta kayıtlıysa, doğrulama bağlantısı gönderildi."}

        if user['email_verified']:
            return {"success": False, "error": "E-posta adresi zaten doğrulanmış"}

        # Generate new token
        verification_token = generate_token()

        cur.execute("""
            UPDATE users SET
                email_verification_token = %s,
                email_verification_sent_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (verification_token, user['id']))
        conn.commit()

        # TODO: Send verification email here

        return {"success": True, "message": "Doğrulama e-postası gönderildi"}

    finally:
        cur.close()
        conn.close()


# ============ USER PROFILE & DATA ENDPOINTS ============

@app.get("/api/auth/profile")
async def get_user_profile(authorization: str = Header(None)):
    """Get logged-in user's profile"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, email, full_name, phone, company_name,
                   email_verified, is_active, role, created_at, last_login_at
            FROM users WHERE id = %s
        """, (user_id,))

        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

        return {
            "success": True,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "phone": user['phone'],
                "company_name": user['company_name'],
                "email_verified": user['email_verified'],
                "is_active": user['is_active'],
                "role": user['role'],
                "created_at": user['created_at'].isoformat() if user['created_at'] else None,
                "last_login_at": user['last_login_at'].isoformat() if user['last_login_at'] else None
            }
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/demo/status")
async def get_user_demo_status(authorization: str = Header(None)):
    """Get demo status for logged-in user"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Check if user has an active license
        cur.execute("""
            SELECT id, license_type, status, expires_at FROM licenses
            WHERE user_id = %s AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        license = cur.fetchone()

        if license:
            return {
                "success": True,
                "has_license": True,
                "license_type": license['license_type'],
                "license_status": license['status'],
                "expires_at": license['expires_at'].isoformat() if license['expires_at'] else None,
                "demo_active": False,
                "days_remaining": None
            }

        # Check demo status
        cur.execute("""
            SELECT * FROM demo_sessions
            WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        demo = cur.fetchone()

        if not demo:
            return {
                "success": True,
                "has_license": False,
                "demo_active": False,
                "days_remaining": 0,
                "can_start_demo": True
            }

        days_remaining = max(0, (demo['demo_end_date'] - datetime.utcnow()).days) if demo['demo_end_date'] else 0
        is_active = demo['status'] == 'active' and days_remaining > 0

        return {
            "success": True,
            "has_license": False,
            "demo_active": is_active,
            "days_remaining": days_remaining,
            "total_usage_minutes": demo['total_usage_minutes'],
            "launch_count": demo['launch_count'],
            "demo_start_date": demo['demo_start_date'].isoformat() if demo['demo_start_date'] else None,
            "demo_end_date": demo['demo_end_date'].isoformat() if demo['demo_end_date'] else None
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/downloads/my")
async def get_user_downloads(authorization: str = Header(None)):
    """Get logged-in user's download history"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, version, file_name, downloaded_at
            FROM downloads
            WHERE user_id = %s
            ORDER BY downloaded_at DESC
            LIMIT 50
        """, (user_id,))

        downloads = []
        for row in cur.fetchall():
            downloads.append({
                "id": row['id'],
                "version": row['version'],
                "file_name": row['file_name'],
                "downloaded_at": row['downloaded_at'].isoformat() if row['downloaded_at'] else None
            })

        return {"success": True, "downloads": downloads, "total": len(downloads)}

    finally:
        cur.close()
        conn.close()


@app.get("/api/orders/my")
async def get_user_orders(authorization: str = Header(None)):
    """Get logged-in user's orders"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, order_number, product_type, product_name, quantity,
                   total_price_cents, payment_status, created_at, paid_at
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))

        orders = []
        for row in cur.fetchall():
            orders.append({
                "id": row['id'],
                "order_number": row['order_number'],
                "product_type": row['product_type'],
                "product_name": row['product_name'],
                "quantity": row['quantity'],
                "total_price": row['total_price_cents'] / 100 if row['total_price_cents'] else 0,
                "payment_status": row['payment_status'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "paid_at": row['paid_at'].isoformat() if row['paid_at'] else None
            })

        return {"success": True, "orders": orders, "total": len(orders)}

    finally:
        cur.close()
        conn.close()


@app.get("/api/licenses/my")
async def get_user_licenses(authorization: str = Header(None)):
    """Get logged-in user's licenses"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get user email first
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return {"success": False, "error": "Kullanıcı bulunamadı"}

        # Get licenses by user email
        cur.execute("""
            SELECT id, license_key, customer_name, email, is_active,
                   machine_id, machine_name, transfer_count, activated_at,
                   last_check, created_at, expires_at
            FROM licenses
            WHERE email = %s OR user_id = %s
            ORDER BY created_at DESC
        """, (user['email'], user_id))

        licenses = []
        for row in cur.fetchall():
            # Mask license key for security (show only first 4 and last 4 chars)
            license_key = row['license_key']
            masked_key = license_key[:4] + '-****-****-' + license_key[-4:] if license_key and len(license_key) > 8 else license_key

            licenses.append({
                "id": row['id'],
                "license_key": license_key,
                "license_key_masked": masked_key,
                "customer_name": row['customer_name'],
                "is_active": row['is_active'],
                "machine_id": row['machine_id'][:20] + '...' if row['machine_id'] and len(row['machine_id']) > 20 else row['machine_id'],
                "machine_name": row['machine_name'],
                "transfer_count": row['transfer_count'] or 0,
                "transfers_remaining": 2 - (row['transfer_count'] or 0),
                "activated_at": row['activated_at'].isoformat() if row['activated_at'] else None,
                "last_check": row['last_check'].isoformat() if row['last_check'] else None,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "expires_at": row['expires_at'].isoformat() if row['expires_at'] else None
            })

        return {"success": True, "licenses": licenses, "total": len(licenses)}

    finally:
        cur.close()
        conn.close()


# ============ ADMIN USER MANAGEMENT ============

@app.get("/api/admin/users")
async def admin_get_users(authorization: str = Header(None)):
    """Get all users (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, email, full_name, phone, company_name,
                   email_verified, is_active, role, created_at, last_login_at
            FROM users
            ORDER BY created_at DESC
        """)

        users = []
        for row in cur.fetchall():
            users.append({
                "id": row['id'],
                "email": row['email'],
                "full_name": row['full_name'],
                "phone": row['phone'],
                "company_name": row['company_name'],
                "email_verified": row['email_verified'],
                "is_active": row['is_active'],
                "role": row['role'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "last_login_at": row['last_login_at'].isoformat() if row['last_login_at'] else None
            })

        return {"success": True, "users": users, "total": len(users)}

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/users/{user_id}/toggle")
async def admin_toggle_user(user_id: int, authorization: str = Header(None)):
    """Toggle user active status (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users SET is_active = NOT is_active, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING is_active
        """, (user_id,))

        result = cur.fetchone()
        if not result:
            return {"success": False, "error": "Kullanıcı bulunamadı"}

        conn.commit()

        status = "aktif" if result[0] else "devre dışı"
        return {"success": True, "message": f"Kullanıcı {status} yapıldı", "is_active": result[0]}

    finally:
        cur.close()
        conn.close()


# ============ ORDER/PAYMENT API ============

# Ürün fiyatları (kuruş cinsinden)
PRODUCT_PRICES = {
    "individual": {
        "name": "TakibiEsasi Bireysel Lisans",
        "price_cents": 599000,  # 5990 TL
        "period": "Ömür Boyu"
    },
    "office_server": {
        "name": "TakibiEsasi Büro Sunucu Lisansı",
        "price_cents": 1499000,  # 14990 TL
        "period": "Ömür Boyu"
    },
    "office_user": {
        "name": "TakibiEsasi Büro Kullanıcı Lisansı",
        "price_cents": 299000,  # 2990 TL
        "period": "Ömür Boyu"
    }
}

@app.post("/api/orders/create")
async def create_order(req: CreateOrderRequest, authorization: str = Header(None)):
    """Create a new order"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get user info for auto-fill billing
        cur.execute("SELECT email, full_name, phone FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        # Determine product info
        if req.product_type in PRODUCT_PRICES:
            # Standard product
            product = PRODUCT_PRICES[req.product_type]
            product_name = product["name"]
            unit_price = product["price_cents"]
        elif req.product_type == 'license' and req.product_name and req.unit_price_cents:
            # Custom/demo product from frontend
            product_name = f"TakibiEsasi {req.product_name} Lisansı"
            unit_price = req.unit_price_cents
        else:
            return {"success": False, "error": "Geçersiz ürün tipi veya eksik bilgi"}

        # Calculate prices
        subtotal = unit_price * req.quantity
        tax_rate = 20  # KDV %20
        tax_cents = int(subtotal * tax_rate / 100)
        total = subtotal + tax_cents

        # Auto-fill billing info from user if not provided
        billing_name = req.billing_name or (user['full_name'] if user else None)
        billing_email = req.billing_email or (user['email'] if user else None)
        billing_phone = req.billing_phone or (user['phone'] if user else None)

        # Generate order number
        cur.execute("SELECT generate_order_number()")
        order_number = cur.fetchone()[0]

        # Create order
        cur.execute("""
            INSERT INTO orders (
                user_id, order_number, product_type, product_name, quantity,
                unit_price_cents, subtotal_cents, tax_rate, tax_cents, total_price_cents,
                billing_name, billing_email, billing_phone, billing_address,
                billing_tax_number, billing_tax_office, customer_notes,
                payment_status
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                'pending'
            )
            RETURNING id, order_number, total_price_cents, created_at
        """, (
            user_id, order_number, req.product_type, product_name, req.quantity,
            unit_price, subtotal, tax_rate, tax_cents, total,
            billing_name, billing_email, billing_phone, req.billing_address,
            req.billing_tax_number, req.billing_tax_office, req.customer_notes
        ))

        order = cur.fetchone()
        conn.commit()

        return {
            "success": True,
            "message": "Sipariş oluşturuldu",
            "order": {
                "id": order['id'],
                "order_number": order['order_number'],
                "product_name": product_name,
                "quantity": req.quantity,
                "subtotal": subtotal / 100,  # TL cinsinden
                "tax": tax_cents / 100,
                "total": total / 100,
                "created_at": order['created_at'].isoformat() if order['created_at'] else None
            }
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Sipariş oluşturulamadı: {str(e)}"}

    finally:
        cur.close()
        conn.close()


@app.get("/api/orders/my-orders")
async def get_my_orders(authorization: str = Header(None)):
    """Get current user's orders"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT id, order_number, product_type, product_name, quantity,
                   total_price_cents, payment_status, created_at, paid_at
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))

        orders = []
        for row in cur.fetchall():
            orders.append({
                "id": row['id'],
                "order_number": row['order_number'],
                "product_type": row['product_type'],
                "product_name": row['product_name'],
                "quantity": row['quantity'],
                "total": row['total_price_cents'] / 100,
                "status": row['payment_status'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "paid_at": row['paid_at'].isoformat() if row['paid_at'] else None
            })

        return {"success": True, "orders": orders}

    finally:
        cur.close()
        conn.close()


@app.get("/api/orders/{order_id}")
async def get_order_detail(order_id: int, authorization: str = Header(None)):
    """Get order details"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT * FROM orders WHERE id = %s AND user_id = %s
        """, (order_id, user_id))

        order = cur.fetchone()

        if not order:
            return {"success": False, "error": "Sipariş bulunamadı"}

        return {
            "success": True,
            "order": {
                "id": order['id'],
                "order_number": order['order_number'],
                "product_type": order['product_type'],
                "product_name": order['product_name'],
                "quantity": order['quantity'],
                "unit_price": order['unit_price_cents'] / 100,
                "subtotal": order['subtotal_cents'] / 100,
                "tax_rate": order['tax_rate'],
                "tax": order['tax_cents'] / 100,
                "total": order['total_price_cents'] / 100,
                "status": order['payment_status'],
                "billing_name": order['billing_name'],
                "billing_email": order['billing_email'],
                "billing_phone": order['billing_phone'],
                "billing_address": order['billing_address'],
                "created_at": order['created_at'].isoformat() if order['created_at'] else None,
                "paid_at": order['paid_at'].isoformat() if order['paid_at'] else None
            }
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/orders/{order_id}/pay")
async def mock_payment(order_id: int, req: MockPaymentRequest, authorization: str = Header(None)):
    """Process mock payment for an order"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Get order
        cur.execute("""
            SELECT * FROM orders WHERE id = %s AND user_id = %s
        """, (order_id, user_id))

        order = cur.fetchone()

        if not order:
            return {"success": False, "error": "Sipariş bulunamadı"}

        if order['payment_status'] == 'completed':
            return {"success": False, "error": "Bu sipariş zaten ödenmiş"}

        if order['payment_status'] == 'cancelled':
            return {"success": False, "error": "Bu sipariş iptal edilmiş"}

        # Demo mode - accept transaction_id directly or generate one
        if req.transaction_id:
            # Demo mode with frontend-provided transaction ID
            transaction_id = req.transaction_id
            card_last4 = "DEMO"
            card_holder = "Demo User"
        elif req.card_number:
            # Card payment mode
            if len(req.card_number.replace(" ", "")) < 16:
                return {"success": False, "error": "Geçersiz kart numarası"}
            transaction_id = f"TXN-{secrets.token_hex(8).upper()}"
            card_last4 = req.card_number.replace(" ", "")[-4:]
            card_holder = req.card_holder or "Unknown"
        else:
            return {"success": False, "error": "Ödeme bilgisi gerekli"}

        # Update order with payment info
        cur.execute("""
            UPDATE orders SET
                payment_status = 'completed',
                payment_method = 'credit_card',
                installment_count = %s,
                mock_card_last4 = %s,
                mock_card_holder = %s,
                mock_transaction_id = %s,
                paid_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, order_number
        """, (
            req.installment_count,
            card_last4,
            card_holder,
            transaction_id,
            order_id
        ))

        updated_order = cur.fetchone()

        # Create license for the user
        license_key = generate_license_key()
        cur.execute("""
            INSERT INTO licenses (
                license_key, customer_name, email, is_active,
                user_id, order_id, purchase_price_cents, purchase_date, source
            ) VALUES (
                %s, %s, %s, TRUE,
                %s, %s, %s, CURRENT_TIMESTAMP, 'purchase'
            )
            RETURNING license_key
        """, (
            license_key, order['billing_name'], order['billing_email'],
            user_id, order_id, order['total_price_cents']
        ))

        new_license = cur.fetchone()
        conn.commit()

        # TODO: Send purchase confirmation email

        return {
            "success": True,
            "message": "Ödeme başarılı! Lisans anahtarınız oluşturuldu.",
            "transaction_id": transaction_id,
            "license_key": new_license['license_key'],
            "order_number": updated_order['order_number']
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ödeme işlemi başarısız: {str(e)}"}

    finally:
        cur.close()
        conn.close()


@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: int, authorization: str = Header(None)):
    """Cancel a pending order"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE orders SET
                payment_status = 'cancelled',
                cancelled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s AND payment_status = 'pending'
            RETURNING id
        """, (order_id, user_id))

        result = cur.fetchone()

        if not result:
            return {"success": False, "error": "Sipariş bulunamadı veya iptal edilemez"}

        conn.commit()
        return {"success": True, "message": "Sipariş iptal edildi"}

    finally:
        cur.close()
        conn.close()


# ============ ADMIN ORDER MANAGEMENT ============

@app.get("/api/admin/orders")
async def admin_get_orders(authorization: str = Header(None)):
    """Get all orders (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT o.*, u.email as user_email, u.full_name as user_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            ORDER BY o.created_at DESC
        """)

        orders = []
        for row in cur.fetchall():
            orders.append({
                "id": row['id'],
                "order_number": row['order_number'],
                "user_email": row['user_email'],
                "user_name": row['user_name'],
                "product_name": row['product_name'],
                "quantity": row['quantity'],
                "total": row['total_price_cents'] / 100,
                "status": row['payment_status'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "paid_at": row['paid_at'].isoformat() if row['paid_at'] else None
            })

        return {"success": True, "orders": orders, "total": len(orders)}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/orders/{order_id}")
async def admin_get_order_detail(order_id: int, authorization: str = Header(None)):
    """Get order details (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT o.*, u.email as user_email, u.full_name as user_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            WHERE o.id = %s
        """, (order_id,))

        order = cur.fetchone()

        if not order:
            return {"success": False, "error": "Sipariş bulunamadı"}

        return {
            "success": True,
            "order": dict(order)
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/orders/{order_id}/status")
async def admin_update_order_status(order_id: int, req: OrderStatusUpdateRequest, authorization: str = Header(None)):
    """Update order status (admin only)"""
    verify_admin_token(authorization)

    valid_statuses = ['pending', 'processing', 'completed', 'failed', 'refunded', 'cancelled']
    if req.status not in valid_statuses:
        return {"success": False, "error": "Geçersiz durum"}

    conn = get_db()
    cur = conn.cursor()

    try:
        update_fields = ["payment_status = %s", "updated_at = CURRENT_TIMESTAMP"]
        values = [req.status]

        if req.status == 'completed':
            update_fields.append("paid_at = CURRENT_TIMESTAMP")
        elif req.status == 'cancelled':
            update_fields.append("cancelled_at = CURRENT_TIMESTAMP")
        elif req.status == 'refunded':
            update_fields.append("refunded_at = CURRENT_TIMESTAMP")

        values.append(order_id)

        cur.execute(f"""
            UPDATE orders SET {', '.join(update_fields)}
            WHERE id = %s
            RETURNING id
        """, values)

        result = cur.fetchone()

        if not result:
            return {"success": False, "error": "Sipariş bulunamadı"}

        conn.commit()
        return {"success": True, "message": f"Sipariş durumu '{req.status}' olarak güncellendi"}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/orders/stats")
async def admin_order_stats(authorization: str = Header(None)):
    """Get order statistics (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Total orders
        cur.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cur.fetchone()['count']

        # Completed orders
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE payment_status = 'completed'")
        completed_orders = cur.fetchone()['count']

        # Total revenue
        cur.execute("SELECT COALESCE(SUM(total_price_cents), 0) as total FROM orders WHERE payment_status = 'completed'")
        total_revenue = cur.fetchone()['total'] / 100

        # Today's orders
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = CURRENT_DATE")
        today_orders = cur.fetchone()['count']

        # Today's revenue
        cur.execute("""
            SELECT COALESCE(SUM(total_price_cents), 0) as total
            FROM orders
            WHERE DATE(paid_at) = CURRENT_DATE AND payment_status = 'completed'
        """)
        today_revenue = cur.fetchone()['total'] / 100

        # Pending orders
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE payment_status = 'pending'")
        pending_orders = cur.fetchone()['count']

        return {
            "success": True,
            "stats": {
                "total_orders": total_orders,
                "completed_orders": completed_orders,
                "pending_orders": pending_orders,
                "total_revenue": total_revenue,
                "today_orders": today_orders,
                "today_revenue": today_revenue
            }
        }

    finally:
        cur.close()
        conn.close()


# ============ INVOICE API ============

@app.post("/api/invoices/create")
async def create_invoice(req: CreateInvoiceRequest, authorization: str = Header(None)):
    """Create invoice for a completed order (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("SELECT * FROM orders WHERE id = %s", (req.order_id,))
        order = cur.fetchone()

        if not order:
            return {"success": False, "error": "Sipariş bulunamadı"}

        if order['payment_status'] != 'completed':
            return {"success": False, "error": "Sadece tamamlanmış siparişler için fatura oluşturulabilir"}

        cur.execute("SELECT id FROM invoices WHERE order_id = %s", (req.order_id,))
        if cur.fetchone():
            return {"success": False, "error": "Bu sipariş için zaten fatura oluşturulmuş"}

        cur.execute("SELECT generate_invoice_number()")
        invoice_number = cur.fetchone()[0]

        buyer_type = 'corporate' if order['billing_tax_number'] else 'individual'

        cur.execute("""
            INSERT INTO invoices (
                order_id, user_id, invoice_number, invoice_date,
                buyer_type, buyer_name, buyer_email, buyer_phone,
                buyer_address, buyer_tax_number, buyer_tax_office,
                subtotal_cents, tax_rate, tax_cents, total_cents,
                status, issued_at
            ) VALUES (
                %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, 'issued', CURRENT_TIMESTAMP
            )
            RETURNING id, invoice_number
        """, (
            order['id'], order['user_id'], invoice_number, buyer_type,
            order['billing_name'], order['billing_email'], order['billing_phone'],
            order['billing_address'], order['billing_tax_number'], order['billing_tax_office'],
            order['subtotal_cents'], order['tax_rate'], order['tax_cents'], order['total_price_cents']
        ))

        invoice = cur.fetchone()
        cur.execute("UPDATE orders SET invoice_id = %s WHERE id = %s", (invoice['id'], order['id']))
        conn.commit()

        return {"success": True, "invoice": {"id": invoice['id'], "invoice_number": invoice['invoice_number']}}

    finally:
        cur.close()
        conn.close()


@app.get("/api/invoices/my-invoices")
async def get_my_invoices(authorization: str = Header(None)):
    """Get current user's invoices"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT i.*, o.order_number, o.product_name FROM invoices i
            JOIN orders o ON i.order_id = o.id WHERE i.user_id = %s ORDER BY i.created_at DESC
        """, (user_id,))

        invoices = [{"id": r['id'], "invoice_number": r['invoice_number'], "order_number": r['order_number'],
                     "product_name": r['product_name'], "total": r['total_cents'] / 100, "status": r['status'],
                     "invoice_date": r['invoice_date'].isoformat() if r['invoice_date'] else None} for r in cur.fetchall()]

        return {"success": True, "invoices": invoices}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/invoices")
async def admin_get_invoices(authorization: str = Header(None)):
    """Get all invoices (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT i.*, o.order_number, u.email as user_email FROM invoices i
            JOIN orders o ON i.order_id = o.id LEFT JOIN users u ON i.user_id = u.id ORDER BY i.created_at DESC
        """)

        invoices = [{"id": r['id'], "invoice_number": r['invoice_number'], "order_number": r['order_number'],
                     "user_email": r['user_email'], "buyer_name": r['buyer_name'], "total": r['total_cents'] / 100,
                     "status": r['status'], "invoice_date": r['invoice_date'].isoformat() if r['invoice_date'] else None}
                    for r in cur.fetchall()]

        return {"success": True, "invoices": invoices, "total": len(invoices)}

    finally:
        cur.close()
        conn.close()


# ============ DOWNLOAD TRACKING API ============

@app.post("/api/downloads/track")
async def track_download(req: DownloadTrackRequest, request: Request, authorization: str = Header(None)):
    """Track a download"""
    user_id = verify_user_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        cur.execute("""
            INSERT INTO downloads (user_id, version, file_name, file_size_bytes, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (user_id, req.version, req.file_name, req.file_size_bytes, client_ip, user_agent))

        download_id = cur.fetchone()[0]
        conn.commit()

        return {"success": True, "download_id": download_id}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/downloads/stats")
async def admin_download_stats(authorization: str = Header(None)):
    """Get download statistics (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("SELECT COUNT(*) as count FROM downloads")
        total = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM downloads WHERE DATE(downloaded_at) = CURRENT_DATE")
        today = cur.fetchone()['count']

        cur.execute("SELECT version, COUNT(*) as count FROM downloads GROUP BY version ORDER BY count DESC LIMIT 10")
        by_version = [{"version": r['version'], "count": r['count']} for r in cur.fetchall()]

        return {"success": True, "stats": {"total_downloads": total, "today_downloads": today, "by_version": by_version}}

    finally:
        cur.close()
        conn.close()


# ============ DEMO HEARTBEAT API ============

@app.post("/api/demo/heartbeat")
async def demo_heartbeat(req: DemoHeartbeatRequest, request: Request):
    """Record demo usage heartbeat"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("SELECT id, status, demo_end_date FROM demo_sessions WHERE machine_id = %s", (req.machine_id,))
        session = cur.fetchone()

        if not session:
            demo_end = datetime.utcnow() + timedelta(days=14)
            cur.execute("""
                INSERT INTO demo_sessions (machine_id, machine_name, os_info, demo_start_date, demo_end_date, last_heartbeat, total_usage_minutes)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP, %s) RETURNING id, demo_end_date, status
            """, (req.machine_id, req.machine_name, req.os_info, demo_end, req.usage_minutes))
            conn.commit()
            return {"success": True, "status": "active", "days_remaining": 14, "message": "Demo başlatıldı"}

        cur.execute("""
            UPDATE demo_sessions SET last_heartbeat = CURRENT_TIMESTAMP, total_usage_minutes = total_usage_minutes + %s,
            launch_count = launch_count + 1, machine_name = COALESCE(%s, machine_name), os_info = COALESCE(%s, os_info)
            WHERE id = %s
        """, (req.usage_minutes, req.machine_name, req.os_info, session['id']))
        conn.commit()

        days_remaining = max(0, (session['demo_end_date'] - datetime.utcnow()).days) if session['demo_end_date'] else 0
        status = session['status']

        if days_remaining <= 0 and status == 'active':
            cur.execute("UPDATE demo_sessions SET status = 'expired' WHERE id = %s", (session['id'],))
            conn.commit()
            status = 'expired'

        return {"success": True, "status": status, "days_remaining": days_remaining}

    finally:
        cur.close()
        conn.close()


@app.get("/api/demo/status/{machine_id}")
async def get_demo_status(machine_id: str):
    """Get demo status for a machine"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("SELECT * FROM demo_sessions WHERE machine_id = %s", (machine_id,))
        session = cur.fetchone()

        if not session:
            return {"success": True, "status": "no_demo", "can_start": True}

        days_remaining = max(0, (session['demo_end_date'] - datetime.utcnow()).days) if session['demo_end_date'] else 0

        return {"success": True, "status": session['status'], "days_remaining": days_remaining,
                "total_usage_minutes": session['total_usage_minutes'], "launch_count": session['launch_count']}

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/demo-sessions")
async def admin_get_demo_sessions(authorization: str = Header(None)):
    """Get all demo sessions (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("""
            SELECT ds.*, u.email as user_email FROM demo_sessions ds
            LEFT JOIN users u ON ds.user_id = u.id ORDER BY ds.created_at DESC
        """)

        sessions = []
        for r in cur.fetchall():
            days_remaining = max(0, (r['demo_end_date'] - datetime.utcnow()).days) if r['demo_end_date'] else 0
            sessions.append({"id": r['id'], "machine_id": r['machine_id'][:20] + "..." if r['machine_id'] and len(r['machine_id']) > 20 else r['machine_id'],
                             "machine_name": r['machine_name'], "user_email": r['user_email'], "status": r['status'],
                             "days_remaining": days_remaining, "total_usage_minutes": r['total_usage_minutes'], "launch_count": r['launch_count']})

        return {"success": True, "sessions": sessions, "total": len(sessions)}

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/demo-sessions/{demo_id}/extend")
async def admin_extend_demo(demo_id: int, req: DemoExtendRequest, authorization: str = Header(None)):
    """Extend a demo session (admin only)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE demo_sessions SET demo_end_date = demo_end_date + INTERVAL '%s days', status = 'extended',
            extension_count = extension_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id
        """, (req.days, demo_id))

        if not cur.fetchone():
            return {"success": False, "error": "Demo oturumu bulunamadı"}

        conn.commit()
        return {"success": True, "message": f"Demo {req.days} gün uzatıldı"}

    finally:
        cur.close()
        conn.close()


# ============ STATIC FILES ============

# Mount download directory for static file serving
if os.path.exists(DOWNLOAD_DIR):
    app.mount("/download", StaticFiles(directory=DOWNLOAD_DIR), name="download")

# Mount media directory for image serving
if os.path.exists(MEDIA_DIR):
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
