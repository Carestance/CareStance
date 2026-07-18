import asyncio
import sys
import os
from sqlalchemy.future import select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app.models import User

async def list_all_users():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()

            if users:
                print("\n--- Users in Database ✅ ---")
                for user in users:
                    print(f"  ID: {user.id:<5} | Email: {user.email:<30} | Name: {user.full_name:<25} | Role: {user.role}")
                print("------------------------------\n")
            else:
                print("\n--- No Users Found ---")
                print("The 'users' table is empty.")
                print("------------------------\n")

if __name__ == "__main__":
    try:
        asyncio.run(list_all_users())
    except KeyboardInterrupt:
        print("\nScript cancelled by user.")
