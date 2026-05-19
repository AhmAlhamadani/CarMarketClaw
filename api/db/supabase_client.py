import os
import re

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def _normalize_supabase_url(url: str | None) -> str:
    """Strip /rest/v1 — create_client adds the REST path itself."""
    if not url:
        return ""
    normalized = url.strip().rstrip("/")
    normalized = re.sub(r"/rest/v1/?$", "", normalized, flags=re.IGNORECASE)
    return normalized.rstrip("/")


SUPABASE_URL = _normalize_supabase_url(os.getenv("SUPABASE_URL"))
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
