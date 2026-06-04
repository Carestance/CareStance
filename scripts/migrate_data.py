import sys
import os
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Base
from app.database import SQLALCHEMY_DATABASE_URL

load_dotenv()

# Source: Local SQLite
SQLITE_URL = "sqlite:///./learnloop.db"
# Destination: From ENV or manually provided
# During Docker-to-Postgres switch, the DATABASE_URL is set in docker-compose
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL or "sqlite" in POSTGRES_URL:
    print("Error: DATABASE_URL is not set or still pointing to SQLite.")
    print("Usage: DATABASE_URL=postgresql://user:password@host:port/db python scripts/migrate_data.py")
    sys.exit(1)

def migrate():
    print(f"Connecting to Source (SQLite): {SQLITE_URL}")
    sqlite_engine = create_engine(SQLITE_URL)
    
    print(f"Connecting to Destination (Postgres): {POSTGRES_URL}")
    postgres_engine = create_engine(POSTGRES_URL)
    
    # Tables in order of migration (dependencies first)
    tables_to_migrate = [
        "users",
        "counsellor_profiles",
        "assessment_results",
        "chat_messages",
        "feedbacks",
        "tickets",
        "career_paths",
        "appointments",
        "college_recommendations",
        "student_connections",
        "student_messages",
        "notifications",
        "moderation_flags",
        "payments",
        "transfers",
        "counsellor_ratings"
    ]
    
    # Reflect metadata from source
    metadata = MetaData()
    metadata.reflect(bind=sqlite_engine)
    
    from sqlalchemy import inspect
    inspector = inspect(postgres_engine)
    existing_tables = inspector.get_table_names()
    
    with postgres_engine.begin() as pg_conn:
        # 1. Disable constraints or just rely on order
        # In Postgres, we might need to truncate if re-running
        print("Emptying existing tables in Postgres to avoid duplicates...")
        for table_name in reversed(tables_to_migrate):
            if table_name in existing_tables:
                pg_conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
        
        # 2. Migration
        for table_name in tables_to_migrate:
            if table_name not in metadata.tables:
                print(f"⚠️ Skipping {table_name}: not found in SQLite.")
                continue
                
            table = metadata.tables[table_name]
            print(f"📦 Migrating {table_name}...")
            
            with sqlite_engine.connect() as sl_conn:
                rows = sl_conn.execute(table.select()).fetchall()
                if not rows:
                    print(f"  (Table is empty)")
                    continue
                
                # Convert rows to dicts for insertion (SQLAlchemy 2.0 way)
                data = [dict(row._mapping) for row in rows]
                
                # Bulk insert into Postgres
                pg_conn.execute(table.insert(), data)
                print(f"  ✅ Migrated {len(data)} rows.")
                
            # 3. Reset Postgres sequence (Crucial for Postgres Identity columns)
            # This ensures that future inserts using the app won't collide with migrated IDs
            try:
                # Find if table has an 'id' column
                if 'id' in table.columns:
                    pg_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), (SELECT MAX(id) FROM {table_name}))"))
                    print(f"  🔥 Reset sequence for {table_name}.id")
            except Exception as e:
                # Some tables might not have a serial 'id' or sequence name might differ
                print(f"  ℹ️ Sequence reset skipped for {table_name}: {e}")

    print("\n🎉 Migration complete!")

if __name__ == "__main__":
    migrate()
