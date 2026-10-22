"""JWT settings shared by the page and voice API authentication checks."""

import os
from pathlib import Path

from dotenv import dotenv_values

APP_DIR = Path(__file__).resolve().parent
WORKPLACE_ENV = APP_DIR.parent.parent / "workplace" / ".env"

# Prefer the process environment, then this app's .env. For the local
# multi-project setup, use the Java auth server's .env as a fallback.
SECRET_KEY = os.getenv("JWT_SECRET")
if SECRET_KEY is None:
    SECRET_KEY = dotenv_values(APP_DIR / ".env").get("JWT_SECRET")
if SECRET_KEY is None:
    SECRET_KEY = dotenv_values(WORKPLACE_ENV).get("JWT_SECRET")
if not SECRET_KEY or not SECRET_KEY.strip():
    raise RuntimeError(
        "JWT_SECRET is missing. Set it to the same value as the Java auth server."
    )

ALGORITHM = "HS256"
ISSUER = "simple-auth-server"
