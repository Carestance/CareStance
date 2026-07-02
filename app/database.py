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

# Fix for Supabase Transaction Mode/Poolers (6543 is bouncer)
if ":6543" in SQLALCHEMY_DATABASE_URL:
    engine_args.setdefault("connect_args", {})["statement_cache_size"] = 0

if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Use NullPool for serverless/constrained environments, but add pre-ping for stability
    from sqlalchemy.pool import NullPool
    engine_args["poolclass"] = NullPool
    engine_args["pool_pre_ping"] = True
    
    # Supabase often requires SSL; ensure it's handled for asyncpg
    if "supabase.com" in SQLALCHEMY_DATABASE_URL:
        # asyncpg specific SSL requirements can sometimes be tricky on Windows
        # We'll let the connection string handle it usually, but ensure the engine is robust
        pass

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

