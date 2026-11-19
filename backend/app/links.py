import re
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user
from app.database import get_db
from app.models import ClickEvent, Link, User
from app.schemas import (
    SHORT_CODE_PATTERN,
    DayStat,
    LinkCreate,
    LinkOut,
    LinkPage,
    LinkPatch,
    LinkStats,
)

router = APIRouter(tags=["links"])


def owned_link(link_id: uuid.UUID, user: User, db: Session) -> Link:
    link = db.scalar(select(Link).where(Link.id == link_id, Link.owner_id == user.id))
    if link is None:
        raise HTTPException(404, "Link not found")
    return link


def clicks_for(link_id: uuid.UUID, db: Session) -> int:
    return (
        db.scalar(select(func.count()).select_from(ClickEvent).where(ClickEvent.link_id == link_id))
        or 0
    )


@router.post("/api/links", response_model=LinkOut, status_code=201)
def create_link(
    body: LinkCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    for _ in range(5):
        link = Link(
            owner_id=user.id,
            name=body.name,
            target_url=str(body.target_url),
            code=body.custom_code
            or "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8)),
        )
        try:
            with db.begin_nested():
                db.add(link)
                db.flush()
            db.commit()
            return link
        except IntegrityError as exc:
            if getattr(exc.orig.diag, "constraint_name", "") != "links_code_key":
                raise
            if body.custom_code is not None:
                raise HTTPException(
                    409, "This short link is already taken. Choose another ending."
                ) from None
    raise HTTPException(503, "Please try again")


@router.get("/api/links", response_model=LinkPage)
def list_links(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    counts = (
        select(ClickEvent.link_id, func.count().label("clicks"))
        .group_by(ClickEvent.link_id)
        .subquery()
    )
    rows = db.execute(
        select(Link, func.coalesce(counts.c.clicks, 0))
        .outerjoin(counts, counts.c.link_id == Link.id)
        .where(Link.owner_id == user.id)
        .order_by(Link.created_at.desc(), Link.id)
        .offset(offset)
        .limit(limit)
    ).all()
    total, active = db.execute(
        select(func.count(), func.count().filter(Link.enabled.is_(True))).where(
            Link.owner_id == user.id
        )
    ).one()
    total_clicks = (
        db.scalar(
            select(func.count())
            .select_from(ClickEvent)
            .join(Link, ClickEvent.link_id == Link.id)
            .where(Link.owner_id == user.id)
        )
        or 0
    )
    return LinkPage(
        items=[
            LinkOut.model_validate(link).model_copy(update={"total_clicks": clicks})
            for link, clicks in rows
        ],
        total=total,
        active=active,
        total_clicks=total_clicks,
    )


@router.get("/api/links/{link_id}", response_model=LinkOut)
def get_link(link_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    link = owned_link(link_id, user, db)
    return LinkOut.model_validate(link).model_copy(update={"total_clicks": clicks_for(link.id, db)})


@router.patch("/api/links/{link_id}", response_model=LinkOut)
def update_link(
    link_id: uuid.UUID,
    body: LinkPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    link = owned_link(link_id, user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(link, field, str(value) if field == "target_url" else value)
    db.commit()
    return LinkOut.model_validate(link).model_copy(update={"total_clicks": clicks_for(link.id, db)})


@router.delete("/api/links/{link_id}", status_code=204)
def delete_link(
    link_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    link = owned_link(link_id, user, db)
    db.execute(delete(Link).where(Link.id == link.id))
    db.commit()


@router.get("/api/links/{link_id}/stats", response_model=LinkStats)
def stats(link_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    link = owned_link(link_id, user, db)
    today = datetime.now(UTC).date()
    start = today - timedelta(days=29)
    # Group the stored clicks directly; there is no background rollup to wait for.
    day = cast(func.timezone("UTC", ClickEvent.clicked_at), Date)
    rows = dict(
        db.execute(
            select(day, func.count())
            .where(
                ClickEvent.link_id == link.id,
                ClickEvent.clicked_at >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                ClickEvent.clicked_at
                < datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            )
            .group_by(day)
        ).all()
    )
    return LinkStats(
        total_clicks=clicks_for(link.id, db),
        days=[
            DayStat(day=start + timedelta(days=i), clicks=rows.get(start + timedelta(days=i), 0))
            for i in range(30)
        ],
    )


@router.get("/r/{code}")
def redirect(code: str, db: Session = Depends(get_db)):
    if not re.fullmatch(SHORT_CODE_PATTERN, code):
        raise HTTPException(404, "Link not found")
    # A shared row lock lets clicks run concurrently and serializes edits/deletion with this visit.
    link = db.scalar(
        select(Link).where(Link.code == code, Link.enabled.is_(True)).with_for_update(read=True)
    )
    if link is None:
        raise HTTPException(404, "Link not found")
    db.add(ClickEvent(id=uuid.uuid4(), link_id=link.id, clicked_at=datetime.now(UTC)))
    db.commit()
    return RedirectResponse(link.target_url, status_code=302, headers={"Cache-Control": "no-store"})
