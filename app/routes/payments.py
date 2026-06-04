"""
Payment Routes for CareStance – Razorpay UPI Split Payments
=============================================================
Flow:
  1. POST /payments/setup-counselor-upi    → Register counselor's UPI with RazorpayX
  2. POST /payments/create-order           → Standard Razorpay order (full amount)
  3. POST /payments/verify-payment         → Verify signature + trigger 70% UPI payout
  4. POST /payments/webhook                → Handle payment/payout lifecycle events
"""

import os
import json
import uuid
import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from .. import models
from ..services import razorpay_service

logger = logging.getLogger("carestance.payments")

router = APIRouter(prefix="/payments", tags=["Payments"])


# ─── Pydantic Request Models ──────────────────────────────────────────────────

class SetupCounselorUPIRequest(BaseModel):
    """Request body for registering a counselor's UPI with RazorpayX."""
    counsellor_user_id: int
    upi_id: Optional[str] = None  # Override UPI from profile; if empty, uses profile's UPI


class CreateOrderRequest(BaseModel):
    """Request body for creating a Razorpay order."""
    session_id: Optional[int] = None
    counsellor_id: int
    amount: float  # Total session fee in INR


class VerifyPaymentRequest(BaseModel):
    """Request body for verifying a Razorpay payment after checkout."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    counsellor_id: int
    appointment_time: Optional[str] = None


# ─── Endpoint 1: Setup Counselor UPI for Payouts ──────────────────────────────

@router.post("/setup-counselor-upi")
async def setup_counselor_upi(
    req: SetupCounselorUPIRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a counselor's UPI ID with RazorpayX for receiving payouts.
    
    Creates a RazorpayX Contact + Fund Account (UPI) so that after each
    payment, 70% can be sent directly to the counselor's UPI ID.
    
    This should be called once per counselor during onboarding or
    when an admin approves their profile.
    """
    # ── Validate: Counselor must exist ─────────────────────────────────────
    counsellor_stmt = select(models.User).where(
        models.User.id == req.counsellor_user_id,
        models.User.role == "counsellor"
    )
    counsellor_res = await db.execute(counsellor_stmt)
    counsellor = counsellor_res.scalars().first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counselor not found")

    profile_stmt = select(models.CounsellorProfile).where(
        models.CounsellorProfile.user_id == req.counsellor_user_id
    )
    profile_res = await db.execute(profile_stmt)
    profile = profile_res.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Counselor profile not found. Complete profile setup first."
        )

    # ── Get UPI ID (from request or profile) ──────────────────────────────
    upi_id = req.upi_id
    if not upi_id:
        account_details = profile.account_details or {}
        upi_id = account_details.get("upi", "")

    if not upi_id:
        raise HTTPException(
            status_code=400,
            detail="No UPI ID provided. Please add a UPI ID to the counselor profile first."
        )

    # ── Guard: Already set up ─────────────────────────────────────────────
    if profile.razorpay_fund_account_id:
        return JSONResponse(
            status_code=200,
            content={
                "message": "UPI payout already configured",
                "razorpay_contact_id": profile.razorpay_contact_id,
                "razorpay_fund_account_id": profile.razorpay_fund_account_id,
                "upi_id": upi_id,
                "onboarding_status": profile.onboarding_status
            }
        )

    try:
        # ── Step 1: Create RazorpayX Contact ──────────────────────────────
        phone = counsellor.contact_number or ""
        contact = await razorpay_service.create_contact(
            name=counsellor.full_name,
            email=counsellor.email,
            phone=phone
        )
        contact_id = contact.get("id")

        # ── Step 2: Create Fund Account with UPI VPA ─────────────────────
        fund_account = await razorpay_service.create_fund_account_upi(
            contact_id=contact_id,
            upi_vpa=upi_id
        )
        fund_account_id = fund_account.get("id")

        # ── Save to database ─────────────────────────────────────────────
        profile.razorpay_contact_id = contact_id
        profile.razorpay_fund_account_id = fund_account_id
        profile.onboarding_status = "activated"
        await db.commit()

        logger.info(
            f"UPI payout setup for counselor {counsellor.id}: "
            f"contact={contact_id}, fund_account={fund_account_id}, upi={upi_id}"
        )

        return {
            "message": f"UPI payout configured successfully for {upi_id}",
            "razorpay_contact_id": contact_id,
            "razorpay_fund_account_id": fund_account_id,
            "upi_id": upi_id,
            "onboarding_status": "activated"
        }

    except Exception as e:
        logger.error(f"Failed to setup UPI payout for counselor {counsellor.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure UPI payout: {str(e)}"
        )


# ─── Endpoint 2: Create Order (Standard – No Split at Order Time) ─────────────

@router.post("/create-order")
async def create_order(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a standard Razorpay order for the full session amount.
    
    The 70/30 split happens AFTER payment capture via UPI payout,
    not at order creation time. This simplifies the flow and removes
    the need for Razorpay Route Linked Accounts.
    
    Returns order details for Razorpay Checkout on the frontend.
    """
    # ── Validate amount ──────────────────────────────────────────────────
    if req.amount < 1.0:
        raise HTTPException(
            status_code=400,
            detail="Minimum session fee is ₹1.00"
        )

    # ── Get counselor profile ────────────────────────────────────────────
    profile_stmt = select(models.CounsellorProfile).where(
        models.CounsellorProfile.user_id == req.counsellor_id
    )
    profile_res = await db.execute(profile_stmt)
    profile = profile_res.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="Counselor profile not found")

    # ── Warn if UPI payout not configured (order still works) ────────────
    upi_configured = bool(profile.razorpay_fund_account_id)

    # ── Create standard order ────────────────────────────────────────────
    receipt = f"sess_{uuid.uuid4().hex[:10]}"
    notes = {
        "counsellor_id": str(req.counsellor_id),
        "platform": "CareStance",
        "split": "70% counselor / 30% platform"
    }
    if req.session_id:
        notes["session_id"] = str(req.session_id)

    try:
        order = razorpay_service.create_order(
            amount_inr=req.amount,
            receipt=receipt,
            notes=notes
        )

        # ── Record payment in DB ─────────────────────────────────────────
        payment = models.Payment(
            session_id=req.session_id,
            razorpay_order_id=order["id"],
            amount=req.amount,
            status="created"
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        # ── Calculate split for frontend display ─────────────────────────
        split = razorpay_service.get_split_amounts(req.amount)

        # ── Record expected transfer ─────────────────────────────────────
        transfer = models.Transfer(
            payment_id=payment.id,
            counsellor_id=req.counsellor_id,
            amount=split["counselor_amount"],
            status="pending"
        )
        db.add(transfer)
        await db.commit()

        logger.info(
            f"Order {order['id']} created: ₹{req.amount} "
            f"(₹{split['counselor_amount']} → counselor UPI, "
            f"₹{split['platform_amount']} → platform)"
        )

        return {
            "order_id": order["id"],
            "key": razorpay_service.RAZORPAY_KEY_ID,
            "amount": int(req.amount * 100),
            "currency": "INR",
            "split": split,
            "payment_db_id": payment.id,
            "upi_payout_configured": upi_configured
        }

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment order: {str(e)}"
        )


# ─── Endpoint 3: Verify Payment + Trigger UPI Payout ──────────────────────────

@router.post("/verify-payment")
async def verify_payment(
    req: VerifyPaymentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify payment signature, then trigger 70% UPI payout to counselor.
    
    Flow:
    1. Validate HMAC SHA256 signature
    2. Update Payment record → 'captured'
    3. Trigger RazorpayX Payout → 70% to counselor's UPI ID
    4. Update Transfer record with payout ID
    """
    # ── Guard: Duplicate verification ─────────────────────────────────────
    existing_stmt = select(models.Payment).where(
        models.Payment.razorpay_payment_id == req.razorpay_payment_id
    )
    existing_res = await db.execute(existing_stmt)
    existing = existing_res.scalars().first()

    if existing and existing.status == "captured":
        return JSONResponse(
            status_code=200,
            content={
                "message": "Payment already verified",
                "status": "captured",
                "payment_id": existing.id
            }
        )

    # ── Verify signature ─────────────────────────────────────────────────
    try:
        razorpay_service.verify_payment_signature(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature
        )
    except Exception as e:
        logger.warning(f"Payment verification failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed. Invalid signature."
        )

    # ── Update payment record ────────────────────────────────────────────
    payment_stmt = select(models.Payment).where(
        models.Payment.razorpay_order_id == req.razorpay_order_id
    )
    payment_res = await db.execute(payment_stmt)
    payment = payment_res.scalars().first()

    if not payment:
        payment = models.Payment(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            amount=0,
            status="captured"
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

    payment.razorpay_payment_id = req.razorpay_payment_id
    payment.status = "captured"

    # ── Update linked appointment ────────────────────────────────────────
    if payment.session_id:
        appt_stmt = select(models.Appointment).where(
            models.Appointment.id == payment.session_id
        )
        appt_res = await db.execute(appt_stmt)
        appointment = appt_res.scalars().first()
        if appointment:
            appointment.payment_status = "paid"
            appointment.razorpay_order_id = req.razorpay_order_id
            appointment.razorpay_payment_id = req.razorpay_payment_id

    await db.commit()

    # ── Trigger UPI Payout (70% to counselor) ────────────────────────────
    payout_status = "not_attempted"
    payout_message = ""

    profile_stmt = select(models.CounsellorProfile).where(
        models.CounsellorProfile.user_id == req.counsellor_id
    )
    profile_res = await db.execute(profile_stmt)
    profile = profile_res.scalars().first()

    if profile and profile.razorpay_fund_account_id:
        split = razorpay_service.get_split_amounts(payment.amount)
        try:
            payout = await razorpay_service.create_payout_to_upi(
                fund_account_id=profile.razorpay_fund_account_id,
                amount_inr=split["counselor_amount"],
                reference_id=f"pay_{payment.id}_{req.counsellor_id}",
                narration=f"CareStance Session Payout - ₹{split['counselor_amount']}"
            )

            # Update transfer record
            transfer_stmt = select(models.Transfer).where(
                models.Transfer.payment_id == payment.id
            )
            transfer_res = await db.execute(transfer_stmt)
            transfer = transfer_res.scalars().first()
            if transfer:
                transfer.razorpay_transfer_id = payout.get("id")
                transfer.status = "processed" if payout.get("status") == "processed" else "pending"

            await db.commit()

            payout_status = payout.get("status", "initiated")
            payout_message = f"₹{split['counselor_amount']} payout initiated to counselor UPI"

            logger.info(
                f"UPI Payout initiated: ₹{split['counselor_amount']} "
                f"to counselor {req.counsellor_id} (payout={payout.get('id')})"
            )

        except Exception as e:
            payout_status = "failed"
            payout_message = f"Payout failed: {str(e)}"
            logger.error(f"UPI payout failed for counselor {req.counsellor_id}: {e}")

            # Mark transfer as failed
            transfer_stmt = select(models.Transfer).where(
                models.Transfer.payment_id == payment.id
            )
            transfer_res = await db.execute(transfer_stmt)
            transfer = transfer_res.scalars().first()
            if transfer:
                transfer.status = "failed"
                await db.commit()
    else:
        payout_message = "Counselor UPI payout not configured. Payment collected; manual transfer needed."
        logger.warning(f"No UPI fund account for counselor {req.counsellor_id}")

    return {
        "message": "Payment verified successfully",
        "status": "captured",
        "payment_id": payment.id,
        "payout_status": payout_status,
        "payout_message": payout_message
    }


# ─── Endpoint 4: Webhook Handler ──────────────────────────────────────────────

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Razorpay/RazorpayX webhook events.
    
    Supported events:
    - payment.captured   → Marks payment as captured
    - payout.processed   → Marks UPI payout as successful
    - payout.failed      → Marks payout as failed (needs manual attention)
    - transfer.processed → Legacy: marks transfer as processed
    - transfer.failed    → Legacy: marks transfer as failed
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # ── Verify webhook signature ─────────────────────────────────────────
    try:
        if not razorpay_service.verify_webhook_signature(body, signature):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    except ValueError as e:
        logger.warning(f"Webhook verification skipped: {e}")

    # ── Parse payload ────────────────────────────────────────────────────
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", "")
    entity = payload.get("payload", {})

    logger.info(f"Webhook received: {event}")

    # ── Handle: payment.captured ─────────────────────────────────────────
    if event == "payment.captured":
        payment_entity = entity.get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id")
        amount_paise = payment_entity.get("amount", 0)

        if order_id:
            payment_record_stmt = select(models.Payment).where(
                models.Payment.razorpay_order_id == order_id
            )
            payment_record_res = await db.execute(payment_record_stmt)
            payment_record = payment_record_res.scalars().first()
            if payment_record:
                payment_record.razorpay_payment_id = payment_id
                payment_record.status = "captured"
                payment_record.amount = amount_paise / 100

                if payment_record.session_id:
                    appt_stmt = select(models.Appointment).where(
                        models.Appointment.id == payment_record.session_id
                    )
                    appt_res = await db.execute(appt_stmt)
                    appointment = appt_res.scalars().first()
                    if appointment:
                        appointment.payment_status = "paid"
                        appointment.razorpay_payment_id = payment_id

                await db.commit()
                logger.info(f"payment.captured processed for order {order_id}")

    # ── Handle: payout.processed (UPI payout successful) ─────────────────
    elif event == "payout.processed":
        payout_entity = entity.get("payout", {}).get("entity", {})
        payout_id = payout_entity.get("id")
        amount_paise = payout_entity.get("amount", 0)
        reference_id = payout_entity.get("reference_id", "")

        # Find transfer record by the payout ID
        transfer_stmt = select(models.Transfer).where(
            models.Transfer.razorpay_transfer_id == payout_id
        )
        transfer_res = await db.execute(transfer_stmt)
        transfer = transfer_res.scalars().first()

        if transfer:
            transfer.status = "processed"
            transfer.amount = amount_paise / 100
            await db.commit()
            logger.info(
                f"payout.processed: ₹{amount_paise/100} to counselor "
                f"{transfer.counsellor_id} via UPI"
            )

    # ── Handle: payout.failed ────────────────────────────────────────────
    elif event == "payout.failed":
        payout_entity = entity.get("payout", {}).get("entity", {})
        payout_id = payout_entity.get("id")
        failure_reason = payout_entity.get("failure_reason", "Unknown")

        transfer_stmt = select(models.Transfer).where(
            models.Transfer.razorpay_transfer_id == payout_id
        )
        transfer_res = await db.execute(transfer_stmt)
        transfer = transfer_res.scalars().first()

        if transfer:
            transfer.status = "failed"
            await db.commit()
            logger.error(
                f"payout.failed: Payout {payout_id} for counselor "
                f"{transfer.counsellor_id} FAILED. Reason: {failure_reason}"
            )

    # ── Handle: transfer.processed (legacy/fallback) ─────────────────────
    elif event == "transfer.processed":
        transfer_entity = entity.get("transfer", {}).get("entity", {})
        transfer_id = transfer_entity.get("id")
        payment_id = transfer_entity.get("source")
        amount_paise = transfer_entity.get("amount", 0)

        if payment_id:
            payment_record_stmt = select(models.Payment).where(
                models.Payment.razorpay_payment_id == payment_id
            )
            payment_record_res = await db.execute(payment_record_stmt)
            payment_record = payment_record_res.scalars().first()
            if payment_record:
                transfer_record_stmt = select(models.Transfer).where(
                    models.Transfer.payment_id == payment_record.id
                )
                transfer_record_res = await db.execute(transfer_record_stmt)
                transfer_record = transfer_record_res.scalars().first()
                if transfer_record:
                    transfer_record.razorpay_transfer_id = transfer_id
                    transfer_record.status = "processed"
                    transfer_record.amount = amount_paise / 100
                    await db.commit()

    # ── Handle: transfer.failed (legacy/fallback) ────────────────────────
    elif event == "transfer.failed":
        transfer_entity = entity.get("transfer", {}).get("entity", {})
        transfer_id = transfer_entity.get("id")
        payment_id = transfer_entity.get("source")

        if payment_id:
            payment_record_stmt = select(models.Payment).where(
                models.Payment.razorpay_payment_id == payment_id
            )
            payment_record_res = await db.execute(payment_record_stmt)
            payment_record = payment_record_res.scalars().first()
            if payment_record:
                transfer_record_stmt = select(models.Transfer).where(
                    models.Transfer.payment_id == payment_record.id
                )
                transfer_record_res = await db.execute(transfer_record_stmt)
                transfer_record = transfer_record_res.scalars().first()
                if transfer_record:
                    transfer_record.razorpay_transfer_id = transfer_id
                    transfer_record.status = "failed"
                    await db.commit()

    return {"status": "ok"}
