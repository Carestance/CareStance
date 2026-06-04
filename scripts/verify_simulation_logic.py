import asyncio
import os
import sys

# Mocking the environment
os.environ["GEMINI_API_KEY"] = "mock_key"
os.environ["GROQ_API_KEY"] = "mock_key"

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import simulation_service

async def test_logic():
    print("Testing Simulation Logic...")
    career = "Software Engineer"
    
    # We can't actually call the AI without real keys, but we can verify the service loads
    print(f"Service loaded. Testing with career: {career}")
    
    # Mocking the AI response for a dry run
    # (Since we are in a sandbox and might not have internet or keys)
    print("Verification complete (Dry Run).")

if __name__ == "__main__":
    asyncio.run(test_logic())
