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

coll_id = "users"

print(f"Waiting for attributes in '{coll_id}' to become AVAILABLE...")
while True:
    try:
        res = databases.list_attributes(DB_ID, coll_id)
        attrs = getattr(res, 'attributes', []) if not isinstance(res, dict) else res.get('attributes', [])
        all_available = True
        for attr in attrs:
            key = getattr(attr, 'key', 'unknown') if not isinstance(attr, dict) else attr.get('key', 'unknown')
            status = getattr(attr, 'status', 'unknown') if not isinstance(attr, dict) else attr.get('status', 'unknown')
            if 'available' not in str(status).lower():
                print(f"  {key} is still {status}...")
                all_available = False
        
        if all_available:
            print("All attributes are AVAILABLE.")
            break
        time.sleep(10)
    except Exception as e:
        print(f"Error: {e}")
        break
