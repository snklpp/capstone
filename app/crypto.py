"""Cryptography utilities — key generation, VC/VP signing and verification.

Uses ECDSA with P-256 (ES256) for signing, and JWK format for key exchange.
"""

import json
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from jose import jwt, JWTError


# ── Key generation ────────────────────────────────────────────────────────────


def generate_ec_key_pair() -> tuple[dict[str, Any], str]:
    """Generate an EC P-256 key pair.

    Returns:
        (public_key_jwk, private_key_pem)
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Build JWK from public key numbers
    pub_numbers = public_key.public_numbers()
    x_bytes = pub_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = pub_numbers.y.to_bytes(32, byteorder="big")

    import base64

    public_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode("utf-8"),
        "y": base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode("utf-8"),
    }

    return public_jwk, private_pem


def private_pem_to_jwk(private_pem: str) -> dict[str, Any]:
    """Convert a PEM-encoded EC private key to a JWK dict (with private 'd')."""
    import base64

    private_key = serialization.load_pem_private_key(
        private_pem.encode("utf-8"), password=None
    )
    priv_numbers = private_key.private_numbers()
    pub_numbers = priv_numbers.public_numbers

    x_bytes = pub_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = pub_numbers.y.to_bytes(32, byteorder="big")
    d_bytes = priv_numbers.private_value.to_bytes(32, byteorder="big")

    return {
        "kty": "EC",
        "crv": "P-256",
        "x": base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode("utf-8"),
        "y": base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode("utf-8"),
        "d": base64.urlsafe_b64encode(d_bytes).rstrip(b"=").decode("utf-8"),
    }


# ── VC / VP Signing ──────────────────────────────────────────────────────────


def sign_credential(payload: dict, private_key_pem: str) -> str:
    """Sign a Verifiable Credential payload as a JWT (ES256).

    Args:
        payload: The VC claims (iss, sub, vc, iat, etc.)
        private_key_pem: PEM-encoded EC private key

    Returns:
        A JWT string representing the signed VC.
    """
    private_jwk = private_pem_to_jwk(private_key_pem)
    return jwt.encode(payload, private_jwk, algorithm="ES256")


def verify_credential(vc_jwt: str, public_key_jwk: dict) -> dict:
    """Verify a VC/VP JWT signature and return the decoded payload.

    Args:
        vc_jwt: The JWT string
        public_key_jwk: The signer's public key in JWK format

    Returns:
        Decoded JWT payload

    Raises:
        ValueError if the signature is invalid or the token is malformed.
    """
    try:
        payload = jwt.decode(
            vc_jwt,
            public_key_jwk,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid credential signature: {e}")


def sign_presentation(payload: dict, private_key_pem: str) -> str:
    """Sign a Verifiable Presentation as a JWT (ES256)."""
    private_jwk = private_pem_to_jwk(private_key_pem)
    return jwt.encode(payload, private_jwk, algorithm="ES256")


def verify_presentation(vp_jwt: str, public_key_jwk: dict) -> dict:
    """Verify a VP JWT signature and return the decoded payload."""
    try:
        payload = jwt.decode(
            vp_jwt,
            public_key_jwk,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid presentation signature: {e}")


# ── did:key resolution ────────────────────────────────────────────────────────

_BASE58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58btc_decode(s: str) -> bytes:
    """Decode a base58btc-encoded string to bytes."""
    n = 0
    for c in s.encode("ascii"):
        n = n * 58 + _BASE58_ALPHABET.index(c)
    pad_size = 0
    for c in s.encode("ascii"):
        if c == _BASE58_ALPHABET[0]:
            pad_size += 1
        else:
            break
    result = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad_size + result


def resolve_did_key_to_jwk(did_key: str) -> dict[str, Any]:
    """Resolve a did:key: URI (P-256) to a JWK dict.

    Supports P-256 keys (multicodec 0x1200, multibase z = base58btc).
    Format: did:key:z<base58btc-encoded-multicodec-key>[#fragment]
    """
    import base64
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256R1,
        EllipticCurvePublicKey,
    )

    # did:key:zDnae...#zDnae... → zDnae...
    key_part = did_key.split("did:key:")[1].split("#")[0]

    if not key_part.startswith("z"):
        raise ValueError(f"Unsupported multibase prefix: {key_part[0]}")

    decoded = _base58btc_decode(key_part[1:])  # strip 'z', base58btc decode

    # P-256 multicodec: 0x1200 → varint [0x80, 0x24]
    if len(decoded) >= 2 and decoded[0] == 0x80 and decoded[1] == 0x24:
        compressed_key = decoded[2:]
        if len(compressed_key) != 33:
            raise ValueError(
                f"Expected 33 bytes for compressed P-256 key, got {len(compressed_key)}"
            )
        pub_key = EllipticCurvePublicKey.from_encoded_point(
            SECP256R1(), compressed_key
        )
        pub_numbers = pub_key.public_numbers()
        x_bytes = pub_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = pub_numbers.y.to_bytes(32, byteorder="big")
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode("utf-8"),
            "y": base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode("utf-8"),
        }
    else:
        raise ValueError(f"Unsupported multicodec prefix: {decoded[:2].hex()}")
