"""Test the credential endpoint with kid-based proof (like Altme sends)."""
import requests, json, base64, time
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes

BASE = "http://localhost:8000"

# 1. Exchange the pre-authorized code for a token
token_resp = requests.post(f"{BASE}/auth/token", data={
    "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
    "pre-authorized_code": "demo-1774708008-d226",
    "client_id": "did:jwk:test",
})
print("Token status:", token_resp.status_code)
assert token_resp.status_code == 200, token_resp.text
token_data = token_resp.json()
access_token = token_data["access_token"]
c_nonce = token_data["c_nonce"]
print("c_nonce:", c_nonce)

# 2. Generate an EC P-256 key (simulating wallet key)
key = ec.generate_private_key(ec.SECP256R1())
pub = key.public_key()
nums = pub.public_numbers()

def b64url_int(n, length):
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

jwk = {"crv": "P-256", "kty": "EC", "x": b64url_int(nums.x, 32), "y": b64url_int(nums.y, 32)}
jwk_b64 = base64.urlsafe_b64encode(json.dumps(jwk, separators=(",", ":")).encode()).rstrip(b"=").decode()
kid = f"did:jwk:{jwk_b64}#0"

# 3. Build proof JWT with "kid" (NOT "jwk") — this is what Altme does
header = {"alg": "ES256", "typ": "openid4vci-proof+jwt", "kid": kid}
payload = {
    "iat": int(time.time()),
    "aud": token_data.get("issuer", "https://administrative-operates-containing-conflicts.trycloudflare.com"),
    "iss": f"did:jwk:{jwk_b64}",
    "nonce": c_nonce,
}

header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
signing_input = f"{header_b64}.{payload_b64}"

sig = key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
r, s = decode_dss_signature(sig)
sig_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")
sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()

proof_jwt = f"{signing_input}.{sig_b64}"

print("\nProof JWT header has kid (no jwk):", "kid" in header and "jwk" not in header)

# 4. Call credential endpoint exactly like Altme does
resp = requests.post(f"{BASE}/admin/issue",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    },
    json={
        "proof": {"proof_type": "jwt", "jwt": proof_jwt},
        "format": "jwt_vc_json",
        "credential_definition": {"type": ["VerifiableCredential", "UniversityDegreeCredential"]},
    },
)
print("\nCredential endpoint status:", resp.status_code)
print("Response:", json.dumps(resp.json(), indent=2)[:500])

if resp.status_code == 200:
    print("\n✅ SUCCESS — Credential issued with kid-based proof (Altme format)")
else:
    print("\n❌ FAILED —", resp.json().get("detail", "unknown error"))
