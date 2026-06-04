from app.database import engine
from sqlalchemy import inspect
import os

def check_schema():
    print(f"Checking DB: {os.getenv('DATABASE_URL', 'local sqlite')}")
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        print(f"Table: {table_name}")
        print(f"Columns: {cols}")

if __name__ == "__main__":
    check_schema()
