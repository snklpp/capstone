"""Student router — DID creation, VC listing, challenges, VP response."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_role
from app.crypto import generate_ec_key_pair
from app.database import get_db
from app.models import User, DIDDocument, VerifiableCredential, VerificationSession, KeyHistory
from app.schemas import (
    DIDCreateRequest,
    DIDCreateResponse,
    KeyRotateResponse,
    VCListItem,
    VCDetailResponse,
    ChallengeItem,
)
from app.config import DID_DOMAIN

router = APIRouter(prefix="/students", tags=["Students"])


# ── Part 1: DID Creation (steps 5-10) ────────────────────────────────────────


@router.post("/did", response_model=DIDCreateResponse)
def create_did(
    body: DIDCreateRequest,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Create a DID for the authenticated student (manual path).

    NOTE: In the primary wallet-based flow, the DID is created automatically
    when the student's wallet (e.g. Altme) claims a credential offer via
    the OID4VCI endpoint.  This manual endpoint is kept for advanced use.
    """
    # Check if student already has a DID
    existing = db.query(DIDDocument).filter(DIDDocument.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DID already exists: {existing.did_uri}",
        )

    if not current_user.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a student_id assigned",
        )

    # Construct the DID URI
    did_uri = f"did:web:{DID_DOMAIN}:students:{current_user.student_id}"

    # Build the W3C DID Document
    did_document = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did_uri,
        "verificationMethod": [
            {
                "id": f"{did_uri}#key-1",
                "type": "JsonWebKey2020",
                "controller": did_uri,
                "publicKeyJwk": body.public_key_jwk,
            }
        ],
        "authentication": [f"{did_uri}#key-1"],
    }

    did_doc = DIDDocument(
        did_uri=did_uri,
        user_id=current_user.id,
        public_key_jwk=body.public_key_jwk,
        did_document=did_document,
    )
    db.add(did_doc)
    db.commit()

    return DIDCreateResponse(did=did_uri)


# ── Key Rotation ──────────────────────────────────────────────────────────


class KeyRotateRequest(BaseModel):
    new_public_key_jwk: dict[str, Any]

@router.post("/did/rotate-key", response_model=KeyRotateResponse)
def rotate_key(
    body: KeyRotateRequest,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Rotate the student's DID key pair.

    In the decentralized model, the wallet generates a new key pair and
    sends the new public key here. The server archives the old public key,
    updates the DID document with the new key, and increments the version.
    """
    did = db.query(DIDDocument).filter(DIDDocument.user_id == current_user.id).first()
    if not did:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No DID found. Create a DID first.",
        )

    # Archive the current key
    old_key_version = did.key_version or 1
    old_key_id = f"{did.did_uri}#key-{old_key_version}"
    history_entry = KeyHistory(
        did_id=did.id,
        public_key_jwk=did.public_key_jwk,
        key_id=old_key_id,
    )
    db.add(history_entry)

    # The new public key comes from the wallet
    new_public_jwk = body.new_public_key_jwk

    # Increment version
    new_key_version = old_key_version + 1
    new_key_id = f"{did.did_uri}#key-{new_key_version}"

    # Rebuild DID Document
    did_document = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did.did_uri,
        "verificationMethod": [
            {
                "id": new_key_id,
                "type": "JsonWebKey2020",
                "controller": did.did_uri,
                "publicKeyJwk": new_public_jwk,
            }
        ],
        "authentication": [new_key_id],
    }

    # Update DIDDocument record
    did.public_key_jwk = new_public_jwk
    did.did_document = did_document
    did.key_version = new_key_version
    db.commit()

    return KeyRotateResponse(
        message="Key rotated successfully",
        new_key_id=new_key_id,
        previous_key_id=old_key_id,
    )


# ── Part 5: List VCs (steps 1-4) ─────────────────────────────────────────────


@router.get("/vcs")
def list_vcs(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """List all VCs and pending offers for the student.

    Credentials only exist in the DB *after* the wallet claims the offer via
    the OID4VCI credential endpoint.  Unclaimed offers are shown separately
    with a QR code for the wallet to scan.
    """
    from app.models import CredentialOffer
    from urllib.parse import quote
    import json

    result = []
    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL

    # 1. Claimed VCs (wallet already accepted these)
    did = db.query(DIDDocument).filter(
        DIDDocument.user_id == current_user.id
    ).first()
    if did:
        vcs = (
            db.query(VerifiableCredential)
            .filter(VerifiableCredential.did_id == did.id)
            .order_by(VerifiableCredential.issued_at.desc())
            .all()
        )
        for vc in vcs:
            details = {}
            try:
                import base64 as _b64, json as _json
                def _dec(s):
                    return _json.loads(_b64.urlsafe_b64decode(s + '==' ))
                pl = _dec(vc.vc_jwt.split('.')[1])
                cs = pl.get('vc', {}).get('credentialSubject', {})
                if vc.vc_type == 'UniversityDegreeCredential':
                    details = {
                        'student_name':    cs.get('student_name', ''),
                        'student_id':      cs.get('student_id', ''),
                        'degree':          cs.get('degree', ''),
                        'branch':          cs.get('branch', ''),
                        'specialization':  cs.get('specialization', ''),
                        'cgpa':            str(cs.get('cgpa', '')),
                        'graduation_year': str(cs.get('graduation_year', '')),
                        'honours':         cs.get('honours', ''),
                        'issued_on':       cs.get('issued_on', ''),
                    }
                elif vc.vc_type == 'InternshipCredential':
                    details = {
                        'student_name': cs.get('student_name', ''),
                        'company':  cs.get('company', ''),
                        'role':     cs.get('role', ''),
                        'duration': cs.get('duration', ''),
                        'issued_on': cs.get('issued_on', ''),
                    }
                elif vc.vc_type == 'SkillBadgeCredential':
                    details = {
                        'student_name': cs.get('student_name', ''),
                        'skill_name':  cs.get('skill_name', ''),
                        'proficiency': cs.get('proficiency', ''),
                        'issued_on':   cs.get('issued_on', ''),
                    }
            except Exception:
                pass
            result.append({
                "vc_id": vc.vc_id,
                "type": vc.vc_type,
                "issued_at": vc.issued_at,
                "status": "CLAIMED",
                "offer_url": None,
                "details": details,
            })

    # 2. Unclaimed offers (pending wallet scan)
    unclaimed = (
        db.query(CredentialOffer)
        .filter(
            CredentialOffer.user_id == current_user.id,
            CredentialOffer.status == "OFFERED",
        )
        .order_by(CredentialOffer.created_at.desc())
        .all()
    )
    for o in unclaimed:
        credential_offer_obj = {
            "credential_issuer": base_url,
            "credential_configuration_ids": [o.vc_type],
            "grants": {
                "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                    "pre-authorized_code": o.pre_authorized_code,
                }
            },
        }
        offer_url = (
            "openid-credential-offer://?credential_offer="
            + quote(json.dumps(credential_offer_obj))
        )
        od = o.offer_details or {}
        offer_details_out = {}
        if o.vc_type == 'UniversityDegreeCredential':
            offer_details_out = {
                'degree':          od.get('degree', ''),
                'branch':          od.get('branch', ''),
                'specialization':  od.get('specialization', ''),
                'cgpa':            str(od.get('cgpa', '')),
                'graduation_year': str(od.get('graduation_year', '') or od.get('year', '')),
                'honours':         od.get('honours', ''),
            }
        elif o.vc_type == 'InternshipCredential':
            offer_details_out = {'company': od.get('company', ''), 'role': od.get('role', ''), 'duration': od.get('duration', '')}
        elif o.vc_type == 'SkillBadgeCredential':
            offer_details_out = {'skill_name': od.get('skill_name', ''), 'proficiency': od.get('proficiency', '')}
        result.append({
            "vc_id": f"offer_{o.id[:8]}",
            "type": o.vc_type,
            "issued_at": o.created_at,
            "status": "PENDING",
            "offer_url": offer_url,
            "details": offer_details_out,
        })

    return result


# ── Part 5: Download specific VC (steps 5-7) ─────────────────────────────────


@router.get("/vcs/{vc_id}")
def get_vc(
    vc_id: str,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Download a specific Verifiable Credential with decoded certificate data.

    Flow (Part 5, steps 5-7):
    5. GET /students/vcs/{vc_id}
    6. Fetch VC from DB + verify ownership
    7. Return the signed VC JWT + decoded data for certificate display
    """
    did = db.query(DIDDocument).filter(DIDDocument.user_id == current_user.id).first()
    if not did:
        raise HTTPException(status_code=404, detail="No DID found.")

    vc = (
        db.query(VerifiableCredential)
        .filter(
            VerifiableCredential.vc_id == vc_id,
            VerifiableCredential.did_id == did.id,
        )
        .first()
    )
    if not vc:
        raise HTTPException(status_code=404, detail="VC not found or access denied.")

    # Decode VC JWT payload for certificate display (no signature verification needed here)
    import json, base64
    parts = vc.vc_jwt.split(".")
    payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
    vc_payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    vc_data = vc_payload.get("vc", {})
    cred_subject = vc_data.get("credentialSubject", {})

    return {
        "verifiable_credential": vc.vc_jwt,
        "certificate": {
            "vc_id": vc.vc_id,
            "student_name": cred_subject.get("student_name", current_user.full_name or current_user.username),
            "student_id": cred_subject.get("student_id", current_user.student_id or ""),
            "student_did": cred_subject.get("id", ""),
            "degree": cred_subject.get("degree", ""),
            "branch": cred_subject.get("branch", ""),
            "specialization": cred_subject.get("specialization", ""),
            "cgpa": cred_subject.get("cgpa", ""),
            "graduation_year": cred_subject.get("graduation_year", ""),
            "honours": cred_subject.get("honours", ""),
            "company": cred_subject.get("company", ""),
            "role": cred_subject.get("role", ""),
            "duration": cred_subject.get("duration", ""),
            "skill_name": cred_subject.get("skill_name", ""),
            "proficiency": cred_subject.get("proficiency", ""),
            "issued_on": cred_subject.get("issued_on", ""),
            "issuer": vc_data.get("issuer", ""),
            "issuance_date": vc_data.get("issuanceDate", ""),
            "vc_type": vc_data.get("type", []),
        },
    }


# ── Part 6b: Get pending challenges (steps 1-3) ──────────────────────────────


@router.get("/challenges")
def get_challenges(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Get pending verification challenges for the student.
    Returns challenges targeted at this student's DID (or untargeted ones).
    Includes qr_content so the frontend can render the QR for wallet scanning.
    """
    from app.config import DID_DOMAIN
    from sqlalchemy import or_

    did = db.query(DIDDocument).filter(DIDDocument.user_id == current_user.id).first()
    if not did:
        return []

    # Find challenges targeted at this student OR untargeted (open to anyone)
    sessions = (
        db.query(VerificationSession)
        .filter(
            VerificationSession.status == "PENDING",
            or_(
                VerificationSession.target_did == did.did_uri,
                VerificationSession.target_did == None,
            )
        )
        .order_by(VerificationSession.created_at.desc())
        .all()
    )

    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL
    import urllib.parse
    result = []
    for s in sessions:
        query = urllib.parse.urlencode({
            "client_id": base_url,
            "request_uri": f"{base_url}/api/verify/request/{s.verification_id}"
        })
        qr_content = f"openid4vp://?{query}"

        result.append({
            "verification_id": s.verification_id,
            "nonce": s.nonce,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "qr_content": qr_content,
        })

    return result


# ── Part 6c: Verification History (student's perspective) ────────────────────


@router.get("/verification-history")
def get_verification_history(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """List all verification sessions where this student's credential was verified."""
    import json, base64

    did = db.query(DIDDocument).filter(DIDDocument.user_id == current_user.id).first()
    if not did:
        raise HTTPException(status_code=404, detail="No DID found.")

    sessions = (
        db.query(VerificationSession)
        .filter(VerificationSession.holder_did == did.did_uri)
        .order_by(VerificationSession.created_at.desc())
        .all()
    )

    result = []
    for s in sessions:
        # Resolve verifier info
        verifier = db.query(User).filter(User.id == s.verifier_id).first()
        verifier_name = verifier.full_name or verifier.username if verifier else "—"

        # Decode VC JWT for degree info
        degree_name = ""
        year = ""
        if s.vc_jwt:
            try:
                parts = s.vc_jwt.split(".")
                payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                vc_data = payload.get("vc", {})
                cs = vc_data.get("credentialSubject", {})
                deg = cs.get("degree", {})
                degree_name = deg.get("name", "")
                year = deg.get("year", "")
            except Exception:
                pass

        result.append({
            "verification_id": s.verification_id,
            "verifier_name": verifier_name,
            "degree_name": degree_name,
            "year": year,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "verified_at": s.verified_at.isoformat() if s.verified_at else None,
        })
    return result
