import base64
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.mobile import (
    PushSubscriptionRequest,
    _is_supported_push_endpoint,
    save_push_subscription,
)
from app.services.push_notifications import get_vapid_public_key


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/subscription-token",
        "https://updates.push.services.mozilla.com/wpush/v2/subscription-token",
        "https://web.push.apple.com/subscription-token",
        "https://wns2.notify.windows.com/w/?token=subscription-token",
    ],
)
def test_push_endpoints_allow_supported_https_push_services(endpoint):
    assert _is_supported_push_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/token",
        "https://127.0.0.1/internal",
        "https://example.com/push",
        "https://fcm.googleapis.com:invalid/push",
        "https://fcm.googleapis.com",
    ],
)
def test_push_endpoints_reject_non_push_or_malformed_urls(endpoint):
    assert not _is_supported_push_endpoint(endpoint)


@pytest.mark.asyncio
async def test_subscription_route_rejects_untrusted_endpoint_before_database_access():
    payload = PushSubscriptionRequest(
        endpoint="https://example.com/push",
        keys={"p256dh": "key", "auth": "secret"},
    )

    with pytest.raises(HTTPException) as error:
        await save_push_subscription(
            payload=payload,
            user=SimpleNamespace(id=12),
            db=None,
        )

    assert error.value.status_code == 422


def test_public_vapid_key_is_derived_from_private_key(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    expected_public_key = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    monkeypatch.setenv("VAPID_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:push@example.com")

    assert get_vapid_public_key() == base64.urlsafe_b64encode(
        expected_public_key
    ).rstrip(b"=").decode("ascii")


def test_push_is_disabled_when_vapid_is_not_configured(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)

    assert get_vapid_public_key() is None


@pytest.mark.asyncio
async def test_existing_user_notification_is_sent_to_saved_push_subscription(monkeypatch):
    import json

    import pywebpush

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from app.services.push_notifications import send_user_push_notification

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:push@example.com")

    subscription = SimpleNamespace(
        endpoint="https://fcm.googleapis.com/fcm/send/subscription-token",
        p256dh="public-key",
        auth="auth-secret",
    )
    sent = []

    class _Scalars:
        def all(self):
            return [subscription]

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Database:
        async def execute(self, statement):
            return _Result()

    def fake_webpush(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)

    await send_user_push_notification(_Database(), 42, "Booking confirmed", "Your booking is ready.")

    assert len(sent) == 1
    assert sent[0]["subscription_info"]["endpoint"] == subscription.endpoint
    assert isinstance(sent[0]["vapid_private_key"], pywebpush.Vapid01)
    assert json.loads(sent[0]["data"]) == {
        "title": "Booking confirmed",
        "body": "Your booking is ready.",
        "url": "/",
    }
