import uuid
from typing import Annotated, Generic, TypeVar

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict

T = TypeVar("T")


def _normalize_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError("Enter a valid email address") from None


Email = Annotated[str, AfterValidator(_normalize_email)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(ORM):
    id: uuid.UUID
    name: str


class ProjectRef(ORM):
    id: uuid.UUID
    name: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
