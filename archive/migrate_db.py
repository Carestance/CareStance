import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "learnloop.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column_if_missing(table, column, type_str, default=None):
    # Check if column exists
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    
    if column not in columns:
        try:
            query = f"ALTER TABLE {table} ADD COLUMN {column} {type_str}"
            if default is not None:
                query += f" DEFAULT {default}"
            cursor.execute(query)
            print(f"Added column '{column}' ({type_str}) to table '{table}'.")
        except Exception as e:
            print(f"Error adding column '{column}' to table '{table}': {e}")
    else:
        print(f"Column '{column}' already exists in table '{table}'.")

# Migrate User Table Columns
add_column_if_missing("users", "simulations_completed", "INTEGER", default="0")
add_column_if_missing("users", "simulation_paid", "BOOLEAN", default="0")
add_column_if_missing("users", "simulation_credits", "INTEGER", default="0")

# Migrate AssessmentResults Table Columns
add_column_if_missing("assessment_results", "selected_class", "VARCHAR")
add_column_if_missing("assessment_results", "student_type", "VARCHAR", default="'10th'")
add_column_if_missing("assessment_results", "current_phase", "INTEGER", default="1")
add_column_if_missing("assessment_results", "intake_turn", "INTEGER", default="1")
add_column_if_missing("assessment_results", "intake_name", "VARCHAR")
add_column_if_missing("assessment_results", "intake_grade", "INTEGER")
add_column_if_missing("assessment_results", "intake_stream", "VARCHAR")
add_column_if_missing("assessment_results", "telemetry_logs", "JSON")
add_column_if_missing("assessment_results", "reality_answers", "JSON")
add_column_if_missing("assessment_results", "chat_messages", "JSON")
add_column_if_missing("assessment_results", "chat_turn", "INTEGER", default="0")
add_column_if_missing("assessment_results", "proxy_answers", "JSON")
add_column_if_missing("assessment_results", "scenario_answers", "JSON")
add_column_if_missing("assessment_results", "worldview_answers", "JSON")
add_column_if_missing("assessment_results", "future_self_answers", "JSON")
add_column_if_missing("assessment_results", "assessment_report", "JSON")
add_column_if_missing("assessment_results", "simulations_completed", "INTEGER", default="0")
add_column_if_missing("assessment_results", "simulation_paid", "BOOLEAN", default="0")
add_column_if_missing("assessment_results", "simulation_credits", "INTEGER", default="0")

conn.commit()
conn.close()
print("Migration run finished successfully!")
