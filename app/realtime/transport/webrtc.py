import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class WebRTCOffer(BaseModel):
    sdp: str
    type: str

def parse_turn_urls(raw_urls: Optional[str]) -> List[str]:
    """
    Parses and validates TURN URLs from environment configuration.
    Supports comma or whitespace separated URLs.
    Validates scheme ('turn:' or 'turns:').
    Automatically generates UDP and TCP variants if no transport query param is present.
    """
    if not raw_urls or not raw_urls.strip():
        return []
    
    parts = [p.strip() for p in raw_urls.replace(',', ' ').split() if p.strip()]
    turn_urls: List[str] = []
    
    for p in parts:
        if not (p.startswith("turn:") or p.startswith("turns:")):
            raise ValueError(f"Invalid TURN URL scheme in '{p}'. Must start with 'turn:' or 'turns:'.")
        
        if "?transport=" not in p:
            if p.startswith("turns:"):
                turn_urls.append(f"{p}?transport=tcp")
            else:
                turn_urls.append(f"{p}?transport=udp")
                turn_urls.append(f"{p}?transport=tcp")
        else:
            turn_urls.append(p)
            
    return turn_urls

def get_ice_servers_config() -> List[Dict[str, Any]]:
    """
    Returns sanitized ICE server configuration for browser clients.
    Includes STUN and, if configured, TURN servers.
    Does NOT leak backend secrets or unrelated environment variables.
    """
    ice_servers: List[Dict[str, Any]] = [
        {
            "urls": [
                "stun:stun.l.google.com:19302",
                "stun:stun1.l.google.com:19302",
                "stun:stun2.l.google.com:19302",
            ]
        }
    ]

    turn_server_url = os.getenv("TURN_SERVER_URL") or os.getenv("TURN_SERVER_URLS")
    if turn_server_url:
        turn_username = os.getenv("TURN_USERNAME")
        turn_password = os.getenv("TURN_PASSWORD")
        
        if not turn_username or not turn_password:
            raise ValueError(
                "Incomplete TURN configuration: TURN_USERNAME and TURN_PASSWORD are required when TURN_SERVER_URL is set."
            )
            
        parsed_urls = parse_turn_urls(turn_server_url)
        if parsed_urls:
            ice_servers.append({
                "urls": parsed_urls,
                "username": turn_username,
                "credential": turn_password
            })
            
    return ice_servers

def get_backend_ice_servers() -> List[Any]:
    """
    Returns aiortc RTCIceServer instances for SmallWebRTCConnection.
    Always includes Google STUN.
    Adds TURN RTCIceServer only when validly configured.
    """
    from aiortc import RTCIceServer
    
    servers = [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    
    turn_server_url = os.getenv("TURN_SERVER_URL") or os.getenv("TURN_SERVER_URLS")
    if turn_server_url:
        turn_username = os.getenv("TURN_USERNAME")
        turn_password = os.getenv("TURN_PASSWORD")
        
        if not turn_username or not turn_password:
            raise ValueError(
                "Incomplete TURN configuration: TURN_USERNAME and TURN_PASSWORD are required when TURN_SERVER_URL is set."
            )
            
        parsed_urls = parse_turn_urls(turn_server_url)
        if parsed_urls:
            servers.append(
                RTCIceServer(
                    urls=parsed_urls,
                    username=turn_username,
                    credential=turn_password
                )
            )
            
    return servers

class WebRTCTransportConfig:
    """Isolates the WebRTC transport initialization for Pipecat."""
    @staticmethod
    def create_transport(host: str = "0.0.0.0", port: int = 8765):
        try:
            from pipecat.transports.network.fastapi_webrtc import (
                FastAPIWebRTCTransport, 
                FastAPIWebRTCParams
            )
        except ImportError:
            raise RuntimeError("pipecat-ai is not installed")

        # Standard Pipecat FastAPI WebRTC transport
        transport = FastAPIWebRTCTransport(
            params=FastAPIWebRTCParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_audio_capture_track=True
            )
        )
        return transport

