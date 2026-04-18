"""SQLAlchemy ORM models for the University Portal."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Users table — students, admins, and verifiers."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        SAEnum("student", "admin", "verifier", name="user_role"),
        nullable=False,
    )
    full_name = Column(String(200), nullable=True)
    student_id = Column(String(50), unique=True, nullable=True)  # only for students
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    did = relationship("DIDDocument", back_populates="user", uselist=False)


class DIDDocument(Base):
    """DID documents linked to users."""

    __tablename__ = "dids"

    id = Column(String, primary_key=True, default=generate_uuid)
    did_uri = Column(String(500), unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    public_key_jwk = Column(JSON, nullable=False)
    did_document = Column(JSON, nullable=False)
    key_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="did")
    credentials = relationship("VerifiableCredential", back_populates="did")
    key_history = relationship("KeyHistory", back_populates="did", order_by="KeyHistory.rotated_at.desc()")
    verification_sessions = relationship(
        "VerificationSession",
        back_populates="holder_did_rel",
        foreign_keys="VerificationSession.holder_did",
    )


class VerifiableCredential(Base):
    """Verifiable Credentials issued to students."""

    __tablename__ = "verifiable_credentials"

    id = Column(String, primary_key=True, default=generate_uuid)
    vc_id = Column(String(100), unique=True, nullable=False, index=True)
    did_id = Column(String, ForeignKey("dids.id"), nullable=False)
    vc_type = Column(String(200), nullable=False, default="UniversityDegreeCredential")
    vc_jwt = Column(Text, nullable=False)  # The signed VC as a JWT
    issued_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    did = relationship("DIDDocument", back_populates="credentials")


class CredentialOffer(Base):
    """Temporary record for a credential offer (pre-issuance)."""

    __tablename__ = "credential_offers"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    vc_type = Column(String(200), nullable=False)
    offer_details = Column(JSON, nullable=False)
    pre_authorized_code = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SAEnum("OFFERED", "CLAIMED", "EXPIRED", name="offer_status"), default="OFFERED")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")


class VerificationSession(Base):
    """Verification sessions for the OID4VP flow."""

    __tablename__ = "verification_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    verification_id = Column(String(100), unique=True, nullable=False, index=True)
    verifier_id = Column(String, ForeignKey("users.id"), nullable=False)
    target_did = Column(String(500), nullable=True)  # Optional: which student DID this targets
    holder_did = Column(String(500), ForeignKey("dids.did_uri"), nullable=True) # Filled after wallet scan
    nonce = Column(String(100), nullable=False)
    status = Column(
        SAEnum("PENDING", "VERIFIED", "EXPIRED", name="verification_status"),
        nullable=False,
        default="PENDING",
    )
    presentation_definition = Column(JSON, nullable=True) # The DIF request
    vc_jwt = Column(Text, nullable=True)  # The original VC (optional backup)
    vp_jwt = Column(Text, nullable=True)  # The proof received from wallet
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    verifier = relationship("User", foreign_keys=[verifier_id])
    holder_did_rel = relationship(
        "DIDDocument",
        back_populates="verification_sessions",
        foreign_keys=[holder_did],
    )


class KeyHistory(Base):
    """Archived public keys from DID key rotations."""

    __tablename__ = "key_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    did_id = Column(String, ForeignKey("dids.id"), nullable=False)
    public_key_jwk = Column(JSON, nullable=False)
    key_id = Column(String(100), nullable=False)  # e.g., "#key-1"
    rotated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    did = relationship("DIDDocument", back_populates="key_history")
