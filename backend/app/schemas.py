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


class LinkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_url: HttpUrl = Field(max_length=4096)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if value is None:
            raise ValueError("Name cannot be null")
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class LinkPatch(LinkCreate):
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
