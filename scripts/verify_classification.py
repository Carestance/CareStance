import requests
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define the endpoint URL
url = "http://127.0.0.1:8000/assessment/submit"

# Simulate user authentication (cookie)
# We need a valid user_id. We can get one by inspecting the database or just trying to log in first.
# For simplicity, let's assume user_id=1 exists (created during signup/login).
cookies = {"user_id": "1"}

# Define a set of answers
# Q1-Q6 Determine Personality (Int/Amb/Ext)
# Q7-Q10 Determine Goal Status (Aware/Exploring)
payload = {
    "Q1_SocialBattery": "A", # Introvert
    "Q2_Communication": "A", # Introvert
    "Q3_Workspace": "A", # Introvert
    "Q4_ProblemSolving": "A", # Introvert
    "Q5_MeetingRole": "A", # Introvert
    "Q6_LearningStyle": "A", # Introvert
    "Q7_GoalPath": "A", # Goal Aware
    "Q8_GoalVision": "A", # Goal Aware
    "Q9_GoalSpeed": "A", # Goal Aware
    "Q10_GoalChoice": "A" # Goal Aware
}
# Expected: "Focused Specialist" (Introvert + Goal Aware)

print("Sending request to /assessment/submit...")
try:
    # We need to use a session to persist cookies if needed, but requests.post with cookies arg works
    response = requests.post(url, data=payload, cookies=cookies, allow_redirects=True)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Success! Redirected to result page.")
        # To verify the actual result, we'd need to parse the HTML or check the DB.
        # But for this script, let's just check if we got the result page.
        if "/assessment/result" in response.url:
             print("Redirected to result page correctly.")
        else:
             print(f"Unexpected URL: {response.url}")

        # Let's try to fetch the result from the DB directly to be sure
        import sqlite3
        conn = sqlite3.connect('learnloop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT phase_2_category, personality, goal_status, reasoning FROM assessment_results WHERE user_id=1 ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            print("\n--- DB Result ---")
            print(f"Category: {row[0]}")
            print(f"Personality: {row[1]}")
            print(f"Goal Status: {row[2]}")
            print(f"Reasoning: {row[3]}")
        else:
            print("No result found in DB for user 1.")
        conn.close()

    else:
        print("Failed.")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")
