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
DB_ID = "main"

DOWNLOADS_DIR = "/Users/rahulmanchanda/Downloads"

COLLECTIONS_CONFIG = {
    "transfers": {
        "attributes": [
            ("id", "integer", None, False),
            ("payment_id", "integer", None, False),
            ("counsellor_id", "integer", None, False),
            ("amount", "float", None, False),
            ("razorpay_transfer_id", "string", 255, False),
            ("status", "string", 50, False),
            ("created_at", "string", 100, False),
            ("updated_at", "string", 100, False)
        ]
    }
}

def create_schema():
    print("Step 1: Creating Appwrite Schema for 'transfers'...")
    for coll_id, config in COLLECTIONS_CONFIG.items():
        print(f"  Setting up collection: {coll_id}")
        try:
            databases.create_collection(DB_ID, coll_id, coll_id.capitalize())
            time.sleep(2)
        except Exception as e:
            print(f"    Collection '{coll_id}' already exists.")
        
        for attr_name, attr_type, size, required in config["attributes"]:
            try:
                if attr_type == "string":
                    databases.create_string_attribute(DB_ID, coll_id, attr_name, size, required)
                elif attr_type == "integer":
                    databases.create_integer_attribute(DB_ID, coll_id, attr_name, required)
                elif attr_type == "float":
                    databases.create_float_attribute(DB_ID, coll_id, attr_name, required)
                elif attr_type == "boolean":
                    databases.create_boolean_attribute(DB_ID, coll_id, attr_name, required)
                time.sleep(0.5)
            except Exception as e:
                if "already exists" not in str(e): print(f"    Attr Error: {e}")
    
    print("Schema setup completed. Waiting 20s for propagation...")
    time.sleep(20)

if __name__ == "__main__":
    create_schema()
    print("Transfers collection is ready.")
