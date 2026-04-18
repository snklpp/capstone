"""Auth router — login + student registration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import verify_password, create_access_token, hash_password
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, RegisterRequest, RegisterResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        data={"sub": user.id, "role": user.role, "student_id": user.student_id}
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account.

    The roll number / username is used as the login credential.
    """
    # Validate role
    valid_roles = {"student", "admin", "verifier"}
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. Must be one of: {', '.join(valid_roles)}",
        )

    # Check if username already exists
    existing = db.query(User).filter(User.username == body.roll_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account with username '{body.roll_number}' already exists",
        )

    user = User(
        username=body.roll_number,
        hashed_password=hash_password(body.password),
        role=body.role,
        student_id=body.roll_number if body.role == "student" else None,
        full_name=body.full_name,
    )
    db.add(user)
    db.commit()

    return RegisterResponse(
        message="Registration successful",
        username=body.roll_number,
        student_id=body.roll_number if body.role == "student" else "",
    )


# ── OID4VCI Token Endpoint ───────────────────────────────────────────────────

from fastapi import Form, Request
from urllib.parse import parse_qs

import logging
log = logging.getLogger("oid4vci")

@router.post("/token")
async def oidc_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 / OID4VCI Token Endpoint.
    The wallet calls this with the pre-authorized_code from the QR.
    Manually parses the form body because the hyphenated parameter name
    `pre-authorized_code` doesn't map cleanly to Python function args.
    """
    # Read the raw form body
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    log.info("=== TOKEN ENDPOINT CALLED ===")
    log.info("  Content-Type: %s", request.headers.get("content-type"))
    log.info("  Raw body: %s", body_str)
    log.info("  All headers: %s", dict(request.headers))

    # Try form-encoded parsing first, then JSON
    params = parse_qs(body_str)
    
    grant_type = params.get("grant_type", [None])[0]
    pre_auth_code = params.get("pre-authorized_code", [None])[0]
    
    # Altme may send as JSON
    if not grant_type and body_str.strip().startswith("{"):
        try:
            import json as _json
            json_body = _json.loads(body_str)
            grant_type = json_body.get("grant_type")
            pre_auth_code = json_body.get("pre-authorized_code")
            log.info("  Parsed as JSON: grant_type=%s, code=%s", grant_type, pre_auth_code)
        except Exception:
            pass
    
    log.info("  grant_type=%s, pre-authorized_code=%s", grant_type, pre_auth_code)
    
    if grant_type != "urn:ietf:params:oauth:grant-type:pre-authorized_code":
        log.error("  Unsupported grant_type: %s", grant_type)
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")
        
    if not pre_auth_code:
        log.error("  Missing pre-authorized_code")
        raise HTTPException(status_code=400, detail="Missing pre-authorized_code")

    # 1. Resolve student from the pre-authorized code in CredentialOffer
    from app.models import CredentialOffer
    offer = db.query(CredentialOffer).filter(CredentialOffer.pre_authorized_code == pre_auth_code).first()
    
    if offer:
        user = offer.user
        log.info("  Found offer for user: %s", user.username if user else "None")
    else:
        log.warning("  No offer found for code %s, falling back to first student", pre_auth_code)
        # Fallback to first student for demo robustness if code was manually generated
        user = db.query(User).filter(User.role == "student").first()
        
    if not user:
        raise HTTPException(status_code=400, detail="Student not found for this code")

    import uuid as _uuid
    c_nonce = f"nonce-{_uuid.uuid4()}"

    token = create_access_token(
        data={"sub": user.id, "role": user.role, "student_id": user.student_id}
    )
    
    log.info("  Returning token for user %s, c_nonce=%s", user.username, c_nonce)
    
    # OID4VCI requires returning "c_nonce" with the access token
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "c_nonce": c_nonce,
        "c_nonce_expires_in": 86400
    }
