"""写库事务：统一 commit / rollback。"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction(db: Session) -> Generator[Session, None, None]:
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
