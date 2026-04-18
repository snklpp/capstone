"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./university_portal.db")

# The DID domain used for constructing did:web identifiers
DID_DOMAIN: str = os.getenv("DID_DOMAIN", "university.edu")

# Public base URL — set this to your Render URL so wallets can reach the server.
# Falls back to local development URL if not set.
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
