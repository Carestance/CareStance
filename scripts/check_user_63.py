import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def check_user():
    async with AsyncSessionLocal() as db:
        stmt = select(models.User).where(models.User.id == 63)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if user:
            print(f"User 63 found: {user.full_name}, role: {user.role}")
        else:
            print("User 63 NOT found")

if __name__ == "__main__":
    asyncio.run(check_user())
