"""
src/api/middleware/auth.py — API-key auth (brief §4.2: from day one).
OWNER: Chief Engineer.

Simple header scheme: X-API-Key must equal the SAF_API_KEY environment
variable. With SAF_API_KEY unset the API refuses to serve protected routes
(503) rather than running open — misconfiguration fails closed.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SAF_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="server has no SAF_API_KEY configured")
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
