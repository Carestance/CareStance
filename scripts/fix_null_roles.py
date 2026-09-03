"""Fix users with NULL role in PostgreSQL DB."""
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

async def main():
    url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url, statement_cache_size=0)
    
    # Update NULL roles to 'student'
    result = await conn.execute(
        "UPDATE users SET role = 'student' WHERE role IS NULL OR role = ''"
    )
    print(f"Updated users without role: {result}")
    await conn.close()

asyncio.run(main())
