from app.database import engine
from sqlalchemy import text

def try_add_column(table, col, col_type):
    with engine.connect() as conn:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
            conn.commit()
            print(f"Added {col} to {table}")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print(f"{col} already exists in {table}")
            else:
                print(f"Error adding {col} to {table}: {e}")

def update_schema():
    print("Starting robust schema update...")
    
    # Users table
    try_add_column("users", "contact_number", "VARCHAR")
    try_add_column("users", "full_name", "VARCHAR")
    try_add_column("users", "role", "VARCHAR DEFAULT 'student'")
    try_add_column("users", "profile_photo", "VARCHAR")
    
    # Appointments table
    try_add_column("appointments", "razorpay_order_id", "VARCHAR")
    try_add_column("appointments", "razorpay_payment_id", "VARCHAR")
    try_add_column("appointments", "counsellor_joined", "BOOLEAN DEFAULT FALSE")
    try_add_column("appointments", "joined_at", "TIMESTAMP")
    
    # Tickets table
    try_add_column("tickets", "admin_reply", "TEXT")
    
    # Counsellor Profiles
    try_add_column("counsellor_profiles", "certificates", "JSON")
    try_add_column("counsellor_profiles", "experience", "TEXT")
    try_add_column("counsellor_profiles", "is_verified", "BOOLEAN DEFAULT FALSE")
    try_add_column("counsellor_profiles", "verification_status", "VARCHAR DEFAULT 'pending'")
    try_add_column("counsellor_profiles", "account_details", "JSON")
    
    # Assessment Results
    try_add_column("assessment_results", "selected_class", "VARCHAR")
    try_add_column("assessment_results", "phase3_result", "VARCHAR")
    try_add_column("assessment_results", "phase3_answers", "JSON")
    try_add_column("assessment_results", "phase3_analysis", "TEXT")
    try_add_column("assessment_results", "final_answers", "JSON")
    try_add_column("assessment_results", "stream_scores", "JSON")
    try_add_column("assessment_results", "recommended_stream", "VARCHAR")
    try_add_column("assessment_results", "final_analysis", "TEXT")
    try_add_column("assessment_results", "stream_pros", "JSON")
    try_add_column("assessment_results", "stream_cons", "JSON")
    
    print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
