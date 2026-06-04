from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import os
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL for Vercel/Production, fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # SQLAlchemy requires 'postgresql://' but many platforms provide 'postgres://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
else:
    if os.getenv("VERCEL"):
        SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:////tmp/learnloop.db"
    else:
        SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./learnloop.db"

engine_args = {}

# Fix for Supabase Transaction Mode/Poolers
if ":6543" in SQLALCHEMY_DATABASE_URL and "prepare_threshold" not in SQLALCHEMY_DATABASE_URL:
    if "?" in SQLALCHEMY_DATABASE_URL:
        SQLALCHEMY_DATABASE_URL += "&prepare_threshold=0"
    else:
        SQLALCHEMY_DATABASE_URL += "?prepare_threshold=0"

if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Use NullPool to completely avoid connection exhaustion/limitations on async serverless deployments
    from sqlalchemy.pool import NullPool
    engine_args["poolclass"] = NullPool

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, **engine_args)
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    """Async DB session for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session

