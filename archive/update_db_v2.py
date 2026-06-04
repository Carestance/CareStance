import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "learnloop.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column(table, column, type, default=None):
    try:
        if default:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type} DEFAULT {default}")
        else:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type}")
        print(f"Added {column} to {table}.")
    except sqlite3.OperationalError as e:
        print(f"Error adding {column} to {table} (it might already exist): {e}")

# User updates
add_column("users", "profile_photo", "VARCHAR")

# Counsellor Profile updates
add_column("counsellor_profiles", "certificates", "JSON")
add_column("counsellor_profiles", "experience", "TEXT")
add_column("counsellor_profiles", "is_verified", "BOOLEAN", default="0")
add_column("counsellor_profiles", "verification_status", "VARCHAR", default="'pending'")

conn.commit()
conn.close()

print("Database columns update completed.")
