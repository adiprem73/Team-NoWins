"""
auth.py — Extracts authenticated user identity from the JWT.

API Gateway validates the Cognito JWT (rejects 401 if invalid/expired).
By the time a request reaches this code, the token is guaranteed valid.
We simply decode the claims payload — no crypto verification needed.
"""
import json
import base64
from fastapi import Header, HTTPException, status


async def get_current_user(
    authorization: str = Header(None),
    x_user_sub: str = Header(None, alias="X-User-Sub"),
    x_user_email: str = Header(None, alias="X-User-Email"),
) -> dict:
    """
    FastAPI dependency — extracts the authenticated user identity.

    Supports two modes:
      1. X-User-Sub header (if API Gateway parameter mapping is configured)
      2. Decode claims from the Bearer JWT (fallback — always works)

    Usage:
        @app.post("/analyze/text")
        async def analyze(request: Request, user=Depends(get_current_user)):
            user_id = user["sub"]
    """
    # Mode 1: Header injected by API Gateway parameter mapping
    if x_user_sub:
        return {"sub": x_user_sub, "email": x_user_email or ""}

    # Mode 2: Decode JWT payload (API Gateway already validated signature)
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ", 1)[1]
            # JWT structure: header.payload.signature
            payload_b64 = token.split(".")[1]
            # Fix base64 padding
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
            sub = claims.get("sub")
            if not sub:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT missing 'sub' claim",
                )
            return {"sub": sub, "email": claims.get("email", "")}
        except (IndexError, ValueError, json.JSONDecodeError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token format: {e}",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Authorization header. Login required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
