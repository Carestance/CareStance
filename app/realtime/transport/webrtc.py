from typing import Any, Dict
from pydantic import BaseModel

class WebRTCOffer(BaseModel):
    sdp: str
    type: str

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
