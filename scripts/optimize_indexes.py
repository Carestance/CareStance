import os
import time
from appwrite.client import Client
from appwrite.services.databases import Databases
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = Databases(client)
DB_ID = "main"

# Configuration: Collection ID -> List of Attributes to Index
INDEX_CONFIG = {
    "users": ["email", "role", "id"],
    "assessment_results": ["user_id"],
    "appointments": ["student_id", "counsellor_id", "status"],
    "career_paths": ["user_id"],
    "tickets": ["user_id", "status"],
    "student_messages": ["sender_id", "receiver_id"],
    "student_connections": ["requester_id", "receiver_id", "status"],
    "payments": ["session_id", "status"],
    "chat_messages": ["user_id"],
    "counsellor_ratings": ["counsellor_id", "student_id"],
    "counsellor_profiles": ["user_id"],
    "feedbacks": ["user_id"],
    "moderation_flags": ["user_id"],
    "college_recommendations": ["user_id"],
    "transfers": ["status", "payment_id", "counsellor_id"]
}

def create_indexes():
    print("Starting Indexing optimization...")
    for coll_id, attrs in INDEX_CONFIG.items():
        print(f"  Optimizing collection: {coll_id}")
        for attr in attrs:
            index_key = f"idx_{attr}"
            try:
                # Appwrite API: create_index(database_id, collection_id, key, type, attributes, orders=None)
                # Note: 'key' type is standard B-tree index
                databases.create_index(
                    database_id=DB_ID,
                    collection_id=coll_id,
                    key=index_key,
                    type="key",
                    attributes=[attr]
                )
                print(f"    Created index for: {attr}")
                time.sleep(1) # Rate limit protection
            except Exception as e:
                if "already exists" in str(e).lower():
                    pass
                else:
                    print(f"    Error indexing {attr} in {coll_id}: {e}")

if __name__ == "__main__":
    create_indexes()
    print("Indexing logic completed.")
