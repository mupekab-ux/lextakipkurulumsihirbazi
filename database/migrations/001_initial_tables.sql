-- ============================================
-- TakibiEsasi - Veritabanı Migration
-- FAZ 2: Tüm Tablolar
-- Tarih: 2024
-- ============================================

-- ============================================
-- 1. USERS (Kullanıcılar)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(20),
    company_name VARCHAR(200),
    tax_number VARCHAR(20),

    -- KVKK ve pazarlama onayları
    kvkk_accepted BOOLEAN DEFAULT FALSE,
    kvkk_accepted_at TIMESTAMP,
    kvkk_ip_address VARCHAR(50),
    marketing_accepted BOOLEAN DEFAULT FALSE,
    marketing_accepted_at TIMESTAMP,

    -- E-posta doğrulama
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_token VARCHAR(100),
    email_verification_sent_at TIMESTAMP,
    email_verified_at TIMESTAMP,

    -- Şifre sıfırlama
    password_reset_token VARCHAR(100),
    password_reset_expires_at TIMESTAMP,

    -- Durum ve rol
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(20) DEFAULT 'user',  -- user, admin

    -- Tarihler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(50)
);

-- Users Index'leri
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);

COMMENT ON TABLE users IS 'Kayıtlı kullanıcılar - site ve uygulama kullanıcıları';


-- ============================================
-- 2. USER_SESSIONS (Oturum Yönetimi)
-- ============================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Token'lar
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,

    -- Cihaz bilgileri
    ip_address VARCHAR(50),
    user_agent TEXT,
    device_info VARCHAR(200),

    -- Süre
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Durum
    is_active BOOLEAN DEFAULT TRUE
);

-- User Sessions Index'leri
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

COMMENT ON TABLE user_sessions IS 'Aktif kullanıcı oturumları - JWT token takibi';


-- ============================================
-- 3. DEMO_SESSIONS (Demo Oturumları)
-- ============================================
CREATE TABLE IF NOT EXISTS demo_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Makine tanımlama
    machine_id VARCHAR(100) NOT NULL,  -- CPU+MAC+UUID hash
    machine_name VARCHAR(200),         -- Bilgisayar adı
    os_info VARCHAR(100),              -- Windows 10, Windows 11, etc.

    -- Demo süreleri
    demo_start_date TIMESTAMP NOT NULL,
    demo_end_date TIMESTAMP NOT NULL,  -- start + 14 gün

    -- Kullanım takibi
    last_heartbeat TIMESTAMP,
    total_usage_minutes INTEGER DEFAULT 0,
    launch_count INTEGER DEFAULT 1,

    -- Durum
    status VARCHAR(20) DEFAULT 'active',  -- active, expired, converted, extended

    -- Dönüşüm bilgisi
    converted_to_license_id INTEGER,
    converted_at TIMESTAMP,

    -- Uzatma
    extension_count INTEGER DEFAULT 0,
    extended_by_admin_id INTEGER,
    extension_notes TEXT,

    -- Tarihler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Benzersizlik: Aynı kullanıcı aynı makinede tek demo
    UNIQUE(user_id, machine_id)
);

-- Demo Sessions Index'leri
CREATE INDEX IF NOT EXISTS idx_demo_user ON demo_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_demo_machine ON demo_sessions(machine_id);
CREATE INDEX IF NOT EXISTS idx_demo_status ON demo_sessions(status);
CREATE INDEX IF NOT EXISTS idx_demo_end_date ON demo_sessions(demo_end_date);

COMMENT ON TABLE demo_sessions IS 'Demo kullanım takibi - hangi bilgisayarda ne kadar süre';


-- ============================================
-- 4. DOWNLOADS (İndirme Kayıtları)
-- ============================================
CREATE TABLE IF NOT EXISTS downloads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- İndirme bilgileri
    version VARCHAR(20) NOT NULL,      -- v1.0.0
    file_name VARCHAR(200) NOT NULL,   -- TakibiEsasi-Setup-v1.0.0.exe
    file_size_bytes BIGINT,

    -- İstek bilgileri
    ip_address VARCHAR(50),
    user_agent TEXT,
    referrer VARCHAR(500),

    -- Tarih
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Downloads Index'leri
CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id);
CREATE INDEX IF NOT EXISTS idx_downloads_date ON downloads(downloaded_at);
CREATE INDEX IF NOT EXISTS idx_downloads_version ON downloads(version);

COMMENT ON TABLE downloads IS 'Kullanıcı indirme geçmişi';


-- ============================================
-- 5. ORDERS (Siparişler)
-- ============================================
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Sipariş numarası
    order_number VARCHAR(50) UNIQUE NOT NULL,  -- ORD-2024-00001

    -- Ürün bilgileri
    product_type VARCHAR(50) NOT NULL,  -- individual, office_server, office_user
    product_name VARCHAR(200) NOT NULL, -- TakibiEsasi Bireysel Lisans
    quantity INTEGER DEFAULT 1,

    -- Fiyatlandırma (kuruş cinsinden)
    unit_price_cents INTEGER NOT NULL,      -- 599000 (5990₺)
    discount_cents INTEGER DEFAULT 0,
    subtotal_cents INTEGER NOT NULL,
    tax_rate INTEGER DEFAULT 20,            -- KDV %20
    tax_cents INTEGER NOT NULL,
    total_price_cents INTEGER NOT NULL,

    -- Ödeme bilgileri
    payment_method VARCHAR(50),             -- credit_card, bank_transfer
    payment_status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed, refunded, cancelled
    installment_count INTEGER DEFAULT 1,

    -- Mock ödeme bilgileri (test için)
    mock_card_last4 VARCHAR(4),
    mock_card_holder VARCHAR(200),
    mock_transaction_id VARCHAR(100),

    -- İlişkiler
    license_id INTEGER,
    invoice_id INTEGER,

    -- Fatura bilgileri (sipariş anında)
    billing_name VARCHAR(200),
    billing_email VARCHAR(200),
    billing_phone VARCHAR(20),
    billing_address TEXT,
    billing_tax_number VARCHAR(20),
    billing_tax_office VARCHAR(100),

    -- Tarihler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    refunded_at TIMESTAMP,

    -- Notlar
    admin_notes TEXT,
    customer_notes TEXT
);

-- Orders Index'leri
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(payment_status);
CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

COMMENT ON TABLE orders IS 'Tüm siparişler - mock ve gerçek';


-- ============================================
-- 6. INVOICES (Faturalar)
-- ============================================
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Fatura numarası
    invoice_number VARCHAR(50) UNIQUE NOT NULL,  -- INV-2024-00001
    invoice_date DATE NOT NULL,
    due_date DATE,

    -- Alıcı bilgileri
    buyer_type VARCHAR(20) DEFAULT 'individual',  -- individual, corporate
    buyer_name VARCHAR(200) NOT NULL,
    buyer_email VARCHAR(200) NOT NULL,
    buyer_phone VARCHAR(20),
    buyer_address TEXT,
    buyer_city VARCHAR(100),
    buyer_country VARCHAR(100) DEFAULT 'Türkiye',
    buyer_postal_code VARCHAR(20),
    buyer_tax_number VARCHAR(20),
    buyer_tax_office VARCHAR(100),

    -- Tutar (kuruş)
    subtotal_cents INTEGER NOT NULL,
    discount_cents INTEGER DEFAULT 0,
    tax_rate INTEGER DEFAULT 20,
    tax_cents INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,

    -- Durum
    status VARCHAR(50) DEFAULT 'draft',  -- draft, issued, sent, paid, cancelled

    -- PDF
    pdf_path VARCHAR(500),
    pdf_generated_at TIMESTAMP,

    -- E-fatura (gelecekte)
    e_invoice_id VARCHAR(100),
    e_invoice_status VARCHAR(50),

    -- Tarihler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issued_at TIMESTAMP,
    sent_at TIMESTAMP,
    paid_at TIMESTAMP
);

-- Invoices Index'leri
CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_user ON invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);

COMMENT ON TABLE invoices IS 'Fatura kayıtları';


-- ============================================
-- 7. LICENSES TABLOSU GÜNCELLEME
-- ============================================
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS order_id INTEGER REFERENCES orders(id);
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS purchase_price_cents INTEGER;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS purchase_date TIMESTAMP;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'direct';  -- direct, demo_conversion, transfer

-- Licenses Index'leri
CREATE INDEX IF NOT EXISTS idx_licenses_user ON licenses(user_id);
CREATE INDEX IF NOT EXISTS idx_licenses_order ON licenses(order_id);


-- ============================================
-- 8. EMAIL_LOGS (E-posta Logları)
-- ============================================
CREATE TABLE IF NOT EXISTS email_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- E-posta bilgileri
    email_type VARCHAR(50) NOT NULL,  -- welcome, verification, password_reset, demo_reminder, purchase_confirmation
    to_email VARCHAR(200) NOT NULL,
    subject VARCHAR(500),

    -- Durum
    status VARCHAR(20) DEFAULT 'pending',  -- pending, sent, failed, bounced
    error_message TEXT,

    -- Tarihler
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,

    -- Meta
    template_version VARCHAR(20),
    metadata JSONB
);

-- Email Logs Index'leri
CREATE INDEX IF NOT EXISTS idx_email_logs_user ON email_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_type ON email_logs(email_type);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);

COMMENT ON TABLE email_logs IS 'E-posta gönderim kayıtları';


-- ============================================
-- 9. SEQUENCES (Numara Üretimi)
-- ============================================
CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1;
CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1;


-- ============================================
-- 10. FUNCTIONS (Yardımcı Fonksiyonlar)
-- ============================================

-- Sipariş numarası oluştur
CREATE OR REPLACE FUNCTION generate_order_number()
RETURNS VARCHAR AS $$
BEGIN
    RETURN 'ORD-' || TO_CHAR(CURRENT_DATE, 'YYYY') || '-' || LPAD(nextval('order_number_seq')::TEXT, 5, '0');
END;
$$ LANGUAGE plpgsql;

-- Fatura numarası oluştur
CREATE OR REPLACE FUNCTION generate_invoice_number()
RETURNS VARCHAR AS $$
BEGIN
    RETURN 'INV-' || TO_CHAR(CURRENT_DATE, 'YYYY') || '-' || LPAD(nextval('invoice_number_seq')::TEXT, 5, '0');
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- KONTROL SORGULARI
-- Migration sonrası çalıştır:
-- ============================================
--
-- -- Tabloları listele
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- ORDER BY table_name;
--
-- -- Her tablonun sütun sayısı
-- SELECT
--     t.table_name,
--     COUNT(c.column_name) as column_count
-- FROM information_schema.tables t
-- LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
-- WHERE t.table_schema = 'public'
-- GROUP BY t.table_name
-- ORDER BY t.table_name;
--
-- -- Index'leri listele
-- SELECT tablename, indexname FROM pg_indexes
-- WHERE schemaname = 'public'
-- ORDER BY tablename;
--
-- -- Fonksiyonları kontrol et
-- SELECT generate_order_number();
-- SELECT generate_invoice_number();
-- ============================================
