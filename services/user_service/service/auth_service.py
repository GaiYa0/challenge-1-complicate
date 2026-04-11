import bcrypt
from sqlalchemy.orm import Session

from services.user_service.core.exceptions import AuthError
from services.user_service.core.jwt_tokens import create_token
from services.user_service.core.security_audit import log_event
from services.user_service.repository import user_repo


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _is_bcrypt_hash(value: str) -> bool:
    return value.startswith("$2") and len(value) >= 59


def login(db: Session, username: str, password: str) -> str:
    user = user_repo.get_user_by_username(db, username.strip())
    if user is None:
        log_event("login_failed", username=username.strip())
        raise AuthError("invalid username or password", code=40102)

    if _is_bcrypt_hash(user.password):
        valid = verify_password(password, user.password)
    else:
        valid = (user.password == password)
        if valid:
            user.password = hash_password(password)
            db.commit()

    if not valid:
        log_event("login_failed", username=username.strip())
        raise AuthError("invalid username or password", code=40102)
    return create_token({"user_id": user.id, "role": user.role})
