import sqlite3

# Connect to database
conn = sqlite3.connect('learnloop.db')
cursor = conn.cursor()

# Add columns if not exist
try:
    cursor.execute("ALTER TABLE assessment_results ADD COLUMN final_answers JSON")
    print("Added final_answers")
except Exception as e:
    print(f"final_answers exists or error: {e}")

try:
    cursor.execute("ALTER TABLE assessment_results ADD COLUMN stream_scores JSON")
    print("Added stream_scores")
except Exception as e:
    print(f"stream_scores exists or error: {e}")

try:
    cursor.execute("ALTER TABLE assessment_results ADD COLUMN recommended_stream VARCHAR")
    print("Added recommended_stream")
except Exception as e:
    print(f"recommended_stream exists or error: {e}")

conn.commit()
conn.close()
