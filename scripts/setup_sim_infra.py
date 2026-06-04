import os
import time
from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

databases = TablesDB(client)
DB_ID = "main"

SIM_COLLECTIONS = {
    "scenarios": {
        "attributes": [
            ("scenario_id", "string", 50, True),
            ("career", "string", 50, True),
            ("type", "string", 20, True),
            ("scenario_data", "string", 30000, False)
        ],
        "indexes": [("scenario_id", "unique")]
    },
    "simulation_sessions": {
        "attributes": [
            ("user_id", "integer", None, True),
            ("career_title", "string", 100, True),
            ("current_step", "integer", None, True),
            ("is_completed", "boolean", None, True),
            ("session_data", "string", 40000, False) # Consolidated JSON
        ],
        "indexes": [("user_id", "key")]
    }
}

def setup_sim_infra():
    print("Force Re-initializing Simulation Infrastructure...")
    for coll_id, config in SIM_COLLECTIONS.items():
        print(f"  Processing: {coll_id}")
        try:
            # Delete old table to clear conflicting required attributes
            databases.delete_table(DB_ID, coll_id)
            print(f"    Deleted existing {coll_id}")
            time.sleep(3)
        except: pass
        
        try:
            databases.create_table(DB_ID, coll_id, coll_id.replace("_", " ").capitalize())
            time.sleep(3)
        except Exception as e:
            print(f"    Create Error: {e}")
        
        for attr_name, attr_type, size, required in config["attributes"]:
            try:
                if attr_type == "string":
                    databases.create_string_column(DB_ID, coll_id, attr_name, size, required)
                elif attr_type == "integer":
                    databases.create_integer_column(DB_ID, coll_id, attr_name, required)
                elif attr_type == "boolean":
                    databases.create_boolean_column(DB_ID, coll_id, attr_name, required)
                time.sleep(1)
            except Exception as e:
                print(f"    Attr Error ({attr_name}): {e}")
        
        for idx_key, idx_type in config["indexes"]:
            try:
                # Wait for attributes to be available before indexing
                time.sleep(5) 
                databases.create_index(DB_ID, coll_id, f"idx_{idx_key}", idx_type, [idx_key])
                print(f"    Index created for {idx_key}")
            except: pass

    print("Infrastructure cleanup and setup completed.")

if __name__ == "__main__":
    setup_sim_infra()
