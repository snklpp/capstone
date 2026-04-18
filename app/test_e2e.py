"""End-to-end test script for the University Portal API.

Exercises the full flow:
  Part 1: Login + DID creation
  Part 3: Public DID resolution
  Part 4: Admin issues VC
  Part 5: Student lists & downloads VC
  Part 6a: Verifier initiates verification
  Part 6b: Student responds with VP
  Part 6c: Verifier checks result
"""

import sys
import os
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.crypto import generate_ec_key_pair, sign_presentation, private_pem_to_jwk

BASE = "http://127.0.0.1:8000"
PASS = "✅"
FAIL = "❌"


def header(token):
    return {"Authorization": f"Bearer {token}"}


def test_step(name, response, expected_status=200):
    ok = response.status_code == expected_status
    icon = PASS if ok else FAIL
    print(f"  {icon} {name} — HTTP {response.status_code}")
    if not ok:
        print(f"     Expected {expected_status}, got {response.status_code}")
        print(f"     Body: {response.text[:300]}")
    return ok


def main():
    results = []

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 1: Student Authentication & DID Creation ═══\n")

    # Step 1-4: Login as student
    r = requests.post(f"{BASE}/auth/login", json={"username": "2021CS001", "password": "pass1234"})
    results.append(test_step("POST /auth/login (student)", r))
    student_token = r.json().get("access_token", "")

    # Login as admin
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    results.append(test_step("POST /auth/login (admin)", r))
    admin_token = r.json().get("access_token", "")

    # Login as verifier
    r = requests.post(f"{BASE}/auth/login", json={"username": "verifier1", "password": "verifier123"})
    results.append(test_step("POST /auth/login (verifier)", r))
    verifier_token = r.json().get("access_token", "")

    # Step 5-10: Generate key pair & create DID
    student_public_jwk, student_private_pem = generate_ec_key_pair()
    r = requests.post(
        f"{BASE}/students/did",
        json={
            "public_key_jwk": student_public_jwk,
            "private_key_pem": student_private_pem,
        },
        headers=header(student_token),
    )
    results.append(test_step("POST /students/did (create DID)", r))
    student_did = r.json().get("did", "")
    print(f"     DID: {student_did}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 3: DID Resolution (Public) ═══\n")

    r = requests.get(f"{BASE}/students/2021CS001/did.json")
    results.append(test_step("GET /students/2021CS001/did.json (public)", r))
    did_doc = r.json()
    print(f"     DID Document ID: {did_doc.get('id', 'N/A')}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 4: Credential Issuance ═══\n")

    r = requests.post(
        f"{BASE}/admin/issue-vc",
        json={
            "student_did": student_did,
            "degree": "Bachelor of Computer Science",
            "year": 2025,
        },
        headers=header(admin_token),
    )
    results.append(test_step("POST /admin/issue-vc", r))
    vc_id = r.json().get("vc_id", "")
    print(f"     VC ID: {vc_id}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 5: Student Lists & Downloads VC ═══\n")

    r = requests.get(f"{BASE}/students/vcs", headers=header(student_token))
    results.append(test_step("GET /students/vcs (list)", r))
    vcs = r.json()
    print(f"     VCs found: {len(vcs)}")

    r = requests.get(f"{BASE}/students/vcs/{vc_id}", headers=header(student_token))
    results.append(test_step(f"GET /students/vcs/{vc_id} (download)", r))
    vc_jwt = r.json().get("verifiable_credential", "")
    print(f"     VC JWT length: {len(vc_jwt)} chars")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 6a: Verifier Initiates Verification ═══\n")

    r = requests.post(
        f"{BASE}/verify",
        json={"verifiable_credential": vc_jwt},
        headers=header(verifier_token),
    )
    results.append(test_step("POST /verify (initiate)", r))
    verification_id = r.json().get("verification_id", "")
    expires_at = r.json().get("expires_at", "")
    print(f"     Verification ID: {verification_id}")
    print(f"     Expires at: {expires_at}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 6b: Student Responds with VP ═══\n")

    # Get challenges
    r = requests.get(f"{BASE}/students/challenges", headers=header(student_token))
    results.append(test_step("GET /students/challenges", r))
    challenges = r.json()
    print(f"     Pending challenges: {len(challenges)}")

    # Build VP with nonce and sign it
    nonce = challenges[0]["nonce"] if challenges else ""
    vp_payload = {
        "iss": student_did,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [vc_jwt],
        },
        "nonce": nonce,
    }
    vp_jwt = sign_presentation(vp_payload, student_private_pem)

    r = requests.post(
        f"{BASE}/verify/respond",
        json={"verification_id": verification_id, "vp_jwt": vp_jwt},
        headers=header(student_token),
    )
    results.append(test_step("POST /verify/respond", r))
    print(f"     Status: {r.json().get('status', 'N/A')}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 6c: Verifier Checks Result ═══\n")

    r = requests.get(
        f"{BASE}/verifications/{verification_id}",
        headers=header(verifier_token),
    )
    results.append(test_step(f"GET /verifications/{verification_id}", r))
    result = r.json()
    print(f"     Status: {result.get('status')}")
    print(f"     Issuer verified: {result.get('issuer_verified')}")
    print(f"     Holder bound: {result.get('holder_bound')}")

    # ────────────────────────────────────────────────────────────────────────
    print("\n═══ Part 7: Key Rotation ═══\n")

    # Step 1: Rotate the student's key
    r = requests.post(
        f"{BASE}/students/did/rotate-key",
        headers=header(student_token),
    )
    results.append(test_step("POST /students/did/rotate-key", r))
    rotate_data = r.json()
    print(f"     Previous key: {rotate_data.get('previous_key_id')}")
    print(f"     New key: {rotate_data.get('new_key_id')}")

    # Step 2: Resolve DID document and verify key was updated
    r = requests.get(f"{BASE}/students/2021CS001/did.json")
    results.append(test_step("GET /students/2021CS001/did.json (after rotation)", r))
    rotated_doc = r.json()
    new_vm_id = rotated_doc.get("verificationMethod", [{}])[0].get("id", "")
    key_updated = new_vm_id == rotate_data.get("new_key_id")
    icon = PASS if key_updated else FAIL
    print(f"  {icon} DID Document verificationMethod updated to {new_vm_id}")
    results.append(key_updated)

    # Step 3: Get the new private key for VP signing
    r = requests.get(f"{BASE}/students/private-key", headers=header(student_token))
    results.append(test_step("GET /students/private-key (new key)", r))
    new_private_pem = r.json().get("private_key_pem", "")

    # Step 4: Full verification cycle with the rotated key
    print("\n  ── Verification with rotated key ──\n")

    r = requests.post(
        f"{BASE}/verify",
        json={"verifiable_credential": vc_jwt},
        headers=header(verifier_token),
    )
    results.append(test_step("POST /verify (new challenge after rotation)", r))
    verification_id_2 = r.json().get("verification_id", "")

    r = requests.get(f"{BASE}/students/challenges", headers=header(student_token))
    results.append(test_step("GET /students/challenges (after rotation)", r))
    challenges_2 = r.json()
    nonce_2 = challenges_2[0]["nonce"] if challenges_2 else ""

    vp_payload_2 = {
        "iss": student_did,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [vc_jwt],
        },
        "nonce": nonce_2,
    }
    vp_jwt_2 = sign_presentation(vp_payload_2, new_private_pem)

    r = requests.post(
        f"{BASE}/verify/respond",
        json={"verification_id": verification_id_2, "vp_jwt": vp_jwt_2},
        headers=header(student_token),
    )
    results.append(test_step("POST /verify/respond (rotated key VP)", r))
    print(f"     Status: {r.json().get('status', 'N/A')}")

    # ── Summary ───────────────────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    print(f"\n{'═' * 50}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'═' * 50}\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
