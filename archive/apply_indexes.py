from app.database import engine
from sqlalchemy import text, inspect

def apply_indexes():
    """
    Manually creates missing indexes for existing tables (SQLite/PostgreSQL).
    """
    print("Starting index application...")
    
    inspector = inspect(engine)
    
    # List of (table, column, index_name)
    indexes_to_create = [
        ("assessment_results", "user_id", "ix_assessment_results_user_id"),
        ("chat_messages", "user_id", "ix_chat_messages_user_id"),
        ("chat_messages", "sender", "ix_chat_messages_sender"),
        ("feedbacks", "user_id", "ix_feedbacks_user_id"),
        ("tickets", "user_id", "ix_tickets_user_id"),
        ("career_paths", "user_id", "ix_career_paths_user_id"),
        ("counsellor_profiles", "user_id", "ix_counsellor_profiles_user_id"),
        ("college_recommendations", "user_id", "ix_college_recommendations_user_id"),
        ("student_connections", "requester_id", "ix_student_connections_requester_id"),
        ("student_connections", "receiver_id", "ix_student_connections_receiver_id"),
        ("student_connections", "status", "ix_student_connections_status"),
        ("student_messages", "sender_id", "ix_student_messages_sender_id"),
        ("student_messages", "receiver_id", "ix_student_messages_receiver_id"),
        ("notifications", "user_id", "ix_notifications_user_id"),
        ("notifications", "type", "ix_notifications_type"),
        ("moderation_flags", "user_id", "ix_moderation_flags_user_id"),
        ("payments", "session_id", "ix_payments_session_id"),
        ("transfers", "payment_id", "ix_transfers_payment_id"),
        ("transfers", "counsellor_id", "ix_transfers_counsellor_id"),
        ("assessment_results", "phase_2_category", "ix_assessment_results_phase_2_category"),
        ("assessment_results", "personality", "ix_assessment_results_personality"),
        ("assessment_results", "selected_class", "ix_assessment_results_selected_class"),
        ("career_paths", "career_title", "ix_career_paths_career_title"),
        ("college_recommendations", "career_title", "ix_college_recommendations_career_title"),
        ("appointments", "payment_status", "ix_appointments_payment_status"),
        ("counsellor_ratings", "rating", "ix_counsellor_ratings_rating"),
    ]

    with engine.connect() as conn:
        for table, col, index_name in indexes_to_create:
            try:
                # Check if index exists
                existing_indexes = [idx['name'] for idx in inspector.get_indexes(table)]
                if index_name in existing_indexes:
                    print(f"Index {index_name} already exists on {table}")
                    continue

                print(f"Creating index {index_name} on {table}({col})...")
                # SQLite and PostgreSQL syntax differs slightly but this works for simple indexes
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({col})"))
                conn.commit()
                print(f"Success: {index_name}")
            except Exception as e:
                print(f"Error creating index {index_name} on {table}: {e}")

    print("Index application complete.")

if __name__ == "__main__":
    apply_indexes()
