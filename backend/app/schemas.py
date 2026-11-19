import re
import uuid
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str


SHORT_CODE_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}"


class LinkFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    target_url: HttpUrl = Field(max_length=4096)

    @field_validator("target_url", mode="before")
    @classmethod
    def check_url_input(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not re.match(r"^https?://", value, re.IGNORECASE) or any(
                ord(char) < 32 or ord(char) == 127 for char in value
            ):
                raise ValueError("Enter a valid URL starting with http:// or https://")
        return value

    @field_validator("target_url")
    @classmethod
    def check_destination(cls, value):
        if value is not None:
            if value.username is not None or value.password is not None:
                raise ValueError("Destination URLs cannot contain a username or password")
            if len(str(value)) > 4096:
                raise ValueError("Destination URL must be at most 4096 characters")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if value is None:
            raise ValueError("Name cannot be null")
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class LinkCreate(LinkFields):
    custom_code: str | None = None

    @field_validator("custom_code")
    @classmethod
    def check_custom_code(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not re.fullmatch(SHORT_CODE_PATTERN, value):
            raise ValueError(
                "Use 3–64 letters, numbers, hyphens or underscores; start with a letter or number"
            )
        return value


class LinkPatch(LinkFields):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_url: HttpUrl | None = Field(default=None, max_length=4096)
    enabled: bool | None = None

    @model_validator(mode="after")
    def no_explicit_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Fields cannot be null")
        return self


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    target_url: str
    enabled: bool
    created_at: datetime
    total_clicks: int = 0


class LinkPage(BaseModel):
    items: list[LinkOut]
    total: int
    total_clicks: int
    active: int


class DayStat(BaseModel):
    day: date
    clicks: int


class LinkStats(BaseModel):
    total_clicks: int
    days: list[DayStat]
