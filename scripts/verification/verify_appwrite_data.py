import os
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.users import Users
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = Databases(client)
users_service = Users(client)
DB_ID = "main"

collections = [
    "users", "assessment_results", "appointments", "career_paths", 
    "tickets", "student_messages", "student_connections", "payments"
]

print("--- Data Audit ---")
try:
    auth_users = users_service.list()
    total = getattr(auth_users, 'total', 0) if not isinstance(auth_users, dict) else auth_users.get('total', 0)
    print(f"Auth Users: {total} users")
except Exception as e:
    print(f"Auth Users Error: {e}")

for coll in collections:
    try:
        res = databases.list_documents(DB_ID, coll)
        total = getattr(res, 'total', 0) if not isinstance(res, dict) else res.get('total', 0)
        print(f"Collection '{coll}': {total} documents")
    except Exception as e:
        print(f"Collection '{coll}' Error: {e}")
