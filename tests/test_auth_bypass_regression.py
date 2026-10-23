"""Regression tests for authentication bypass vulnerability.

Verifies that:
1. A request containing user_id=1 without a valid authentication token cannot authenticate as user 1.
2. Numeric values in the user_id cookie never establish identity.
3. Invalid and tampered JWTs are rejected.
4. Expired tokens are rejected.
5. A valid token authenticates the correct user.
6. A regular user cannot access administrator-only endpoints.
7. Existing legitimate login, logout, and session flows continue to work.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.dependencies.admin_auth import _decode_cookie_user_id, get_current_admin
from app.main import app, get_current_user
from app.models import User
from app.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    get_jwt_secret_key,
)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


def _create_mock_request(cookies: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    req = Request(scope)
    if cookies:
        req._cookies = cookies
    else:
        req._cookies = {}
    return req


# 1. Numeric values in the user_id cookie never establish identity
@pytest.mark.parametrize("numeric_val", ["1", "2", "42", "0", "9999", "123456789"])
def test_numeric_user_id_cookie_rejected_by_decode(numeric_val):
    assert decode_access_token(numeric_val) is None
    assert _decode_cookie_user_id(numeric_val) is None


# 2. Invalid and tampered JWTs are rejected
def test_invalid_and_tampered_jwts_rejected():
    assert decode_access_token(None) is None
    assert decode_access_token("") is None
    assert decode_access_token("   ") is None
    assert decode_access_token("invalid.jwt.token") is None
    assert decode_access_token("not-a-token-at-all") is None

    # Token signed with an attacker's key
    attacker_token = jwt.encode(
        {"sub": "1", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)},
        "wrong_secret_key_used_by_attacker",
        algorithm=JWT_ALGORITHM,
    )
    assert decode_access_token(attacker_token) is None
    assert _decode_cookie_user_id(attacker_token) is None

    # Tampered signature
    valid_token = create_access_token(1)
    tampered_token = valid_token[:-4] + "abcd"
    assert decode_access_token(tampered_token) is None
    assert _decode_cookie_user_id(tampered_token) is None


# 3. Expired tokens are rejected
def test_expired_tokens_rejected():
    expired_token = create_access_token(
        1,
        expires_delta=datetime.timedelta(seconds=-10),
    )
    assert decode_access_token(expired_token) is None
    assert _decode_cookie_user_id(expired_token) is None


# 4. Valid token authenticates the correct user
def test_valid_token_decodes_correct_user_id():
    token = create_access_token("42")
    assert decode_access_token(token) == "42"
    assert _decode_cookie_user_id(token) == "42"

    token_int = create_access_token(100)
    assert decode_access_token(token_int) == "100"
    assert _decode_cookie_user_id(token_int) == "100"


# 5. get_current_user rejects user_id=1 without valid JWT
@pytest.mark.asyncio
async def test_get_current_user_rejects_raw_numeric_cookie(mock_db):
    req = _create_mock_request(cookies={"user_id": "1"})
    user = await get_current_user(req, mock_db)
    assert user is None
    # Verifies database was not queried because token was rejected immediately
    mock_db.execute.assert_not_called()


# 6. get_current_user authenticates valid token
@pytest.mark.asyncio
async def test_get_current_user_accepts_valid_jwt(mock_db):
    valid_token = create_access_token("1")
    req = _create_mock_request(cookies={"user_id": valid_token})

    fake_user = User(id=1, email="user1@example.com", full_name="User One", role="student")
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    user = await get_current_user(req, mock_db)
    assert user is not None
    assert user.id == 1
    assert user.email == "user1@example.com"


# 7. get_current_admin rejects raw numeric cookie
@pytest.mark.asyncio
async def test_get_current_admin_rejects_raw_numeric_cookie(mock_db):
    req = _create_mock_request(cookies={"user_id": "1"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)

    assert exc_info.value.status_code == 302
    assert exc_info.value.headers.get("Location") == "/login"
    mock_db.execute.assert_not_called()


# 8. get_current_admin rejects regular user
@pytest.mark.asyncio
async def test_get_current_admin_rejects_regular_user(mock_db):
    regular_user_token = create_access_token("2")
    req = _create_mock_request(cookies={"user_id": regular_user_token})

    fake_student = User(id=2, email="student@example.com", full_name="Student", role="student")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_student
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)

    assert exc_info.value.status_code == 302
    assert "Admin+access+denied" in exc_info.value.headers.get("Location", "")


# 9. get_current_admin allows administrator
@pytest.mark.asyncio
async def test_get_current_admin_allows_admin(mock_db):
    admin_token = create_access_token("1")
    req = _create_mock_request(cookies={"user_id": admin_token})

    fake_admin = User(id=1, email="admin@example.com", full_name="Admin", role="admin")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_admin
    mock_db.execute.return_value = mock_result

    admin = await get_current_admin(req, mock_db)
    assert admin is not None
    assert admin.id == 1
    assert admin.role == "admin"


# 10. HTTP Endpoint-level tests with TestClient
def test_endpoint_numeric_cookie_cannot_access_admin():
    client = TestClient(app, follow_redirects=False)
    # Attacker tries to access /admin with cookie user_id=1
    response = client.get("/admin", cookies={"user_id": "1"})
    assert response.status_code == 302
    assert response.headers.get("location") == "/login"


def test_endpoint_numeric_cookie_cannot_access_protected_page():
    client = TestClient(app, follow_redirects=False)
    # Attacker tries to access /my-connections with cookie user_id=1
    response = client.get("/my-connections", cookies={"user_id": "1"})
    assert response.status_code == 302
    assert response.headers.get("location") == "/login"


def test_endpoint_tampered_token_cannot_access_protected_page():
    client = TestClient(app, follow_redirects=False)
    tampered_token = create_access_token(1) + "malicious_tamper"
    response = client.get("/my-connections", cookies={"user_id": tampered_token})
    assert response.status_code == 302
    assert response.headers.get("location") == "/login"


def test_logout_clears_user_id_cookie():
    client = TestClient(app, follow_redirects=False)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers.get("location") == "/login"
    # Ensure Set-Cookie deletes or expires user_id
    cookies_header = response.headers.get("set-cookie", "")
    assert "user_id" in cookies_header


# 11. Claim-level edge cases: missing exp, missing sub, algorithm none, empty sub
def test_jwt_claims_validation_edge_cases():
    secret = get_jwt_secret_key()

    # Missing 'exp' claim
    token_no_exp = jwt.encode({"sub": "1"}, secret, algorithm=JWT_ALGORITHM)
    assert decode_access_token(token_no_exp) is None

    # Missing 'sub' claim
    token_no_sub = jwt.encode(
        {"exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)},
        secret,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_access_token(token_no_sub) is None

    # Empty string sub claim
    token_empty_sub = jwt.encode(
        {"sub": "", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)},
        secret,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_access_token(token_empty_sub) is None

    # Algorithm 'none' attack
    token_alg_none = jwt.encode(
        {"sub": "1", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)},
        key="",
        algorithm="none",
    )
    assert decode_access_token(token_alg_none) is None


# 12. Client-forged admin claims in token cannot grant administrator access
@pytest.mark.asyncio
async def test_forged_admin_claim_in_jwt_cannot_grant_admin_access(mock_db):
    secret = get_jwt_secret_key()
    # Attacker crafts token claiming role=admin or is_admin=True
    forged_token = jwt.encode(
        {
            "sub": "2",
            "role": "admin",
            "is_admin": True,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        },
        secret,
        algorithm=JWT_ALGORITHM,
    )
    req = _create_mock_request(cookies={"user_id": forged_token})

    # In database, user 2 is a regular student
    fake_student = User(id=2, email="student@example.com", full_name="Student", role="student")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_student
    mock_db.execute.return_value = mock_result

    # Authorization must rely on trusted server-side DB data, rejecting the forged client claims
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)

    assert exc_info.value.status_code == 302
    assert "Admin+access+denied" in exc_info.value.headers.get("Location", "")


# 13. Suspended administrator is blocked from admin operations
@pytest.mark.asyncio
async def test_suspended_admin_blocked(mock_db):
    admin_token = create_access_token("1")
    req = _create_mock_request(cookies={"user_id": admin_token})

    fake_admin = User(id=1, email="admin@example.com", full_name="Admin", role="admin", is_suspended=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_admin
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)

    assert exc_info.value.status_code == 302
    assert exc_info.value.headers.get("Location") == "/suspended"


# 14. Production secret configuration enforcement
def test_production_secret_fails_safely_when_missing_or_default(monkeypatch):
    from app.security import INSECURE_DEFAULT_SECRET

    # Test in production with default insecure secret -> raises RuntimeError
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", INSECURE_DEFAULT_SECRET)
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        get_jwt_secret_key()

    # Test in production with empty secret -> raises RuntimeError
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        get_jwt_secret_key()

    # Test in production with strong custom secret -> succeeds
    monkeypatch.setenv("SECRET_KEY", "super_secure_random_key_for_production_use_only")
    assert get_jwt_secret_key() == "super_secure_random_key_for_production_use_only"


# 15. Self-service signup role tampering prevention
@pytest.mark.asyncio
async def test_signup_cannot_register_as_admin(mock_db):
    from app.main import signup

    req = _create_mock_request()

    # Mock user not existing in DB
    mock_stmt_result = MagicMock()
    mock_stmt_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_stmt_result

    # Attacker submits role="admin" via form
    response = await signup(
        request=req,
        email="hacker@example.com",
        password="SecurePassword123!",
        full_name="Hacker",
        contact_number="+911234567890",
        role="admin",
        db=mock_db,
    )

    # Inspect added User instance in db.add
    added_user = None
    for call_args in mock_db.add.call_args_list:
        obj = call_args[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    # Verifies role was sanitized and cannot be set to admin
    assert added_user.role == "student"


# ==============================================================================
# AUDIT FINDING 1: PUBLIC TEST-USER ENDPOINT (/admin/create-adsense-test-user)
# ==============================================================================

@pytest.mark.asyncio
async def test_adsense_test_user_unauthenticated_blocked(mock_db):
    """Unauthenticated access must be redirected to /login and denied."""
    req = _create_mock_request(cookies={})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)
    assert exc_info.value.status_code == 302
    assert exc_info.value.headers.get("Location") == "/login"


@pytest.mark.asyncio
async def test_adsense_test_user_regular_user_blocked(mock_db):
    """A regular student user must be rejected and denied admin access."""
    token = create_access_token(12)
    req = _create_mock_request(cookies={"user_id": token})

    mock_user = MagicMock()
    mock_user.id = 12
    mock_user.email = "student@example.com"
    mock_user.role = "student"
    mock_user.is_suspended = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(req, mock_db)
    assert exc_info.value.status_code == 302
    assert "Admin+access+denied" in exc_info.value.headers.get("Location", "")


@pytest.mark.asyncio
async def test_adsense_test_user_disabled_in_production(mock_db, monkeypatch):
    """Endpoint must raise 404 in production, even when called by an admin."""
    from app.main import create_adsense_test_user

    monkeypatch.setenv("ENVIRONMENT", "production")

    admin_user = MagicMock()
    admin_user.id = 1
    admin_user.email = "admin@carestance.me"
    admin_user.role = "admin"

    with pytest.raises(HTTPException) as exc_info:
        await create_adsense_test_user(db=mock_db, admin=admin_user)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Endpoint not found"


@pytest.mark.asyncio
async def test_adsense_test_user_admin_in_dev_uses_dynamic_credentials(mock_db, monkeypatch):
    """Admin access in dev creates/rotates test user with a random password, eliminating hardcoded credentials."""
    from app.main import create_adsense_test_user

    monkeypatch.setenv("ENVIRONMENT", "development")

    admin_user = MagicMock()
    admin_user.id = 1
    admin_user.email = "admin@carestance.me"
    admin_user.role = "admin"

    # User does not exist yet
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_scalar_result

    res = await create_adsense_test_user(db=mock_db, admin=admin_user)

    assert res["email"] == "adsense-tester@carestance.me"
    # Never the hardcoded reusable password "CareStance2026!"
    assert res["password"] != "CareStance2026!"
    assert res["password"].startswith("AdSense_")
    assert len(res["password"]) >= 20

    # Ensure user was added to DB with hashed password
    added_user = None
    for call_args in mock_db.add.call_args_list:
        obj = call_args[0][0]
        if hasattr(obj, "email") and obj.email == "adsense-tester@carestance.me":
            added_user = obj
            break
    assert added_user is not None
    assert added_user.hashed_password != "CareStance2026!"


# ==============================================================================
# AUDIT FINDING 2: SENSITIVE DATABASE DUMPS IN GIT
# ==============================================================================

def test_database_dumps_untracked_in_git():
    """Verify that sensitive database dumps and assets are untracked in Git index."""
    import subprocess
    from pathlib import Path

    repo_dir = Path(__file__).resolve().parent.parent

    # Check git ls-files does not return the sensitive sql dumps
    res = subprocess.run(
        ["git", "ls-files", "backups/supabase_users.sql", "backups/supabase_data.sql", "backups/supabase_schema.sql"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"Sensitive backup files still tracked in Git index: {res.stdout}"

    # Verify that local backup files are still preserved on disk
    backup_file = repo_dir / "backups" / "supabase_users.sql"
    assert backup_file.exists(), "Local backup file was deleted from disk! It must remain intact locally."

    # Verify .gitignore ignores them
    res_ignore = subprocess.run(
        ["git", "check-ignore", "backups/supabase_users.sql", "backups/supabase_data.sql"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert res_ignore.returncode == 0
    assert "backups/supabase_users.sql" in res_ignore.stdout


# ==============================================================================
# AUDIT FINDING 3: SECURE AUTHENTICATION COOKIES
# ==============================================================================

def test_auth_cookie_config_across_environments(monkeypatch):
    """Test get_auth_cookie_config attributes in dev vs production environments."""
    from app.security import get_auth_cookie_config

    # Development
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    dev_config = get_auth_cookie_config()
    assert dev_config["httponly"] is True
    assert dev_config["samesite"] == "lax"
    assert dev_config["secure"] is False

    # Production via ENVIRONMENT
    monkeypatch.setenv("ENVIRONMENT", "production")
    prod_config = get_auth_cookie_config()
    assert prod_config["httponly"] is True
    assert prod_config["samesite"] == "lax"
    assert prod_config["secure"] is True

    # Production via VERCEL
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    vercel_config = get_auth_cookie_config()
    assert vercel_config["secure"] is True

    # Production via RAILWAY_ENVIRONMENT
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    railway_config = get_auth_cookie_config()
    assert railway_config["secure"] is True


@pytest.mark.asyncio
async def test_login_cookie_attributes_production_vs_development(mock_db, monkeypatch):
    """Test that login route issues cookies with secure=True in prod and secure=False in dev."""
    from app.main import login
    from app.security import get_password_hash

    # Setup mock user
    user = User(
        id=77,
        email="testcookie@example.com",
        hashed_password=get_password_hash("ValidPass123!"),
        role="student",
        is_suspended=False,
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = user
    mock_db.execute.return_value = mock_result

    req = _create_mock_request()

    # 1. Dev environment
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    res_dev = await login(request=req, email="testcookie@example.com", password="ValidPass123!", db=mock_db)
    cookie_dev = res_dev.headers.get("set-cookie", "")
    assert "user_id=" in cookie_dev
    assert "httponly" in cookie_dev.lower()
    assert "samesite=lax" in cookie_dev.lower()
    assert "secure" not in cookie_dev.lower()

    # 2. Production environment
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a_strong_production_secret_key_1234567890")
    res_prod = await login(request=req, email="testcookie@example.com", password="ValidPass123!", db=mock_db)
    cookie_prod = res_prod.headers.get("set-cookie", "")
    assert "user_id=" in cookie_prod
    assert "httponly" in cookie_prod.lower()
    assert "samesite=lax" in cookie_prod.lower()
    assert "secure" in cookie_prod.lower()


@pytest.mark.asyncio
async def test_logout_cookie_deletion_attributes(monkeypatch):
    """Test that logout properly clears cookies with compatible attributes in prod vs dev."""
    from app.main import logout
    from fastapi import Response

    # Dev environment
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    res_dev = await logout(response=Response())
    cookie_dev = res_dev.headers.get("set-cookie", "")
    assert 'user_id=""' in cookie_dev or "user_id=;" in cookie_dev or 'user_id="deleted"' in cookie_dev or 'user_id=deleted' in cookie_dev
    assert "httponly" in cookie_dev.lower()
    assert "samesite=lax" in cookie_dev.lower()
    assert "secure" not in cookie_dev.lower()

    # Prod environment
    monkeypatch.setenv("ENVIRONMENT", "production")
    res_prod = await logout(response=Response())
    cookie_prod = res_prod.headers.get("set-cookie", "")
    assert 'user_id=""' in cookie_prod or "user_id=;" in cookie_prod or 'user_id="deleted"' in cookie_prod or 'user_id=deleted' in cookie_prod
    assert "httponly" in cookie_prod.lower()
    assert "samesite=lax" in cookie_prod.lower()
    assert "secure" in cookie_prod.lower()


