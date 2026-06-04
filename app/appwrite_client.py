import os
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.account import Account
from appwrite.services.storage import Storage
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = Databases(client)
account = Account(client)
storage = Storage(client)

# Appwrite Constants
DB_ID = "main" # Replace with your Appwrite Database ID
COLLECTIONS = {
    "users": "users",
    "assessment_results": "assessment_results",
    "appointments": "appointments",
    "career_paths": "career_paths",
    "tickets": "tickets",
    "student_messages": "student_messages",
    "student_connections": "student_connections",
    "payments": "payments",
    "chat_messages": "chat_messages",
    "counsellor_ratings": "counsellor_ratings",
    "counsellor_profiles": "counsellor_profiles",
    "feedbacks": "feedbacks",
    "moderation_flags": "moderation_flags",
    "college_recommendations": "college_recommendations",
    "transfers": "transfers"
}
STORAGE_BUCKET_ID = "assets"
