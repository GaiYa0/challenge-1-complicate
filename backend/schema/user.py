from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
