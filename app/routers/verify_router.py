"""Verify router — full verification flow (Parts 6a, 6b, 6c)."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from jose import jwt as jose_jwt

from app.auth import require_role
from app.crypto import (
    verify_credential,
    verify_presentation,
    generate_ec_key_pair,
    private_pem_to_jwk,
)
from app.database import get_db
from app.models import User, DIDDocument, VerificationSession
from app.schemas import (
    VerifyRequest,
    VerifyInitResponse,
    VerifyRespondRequest,
    VerifyRespondResponse,
    VerificationResultResponse,
)
from app.resolver import resolve_did, get_public_key_from_did_doc

router = APIRouter(tags=["Verification"])

CHALLENGE_EXPIRY_MINUTES = 30

# Verifier signing key — used to sign the OID4VP request object JWT
_verifier_public_jwk, _verifier_private_pem = generate_ec_key_pair()


# ── Part 6a: Verifier initiates verification (steps 1-10) ────────────────────


# ── Part 6a: Verifier initiates OID4VP request ──────────────────────────────

@router.post("/verify/init", response_model=dict)
async def initiate_verification(
    request: Request,
    current_user: User = Depends(require_role("verifier")),
    db: Session = Depends(get_db),
):
    """
    Verifier initiates an OID4VP request.
    Optionally targets a specific student by DID so the challenge appears on their dashboard.
    """
    from app.config import DID_DOMAIN
    
    # Read optional target student DID from body
    target_did = None
    try:
        body = await request.json()
        target_did = body.get("target_student_did")
    except Exception:
        pass  # No body or invalid JSON is fine
    
    verification_id = f"vrf_{uuid.uuid4().hex[:8]}"
    nonce = uuid.uuid4().hex
    state = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(minutes=CHALLENGE_EXPIRY_MINUTES)

    presentation_definition = {
        "id": verification_id,
        "format": {
            "jwt_vc_json": {
                "alg": ["ES256"]
            },
            "jwt_vp_json": {
                "alg": ["ES256"]
            }
        },
        "input_descriptors": [
            {
                "id": "iith_credential",
                "name": "IIT Hyderabad Credential",
                "purpose": "Verify your credential from IIT Hyderabad",
                "constraints": {
                    "fields": [
                        {
                            "path": ["$.vc.type[*]", "$.type[*]"],
                            "filter": {
                                "type": "string",
                                "pattern": "UniversityDegreeCredential$|InternshipCredential$|SkillBadgeCredential$"
                            }
                        }
                    ]
                }
            }
        ]
    }

    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL
    callback_url = f"{base_url}/api/verify/callback/{verification_id}"

    session = VerificationSession(
        verification_id=verification_id,
        verifier_id=current_user.id,
        target_did=target_did,
        nonce=nonce,
        status="PENDING",
        presentation_definition=presentation_definition,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    # Build OID4VP Request URI
    # With client_id_scheme "redirect_uri", client_id MUST equal response_uri
    import urllib.parse
    query = urllib.parse.urlencode({
        "client_id": callback_url,
        "request_uri": f"{base_url}/api/verify/request/{verification_id}"
    })
    
    request_uri = f"openid4vp://?{query}"
    
    print(f"[VERIFY] Created session {verification_id}, nonce={nonce}")
    print(f"[VERIFY] QR: {request_uri}")
    
    return {
        "verification_id": verification_id,
        "nonce": nonce,
        "state": state,
        "request_uri": request_uri,
        "qr_content": request_uri,
        "expires_at": expires_at
    }

@router.get("/api/verify/request/{verification_id}")
async def get_oid4vp_request_file(verification_id: str, db: Session = Depends(get_db)):
    """Serves the OID4VP authorization request object as a signed JWT.

    Wallets (e.g. Altme) fetch this URL and expect a JWT that they decode
    with JWTDecode().parseJwt() — returning plain JSON would fail.
    """
    session = db.query(VerificationSession).filter(VerificationSession.verification_id == verification_id).first()
    if not session:
        raise HTTPException(status_code=404)
    
    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL
    callback_url = f"{base_url}/api/verify/callback/{verification_id}"
    
    request_object = {
        "client_id": callback_url,
        "client_id_scheme": "redirect_uri",
        "response_uri": callback_url,
        "response_type": "vp_token",
        "response_mode": "direct_post",
        "state": uuid.uuid4().hex,
        "nonce": session.nonce,
        "presentation_definition": session.presentation_definition
    }
    
    print(f"[VERIFY] Serving JWT request object for {verification_id}")
    
    # Sign the request object as a JWT (ES256)
    private_jwk = private_pem_to_jwk(_verifier_private_pem)
    request_jwt = jose_jwt.encode(
        request_object,
        private_jwk,
        algorithm="ES256",
        headers={"typ": "oauth-authz-req+jwt", "kid": "verifier-key-1"},
    )
    
    return Response(
        content=request_jwt,
        media_type="application/oauth-authz-req+jwt",
    )


# ── Part 6b: Wallet POSTs VP to Callback ─────────────────────────────────────


@router.post("/api/verify/callback/{verification_id}")
async def verify_callback(
    verification_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for the wallet to POST the Verifiable Presentation.
    """
    session = db.query(VerificationSession).filter(VerificationSession.verification_id == verification_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.status != "PENDING":
        return {"status": "error", "message": "Session already processed"}

    # Handle both multipart/form-data and application/json
    try:
        content_type = request.headers.get("content-type", "")
        print(f"[VERIFY] Content-Type: {content_type}")
        print(f"[VERIFY] Headers: {dict(request.headers)}")
        
        raw_body = await request.body()
        print(f"[VERIFY] Raw body ({len(raw_body)} bytes): {raw_body[:500]}")
        
        if "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            vp_jwt = form_data.get("vp_token")
            if not vp_jwt: vp_jwt = form_data.get("presentation")
            presentation_submission = form_data.get("presentation_submission")
            state = form_data.get("state")
            print(f"[VERIFY] Form fields: vp_token={'present' if vp_jwt else 'missing'}, state={state}")
        else:
            import json as _json
            body = _json.loads(raw_body) if raw_body else {}
            vp_jwt = body.get("vp_token") or body.get("vp") or body.get("presentation")
            print(f"[VERIFY] JSON body keys: {list(body.keys())}")
    except Exception as e:
        print(f"[VERIFY] Error reading body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not vp_jwt:
        raise HTTPException(status_code=400, detail="Missing VP token")

    print(f"[VERIFY] Received VP for session {verification_id}")

    # Helper for robust B64 decode
    def b64_decode(data: str) -> dict:
        import json, base64
        padded = data + "=" * ((4 - len(data) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))

    # 1. Decode VP to find Holder DID
    try:
        parts = vp_jwt.split(".")
        payload = b64_decode(parts[1])
        header = b64_decode(parts[0])
        
        holder_did = payload.get("iss") or payload.get("sub")
        print(f"[VERIFY] Holder DID: {holder_did}")
        
        # 2. Resolve Holder DID to get Public Key
        from app.resolver import resolve_did, get_public_key_from_did_doc
        holder_pk = None
        try:
            holder_doc = resolve_did(holder_did)
            holder_pk = get_public_key_from_did_doc(holder_doc, holder_did)
        except Exception as e:
            print(f"[VERIFY] DID Resolution failed for {holder_did}: {e}")

        # 3. Verify VP Signature (Holder check)
        if holder_pk:
            from app.crypto import verify_presentation
            try:
                verify_presentation(vp_jwt, holder_pk)
                print(f"[VERIFY] ✅ VP Signature Valid")
            except Exception as e:
                print(f"[VERIFY] VP Signature Invalid: {e}")

        # 4. Extract and Verify the nested VC (Issuer check)
        # Altme/OID4VP standard: the VP JWT contains 'vp' -> 'verifiableCredential'
        vp_obj = payload.get("vp", {})
        vcs = vp_obj.get("verifiableCredential", [])
        if not vcs:
            vcs = payload.get("verifiableCredential", []) # backup
        
        if not vcs:
            raise HTTPException(status_code=400, detail="No VC found in VP presentation")
            
        vc_jwt = vcs[0] if isinstance(vcs, list) else vcs
        
        # Verify VC Issuer signature
        from app.crypto import verify_credential
        vc_parts = vc_jwt.split(".")
        vc_payload = b64_decode(vc_parts[1])
        issuer_did = vc_payload.get("iss")
        
        issuer_doc = resolve_did(issuer_did)
        issuer_pk = get_public_key_from_did_doc(issuer_doc, issuer_did)
        
        verify_credential(vc_jwt, issuer_pk)
        print(f"[VERIFY] ✅ VC Signature Valid from {issuer_did}")

        # Success! Capture the subject data
        session.status = "VERIFIED"
        session.holder_did = holder_did
        session.vp_jwt = vp_jwt
        session.vc_jwt = vc_jwt
        session.verified_at = datetime.utcnow()
        db.commit()
        
        return {"status": "ok"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[VERIFY] ❌ Final error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Part 6c: Verifier checks status (Polling) ────────────────────────────────

@router.get("/verifications/{verification_id}")
def check_verification(
    verification_id: str,
    db: Session = Depends(get_db),
):
    """
    Verifier checks the result of a verification session.
    """
    session = db.query(VerificationSession).filter(VerificationSession.verification_id == verification_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    result = {
        "status": session.status.lower(),
        "is_verified": session.status == "VERIFIED",
    }
    
    if session.status == "VERIFIED" and session.vc_jwt:
        import json, base64
        try:
            parts = session.vc_jwt.split(".")
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
            vc_data = payload.get("vc", {})
            subject = vc_data.get("credentialSubject", {})
            
            # Find the actual degree/internship info
            summary = "Verified Credential"
            vc_type_str = vc_data.get("type", ["VerifiableCredential"])[-1]
            if vc_type_str == "UniversityDegreeCredential":
                branch = subject.get("branch", "")
                summary = f"{subject.get('degree', 'N/A')}{' — ' + branch if branch else ''} ({subject.get('graduation_year', 'N/A')})"
            elif vc_type_str == "InternshipCredential":
                summary = f"{subject.get('company', subject.get('internship', {}).get('company', 'N/A'))} — {subject.get('role', subject.get('internship', {}).get('role', ''))}"
            elif vc_type_str == "SkillBadgeCredential":
                summary = f"{subject.get('skill_name', subject.get('skill', {}).get('name', 'N/A'))} ({subject.get('proficiency', subject.get('skill', {}).get('level', ''))})"
            else:
                summary = vc_type_str
            
            result["data"] = {
                "holder_did": session.holder_did,
                "summary": summary,
                "vc_type": vc_data.get("type", ["VerifiableCredential"])[-1],
                "issuer": vc_data.get("issuer"),
                "subject_data": subject
            }
        except Exception as e:
            print(f"[VERIFY] Result decode error: {e}")
            
    return result


# ── Verifier: List all sessions ───────────────────────────────────────────────


@router.get("/verifier/sessions")
def list_verifier_sessions(
    current_user: User = Depends(require_role("verifier")),
    db: Session = Depends(get_db),
):
    """List all verification sessions for the logged-in verifier."""
    import json, base64

    sessions = (
        db.query(VerificationSession)
        .filter(VerificationSession.verifier_id == current_user.id)
        .order_by(VerificationSession.created_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        summary = "Pending"
        student_name = "Unknown"
        
        if s.status == "VERIFIED" and s.vc_jwt:
            try:
                parts = s.vc_jwt.split(".")
                payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
                vc_data = payload.get("vc", {})
                subject = vc_data.get("credentialSubject", {})
                student_name = subject.get("student_name") or subject.get("name") or s.holder_did.split(":")[-1]
                vc_type_str = vc_data.get("type", ["VC"])[-1]
                if vc_type_str == "UniversityDegreeCredential":
                    branch = subject.get("branch", "")
                    summary = f"{subject.get('degree', 'N/A')}{' — ' + branch if branch else ''} ({subject.get('graduation_year', 'N/A')})"
                elif vc_type_str == "InternshipCredential":
                    summary = f"{subject.get('company', subject.get('internship', {}).get('company', 'N/A'))} — {subject.get('role', subject.get('internship', {}).get('role', ''))}"
                elif vc_type_str == "SkillBadgeCredential":
                    summary = f"{subject.get('skill_name', subject.get('skill', {}).get('name', 'N/A'))} ({subject.get('proficiency', subject.get('skill', {}).get('level', ''))})"
                else:
                    summary = vc_type_str
            except Exception:
                summary = "Verified Credential"

        result.append({
            "verification_id": s.verification_id,
            "student_name": student_name,
            "holder_did": s.holder_did,
            "summary": summary,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "verified_at": s.verified_at.isoformat() if s.verified_at else None,
        })
    return result
