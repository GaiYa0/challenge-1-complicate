from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: int
    username: str
    role: str


class TokenValidateRequest(BaseModel):
    token: str = Field(min_length=1)


class TokenValidateResponse(BaseModel):
    valid: bool
    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    reason: str | None = None
