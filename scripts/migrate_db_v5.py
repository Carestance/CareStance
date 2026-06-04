from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE assessment_results ADD COLUMN stream_pros JSON"))
            print("Added stream_pros column.")
        except Exception as e:
            print(f"Skipping stream_pros (might exist): {e}")

        try:
            conn.execute(text("ALTER TABLE assessment_results ADD COLUMN stream_cons JSON"))
            print("Added stream_cons column.")
        except Exception as e:
            print(f"Skipping stream_cons (might exist): {e}")

if __name__ == "__main__":
    migrate()
