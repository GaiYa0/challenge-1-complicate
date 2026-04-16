"""
Service 层 —— 认证
职责：登录签发 JWT；不在此处解析 Bearer（由 deps + jwt_tokens 完成）。
"""

import bcrypt
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, AuthError, ForbiddenError
from backend.core.jwt_tokens import create_token
from backend.core.security_audit import log_security_event
from backend.model.models import User
from backend.app.repositories import user_repo


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
        log_security_event("login_failed", username=username.strip())
        raise AuthError("invalid username or password", code=40102)

    if _is_bcrypt_hash(user.password):
        valid = verify_password(password, user.password)
    else:
        valid = (user.password == password)
        if valid:
            user.password = hash_password(password)
            db.commit()

    if not valid:
        log_security_event("login_failed", username=username.strip())
        raise AuthError("invalid username or password", code=40102)
    return create_token({"user_id": user.id, "role": user.role})


def list_users_for_admin(db: Session) -> list[User]:
    """返回全部用户（仅管理员接口使用）。"""
    return user_repo.list_users(db)


def delete_user_as_admin(db: Session, target_id: int, actor: User) -> None:
    from sqlalchemy.exc import IntegrityError

    if target_id == actor.id:
        raise ForbiddenError("cannot delete yourself")
    if user_repo.get_user_by_id(db, target_id) is None:
        raise AppError("user not found", code=40401, status_code=404)
    if user_repo.count_user_related_rows(db, target_id) > 0:
        raise AppError(
            "该用户仍存在文件、反馈或特征等关联数据，请先清理后再删除",
            code=40901,
            status_code=409,
        )
    try:
        if not user_repo.delete_user_by_id(db, target_id):
            raise AppError("user not found", code=40401, status_code=404)
    except IntegrityError as e:
        raise AppError(
            "删除失败：数据库仍存在关联约束，请先清理关联数据",
            code=40901,
            status_code=409,
        ) from e
