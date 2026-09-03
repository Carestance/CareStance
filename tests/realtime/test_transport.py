import pytest
import sys
from unittest.mock import MagicMock

# Mock pipecat module so we can test the transport configs without it installed
mock_pipecat = MagicMock()
mock_pipecat.transports.network.fastapi_webrtc = MagicMock()
mock_pipecat.transports.network.fastapi_webrtc.FastAPIWebRTCTransport = MagicMock()
mock_pipecat.transports.network.fastapi_webrtc.FastAPIWebRTCParams = MagicMock()
sys.modules['pipecat.transports'] = mock_pipecat.transports
sys.modules['pipecat.transports.network'] = mock_pipecat.transports.network
sys.modules['pipecat.transports.network.fastapi_webrtc'] = mock_pipecat.transports.network.fastapi_webrtc

def test_webrtc_offer_model():
    from app.realtime.transport.webrtc import WebRTCOffer
    offer = WebRTCOffer(sdp="v=0...", type="offer")
    assert offer.sdp == "v=0..."
    assert offer.type == "offer"

def test_webrtc_transport_config():
    from app.realtime.transport.webrtc import WebRTCTransportConfig
    transport = WebRTCTransportConfig.create_transport()
    assert transport is not None
