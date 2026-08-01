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
coll_id = "assessment_results"

ATTRIBUTES = [
    # Basic fields
    ("selected_class", "string", 50, False),
    ("student_type", "string", 20, False),
    ("current_phase", "integer", None, False),
    ("intake_turn", "integer", None, False),
    ("intake_name", "string", 255, False),
    ("intake_grade", "integer", None, False),
    ("intake_stream", "string", 255, False),
    ("chat_turn", "integer", None, False),
    ("personality", "string", 1000, False),
    ("goal_status", "string", 1000, False),
    ("confidence", "float", None, False),
    ("reasoning", "string", 30000, False),
    ("phase_2_category", "string", 255, False),
    ("phase3_result", "string", 255, False),
    ("phase3_analysis", "string", 30000, False),
    ("recommended_stream", "string", 255, False),
    ("final_analysis", "string", 30000, False),
    
    # JSON Fields (serialized to string)
    ("telemetry_logs", "string", 30000, False),
    ("reality_answers", "string", 30000, False),
    ("chat_messages", "string", 30000, False),
    ("proxy_answers", "string", 30000, False),
    ("scenario_answers", "string", 30000, False),
    ("worldview_answers", "string", 30000, False),
    ("future_self_answers", "string", 30000, False),
    ("assessment_report", "string", 30000, False),
    ("raw_answers", "string", 30000, False),
    ("phase3_answers", "string", 30000, False),
    ("final_answers", "string", 30000, False),
    ("stream_scores", "string", 30000, False),
    ("stream_pros", "string", 30000, False),
    ("stream_cons", "string", 30000, False)
]

def modify_table():
    print(f"Checking attributes for collection '{coll_id}'...")
    try:
        res = databases.list_attributes(DB_ID, coll_id)
        attrs = getattr(res, 'attributes', []) if not isinstance(res, dict) else res.get('attributes', [])
        existing_keys = set()
        for attr in attrs:
            key = getattr(attr, 'key', None) if not isinstance(attr, dict) else attr.get('key')
            if key:
                existing_keys.add(key)
        print(f"Existing attributes: {existing_keys}")
    except Exception as e:
        print(f"Error fetching existing attributes (likely paused): {e}")
        # Proceed assuming they need to be created
        existing_keys = set()

    for attr_name, attr_type, size, required in ATTRIBUTES:
        if attr_name in existing_keys:
            print(f"Attribute '{attr_name}' already exists. Skipping.")
            continue
            
        print(f"Creating attribute: '{attr_name}' ({attr_type})...")
        try:
            if attr_type == "string":
                databases.create_string_attribute(DB_ID, coll_id, attr_name, size, required)
            elif attr_type == "integer":
                databases.create_integer_attribute(DB_ID, coll_id, attr_name, required)
            elif attr_type == "float":
                databases.create_float_attribute(DB_ID, coll_id, attr_name, required)
            elif attr_type == "boolean":
                databases.create_boolean_attribute(DB_ID, coll_id, attr_name, required)
            time.sleep(1) # Sleep to allow propagation in Appwrite
            print(f"  Successfully created '{attr_name}'")
        except Exception as e:
            print(f"  Error creating '{attr_name}': {e}")

if __name__ == "__main__":
    modify_table()
