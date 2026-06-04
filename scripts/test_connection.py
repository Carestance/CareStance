import os
from appwrite.client import Client
from appwrite.services.account import Account
from appwrite.services.databases import Databases
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
# Use User Session instead of API Key for E2E test if possible,
# but here we just want to verify the Auth service is live.

account = Account(client)
databases = Databases(client)

email = "student@gmail.com"
password = "ChangeMe123!"

print(f"--- E2E Connection Test: {email} ---")
try:
    # 1. Test Login
    session = account.create_email_password_session(email, password)
    print(f"Login Success! Session ID: {session['$id']}")
    
    # 2. Test Data Fetch (using API Key on client instance)
    # We'll use a fresh client with API key for DB calls in this script
    client_admin = Client()
    client_admin.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    client_admin.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    client_admin.set_key(os.getenv("APPWRITE_API_KEY"))
    db_admin = Databases(client_admin)
    
    res = db_admin.list_documents("main", "users", [])
    print(f"Database Connection Success! Total users in DB: {res['total']}")
    
except Exception as e:
    print(f"Connection Error: {e}")
