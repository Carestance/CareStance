import os
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

class WebRTCOffer(BaseModel):
    sdp: str
    type: str

def get_turn_env() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Reads TURN server configuration from environment variables with alias fallbacks.
    Does not print or expose credentials.
    """
    turn_server_url = (
        os.getenv("TURN_SERVER_URL")
        or os.getenv("TURN_SERVER_URLS")
        or os.getenv("TURN_URL")
        or os.getenv("TURN_URLS")
    )
    turn_username = (
        os.getenv("TURN_USERNAME")
        or os.getenv("TURN_USER")
    )
    turn_password = (
        os.getenv("TURN_PASSWORD")
        or os.getenv("TURN_CREDENTIAL")
        or os.getenv("TURN_SECRET")
    )

    if turn_server_url:
        turn_server_url = turn_server_url.strip().strip("'\"")
    if turn_username:
        turn_username = turn_username.strip().strip("'\"")
    if turn_password:
        turn_password = turn_password.strip().strip("'\"")

    return turn_server_url, turn_username, turn_password

def parse_turn_urls(raw_urls: Optional[str]) -> List[str]:
    """
    Parses and validates TURN URLs from environment configuration.
    Supports comma, semicolon, newline, or whitespace separated URLs.
    Supports formats:
      - turn:HOST:3478?transport=udp
      - turn:HOST:3478?transport=tcp
      - turns:HOST:5349?transport=tcp
      - turn:HOST:PORT (auto-generates udp & tcp transports)
      - turns:HOST:PORT (auto-generates tcp transport)
      - HOST:PORT (normalizes to turn:HOST:PORT)
    """
    if not raw_urls or not raw_urls.strip():
        return []
    
    cleaned = raw_urls.replace(',', ' ').replace(';', ' ')
    parts = [p.strip().strip("'\"") for p in cleaned.split() if p.strip().strip("'\"")]
    turn_urls: List[str] = []
    
    for p in parts:
        if "://" in p:
            scheme = p.split("://")[0].lower()
            if scheme not in ("turn", "turns"):
                raise ValueError(f"Invalid TURN URL scheme in '{p}'. Must start with 'turn:' or 'turns:'.")
        elif not (p.startswith("turn:") or p.startswith("turns:")):
            p = f"turn:{p}"
            
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

def get_safe_ice_diagnostics(ice_servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns safe structural information about configured ICE servers without leaking secrets.
    Reports:
      - server_count
      - turn_configured (bool)
      - has_turn_udp (bool)
      - has_turn_tcp (bool)
      - servers: list of safe metadata per URL
    """
    server_summaries = []
    turn_configured = False
    has_udp = False
    has_tcp = False

    for idx, s in enumerate(ice_servers):
        raw_urls = s.get("urls", [])
        if isinstance(raw_urls, str):
            urls = [raw_urls]
        else:
            urls = list(raw_urls)
            
        has_user = bool(s.get("username"))
        has_cred = bool(s.get("credential"))
        
        for u in urls:
            scheme = "unknown"
            host = "unknown"
            transport = "default"
            if ":" in u:
                parts = u.split(":", 1)
                scheme = parts[0].lower()
                rest = parts[1]
                if "?" in rest:
                    host_part, query = rest.split("?", 1)
                    host = host_part.lstrip("/")
                    for q in query.split("&"):
                        if q.startswith("transport="):
                            transport = q.split("=")[1].lower()
                else:
                    host = rest.lstrip("/")
                    transport = "tcp" if scheme == "turns" else "udp"
                    
            if scheme in ("turn", "turns"):
                turn_configured = True
                if transport == "udp":
                    has_udp = True
                elif transport == "tcp":
                    has_tcp = True
                    
            server_summaries.append({
                "server_index": idx + 1,
                "scheme": scheme,
                "host": host,
                "transport": transport,
                "has_username": has_user,
                "has_credential": has_cred
            })

    return {
        "server_count": len(ice_servers),
        "turn_configured": turn_configured,
        "has_turn_udp": has_udp,
        "has_turn_tcp": has_tcp,
        "servers": server_summaries
    }

def get_ice_servers_config() -> List[Dict[str, Any]]:
    """
    Returns sanitized ICE server configuration for browser clients.
    Includes STUN and, if configured, TURN servers with individual transport URLs.
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

    turn_server_url, turn_username, turn_password = get_turn_env()
    if turn_server_url:
        if not turn_username or not turn_password:
            raise ValueError(
                "Incomplete TURN configuration: TURN_USERNAME and TURN_PASSWORD are required when TURN_SERVER_URL is set."
            )
            
        parsed_urls = parse_turn_urls(turn_server_url)
        if parsed_urls:
            ice_servers.append({
                "urls": parsed_urls,
                "username": turn_username,
                "credential": turn_password,
                "credentialType": "password"
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
    
    turn_server_url, turn_username, turn_password = get_turn_env()
    if turn_server_url:
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

