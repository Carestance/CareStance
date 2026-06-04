import os
import sqlite3
import csv
import json
import uuid
import time
import re
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.account import Account
from appwrite.services.users import Users
from dotenv import load_dotenv

load_dotenv()

# Appwrite Setup
client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = Databases(client)
users_service = Users(client)
DB_ID = "main"

DOWNLOADS_DIR = "/Users/rahulmanchanda/Downloads"

COLLECTIONS_CONFIG = {
    "users": {
        "file": "users_rows.csv",
        "attributes": [
            ("email", "string", 255, True),
            ("full_name", "string", 255, False),
            ("contact_number", "string", 50, False),
            ("role", "string", 20, False),
            ("local_id", "integer", None, False)
        ]
    }
}

def get_available_attributes(coll_id):
    try:
        res = databases.list_attributes(DB_ID, coll_id)
        attrs = getattr(res, 'attributes', []) if not isinstance(res, dict) else res.get('attributes', [])
        available = []
        for attr in attrs:
            key = getattr(attr, 'key', 'unknown') if not isinstance(attr, dict) else attr.get('key', 'unknown')
            status = getattr(attr, 'status', 'unknown') if not isinstance(attr, dict) else attr.get('status', 'unknown')
            if 'available' in str(status).lower():
                available.append(key)
        return available
    except:
        return []

def migrate_csv(coll_id, filename):
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.exists(filepath): return

    print(f"  Migrating {coll_id}...")
    available_attrs = get_available_attributes(coll_id)
    print(f"    Available Attributes: {available_attrs}")
    
    success_count = 0
    fail_count = 0
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Map CSV 'id' to 'local_id' if needed
                if 'id' in row and 'local_id' not in row:
                    row['local_id'] = row['id']

                data = {}
                for attr_name, attr_type, size, required in COLLECTIONS_CONFIG[coll_id]["attributes"]:
                    if attr_name not in available_attrs:
                        continue # Skip unavailable attributes
                    
                    val = row.get(attr_name)
                    if attr_type == "integer":
                        try: data[attr_name] = int(val) if val and str(val).isdigit() else 0
                        except: data[attr_name] = 0
                    elif attr_type == "float":
                        try: data[attr_name] = float(val) if val else 0.0
                        except: data[attr_name] = 0.0
                    elif attr_type == "boolean":
                        data[attr_name] = str(val).lower() == "true" if val else False
                    else:
                        data[attr_name] = (val[:size-4] + "...") if size and val and len(val) > size else (val if val else "")
                
                if not data: continue
                
                databases.create_document(DB_ID, coll_id, str(uuid.uuid4())[:20], data)
                success_count += 1
            except Exception as e:
                print(f"    Row Error in {coll_id}: {e}")
                fail_count += 1
    
    print(f"  Completed {coll_id}: {success_count} success, {fail_count} failed.")

if __name__ == "__main__":
    for coll_id, config in COLLECTIONS_CONFIG.items():
        migrate_csv(coll_id, config["file"])
