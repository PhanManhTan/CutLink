from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "cutlink"
    db_user: str = "cutlink"
    db_password: SecretStr = SecretStr("cutlink-local-only")
    jwt_secret: str = Field(min_length=32)
    cookie_secure: bool = True
    allowed_origins: list[str] = ["http://localhost:5173"]
    cookie_name: str = "cutlink_session"
    jwt_hours: int = 8

    @property
    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
