"""
Utility script to promote a user to admin by email.
Usage:
    python scripts/set_admin.py someone@example.com
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import asyncpg


async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else None
    if not email:
        print("Usage: python scripts/set_admin.py <email>")
        sys.exit(1)

    raw_url = os.getenv("DATABASE_URL", "")
    # Strip async driver prefix so asyncpg can use it directly
    url = (
        raw_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
    )

    if not url or url.startswith("sqlite"):
        print("ERROR: DATABASE_URL not set or is SQLite. Check your .env file.")
        sys.exit(1)

    print(f"Connecting to database...")
    conn = await asyncpg.connect(url, statement_cache_size=0)

    # Check if user exists
    user = await conn.fetchrow("SELECT id, email, role FROM users WHERE email = $1", email)
    if not user:
        print(f"ERROR: No user found with email '{email}'")
        await conn.close()
        sys.exit(1)

    print(f"Found user: ID={user['id']}, email={user['email']}, current role={user['role']}")

    # Promote to admin
    await conn.execute("UPDATE users SET role = 'admin' WHERE email = $1", email)
    print(f"SUCCESS: '{email}' has been promoted to admin.")

    await conn.close()


asyncio.run(main())
