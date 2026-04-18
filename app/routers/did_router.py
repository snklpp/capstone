"""DID resolution router — public endpoint for resolving DID documents."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DIDDocument

router = APIRouter(tags=["DID Resolution"])


@router.get("/students/{student_id}/did.json")
def resolve_did(student_id: str, db: Session = Depends(get_db)):
    """Resolve a DID document by student ID — NO authentication required.

    Flow (Part 3, steps 1-3):
    1. GET /students/{student_id}/did.json (no auth)
    2. Fetch DID document from DB by student_id
    3. Return {id: "did:web:...", verificationMethod: [...]}
    """
    # The DID URI ends with the student_id
    did = (
        db.query(DIDDocument)
        .filter(DIDDocument.did_uri.like(f"%:students:{student_id}"))
        .first()
    )
    if not did:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DID not found for student: {student_id}",
        )

    return did.did_document
