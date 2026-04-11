from __future__ import annotations

import jwt
from fastapi import HTTPException, Request


def is_public_route(path: str, method: str) -> bool:
    m = method.upper()
    if m == "OPTIONS":
        return True
    if path == "/user/auth/login" and m == "POST":
        return True
    if path in ("/user/health", "/file/health") and m == "GET":
        return True
    if path == "/health":
        return True
    return False


def require_bearer_jwt(request: Request, jwt_secret: str) -> None:
    if is_public_route(request.url.path, request.method):
        return
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth[7:].strip()
    try:
        jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            issuer="challenge_demo",
            audience="challenge_demo_api",
            leeway=30,
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="token expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e
