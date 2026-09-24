import os
import pytest
from app.realtime.transport.webrtc import (
    parse_turn_urls,
    get_ice_servers_config,
    get_backend_ice_servers
)

def test_turn_urls_absent(monkeypatch):
    monkeypatch.delenv("TURN_SERVER_URL", raising=False)
    monkeypatch.delenv("TURN_SERVER_URLS", raising=False)
    monkeypatch.delenv("TURN_USERNAME", raising=False)
    monkeypatch.delenv("TURN_PASSWORD", raising=False)

    backend_servers = get_backend_ice_servers()
    assert len(backend_servers) == 1
    assert "stun:stun.l.google.com:19302" in backend_servers[0].urls

    frontend_config = get_ice_servers_config()
    assert len(frontend_config) == 1
    assert "urls" in frontend_config[0]
    assert any("stun.l.google.com" in u for u in frontend_config[0]["urls"])

def test_turn_urls_present_with_transports(monkeypatch):
    monkeypatch.setenv("TURN_SERVER_URL", "turn:turn.example.com:3478")
    monkeypatch.setenv("TURN_USERNAME", "test_user")
    monkeypatch.setenv("TURN_PASSWORD", "test_secret_pass")

    backend_servers = get_backend_ice_servers()
    assert len(backend_servers) == 2
    turn_server = backend_servers[1]
    assert "turn:turn.example.com:3478?transport=udp" in turn_server.urls
    assert "turn:turn.example.com:3478?transport=tcp" in turn_server.urls
    assert turn_server.username == "test_user"
    assert turn_server.credential == "test_secret_pass"

    frontend_config = get_ice_servers_config()
    assert len(frontend_config) == 2
    turn_dict = frontend_config[1]
    assert "turn:turn.example.com:3478?transport=udp" in turn_dict["urls"]
    assert "turn:turn.example.com:3478?transport=tcp" in turn_dict["urls"]
    assert turn_dict["username"] == "test_user"
    assert turn_dict["credential"] == "test_secret_pass"

def test_turn_urls_multi_transport_and_turns(monkeypatch):
    raw = "turn:turn.example.com:3478?transport=udp, turns:turn.example.com:5349"
    monkeypatch.setenv("TURN_SERVER_URL", raw)
    monkeypatch.setenv("TURN_USERNAME", "user1")
    monkeypatch.setenv("TURN_PASSWORD", "pass1")

    parsed = parse_turn_urls(raw)
    assert "turn:turn.example.com:3478?transport=udp" in parsed
    assert "turns:turn.example.com:5349?transport=tcp" in parsed

def test_missing_turn_credentials(monkeypatch):
    monkeypatch.setenv("TURN_SERVER_URL", "turn:turn.example.com:3478")
    monkeypatch.delenv("TURN_USERNAME", raising=False)
    monkeypatch.delenv("TURN_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Incomplete TURN configuration"):
        get_backend_ice_servers()

    with pytest.raises(ValueError, match="Incomplete TURN configuration"):
        get_ice_servers_config()

def test_invalid_turn_url_scheme():
    with pytest.raises(ValueError, match="Invalid TURN URL scheme"):
        parse_turn_urls("http://invalid-turn.example.com:3478")

    with pytest.raises(ValueError, match="Invalid TURN URL scheme"):
        parse_turn_urls("tcp://invalid-turn.example.com:3478")
