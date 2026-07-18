import os
import json
import uuid
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
COLL_ID = "scenarios"

SCENARIOS = [
    # --- Machine Learning Engineer ---
    {
        "scenario_id": "ml_001",
        "career": "ML Engineer",
        "type": "decision",
        "data": {
            "context": "[NORMAL] You are reviewing a model for a credit scoring system. The team suggests using 5 new features from social media data. How do you approach this?",
            "options": [
                {"id": 1, "text": "Run a correlation analysis and feature importance test.", "scores": {"skill": 10, "decision": 5}},
                {"id": 2, "text": "Implement them immediately to improve accuracy.", "scores": {"skill": 2, "decision": -5}},
                {"id": 3, "text": "Reject them due to potential bias and privacy concerns.", "scores": {"skill": 5, "decision": 10}}
            ],
            "correct_option": 1,
            "next_map": {"1": "ml_002", "2": "ml_crisis", "3": "ml_002"},
            "impact": {"consistency": 5}
        }
    },
    {
        "scenario_id": "ml_crisis",
        "career": "ML Engineer",
        "type": "coding",
        "data": {
            "context": "[CRISIS] Production model accuracy just dropped by 40%! A dataset drift is detected in the real-time feature pipeline. What is your priority?",
            "options": [
                {"id": 1, "text": "Rollback to the last stable model checkpoint.", "scores": {"skill": 10, "stress": 10, "decision": 10}},
                {"id": 2, "text": "Debug the pipeline live to find the broken feature.", "scores": {"skill": 5, "stress": -5, "decision": 2}},
                {"id": 3, "text": "Retrain the model on the new mismatched data.", "scores": {"skill": -10, "stress": 2, "decision": -10}}
            ],
            "correct_option": 1,
            "next_map": {"1": "ml_003", "2": "ml_003", "3": "ml_003"},
            "impact": {"consistency": -5}
        }
    },
    {
        "scenario_id": "ml_003",
        "career": "ML Engineer",
        "type": "decision",
        "data": {
            "context": "[NORMAL] Things have stabilized. Now you need to decide on the long-term infrastructure for this pipeline. Do you go for a managed cloud solution or custom multi-cluster setup?",
            "options": [
                {"id": 1, "text": "Managed cloud for reliability and speed.", "scores": {"skill": 5, "decision": 8}},
                {"id": 2, "text": "Custom setup for maximum control and cost-efficiency.", "scores": {"skill": 10, "decision": 5}}
            ],
            "next_map": {"1": "fin", "2": "fin"},
            "impact": {"decision": 5}
        }
    },
    # --- Diplomat ---
    {
        "scenario_id": "dip_001",
        "career": "Diplomat",
        "type": "decision",
        "data": {
            "context": "[NORMAL] A neighboring country has proposed a new trade agreement that simplifies tariffs but increases border security checks.",
            "options": [
                {"id": 1, "text": "Accept the deal to strengthen the alliance.", "scores": {"risk": 2, "stability": 8}},
                {"id": 2, "text": "Demand a revision to lower security friction first.", "scores": {"risk": 5, "stability": 5}},
                {"id": 3, "text": "Postpone the deal to conduct a full economic impact study.", "scores": {"risk": 0, "stability": 10}}
            ],
            "next_map": {"1": "dip_002", "2": "dip_crisis", "3": "dip_002"},
            "impact": {"decision": 5}
        }
    },
    {
        "scenario_id": "dip_crisis",
        "career": "Diplomat",
        "type": "decision",
        "data": {
            "context": "[CRISIS] A territorial dispute has escalated into an armed standoff on the Northern border. You have 1 hour to draft a ceasefire proposal.",
            "options": [
                {"id": 1, "text": "Propose an immediate 48-hour de-escalation zone.", "scores": {"risk": 10, "stability": 10}},
                {"id": 2, "text": "Request UN intervention immediately.", "scores": {"risk": 5, "stability": 2}},
                {"id": 3, "text": "Wait for instructions (Risk of escalation).", "scores": {"risk": 0, "stability": -10}}
            ],
            "next_map": json.dumps({"1": "dip_003", "2": "dip_003", "3": "dip_003"}),
            "impact": json.dumps({"stress": 10})
        }
    },
    # --- Navy/Defense ---
    {
        "scenario_id": "nav_001",
        "career": "Navy",
        "type": "timed",
        "data": {
            "context": "[NORMAL] You are on bridge duty. Radar shows an unidentified surface vessel 5 miles out, not responding to radio hails. What is your protocol?",
            "options": [
                {"id": 1, "text": "Dispatch a fast interceptor boat for visual identification.", "scores": {"skill": 10, "decision": 5}},
                {"id": 2, "text": "Fire a warning shot across their bow.", "scores": {"skill": 5, "decision": -10}},
                {"id": 3, "text": "Signal using international code flags and spotlights.", "scores": {"skill": 8, "decision": 10}}
            ],
            "next_map": {"1": "nav_002", "2": "nav_crisis", "3": "nav_002"},
            "impact": {"consistency": 5},
            "urgency": "Medium"
        }
    },
    {
        "scenario_id": "nav_crisis",
        "career": "Navy",
        "type": "rapid_fire",
        "data": {
            "context": "[CRISIS] General Quarters! A hull breach is detected in Section D. Water is flooding the engine room. You have 30 seconds to coordinate emergency teams.",
            "options": [
                {"id": 1, "text": "Seal all watertight doors in Section D immediately.", "scores": {"skill": 10, "stress": 10, "decision": 10}},
                {"id": 2, "text": "Divert all pumps to the engine room and send a damage control team.", "scores": {"skill": 8, "stress": 5, "decision": 5}},
                {"id": 3, "text": "Evacuate Section D and hope for the best.", "scores": {"skill": -10, "stress": -20, "decision": -20}}
            ],
            "next_map": {"1": "nav_003", "2": "nav_003", "3": "nav_003"},
            "impact": {"stress": 20},
            "urgency": "CRITICAL"
        }
    }
]

def seed_scenarios():
    print("Seeding consolidated scenarios...")
    for entry in SCENARIOS:
        try:
            doc_data = {
                "scenario_id": entry["scenario_id"],
                "career": entry["career"],
                "type": entry["type"],
                "scenario_data": json.dumps(entry["data"])
            }
            databases.create_row(DB_ID, COLL_ID, str(uuid.uuid4())[:20], doc_data)
            print(f"  Added: {entry['scenario_id']}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error seeding {entry['scenario_id']}: {e}")

if __name__ == "__main__":
    seed_scenarios()
