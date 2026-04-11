from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from services.user_service.core.database import get_db
from services.user_service.core.exceptions import AuthError
from services.user_service.schema.auth import LoginRequest, TokenData
from services.user_service.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenData)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    try:
        token = auth_service.login(db, body.username, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=e.msg) from e
    return TokenData(access_token=token)
