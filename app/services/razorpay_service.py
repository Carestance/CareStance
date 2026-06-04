"""
Razorpay Service Layer for CareStance Split Payments
=====================================================
Uses RazorpayX Payouts API to transfer counselor's 70% share
directly to their UPI ID after payment capture.

Flow:
1. Student pays full amount → Razorpay Order (standard)
2. Payment captured → verify signature
3. Trigger RazorpayX Payout → 70% sent to counselor's UPI ID
4. 30% stays in CareStance's Razorpay balance
"""

import os
import hmac
import hashlib
import httpx
from dotenv import load_dotenv

load_dotenv()

# ─── Razorpay Client Initialization ────────────────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_your_key_id")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "your_key_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

razorpay_client = None

def get_razorpay_client():
    global razorpay_client
    if razorpay_client is None:
        import razorpay
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return razorpay_client

# RazorpayX account number (found in RazorpayX Dashboard → Account Settings)
# This is the account from which payouts are debited
RAZORPAYX_ACCOUNT_NUMBER = os.getenv("RAZORPAYX_ACCOUNT_NUMBER", "")

RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"

# ─── Commission Split Configuration ────────────────────────────────────────────
COUNSELOR_SHARE_PERCENT = 70  # 70% goes to counselor via UPI
PLATFORM_SHARE_PERCENT = 30   # 30% stays with CareStance


# ═══════════════════════════════════════════════════════════════════════════════
#  ORDER CREATION (Standard — no transfer instructions needed)
# ═══════════════════════════════════════════════════════════════════════════════

def create_order(
    amount_inr: float,
    receipt: str = "",
    notes: dict = None
) -> dict:
    """
    Create a standard Razorpay Order (full amount collected by platform).
    
    The 70/30 split is handled AFTER payment capture via UPI Payout,
    not at order creation time.
    
    Args:
        amount_inr: Total session fee in INR (e.g., 1000.00)
        receipt: Optional receipt identifier
        notes: Optional metadata dict
    
    Returns:
        dict: Razorpay order response
    """
    amount_paise = int(amount_inr * 100)

    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,  # Auto-capture payment
    }

    if notes:
        order_data["notes"] = notes

    razorpay_client = get_razorpay_client()
    order = razorpay_client.order.create(data=order_data)
    return order


# ═══════════════════════════════════════════════════════════════════════════════
#  RAZORPAYX: Contact + Fund Account + Payout (UPI Direct Transfer)
# ═══════════════════════════════════════════════════════════════════════════════

async def create_contact(name: str, email: str, phone: str) -> dict:
    """
    Create a RazorpayX Contact (represents a counselor as a payee).
    
    A Contact is required before creating a Fund Account for payouts.
    
    Args:
        name: Counselor's full name
        email: Counselor's email
        phone: Counselor's phone number
    
    Returns:
        dict: Contact details with 'id' field (cont_XXXX)
    """
    async with httpx.AsyncClient(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
        timeout=30.0
    ) as http:
        response = await http.post(
            f"{RAZORPAY_BASE_URL}/contacts",
            json={
                "name": name,
                "email": email,
                "contact": phone,
                "type": "vendor",
                "notes": {
                    "platform": "CareStance",
                    "role": "counselor"
                }
            }
        )
        response.raise_for_status()
        return response.json()


async def create_fund_account_upi(contact_id: str, upi_vpa: str) -> dict:
    """
    Create a RazorpayX Fund Account linked to a counselor's UPI ID.
    
    This registers the counselor's UPI VPA (e.g., name@upi) so payouts
    can be sent directly to it.
    
    Args:
        contact_id: RazorpayX Contact ID (cont_XXXX)
        upi_vpa: Counselor's UPI ID (e.g., counselor@paytm, name@ybl)
    
    Returns:
        dict: Fund Account details with 'id' field (fa_XXXX)
    """
    async with httpx.AsyncClient(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
        timeout=30.0
    ) as http:
        response = await http.post(
            f"{RAZORPAY_BASE_URL}/fund_accounts",
            json={
                "contact_id": contact_id,
                "account_type": "vpa",
                "vpa": {
                    "address": upi_vpa
                }
            }
        )
        response.raise_for_status()
        return response.json()


async def create_payout_to_upi(
    fund_account_id: str,
    amount_inr: float,
    purpose: str = "payout",
    reference_id: str = "",
    narration: str = "CareStance Session Payout"
) -> dict:
    """
    Create a RazorpayX Payout to send money to the counselor's UPI ID.
    
    This is called after a student's payment is captured to transfer
    the counselor's 70% share directly to their UPI.
    
    Args:
        fund_account_id: RazorpayX Fund Account ID (fa_XXXX)
        amount_inr: Amount to transfer in INR (counselor's 70% share)
        purpose: Purpose code (default: "payout")
        reference_id: Your internal reference
        narration: Description shown to counselor
    
    Returns:
        dict: Payout details with 'id' field (pout_XXXX) and 'status'
    
    Raises:
        httpx.HTTPStatusError: If API call fails
        ValueError: If RAZORPAYX_ACCOUNT_NUMBER is not configured
    """
    if not RAZORPAYX_ACCOUNT_NUMBER:
        raise ValueError(
            "RAZORPAYX_ACCOUNT_NUMBER is not configured. "
            "Set it in your .env file from the RazorpayX Dashboard."
        )

    amount_paise = int(amount_inr * 100)

    async with httpx.AsyncClient(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
        timeout=30.0
    ) as http:
        response = await http.post(
            f"{RAZORPAY_BASE_URL}/payouts",
            json={
                "account_number": RAZORPAYX_ACCOUNT_NUMBER,
                "fund_account_id": fund_account_id,
                "amount": amount_paise,
                "currency": "INR",
                "mode": "UPI",
                "purpose": purpose,
                "queue_if_low_balance": True,
                "reference_id": reference_id,
                "narration": narration,
                "notes": {
                    "platform": "CareStance",
                    "split": f"{COUNSELOR_SHARE_PERCENT}% counselor share"
                }
            }
        )
        response.raise_for_status()
        return response.json()


# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNATURE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> bool:
    """
    Verify the Razorpay payment signature using HMAC SHA256.
    
    Must be called after Razorpay Checkout to confirm payment authenticity.
    
    Raises:
        razorpay.errors.SignatureVerificationError: If signature is invalid
    """
    params_dict = {
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature
    }
    get_razorpay_client().utility.verify_payment_signature(params_dict)
    return True


def verify_webhook_signature(request_body: bytes, signature: str) -> bool:
    """
    Verify Razorpay webhook request signature (HMAC SHA256).
    
    Raises:
        ValueError: If RAZORPAY_WEBHOOK_SECRET is not configured
    """
    if not RAZORPAY_WEBHOOK_SECRET:
        raise ValueError(
            "RAZORPAY_WEBHOOK_SECRET is not configured. "
            "Set it in your .env file from the Razorpay Dashboard."
        )

    expected_signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        msg=request_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_split_amounts(total_amount_inr: float) -> dict:
    """
    Calculate the 70/30 split for a given amount.
    
    Example: ₹1000 → counselor ₹700, platform ₹300
    """
    counselor_amount = round(total_amount_inr * COUNSELOR_SHARE_PERCENT / 100, 2)
    platform_amount = round(total_amount_inr - counselor_amount, 2)
    return {
        "total": total_amount_inr,
        "counselor_amount": counselor_amount,
        "platform_amount": platform_amount,
        "counselor_percent": COUNSELOR_SHARE_PERCENT,
        "platform_percent": PLATFORM_SHARE_PERCENT
    }
