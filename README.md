# University Portal — DID & Verifiable Credentials API

A **FastAPI** backend implementing a **Decentralized Identity (DID)** and **Verifiable Credentials (VC)** system for a university portal.

## Features

| Feature | Endpoint | Auth |
|---|---|---|
| Login | `POST /auth/login` | None |
| Create DID | `POST /students/did` | Student JWT |
| Resolve DID | `GET /students/{id}/did.json` | Public |
| Issue VC | `POST /admin/issue-vc` | Admin JWT |
| List VCs | `GET /students/vcs` | Student JWT |
| Download VC | `GET /students/vcs/{vc_id}` | Student JWT |
| Start Verification | `POST /verify` | Verifier JWT |
| Get Challenges | `GET /students/challenges` | Student JWT |
| Respond with VP | `POST /verify/respond` | Student JWT |
| Check Result | `GET /verifications/{id}` | Verifier JWT |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Seed demo users
python app/seed.py

# Run the server
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

### Demo Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin (Issuer) |
| `student1` | `student123` | Student |
| `student2` | `student456` | Student |
| `verifier1` | `verifier123` | Verifier |

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Language** | Python | 3.x | Backend logic |
| **Framework** | FastAPI | 0.115.0 | Async REST API framework |
| **Server** | Uvicorn | 0.30.6 | ASGI web server |
| **ORM** | SQLAlchemy | 2.0.35 | Database abstraction |
| **Database** | SQLite | Built-in | Embedded relational DB |
| **Auth** | python-jose | 3.3.0 | JWT (HS256) |
| **Security** | passlib + bcrypt | 1.7.4 | Password hashing |
| **Crypto** | cryptography | 43.0.1 | EC P-256 (ES256) |
| **Validation** | Pydantic | v2 | Data validation |
| **Frontend** | Vanilla JS | — | UI logic |
| **Export** | html2canvas | 1.4.1 | PNG download |

## Architecture

- **Auth**: JWT (HS256) with role-based access control
- **Crypto**: ECDSA P-256 (ES256) for VC/VP signing
- **DID Method**: `did:web`
- **Database**: SQLite (SQLAlchemy ORM)
- **VC Format**: JWT-encoded W3C Verifiable Credentials
