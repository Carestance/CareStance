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

# Check if tablesDB exists
if hasattr(databases, 'tablesDB'):
    print("tablesDB exists on databases")
else:
    print("tablesDB does not exist on databases")

# Search for any method containing 'row'
print("--- Methods containing 'row' ---")
for method in dir(databases):
    if 'row' in method.lower():
        print(method)

# Search for any method containing 'list'
print("--- Methods containing 'list' ---")
for method in dir(databases):
    if 'list' in method.lower():
        print(method)
