from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
# Readiness has its own short-lived connection and deadlines, even if the app pool is exhausted.
health_engine = create_engine(
    get_settings().sqlalchemy_url,
    poolclass=NullPool,
    connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
)


def get_db():
    with SessionLocal() as session:
        yield session
