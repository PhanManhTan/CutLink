import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import Credentials, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
# Bound Argon2 memory for the 1 GB task; still uses Argon2id.
hasher = PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1)
dummy_hash = hasher.hash("dummy-password-for-timing-only")


def set_session(response: Response, user: User) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(hours=settings.jwt_hours)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.jwt_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    try:
        claims = jwt.decode(
            request.cookies.get(settings.cookie_name, ""),
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"]},
        )
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Please sign in") from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Please sign in")
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = User(email=str(body.email), password_hash=hasher.hash(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from None
    set_session(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    try:
        hasher.verify(user.password_hash if user else dummy_hash, body.password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, "Email or password is incorrect") from None
    if user is None:
        raise HTTPException(401, "Email or password is incorrect")
    set_session(response, user)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
