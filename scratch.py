import httpx
import asyncio

async def test_assessment():
    async with httpx.AsyncClient() as client:
        # Create a user
        res = await client.post("http://localhost:8080/signup", data={
            "full_name": "Test User",
            "email": "testuser@example.com",
            "password": "password123",
            "role": "student"
        })
        print("Signup:", res.status_code)
        
        # Login
        res = await client.post("http://localhost:8080/login", data={
            "email": "testuser@example.com",
            "password": "password123"
        })
        print("Login:", res.status_code)
        
        # Get cookies
        cookies = client.cookies
        
        # Check State
        res = await client.get("http://localhost:8080/assessment/api/state")
        print("State:", res.status_code, res.text)
        
        # Call intake
        res = await client.post("http://localhost:8080/assessment/api/intake", json={
            "name": "Test User",
            "pursuing": "12th",
            "interests": ["Math", "Science"],
            "family_income": "10L+",
            "father_occupation": "Engineer",
            "mother_occupation": "Teacher",
            "salary_priority": "balanced"
        })
        print("Intake:", res.status_code, res.text)

asyncio.run(test_assessment())
