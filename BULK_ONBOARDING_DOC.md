# Bulk Onboarding Flow

This repository now includes a reusable backend service and an admin entry point for creating a batch of accounts that immediately receive the paid ₹300 bundle behaviour without a Razorpay payment screen.

## Required Flow

1. Admin opens the bulk onboarding form route at `/admin/bulk-onboard-form`.
2. Admin submits a JSON list of user records or a form payload with a `users` JSON array.
3. Backend validates each email, deduplicates against the `users` table, and creates the account.
4. Each created user receives an active `customised` subscription state with an expiry beyond the default 3650-day horizon.
5. A generated password is stored as a bcrypt hash in the user record and is returned or emailed through the service hook if requested.

## Core Service

The service is implemented in `app/services/bulk_onboarding_service.py` and provides:

- `generate_secure_password()`
- `get_bulk_onboarding_plan_assignment()`
- `bulk_onboard_users()`

## Admin Routes

The admin router now includes:

- `GET /admin/bulk-onboard-form`
- `POST /admin/bulk-onboard-form`
- `POST /admin/bulk-onboard`

The backend route `/admin/bulk-onboard` accepts a payload shaped like:

```json
{
  "users": [
    {"email": "student@example.com", "full_name": "Student X", "contact_number": "+91 90000 00000", "role": "student"}
  ],
  "send_credentials": false
}
```

## Access Mapping

The subscription mapping bypasses the payment flow by assigning the `customised` plan state and enabling all service bundle features listed in the `R300_SERVICE_BUNDLE` constant.
