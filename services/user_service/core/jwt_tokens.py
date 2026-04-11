from __future__ import annotations

import time
from typing import Any

import jwt

from services.user_service.core.config import get_settings
from services.user_service.core.exceptions import AuthError

_JWT_ISSUER = "challenge_demo"
_JWT_AUDIENCE = "challenge_demo_api"


def create_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    if "user_id" not in data or "role" not in data:
        raise ValueError("token payload must include user_id and role")
    now = int(time.time())
    exp = now + int(settings.JWT_EXPIRE_MINUTES) * 60
    payload = {**data, "exp": exp, "iss": _JWT_ISSUER, "aud": _JWT_AUDIENCE, "iat": now}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            issuer=_JWT_ISSUER,
            audience=_JWT_AUDIENCE,
            leeway=30,
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except jwt.InvalidIssuerError as e:
        raise AuthError("invalid token issuer") from e
    except jwt.InvalidAudienceError as e:
        raise AuthError("invalid token audience") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid token") from e
