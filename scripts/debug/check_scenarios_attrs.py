import os
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

coll_id = "scenarios"
try:
    res = databases.list_attributes(DB_ID, coll_id)
    print(f"--- Attributes for {coll_id} ---")
    attrs = getattr(res, 'attributes', []) if not isinstance(res, dict) else res.get('attributes', [])
    for attr in attrs:
        key = getattr(attr, 'key', 'unknown') if not isinstance(attr, dict) else attr.get('key', 'unknown')
        status = getattr(attr, 'status', 'unknown') if not isinstance(attr, dict) else attr.get('status', 'unknown')
        print(f"- {key}: status={status}")
except Exception as e:
    print(f"Error: {e}")
