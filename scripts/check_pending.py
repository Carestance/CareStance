import asyncio
import os
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def check_pending():
    async with AsyncSessionLocal() as db:
        stmt = select(models.CounsellorProfile).where(models.CounsellorProfile.verification_status == "pending")
        result = await db.execute(stmt)
        pending = result.scalars().all()
        print(f"Found {len(pending)} pending counsellors")
        for p in pending:
            print(f"ID: {p.id}, User ID: {p.user_id}, Status: {p.verification_status}")

if __name__ == "__main__":
    asyncio.run(check_pending())
