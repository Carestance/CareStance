"""Check user roles and onboarding state in the DB."""
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

async def main():
    url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url, statement_cache_size=0)
    rows = await conn.fetch(
        "SELECT id, email, role, full_name, onboarded FROM users ORDER BY id DESC LIMIT 20"
    )
    print(f"{'ID':>4} | {'email':35} | {'role':12} | {'full_name':20} | onboarded")
    print("-" * 90)
    for r in rows:
        print(f"{r['id']:>4} | {str(r['email']):35} | {str(r['role']):12} | {str(r['full_name']):20} | {r['onboarded']}")
    
    # Also show how many users have NULL role
    null_role = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role IS NULL")
    print(f"\nUsers with NULL role: {null_role}")
    await conn.close()

asyncio.run(main())
