"""IIT Hyderabad — FastAPI application entry point."""

import logging, json as _json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import engine, Base
from app.crypto import generate_ec_key_pair, sign_presentation
from app.routers import auth_router, student_router, did_router, admin_router, verify_router

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("oid4vci")


# ── Request / response logging middleware ──────────────────────────────────
class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only log OID4VCI-relevant paths (token, issue, .well-known)
        path = request.url.path
        interesting = any(p in path for p in [
            "/auth/token", "/admin/issue", "/.well-known",
            "/api/config", "/verify", "/api/verify",
        ])
        if interesting:
            body_bytes = await request.body()
            log.info("─── REQUEST ─── %s %s", request.method, str(request.url))
            log.info("  Headers: %s", dict(request.headers))
            if body_bytes:
                try:
                    log.info("  Body (JSON): %s", _json.loads(body_bytes))
                except Exception:
                    log.info("  Body (raw): %s", body_bytes.decode("utf-8", errors="replace"))
            # Make body readable again for downstream handlers
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive

        response = await call_next(request)

        if interesting:
            log.info("  Response status: %s", response.status_code)
        return response


# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="IIT Hyderabad — DID & Verifiable Credentials",
    description=(
        "A FastAPI backend implementing Decentralized Identity (DID) and "
        "Verifiable Credentials (VC) for a university portal. Supports student "
        "authentication, DID creation, credential issuance, and a full "
        "verification flow with Verifiable Presentations (VPs)."
    ),
    version="1.0.0",
)

# Logging middleware (added before CORS so it captures everything)
app.add_middleware(RequestLogMiddleware)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router.router)
app.include_router(student_router.router)
app.include_router(did_router.router)
app.include_router(admin_router.router)
app.include_router(verify_router.router)


# ── OID4VCI Well-Known Discovery Endpoints ────────────────────────────────

@app.get("/.well-known/openid-credential-issuer", tags=["OID4VCI"])
_BINDING_METHODS = ["did:web"]

def get_oid4vci_metadata():
    """Wallet discovery metadata for OpenID for Verifiable Credential Issuance (Draft 13+)."""
    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL
    
    # Common display for the Issuer
    issuer_display = [{
        "name": "IIT Hyderabad",
        "locale": "en",
        "logo": {
            "url": f"{base_url}/static/logo.svg",
            "alt_text": "IIT Hyderabad Logo"
        },
        "background_color": "#0d47a1",
        "text_color": "#ffffff"
    }]

    return {
        "credential_issuer": base_url,
        "credential_endpoint": f"{base_url}/admin/issue",
        "token_endpoint": f"{base_url}/auth/token",
        "subject_syntax_types_supported": ["did:web"],
        "display": issuer_display,
        "credential_configurations_supported": {
            "UniversityDegreeCredential": {
                "format": "jwt_vc_json",
                "scope": "UniversityDegreeCredential",
                "cryptographic_binding_methods_supported": _BINDING_METHODS,
                "credential_signing_alg_values_supported": ["ES256"],
                "proof_types_supported": {"jwt": {"proof_signing_alg_values_supported": ["ES256"]}},
                "credential_definition": {
                    "type": ["VerifiableCredential", "UniversityDegreeCredential"]
                },
                "display": [
                    {
                        "name": "Degree Certificate",
                        "locale": "en",
                        "background_color": "#1A237E",
                        "text_color": "#FFFFFF",
                        "logo": {
                            "url": f"{base_url}/static/logo.svg",
                            "alt_text": "IIT Hyderabad"
                        },
                        "description": "Official degree credential issued by IIT Hyderabad"
                    }
                ],
                "claims": {
                    "credentialSubject": {
                        "student_name":    {"mandatory": True,  "display": [{"name": "Graduate",        "locale": "en"}]},
                        "student_id":      {"mandatory": True,  "display": [{"name": "Roll No",         "locale": "en"}]},
                        "degree":          {"mandatory": True,  "display": [{"name": "Degree",          "locale": "en"}]},
                        "branch":          {"mandatory": True,  "display": [{"name": "Branch",          "locale": "en"}]},
                        "specialization":  {"mandatory": False, "display": [{"name": "Specialization",  "locale": "en"}]},
                        "cgpa":            {"mandatory": True,  "display": [{"name": "CGPA",            "locale": "en"}]},
                        "graduation_year": {"mandatory": True,  "display": [{"name": "Year of Passing", "locale": "en"}]},
                        "honours":         {"mandatory": False, "display": [{"name": "Honours",         "locale": "en"}]},
                        "issued_on":       {"mandatory": True,  "display": [{"name": "Issued on",       "locale": "en"}]}
                    }
                }
            },
            "InternshipCredential": {
                "format": "jwt_vc_json",
                "scope": "InternshipCredential",
                "cryptographic_binding_methods_supported": _BINDING_METHODS,
                "credential_signing_alg_values_supported": ["ES256"],
                "proof_types_supported": {"jwt": {"proof_signing_alg_values_supported": ["ES256"]}},
                "credential_definition": {
                    "type": ["VerifiableCredential", "InternshipCredential"]
                },
                "display": [
                    {
                        "name": "Internship Certificate",
                        "locale": "en",
                        "background_color": "#1b5e20",
                        "text_color": "#ffffff",
                        "logo": {"url": f"{base_url}/static/logo.svg", "alt_text": "IIT Hyderabad"},
                        "description": "Official internship certificate issued by IIT Hyderabad"
                    }
                ],
                "claims": {
                    "credentialSubject": {
                        "student_name": {"mandatory": True,  "display": [{"name": "Student",  "locale": "en"}]},
                        "company":      {"mandatory": True,  "display": [{"name": "Company",  "locale": "en"}]},
                        "role":         {"mandatory": True,  "display": [{"name": "Role",     "locale": "en"}]},
                        "duration":     {"mandatory": True,  "display": [{"name": "Duration", "locale": "en"}]},
                        "issued_on":    {"mandatory": False, "display": [{"name": "Issued on", "locale": "en"}]}
                    }
                }
            },
            "SkillBadgeCredential": {
                "format": "jwt_vc_json",
                "scope": "SkillBadgeCredential",
                "cryptographic_binding_methods_supported": _BINDING_METHODS,
                "credential_signing_alg_values_supported": ["ES256"],
                "proof_types_supported": {"jwt": {"proof_signing_alg_values_supported": ["ES256"]}},
                "credential_definition": {
                    "type": ["VerifiableCredential", "SkillBadgeCredential"]
                },
                "display": [
                    {
                        "name": "Skill Badge",
                        "locale": "en",
                        "background_color": "#4a148c",
                        "text_color": "#ffffff",
                        "logo": {"url": f"{base_url}/static/logo.svg", "alt_text": "IIT Hyderabad"},
                        "description": "Skill proficiency badge issued by IIT Hyderabad"
                    }
                ],
                "claims": {
                    "credentialSubject": {
                        "student_name": {"mandatory": True,  "display": [{"name": "Recipient",    "locale": "en"}]},
                        "skill_name":   {"mandatory": True,  "display": [{"name": "Skill",        "locale": "en"}]},
                        "proficiency":  {"mandatory": True,  "display": [{"name": "Level",        "locale": "en"}]},
                        "issued_on":    {"mandatory": False, "display": [{"name": "Issued on",    "locale": "en"}]}
                    }
                }
            }
        }
    }

@app.get("/.well-known/jwt-vc-issuer", tags=["OID4VCI"])
def get_jwt_vc_issuer_metadata():
    """Alternative standard discovery for wallets (EBSF/Walt.id)."""
    return get_oid4vci_metadata()

@app.get("/.well-known/openid-configuration", tags=["OID4VCI"])
@app.get("/.well-known/oauth-authorization-server", tags=["OID4VCI"])
def get_oidc_configuration():
    """OIDC/OAuth discovery for wallets to find the token endpoint."""
    from app.config import PUBLIC_BASE_URL
    base_url = PUBLIC_BASE_URL
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/auth/authorize", # Not fully implemented, just a stub
        "token_endpoint": f"{base_url}/auth/token",
        "response_types_supported": ["code", "token"],
        "grant_types_supported": ["authorization_code", "urn:ietf:params:oauth:grant-type:pre-authorized_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["ES256", "RS256"]
    }



# ── Crypto helper endpoints (for frontend use) ───────────────────────────


@app.get("/api/config", tags=["Utilities"])
def api_config():
    """Return public config for the frontend (tunnel URL etc.)."""
    from app.config import PUBLIC_BASE_URL, DID_DOMAIN
    return {"public_base_url": PUBLIC_BASE_URL, "did_domain": DID_DOMAIN}


@app.post("/api/generate-keypair", tags=["Utilities"])
def api_generate_keypair():
    """Generate an EC P-256 key pair for the frontend.
    Returns public_key_jwk and private_key_pem."""
    public_jwk, private_pem = generate_ec_key_pair()
    return {"public_key_jwk": public_jwk, "private_key_pem": private_pem}


from pydantic import BaseModel


class SignVPRequest(BaseModel):
    private_key_pem: str
    iss: str
    nonce: str
    vc_jwt: str


@app.post("/api/sign-vp", tags=["Utilities"])
def api_sign_vp(body: SignVPRequest):
    """Sign a Verifiable Presentation JWT for the frontend.
    In production, signing would happen client-side."""
    vp_payload = {
        "iss": body.iss,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [body.vc_jwt],
        },
        "nonce": body.nonce,
    }
    vp_jwt = sign_presentation(vp_payload, body.private_key_pem)
    return {"vp_jwt": vp_jwt}


# ── Serve frontend ────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Root"])
def root():
    """Serve the frontend SPA."""
    return FileResponse("static/index.html")
