"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Authentication ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    roll_number: str = Field(..., description="Student roll number or username", examples=["2021CS123"])
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., examples=["Sankalp Kumar"])
    role: str = Field("student", description="User role: student, admin, or verifier")


class RegisterResponse(BaseModel):
    message: str
    username: str
    student_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── DID ───────────────────────────────────────────────────────────────────────

class DIDCreateRequest(BaseModel):
    public_key_jwk: dict[str, Any] = Field(
        ..., description="The student's public key in JWK format"
    )


class DIDCreateResponse(BaseModel):
    did: str


class DIDDocumentResponse(BaseModel):
    """W3C DID Document."""
    id: str
    context: list[str] = Field(alias="@context", default=["https://www.w3.org/ns/did/v1"])
    verification_method: list[dict[str, Any]] = Field(alias="verificationMethod", default=[])
    authentication: list[str] = []

    class Config:
        populate_by_name = True


class KeyRotateResponse(BaseModel):
    message: str
    new_key_id: str
    previous_key_id: str


# ── Verifiable Credentials ───────────────────────────────────────────────────

class IssueVCRequest(BaseModel):
    student_did: str
    vc_type: str = Field("UniversityDegreeCredential", description="Type of credential to issue")
    
    # Degree fields (optional)
    degree: Optional[str] = None          # e.g. "B.Tech"
    year: Optional[int] = None            # kept for back-compat; prefer graduation_year
    graduation_year: Optional[int] = None
    branch: Optional[str] = None          # e.g. "Electrical Engineering"
    specialization: Optional[str] = None  # optional sub-specialization
    cgpa: Optional[str] = None            # e.g. "9.1"
    honours: Optional[str] = None         # e.g. "With Distinction"
    
    # Internship fields (optional)
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    
    # Skill Badge fields (optional)
    skill_name: Optional[str] = None
    proficiency: Optional[str] = None


class IssueVCResponse(BaseModel):
    vc_id: str
    pre_authorized_code: str


class VCListItem(BaseModel):
    vc_id: str
    type: str
    issued_at: datetime


class VCDetailResponse(BaseModel):
    verifiable_credential: str  # The signed VC JWT


# ── Verification ──────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    verifiable_credential: str  # VC JWT


class VerifyInitResponse(BaseModel):
    verification_id: str
    expires_at: datetime


class ChallengeItem(BaseModel):
    verification_id: str
    nonce: str
    expires_at: datetime


class VerifyRespondRequest(BaseModel):
    verification_id: str
    vp_jwt: str


class VerifyRespondResponse(BaseModel):
    status: str


class VerificationResultResponse(BaseModel):
    status: str
    issuer_verified: bool
    holder_bound: bool


# ── General ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str


# ── Admin: Student listing ────────────────────────────────────────────────────

class StudentListItem(BaseModel):
    username: str
    student_id: str
    full_name: str
    has_did: bool
    did_uri: Optional[str] = None
    vc_count: int = 0
