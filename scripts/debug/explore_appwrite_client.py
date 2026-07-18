import os
from appwrite.client import Client
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://nyc.cloud.appwrite.io/v1"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID", ""))
client.set_key(os.getenv("APPWRITE_API_KEY", ""))

print("--- Client Methods/Attributes ---")
for attr in dir(client):
    if not attr.startswith("_"):
        print(attr)
