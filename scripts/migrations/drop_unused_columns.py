import os
import asyncio
from sqlalchemy import text
from app.database import engine
from appwrite.client import Client
from appwrite.services.databases import Databases
from dotenv import load_dotenv

load_dotenv()

# Appwrite configuration
client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = Databases(client)
DB_ID = "main"
coll_id = "assessment_results"

UNUSED_COLUMNS = ["reality_answers", "worldview_answers", "future_self_answers"]

async def drop_pg_columns():
    print("--- PostgreSQL: Dropping unused columns ---")
    async with engine.begin() as conn:
        for col in UNUSED_COLUMNS:
            print(f"Dropping column '{col}' from table 'assessment_results' in PostgreSQL...")
            try:
                await conn.execute(text(f"ALTER TABLE assessment_results DROP COLUMN IF EXISTS {col};"))
                print(f"  Successfully dropped '{col}' from PostgreSQL.")
            except Exception as e:
                print(f"  Error dropping '{col}' from PostgreSQL: {e}")

def drop_appwrite_attributes():
    print("\n--- Appwrite: Dropping unused attributes ---")
    for col in UNUSED_COLUMNS:
        print(f"Deleting attribute '{col}' from collection '{coll_id}' in Appwrite...")
        try:
            databases.delete_attribute(DB_ID, coll_id, col)
            print(f"  Successfully deleted '{col}' from Appwrite.")
        except Exception as e:
            print(f"  Error deleting '{col}' from Appwrite: {e}")

async def main():
    await drop_pg_columns()
    drop_appwrite_attributes()
    print("\nDatabase cleanup completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
