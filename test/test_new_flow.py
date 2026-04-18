import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crypto import generate_ec_key_pair
from app.database import SessionLocal
from app.models import DIDDocument, User

db = SessionLocal()
student = db.query(User).filter(User.role == "student").first()
if student:
    print(f"Found student: {student.username}")
    
    # Simulate a wallet generating a key
    pub_jwk, priv_pem = generate_ec_key_pair()
    print("Wallet generated key pair locally.")
    
    # Check current DID
    did = db.query(DIDDocument).filter(DIDDocument.user_id == student.id).first()
    if did:
        # Simulate rotate
        print("Student already has DID, simulating key rotation via the new logic...")
        did.public_key_jwk = pub_jwk
        did.key_version += 1
        db.commit()
        print(f"Rotated! New key version: {did.key_version}")
    else:
        print("Simulating DID Creation with public key only...")
        did_uri = f"did:web:university.edu:students:{student.student_id}"
        did_doc_record = DIDDocument(
            did_uri=did_uri,
            user_id=student.id,
            public_key_jwk=pub_jwk,
            did_document={"id": did_uri}
        )
        db.add(did_doc_record)
        db.commit()
        print("Created DID without private key storage!")

