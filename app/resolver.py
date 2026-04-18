"""DID Resolver — resolves DID documents from memory / DB (no self-HTTP calls)."""

import json
import base64
from fastapi import HTTPException, status
from app.config import DID_DOMAIN

def resolve_did(did: str) -> dict:
    """Resolve a DID identifier to a DID Document.
    
    Supports:
      - did:web:*:issuer  (our issuer — always resolved locally)
      - did:web:*:students:* (our students — always resolved locally)
      - did:jwk:* (self-describing — JWK embedded in DID)
        
    Returns:
        The DID Document as a dictionary.
        
    Raises:
        HTTPException: If resolution fails.
    """
    # ── did:jwk: (self-describing, no network needed) ──────────────────
    if did.startswith("did:jwk:"):
        jwk_b64 = did.split("did:jwk:")[1].split("#")[0]
        jwk_b64 += "=" * ((4 - len(jwk_b64) % 4) % 4)
        try:
            jwk = json.loads(base64.urlsafe_b64decode(jwk_b64))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decode did:jwk: {e}"
            )
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": did.split("#")[0],
            "verificationMethod": [{
                "id": f"{did.split('#')[0]}#0",
                "type": "JsonWebKey2020",
                "controller": did.split("#")[0],
                "publicKeyJwk": jwk,
            }],
            "authentication": [f"{did.split('#')[0]}#0"],
        }

    # ── did:key: (compressed EC key, P-256) ────────────────────────────
    if did.startswith("did:key:"):
        from app.crypto import resolve_did_key_to_jwk
        try:
            jwk = resolve_did_key_to_jwk(did)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decode did:key: {e}"
            )
        did_base = did.split("#")[0]
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": did_base,
            "verificationMethod": [{
                "id": f"{did_base}#{did_base.split('did:key:')[1]}",
                "type": "JsonWebKey2020",
                "controller": did_base,
                "publicKeyJwk": jwk,
            }],
            "authentication": [f"{did_base}#{did_base.split('did:key:')[1]}"],
        }

    # ── did:web: (resolve from memory / DB — no HTTP self-call) ──────
    if not did.startswith("did:web:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported DID method: {did}"
        )
    
    parts = did.split(":")
    
    if len(parts) < 4:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid DID format: {did}"
        )
    
    path_components = parts[3:]
    
    if path_components[0] == "issuer":
        # Resolve issuer DID directly from in-memory key
        from app.routers.admin_router import get_issuer_public_jwk, get_issuer_did
        issuer_did = get_issuer_did()
        issuer_jwk = get_issuer_public_jwk()
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": issuer_did,
            "verificationMethod": [{
                "id": f"{issuer_did}#key-1",
                "type": "JsonWebKey2020",
                "controller": issuer_did,
                "publicKeyJwk": issuer_jwk,
            }],
            "authentication": [f"{issuer_did}#key-1"],
        }
    elif path_components[0] == "students" and len(path_components) >= 2:
        # Resolve student DID from database
        student_id = path_components[1]
        from app.database import SessionLocal
        from app.models import DIDDocument
        db = SessionLocal()
        try:
            did_doc_record = db.query(DIDDocument).filter(
                DIDDocument.did_uri.like(f"%:students:{student_id}")
            ).first()
            if did_doc_record and did_doc_record.did_document:
                return did_doc_record.did_document
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student DID not found: {did}"
            )
        finally:
            db.close()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve DID path: {did}"
        )

def get_public_key_from_did_doc(did_doc: dict, did: str) -> dict:
    """Extract the public key JWK from a DID Document."""
    verification_methods = did_doc.get("verificationMethod", [])
    did_base = did.split("#")[0]
    
    for vm in verification_methods:
        controller = vm.get("controller", "")
        vm_id = vm.get("id", "")
        if (controller == did_base or vm_id.startswith(did_base)
                or controller == did or vm_id.startswith(did)):
            if "publicKeyJwk" in vm:
                return vm["publicKeyJwk"]

    # Fallback: return the first key with a JWK
    for vm in verification_methods:
        if "publicKeyJwk" in vm:
            return vm["publicKeyJwk"]
                
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No public key found in DID Document for {did}"
    )
