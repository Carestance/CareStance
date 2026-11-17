"""Web Push configuration and delivery for CareStance notifications."""

import asyncio
import base64
import json
import logging
import os
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models

logger = logging.getLogger(__name__)


def _vapid_credentials() -> Optional[Tuple[str, str]]:
    private_key = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n").strip()
    subject = os.getenv("VAPID_SUBJECT", "").strip()
    if not private_key or not subject:
        return None
    return private_key, subject


def get_vapid_public_key() -> Optional[str]:
    credentials = _vapid_credentials()
    if credentials is None:
        return None

    from cryptography.hazmat.primitives import serialization

    private_key = serialization.load_pem_private_key(
        credentials[0].encode("utf-8"),
        password=None,
    )
    from cryptography.hazmat.primitives.asymmetric import ec

    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
        private_key.curve, ec.SECP256R1
    ):
        raise ValueError("VAPID_PRIVATE_KEY must be a P-256 elliptic-curve private key.")
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii")


async def send_user_push_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
) -> None:
    credentials = _vapid_credentials()
    if credentials is None:
        return

    try:
        get_vapid_public_key()
    except (TypeError, ValueError) as error:
        logger.error("Web Push is disabled because VAPID_PRIVATE_KEY is invalid: %s", error)
        return

    try:
        subscriptions = (
            await db.execute(
                select(models.PushSubscription).where(models.PushSubscription.user_id == user_id)
            )
        ).scalars().all()
    except SQLAlchemyError:
        logger.exception("Could not load Web Push subscriptions for user %s.", user_id)
        return
    if not subscriptions:
        return

    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush
    from requests.exceptions import RequestException

    vapid_key = Vapid.from_pem(credentials[0].encode("utf-8"))
    stale_subscriptions = []
    for subscription in subscriptions:
        payload = json.dumps({"title": title, "body": body, "url": "/"})
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=vapid_key,
                vapid_claims={"sub": credentials[1]},
                timeout=5,
                ttl=86400,
            )
        except WebPushException as error:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in (404, 410):
                stale_subscriptions.append(subscription)
            else:
                logger.warning(
                    "Web Push delivery failed for user %s (status %s, %s).",
                    user_id,
                    status_code,
                    type(error).__name__,
                )
        except (OSError, TimeoutError, RequestException) as error:
            logger.warning(
                "Web Push delivery failed for user %s (%s).",
                user_id,
                type(error).__name__,
            )

    if stale_subscriptions:
        try:
            for subscription in stale_subscriptions:
                await db.delete(subscription)
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Could not remove expired Web Push subscriptions.")
