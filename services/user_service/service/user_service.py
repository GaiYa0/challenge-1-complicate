from sqlalchemy.orm import Session

from services.user_service.repository import user_repo
from services.user_service.schema.auth import UserPublic


def get_user_public(db: Session, user_id: int) -> UserPublic | None:
    u = user_repo.get_user_by_id(db, user_id)
    if u is None:
        return None
    return UserPublic(id=u.id, username=u.username, role=u.role)
