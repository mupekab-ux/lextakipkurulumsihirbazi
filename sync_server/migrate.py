# -*- coding: utf-8 -*-
"""
Database Migration Script

Eski şemadan yeni künye tabanlı şemaya geçiş.
"""

import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Veritabanı migrasyonunu çalıştır"""

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    inspector = inspect(engine)

    existing_tables = inspector.get_table_names()
    logger.info(f"Mevcut tablolar: {existing_tables}")

    try:
        # 1. firms tablosunu kontrol et (olması lazım)
        if 'firms' not in existing_tables:
            logger.info("firms tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE firms (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    firm_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("✓ firms tablosu oluşturuldu")

        # 2. users tablosu - firm_users varsa migrate et
        if 'users' not in existing_tables:
            if 'firm_users' in existing_tables:
                logger.info("firm_users → users tablosuna migrate ediliyor...")
                # Yeni users tablosunu oluştur (UUID tipli firm_id)
                session.execute(text("""
                    CREATE TABLE users (
                        uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        firm_id UUID NOT NULL REFERENCES firms(id),
                        username VARCHAR(100) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        role VARCHAR(50) DEFAULT 'user',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(firm_id, username)
                    )
                """))

                # firm_users'dan veri migrate et (firm_users'ta uuid kolonu olmayabilir)
                session.execute(text("""
                    INSERT INTO users (uuid, firm_id, username, password_hash, email, role, is_active, created_at)
                    SELECT
                        gen_random_uuid(),
                        firm_id,
                        username,
                        password_hash,
                        COALESCE(email, ''),
                        COALESCE(role, 'user'),
                        COALESCE(is_active, TRUE),
                        COALESCE(created_at, CURRENT_TIMESTAMP)
                    FROM firm_users
                """))
                logger.info("✓ firm_users verileri users tablosuna aktarıldı")
            else:
                logger.info("users tablosu oluşturuluyor...")
                session.execute(text("""
                    CREATE TABLE users (
                        uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        firm_id UUID NOT NULL REFERENCES firms(id),
                        username VARCHAR(100) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        role VARCHAR(50) DEFAULT 'user',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(firm_id, username)
                    )
                """))
                logger.info("✓ users tablosu oluşturuldu")
        else:
            logger.info("users tablosu zaten mevcut")

        # 3. devices tablosunu güncelle (eksik kolonları ekle)
        if 'devices' in existing_tables:
            # device_info kolonu var mı kontrol et
            columns = [col['name'] for col in inspector.get_columns('devices')]

            if 'device_info' not in columns:
                logger.info("devices tablosuna device_info kolonu ekleniyor...")
                session.execute(text("ALTER TABLE devices ADD COLUMN device_info JSONB"))

            if 'last_seen_at' not in columns:
                logger.info("devices tablosuna last_seen_at kolonu ekleniyor...")
                session.execute(text("ALTER TABLE devices ADD COLUMN last_seen_at TIMESTAMP"))

            logger.info("✓ devices tablosu güncellendi")
        else:
            logger.info("devices tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE devices (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    firm_id UUID NOT NULL REFERENCES firms(id),
                    device_id VARCHAR(100) NOT NULL,
                    device_name VARCHAR(255),
                    device_info JSONB,
                    is_approved BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_seen_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(firm_id, device_id)
                )
            """))
            logger.info("✓ devices tablosu oluşturuldu")

        # 4. join_codes tablosunu kontrol et
        if 'join_codes' not in existing_tables:
            logger.info("join_codes tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE join_codes (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    firm_id UUID NOT NULL REFERENCES firms(id),
                    code VARCHAR(50) UNIQUE NOT NULL,
                    max_uses INTEGER DEFAULT 10,
                    use_count INTEGER DEFAULT 0,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by UUID
                )
            """))
            logger.info("✓ join_codes tablosu oluşturuldu")
        else:
            logger.info("join_codes tablosu zaten mevcut")

        # 5. refresh_tokens tablosu (yeni)
        if 'refresh_tokens' not in existing_tables:
            logger.info("refresh_tokens tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE refresh_tokens (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(uuid),
                    device_id UUID,
                    token_hash VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked BOOLEAN DEFAULT FALSE
                )
            """))
            session.execute(text("CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id)"))
            logger.info("✓ refresh_tokens tablosu oluşturuldu")

        # 6. sync_records tablosu (yeni - künye deposu)
        if 'sync_records' not in existing_tables:
            logger.info("sync_records tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE sync_records (
                    uuid UUID PRIMARY KEY,
                    firm_id UUID NOT NULL REFERENCES firms(id),
                    table_name VARCHAR(50) NOT NULL,
                    data JSONB NOT NULL,
                    data_encrypted TEXT,
                    buro_takip_no INTEGER,
                    revision INTEGER DEFAULT 1 NOT NULL,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    server_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    server_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by_device UUID,
                    updated_by_device UUID
                )
            """))

            # Indexler
            session.execute(text("CREATE INDEX idx_sync_records_firm ON sync_records(firm_id)"))
            session.execute(text("CREATE INDEX idx_sync_records_table ON sync_records(table_name)"))
            session.execute(text("CREATE INDEX idx_sync_records_revision ON sync_records(revision)"))
            session.execute(text("CREATE INDEX idx_sync_records_bn ON sync_records(buro_takip_no)"))
            session.execute(text("CREATE INDEX idx_sync_records_deleted ON sync_records(is_deleted)"))
            session.execute(text("CREATE INDEX idx_sync_records_firm_table ON sync_records(firm_id, table_name)"))
            session.execute(text("CREATE INDEX idx_sync_records_firm_updated ON sync_records(firm_id, updated_at)"))

            logger.info("✓ sync_records tablosu oluşturuldu")

            # Eski sync_data varsa migrate et
            if 'sync_data' in existing_tables:
                logger.info("sync_data → sync_records tablosuna migrate ediliyor...")
                try:
                    session.execute(text("""
                        INSERT INTO sync_records (uuid, firm_id, table_name, data, revision, is_deleted, created_at, updated_at)
                        SELECT
                            uuid::uuid,
                            firm_id,
                            table_name,
                            data::jsonb,
                            COALESCE(revision, 1),
                            COALESCE(is_deleted, FALSE),
                            COALESCE(created_at, CURRENT_TIMESTAMP),
                            COALESCE(updated_at, CURRENT_TIMESTAMP)
                        FROM sync_data
                        WHERE data IS NOT NULL AND uuid IS NOT NULL
                    """))
                    count = session.execute(text("SELECT COUNT(*) FROM sync_records")).scalar()
                    logger.info(f"✓ {count} kayıt sync_data'dan migrate edildi")
                except Exception as e:
                    logger.warning(f"sync_data migration hatası (devam edilecek): {e}")
        else:
            logger.info("sync_records tablosu zaten mevcut")

        # 7. global_revisions tablosu (yeni)
        if 'global_revisions' not in existing_tables:
            logger.info("global_revisions tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE global_revisions (
                    firm_id UUID PRIMARY KEY REFERENCES firms(id),
                    current_revision INTEGER DEFAULT 0 NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Mevcut firmalar için revision oluştur
            session.execute(text("""
                INSERT INTO global_revisions (firm_id, current_revision)
                SELECT id, 0 FROM firms
                ON CONFLICT (firm_id) DO NOTHING
            """))
            logger.info("✓ global_revisions tablosu oluşturuldu")

        # 8. sync_logs tablosu (yeni)
        if 'sync_logs' not in existing_tables:
            logger.info("sync_logs tablosu oluşturuluyor...")
            session.execute(text("""
                CREATE TABLE sync_logs (
                    id SERIAL PRIMARY KEY,
                    firm_id UUID,
                    device_id UUID,
                    action VARCHAR(50),
                    record_uuid UUID,
                    table_name VARCHAR(50),
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            session.execute(text("CREATE INDEX idx_sync_logs_firm ON sync_logs(firm_id)"))
            logger.info("✓ sync_logs tablosu oluşturuldu")

        session.commit()
        logger.info("\n" + "="*50)
        logger.info("✓ Migrasyon başarıyla tamamlandı!")
        logger.info("="*50)

        # Son durum raporu
        final_tables = inspect(engine).get_table_names()
        logger.info(f"\nMevcut tablolar: {final_tables}")

        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Migrasyon hatası: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def check_migration_status():
    """Migrasyon durumunu kontrol et"""
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    required_tables = ['firms', 'users', 'devices', 'join_codes',
                       'refresh_tokens', 'sync_records', 'global_revisions', 'sync_logs']

    missing = [t for t in required_tables if t not in existing_tables]

    if missing:
        logger.warning(f"Eksik tablolar: {missing}")
        return False

    logger.info("Tüm tablolar mevcut")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        check_migration_status()
    else:
        run_migration()
