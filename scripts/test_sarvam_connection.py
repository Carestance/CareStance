import asyncio
import os
import aiohttp
from dotenv import load_dotenv

# Ensure monkey patches are applied
from app.realtime.config import config

load_dotenv()

async def test_sarvam():
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        print("SARVAM_API_KEY not found.")
        return
    key = key.strip()
    
    # We will test using Sarvam's API endpoint or by initializing Pipecat's SarvamSTTService briefly
    # Or just making a simple HTTP request to a known Sarvam endpoint that requires auth.
    print(f"Testing Sarvam API key: {'*' * (len(key)-4) + key[-4:] if len(key) > 4 else '***'}")
    
    url = "https://api.sarvam.ai/speech-to-text-translate" # or another valid endpoint
    headers = {
        "api-subscription-key": key
    }
    
    # Actually, STT websockets connect to wss://api.sarvam.ai/speech-to-text-translate/ws or similar.
    # The Pipecat SDK does this. Let's just try to initialize the pipecat service and run it for 1 second.
    from pipecat.services.sarvam.stt import SarvamSTTService
    
    try:
        stt = SarvamSTTService(
            api_key=key,
            settings=SarvamSTTService.Settings(model="saaras:v3")
        )
        print("SarvamSTTService instantiated successfully.")
        await stt._connect()
        print("Connection established!")
    except Exception as e:
        print(f"Error connecting: {e}")

    # To test the connection, we'd need a Pipecat pipeline, but let's check aiohttp direct websocket to Sarvam
    # wait, we can just use the aiohttp client to try wss://api.sarvam.ai/speech-to-text/ws or whatever endpoint they use
    ws_url = "wss://api.sarvam.ai/speech-to-text/ws" # this is a guess, let's see what pipecat uses
    print("Testing complete. We need to check Pipecat's exact websocket url.")

if __name__ == "__main__":
    asyncio.run(test_sarvam())
