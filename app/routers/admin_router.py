"""Admin router — credential issuance."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_role
from app.crypto import generate_ec_key_pair, sign_credential, private_pem_to_jwk
from app.database import get_db
from app.models import User, DIDDocument, VerifiableCredential
from app.schemas import IssueVCRequest, IssueVCResponse
from app.config import DID_DOMAIN

router = APIRouter(prefix="/admin", tags=["Admin"])

# ── Issuer key management ────────────────────────────────────────────────────
# Key is persisted to disk so it survives uvicorn --reload and server restarts.
# Without this, every reload rotates the key and all issued VCs become unverifiable.

import os, json as _json, base64, logging

log = logging.getLogger("oid4vci")

_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "issuer_key.pem")
_JWK_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "issuer_key.jwk")

def _load_or_create_issuer_key():
    pem_b64 = os.environ.get("ISSUER_PRIVATE_KEY_B64")
    jwk_env = os.environ.get("ISSUER_PUBLIC_JWK")
    if pem_b64 and jwk_env:
        private_pem = base64.b64decode(pem_b64).decode()
        public_jwk = _json.loads(jwk_env)
        log.info("[ISSUER] Loaded issuer key from environment variables")
        return public_jwk, private_pem
    if bool(pem_b64) != bool(jwk_env):
        # One env var set without the other — misconfiguration, not a silent fallthrough
        missing = "ISSUER_PUBLIC_JWK" if pem_b64 else "ISSUER_PRIVATE_KEY_B64"
        log.warning("[ISSUER] %s is set but %s is missing — falling back to disk key",
                    "ISSUER_PRIVATE_KEY_B64" if pem_b64 else "ISSUER_PUBLIC_JWK", missing)

    key_file = os.path.abspath(_KEY_FILE)
    jwk_file = os.path.abspath(_JWK_FILE)
    if os.path.exists(key_file) and os.path.exists(jwk_file):
        with open(key_file, "r") as f:
            private_pem = f.read()
        with open(jwk_file, "r") as f:
            public_jwk = _json.load(f)
        log.info("[ISSUER] Loaded persistent issuer key from %s", key_file)
        return public_jwk, private_pem
    public_jwk, private_pem = generate_ec_key_pair()
    with open(key_file, "w") as f:
        f.write(private_pem)
    with open(jwk_file, "w") as f:
        _json.dump(public_jwk, f)
    log.info("[ISSUER] Generated and persisted new issuer key to %s", key_file)
    return public_jwk, private_pem

_issuer_public_jwk, _issuer_private_pem = _load_or_create_issuer_key()

ISSUER_DID = f"did:web:{DID_DOMAIN}:issuer"


def get_issuer_public_jwk() -> dict:
    """Return the issuer's public key (used by verify_router to check VCs)."""
    return _issuer_public_jwk


def get_issuer_did() -> str:
    return ISSUER_DID

from app.models import CredentialOffer, KeyHistory


@router.post("/issue-vc")
def admin_issue_vc_prepare(
    body: IssueVCRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Admin creates a credential offer for a student.
    The VC is NOT signed here — it will be signed and holder-bound when the
    student's wallet (e.g. Altme) claims it via the OID4VCI credential endpoint.
    The wallet's public key will be used to update the student's DID document,
    making the credential holder-bound.
    """
    import time

    # 1. Resolve student
    did_uri = body.student_did
    did_doc = db.query(DIDDocument).filter(DIDDocument.did_uri == did_uri).first()
    if not did_doc:
        user = db.query(User).filter(User.username == did_uri).first()
        if not user:
            raise HTTPException(status_code=404, detail="Student not found")
    else:
        user = did_doc.user

    # 2. Build credential details to store in the offer
    details = {}
    if body.vc_type == "UniversityDegreeCredential":
        details = {
            "degree":          body.degree or "B.Tech",
            "branch":          body.branch or "",
            "specialization":  body.specialization or "",
            "cgpa":            body.cgpa or "",
            "graduation_year": body.graduation_year or body.year or 2025,
            "honours":         body.honours or "",
        }
    elif body.vc_type == "InternshipCredential":
        details = {"company": body.company, "role": body.role, "duration": body.duration}
    elif body.vc_type == "SkillBadgeCredential":
        details = {"skill_name": body.skill_name, "proficiency": body.proficiency}

    # 3. Create CredentialOffer only — NO VC signing yet.
    #    The VC will be signed when the wallet claims via POST /admin/issue,
    #    and the student's DID doc will be updated with the wallet's public key.
    pre_auth_code = f"demo-{int(time.time())}-{uuid.uuid4().hex[:4]}"
    offer = CredentialOffer(
        user_id=user.id, vc_type=body.vc_type,
        offer_details=details, pre_authorized_code=pre_auth_code,
    )
    db.add(offer)
    db.commit()

    # Build the complete OID4VCI offer URL so the frontend / wallet can use it
    from app.config import PUBLIC_BASE_URL
    from urllib.parse import quote
    import json
    credential_offer_obj = {
        "credential_issuer": PUBLIC_BASE_URL,
        "credential_configuration_ids": [body.vc_type],  # OID4VCI Draft 13
        "credentials": [body.vc_type],                   # Draft 11/12 compat (older Altme)
        "grants": {
            "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                "pre-authorized_code": pre_auth_code,
            }
        },
    }
    offer_url = (
        "openid-credential-offer://?credential_offer="
        + quote(json.dumps(credential_offer_obj))
    )

    return {
        "pre_authorized_code": pre_auth_code,
        "offer_url": offer_url,
        "status": "OFFERED",
        "message": "Credential offer created. Student should scan QR with wallet (e.g. Altme) to claim.",
    }


from typing import Any
from fastapi import Request
import traceback


@router.post("/issue")
async def wallet_issue_credential(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    OID4VCI Credential Endpoint — called by the wallet (e.g. Altme) after
    scanning the credential offer QR code.

    The wallet provides:
      - Bearer token (obtained by exchanging the pre-authorized code)
      - Proof of possession (JWT whose *header* carries the wallet's public key)

    This endpoint:
      1. Extracts the wallet's public key from the proof JWT header
      2. Creates / updates the student's DID document with the wallet key
         → this makes the credential **holder-bound**
      3. Signs the VC (issuer key) with the student's DID as subject
      4. Stores the VC and marks the offer as CLAIMED
      5. Returns the signed VC JWT to the wallet
    """
    try:
        log.info("=== CREDENTIAL ENDPOINT CALLED ===")
        # ── 1. Verify the wallet's bearer token ──────────────────────────
        auth_header = request.headers.get("Authorization")
        log.info("  Authorization header present: %s", bool(auth_header))
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = auth_header.split(" ")[1]
        from app.auth import decode_token
        payload = decode_token(token)
        log.info("  Token payload: %s", payload)

        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token user")
        log.info("  User: %s (id=%s, student_id=%s)", user.username, user.id, user.student_id)

        # ── 2. Find the most recent pending offer for this student ───────
        offer = db.query(CredentialOffer).filter(
            CredentialOffer.user_id == user.id,
            CredentialOffer.status == "OFFERED"
        ).order_by(CredentialOffer.created_at.desc()).first()

        if not offer:
            log.error("  No pending offer found for user %s", user.id)
            raise HTTPException(
                status_code=400,
                detail="No pending credential offer found for this student",
            )
        log.info("  Found offer: type=%s, code=%s", offer.vc_type, offer.pre_authorized_code)

        details = offer.offer_details
        vc_type = offer.vc_type

        # ── 3. Extract wallet public key from proof JWT ──────────────────
        body = await request.json()
        log.info("  Request body keys: %s", list(body.keys()))
        log.info("  Full request body: %s", body)
        proof = body.get("proof", {})
        jwt_proof = proof.get("jwt") if isinstance(proof, dict) else None
        log.info("  Proof present: %s, JWT proof present: %s", bool(proof), bool(jwt_proof))

        wallet_jwk = None
        wallet_did_from_proof = None
        if jwt_proof:
            import json as json_mod, base64
            try:
                parts = jwt_proof.split(".")
                # Decode header → contains the wallet's public key as JWK
                hdr_b64 = parts[0] + "=" * ((4 - len(parts[0]) % 4) % 4)
                header = json_mod.loads(base64.urlsafe_b64decode(hdr_b64))
                log.info("  Proof JWT header: %s", header)

                wallet_jwk = header.get("jwk")

                # Altme (and many wallets) use "kid" with a did:jwk: URI
                # instead of putting the JWK directly in the header.
                # Extract the JWK from the did:jwk: URI if present.
                if not wallet_jwk and header.get("kid", "").startswith("did:jwk:"):
                    kid = header["kid"]
                    # did:jwk:<base64url-encoded-JWK>#0
                    jwk_b64 = kid.split("did:jwk:")[1].split("#")[0]
                    jwk_b64 += "=" * ((4 - len(jwk_b64) % 4) % 4)
                    wallet_jwk = json_mod.loads(base64.urlsafe_b64decode(jwk_b64))
                    log.info("  Extracted JWK from did:jwk kid: %s", wallet_jwk)

                # Paradyme (and others) use did:key: format (P-256 compressed)
                if not wallet_jwk and header.get("kid", "").startswith("did:key:"):
                    from app.crypto import resolve_did_key_to_jwk
                    kid = header["kid"]
                    wallet_jwk = resolve_did_key_to_jwk(kid)
                    log.info("  Extracted JWK from did:key kid: %s", wallet_jwk)

                # Decode payload → may contain wallet DID as "iss"
                pay_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                proof_payload = json_mod.loads(base64.urlsafe_b64decode(pay_b64))
                wallet_did_from_proof = proof_payload.get("iss")

                log.info("  Wallet proof received — JWK present: %s, wallet DID: %s",
                         wallet_jwk is not None, wallet_did_from_proof)
            except Exception as exc:
                log.error("  Error decoding proof JWT: %s", exc)
                import traceback as _tb
                _tb.print_exc()

        if not wallet_jwk:
            # Fallback: if the student already has a DID with a key, reuse it
            existing = db.query(DIDDocument).filter(
                DIDDocument.user_id == user.id
            ).first()
            if existing and existing.public_key_jwk:
                wallet_jwk = existing.public_key_jwk
                print("[CREDENTIAL] No JWK in proof — reusing existing DID key")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Wallet must provide a proof JWT with its public key (jwk in header)",
                )

        # ── 4. Create / update the student's DID document ────────────────
        #    The DID document's verification key is set to the WALLET's public
        #    key, so only the wallet can prove holder-binding later.
        did_uri = f"did:web:{DID_DOMAIN}:students:{user.student_id}"
        did = db.query(DIDDocument).filter(
            DIDDocument.user_id == user.id
        ).first()

        new_key_version = 1
        if did:
            new_key_version = did.key_version or 1
            # If the wallet key differs from the current key → rotate
            if did.public_key_jwk != wallet_jwk:
                old_key_id = f"{did.did_uri}#key-{did.key_version or 1}"
                history_entry = KeyHistory(
                    did_id=did.id,
                    public_key_jwk=did.public_key_jwk,
                    key_id=old_key_id,
                )
                db.add(history_entry)
                new_key_version = (did.key_version or 1) + 1
                print(f"[CREDENTIAL] Rotating DID key for {did_uri} "
                      f"(v{did.key_version} → v{new_key_version})")

        key_id = f"{did_uri}#key-{new_key_version}"
        did_document = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": did_uri,
            "verificationMethod": [
                {
                    "id": key_id,
                    "type": "JsonWebKey2020",
                    "controller": did_uri,
                    "publicKeyJwk": wallet_jwk,
                }
            ],
            "authentication": [key_id],
        }

        if did:
            did.public_key_jwk = wallet_jwk
            did.did_document = did_document
            did.key_version = new_key_version
            print(f"[CREDENTIAL] ✅ Updated DID doc for {did_uri} with wallet key (v{new_key_version})")
        else:
            did = DIDDocument(
                did_uri=did_uri,
                user_id=user.id,
                public_key_jwk=wallet_jwk,
                did_document=did_document,
                key_version=1,
            )
            db.add(did)
            db.flush()
            print(f"[CREDENTIAL] ✅ Created DID doc for {did_uri} with wallet key")

        # ── 5. Build & sign the VC (issuer signs, subject = student DID) ─
        vc_id = f"vc_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        subject = {"id": did_uri}

        if vc_type == "UniversityDegreeCredential":
            subject["student_name"]    = user.full_name or user.username
            subject["student_id"]      = user.student_id or ""
            subject["degree"]          = details.get("degree", "B.Tech")
            subject["branch"]          = details.get("branch", "")
            subject["specialization"]  = details.get("specialization", "")
            subject["cgpa"]            = details.get("cgpa", "")
            subject["graduation_year"] = details.get("graduation_year", 2025)
            subject["honours"]         = details.get("honours", "")
            subject["issued_on"]       = now.strftime("%Y-%m-%d")
        elif vc_type == "InternshipCredential":
            subject["student_name"] = user.full_name or user.username
            subject["student_id"]   = user.student_id or ""
            subject["company"]      = details.get("company", "")
            subject["role"]         = details.get("role", "")
            subject["duration"]     = details.get("duration", "")
            subject["issued_on"]    = now.strftime("%Y-%m-%d")
        elif vc_type == "SkillBadgeCredential":
            subject["student_name"] = user.full_name or user.username
            subject["student_id"]   = user.student_id or ""
            subject["skill_name"]   = details.get("skill_name", "")
            subject["proficiency"]  = details.get("proficiency", "")
            subject["issued_on"]    = now.strftime("%Y-%m-%d")

        vc_payload = {
            "iss": ISSUER_DID,
            "sub": did_uri,
            "vc": {
                "@context": ["https://www.w3.org/2018/credentials/v1"],
                "id": vc_id,
                "type": ["VerifiableCredential", vc_type],
                "issuer": ISSUER_DID,
                "issuanceDate": now.isoformat() + "Z",
                "credentialSubject": subject,
            },
        }
        vc_jwt = sign_credential(vc_payload, _issuer_private_pem)

        # ── 6. Persist VC and mark offer as claimed ──────────────────────
        vc_record = VerifiableCredential(
            vc_id=vc_id,
            did_id=did.id,
            vc_type=vc_type,
            vc_jwt=vc_jwt,
            issued_at=now,
        )
        db.add(vc_record)
        offer.status = "CLAIMED"
        db.commit()

        print(f"[CREDENTIAL] ✅ Issued {vc_type} ({vc_id}) to {user.student_id}, "
              f"holder-bound to wallet key")

        return {
            "format": "jwt_vc_json",
            "credential": vc_jwt,
            "c_nonce": str(uuid.uuid4()),
            "c_nonce_expires_in": 86400,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREDENTIAL ERROR] ❌ {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issuer/did.json")
def get_issuer_did_document():
    """Public endpoint to get the issuer's DID document (for VC verification)."""
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": ISSUER_DID,
        "verificationMethod": [
            {
                "id": f"{ISSUER_DID}#key-1",
                "type": "JsonWebKey2020",
                "controller": ISSUER_DID,
                "publicKeyJwk": _issuer_public_jwk,
            }
        ],
        "authentication": [f"{ISSUER_DID}#key-1"],
    }


# ── Admin: Student management ────────────────────────────────────────────────


@router.get("/students")
def list_students(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all registered students with their DID and VC status."""
    students = db.query(User).filter(User.role == "student").all()
    result = []
    for s in students:
        did = db.query(DIDDocument).filter(DIDDocument.user_id == s.id).first()
        vc_count = 0
        if did:
            vc_count = db.query(VerifiableCredential).filter(VerifiableCredential.did_id == did.id).count()
        result.append({
            "username": s.username,
            "student_id": s.student_id,
            "full_name": s.full_name or s.username,
            "has_did": did is not None,
            "did_uri": did.did_uri if did else None,
            "vc_count": vc_count,
        })
    return result


@router.get("/issued-vcs")
def list_issued_vcs(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all issued VCs and pending offers."""
    import json, base64

    # 1. Get already issued VCs
    vcs = db.query(VerifiableCredential).order_by(VerifiableCredential.issued_at.desc()).all()
    result = []
    for vc in vcs:
        did_doc = db.query(DIDDocument).filter(DIDDocument.id == vc.did_id).first()
        student_name, student_id, student_did = "", "", ""
        if did_doc:
            student_did = did_doc.did_uri
            if did_doc.user:
                student_name = did_doc.user.full_name or did_doc.user.username
                student_id = did_doc.user.student_id or ""

        # Decode summary
        summary = ""
        try:
            parts = vc.vc_jwt.split(".")
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
            cs = payload.get("vc", {}).get("credentialSubject", {})
            if vc.vc_type == "UniversityDegreeCredential":
                branch = cs.get('branch', '')
                summary = f"{cs.get('degree', 'N/A')}{' — ' + branch if branch else ''} ({cs.get('graduation_year', 'N/A')})"
            elif vc.vc_type == "InternshipCredential":
                summary = f"{cs.get('company', 'N/A')} — {cs.get('role', 'N/A')} ({cs.get('duration', 'N/A')})"
            elif vc.vc_type == "SkillBadgeCredential":
                summary = f"{cs.get('skill_name', 'N/A')} — {cs.get('proficiency', 'N/A')}"
        except Exception: summary = "OID4VCI Issued"

        result.append({
            "vc_id": vc.vc_id,
            "student_name": student_name,
            "student_id": student_id,
            "student_did": student_did,
            "summary": summary,
            "vc_type": vc.vc_type,
            "status": "ISSUED",
            "issued_at": vc.issued_at.isoformat() if vc.issued_at else None,
        })

    # 2. Get pending offers
    offers = db.query(CredentialOffer).filter(CredentialOffer.status == "OFFERED").all()
    for o in offers:
        summary = ""
        if o.vc_type == "UniversityDegreeCredential":
            summary = f"{o.offer_details.get('degree', 'N/A')} — {o.offer_details.get('branch', '')} ({o.offer_details.get('graduation_year') or o.offer_details.get('year', 'N/A')})".strip(' —')
        elif o.vc_type == "InternshipCredential":
            summary = f"{o.offer_details.get('company', 'N/A')}"
        
        result.append({
            "vc_id": f"offer_{o.id[:8]}",
            "student_name": o.user.full_name or o.user.username,
            "student_id": o.user.student_id or "",
            "student_did": "Pending Claim",
            "summary": summary,
            "vc_type": o.vc_type,
            "status": "PENDING",
            "issued_at": o.created_at.isoformat(),
        })

    # Sort all by date desc
    result.sort(key=lambda x: x["issued_at"], reverse=True)
    return result

@router.get("/vcs/{id_val}")
def get_admin_vc_detail(
    id_val: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get detail for previewing a VC or offer."""
    import json, base64

    # Case 1: Pending Offer
    if id_val.startswith("offer_"):
        # We need to find by some internal ID, let's look for a substring match
        offer = db.query(CredentialOffer).all()
        target = next((o for o in offer if o.id.startswith(id_val.replace("offer_",""))), None)
        if not target: raise HTTPException(status_code=404)
        
        od = target.offer_details
        return {
            "status": "PENDING",
            "certificate": {
                "vc_id": id_val,
                "student_name": target.user.full_name or target.user.username,
                "student_id": target.user.student_id or "",
                "student_did": "Pending claim...",
                "degree": od.get("degree", ""),
                "degree_name": od.get("degree", ""),
                "graduation_year": od.get("graduation_year") or od.get("year", ""),
                "year": od.get("graduation_year") or od.get("year", ""),
                "branch": od.get("branch", ""),
                "specialization": od.get("specialization", ""),
                "cgpa": od.get("cgpa", ""),
                "honours": od.get("honours", ""),
                "company": od.get("company", ""),
                "role": od.get("role", ""),
                "duration": od.get("duration", ""),
                "skill_name": od.get("skill_name", ""),
                "proficiency": od.get("proficiency", ""),
                "vc_type": target.vc_type,
                "issuance_date": target.created_at.isoformat() + "Z",
            }
        }

    # Case 2: Issued VC
    vc = db.query(VerifiableCredential).filter(VerifiableCredential.vc_id == id_val).first()
    if not vc: raise HTTPException(status_code=404)

    # Decode payload
    parts = vc.vc_jwt.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
    vc_data = payload.get("vc", {})
    cs = vc_data.get("credentialSubject", {})
    
    student_name = ""
    if vc.did and vc.did.user:
        student_name = vc.did.user.full_name or vc.did.user.username

    return {
        "status": "ISSUED",
        "verifiable_credential": vc.vc_jwt,
        "certificate": {
            "vc_id": vc.vc_id,
            "student_name": student_name,
            "student_id": vc.did.user.student_id if (vc.did and vc.did.user) else "",
            "student_did": vc.did.did_uri if vc.did else "",
            # degree / graduation_year are flat strings in the credentialSubject
            "degree": cs.get("degree", ""),
            "degree_name": cs.get("degree", ""),
            "graduation_year": cs.get("graduation_year", ""),
            "year": cs.get("graduation_year", ""),
            "branch": cs.get("branch", ""),
            "specialization": cs.get("specialization", ""),
            "cgpa": cs.get("cgpa", ""),
            "honours": cs.get("honours", ""),
            "company": cs.get("company", ""),
            "role": cs.get("role", ""),
            "duration": cs.get("duration", ""),
            "skill_name": cs.get("skill_name", ""),
            "proficiency": cs.get("proficiency", ""),
            "issued_on": cs.get("issued_on", ""),
            "vc_type": vc.vc_type,
            "issuance_date": vc_data.get("issuanceDate", ""),
        }
    }

