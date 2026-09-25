import uuid

from pydantic import BaseModel, field_validator

from app.schemas.common import ORM, Email


class SignupIn(BaseModel):
    name: str
    email: Email
    password: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        if len(value) > 80:
            raise ValueError("Name must be 80 characters or fewer")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(value) > 128:
            raise ValueError("Password must be 128 characters or fewer")
        if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
            raise ValueError("Password must include at least one letter and one number")
        return value


class LoginIn(BaseModel):
    email: Email
    password: str


class UserOut(ORM):
    id: uuid.UUID
    name: str
    email: str


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
