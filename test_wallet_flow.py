"""End-to-end test: Wallet-based credential issuance with holder binding."""
import requests, json, time
from jose import jwt as jose_jwt
from app.crypto import generate_ec_key_pair, private_pem_to_jwk

BASE = "http://localhost:8000"

# 1. Register admin + student
requests.post(f"{BASE}/auth/register", json={"roll_number":"admin","password":"admin123","full_name":"Admin","role":"admin"})
requests.post(f"{BASE}/auth/register", json={"roll_number":"2021CS001","password":"pass1234","full_name":"Sankalp Kumar","role":"student"})

# 2. Admin login
admin_token = requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"admin123"}).json()["access_token"]

# 3. Admin creates credential offer (NO VC signing)
offer_resp = requests.post(f"{BASE}/admin/issue-vc",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"student_did":"2021CS001","vc_type":"UniversityDegreeCredential","degree":"B.Tech Computer Science","year":2025}
).json()
print("=== OFFER RESPONSE ===")
print(json.dumps(offer_resp, indent=2))
assert offer_resp.get("status") == "OFFERED", f"Expected OFFERED, got {offer_resp}"
assert "vc_jwt" not in offer_resp, "VC should NOT be signed yet!"
print("✅ No VC signed at offer time — correct!")

pre_auth_code = offer_resp["pre_authorized_code"]

# 4. Student checks VCs (should see pending offer)
student_token = requests.post(f"{BASE}/auth/login", json={"username":"2021CS001","password":"pass1234"}).json()["access_token"]
vcs = requests.get(f"{BASE}/students/vcs", headers={"Authorization":f"Bearer {student_token}"}).json()
print(f"\n=== STUDENT VCs (before wallet claim) ===")
for v in vcs:
    print(f"  {v['vc_id']} — {v['type']} — {v['status']}")
assert len(vcs) == 1 and vcs[0]["status"] == "PENDING", "Expected one PENDING offer"
print("✅ Student sees pending offer — correct!")

# 5. Wallet exchanges pre-auth code for token
token_resp = requests.post(f"{BASE}/auth/token", data={
    "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
    "pre-authorized_code": pre_auth_code
}).json()
wallet_token = token_resp["access_token"]
c_nonce = token_resp["c_nonce"]
print(f"\n=== TOKEN EXCHANGE ===")
print(f"Access token: {wallet_token[:30]}...")
print(f"c_nonce: {c_nonce}")

# 6. Wallet builds proof JWT with its own public key
wallet_pub_jwk, wallet_priv_pem = generate_ec_key_pair()
wallet_priv_jwk = private_pem_to_jwk(wallet_priv_pem)

proof_header = {"typ": "openid4vci-proof+jwt", "alg": "ES256", "jwk": wallet_pub_jwk}
proof_payload = {"iss": "did:key:z6MkWalletTestDID", "aud": BASE, "iat": int(time.time()), "nonce": c_nonce}
proof_jwt = jose_jwt.encode(proof_payload, wallet_priv_jwk, algorithm="ES256", headers=proof_header)
print(f"\n=== WALLET PROOF JWT ===")
print(f"  {proof_jwt[:60]}...")

# 7. Wallet claims credential via OID4VCI credential endpoint
cred_resp = requests.post(f"{BASE}/admin/issue",
    headers={"Authorization": f"Bearer {wallet_token}"},
    json={"format": "jwt_vc_json", "proof": {"proof_type": "jwt", "jwt": proof_jwt}}
).json()
print(f"\n=== CREDENTIAL RESPONSE ===")
print(f"Format: {cred_resp.get('format')}")
print(f"Credential: {cred_resp.get('credential', '')[:60]}...")
assert cred_resp.get("format") == "jwt_vc_json"
assert cred_resp.get("credential")
print("✅ Wallet received signed VC — correct!")

# 8. Verify DID doc was updated with wallet's public key
did_doc = requests.get(f"{BASE}/students/2021CS001/did.json").json()
print(f"\n=== STUDENT DID DOCUMENT ===")
print(json.dumps(did_doc, indent=2))
vm_key = did_doc["verificationMethod"][0]["publicKeyJwk"]
assert vm_key == wallet_pub_jwk, "DID doc key should be wallet's key!"
print("✅ DID document has wallet public key — holder-bound!")

# 9. Student checks VCs again (should see CLAIMED)
vcs_after = requests.get(f"{BASE}/students/vcs", headers={"Authorization":f"Bearer {student_token}"}).json()
print(f"\n=== STUDENT VCs (after wallet claim) ===")
for v in vcs_after:
    print(f"  {v['vc_id']} — {v['type']} — {v['status']}")
claimed = [v for v in vcs_after if v["status"] == "CLAIMED"]
assert len(claimed) == 1, f"Expected one CLAIMED VC, got {len(claimed)}"
print("✅ Student sees CLAIMED credential — correct!")

print("\n\n🎉 === ALL TESTS PASSED === 🎉")
print("Flow: Admin creates offer → Student scans QR → Wallet claims VC")
print("      → DID doc updated with wallet key → VC is holder-bound")
