import logging
import uuid
from datetime import datetime

from celery import Celery
from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import SessionLocal
from app.models import ClickEvent, DailyLinkStat, Link

logger = logging.getLogger(__name__)
celery = Celery("cutlink", broker=get_settings().redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_ignore_result=True,
    task_publish_retry=False,
    broker_pool_limit=0,
    broker_connection_timeout=0.2,
    broker_transport_options={
        "socket_connect_timeout": 0.2,
        "socket_timeout": 0.2,
        "retry_on_timeout": False,
        "max_retries": 0,
        "visibility_timeout": 300,
    },
    worker_prefetch_multiplier=1,
    beat_schedule={"daily-click-rollup": {"task": "app.tasks.aggregate_clicks", "schedule": 60.0}},
)


@celery.task(
    name="app.tasks.record_click",
    bind=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def record_click(self, event_id: str, link_id: str, clicked_at: str):
    with SessionLocal.begin() as db:
        # Lock the parent against deletion until the insert commits. Deleted links are skipped.
        parent = db.scalar(select(Link.id).where(Link.id == uuid.UUID(link_id)).with_for_update())
        if parent is None:
            return
        db.execute(
            insert(ClickEvent)
            .values(
                id=uuid.UUID(event_id),
                link_id=parent,
                clicked_at=datetime.fromisoformat(clicked_at),
            )
            .on_conflict_do_nothing(index_elements=[ClickEvent.id])
        )


@celery.task(name="app.tasks.aggregate_clicks", autoretry_for=(Exception,), retry_backoff=True)
def aggregate_clicks():
    with SessionLocal.begin() as db:
        # Serialize rollups: a stale concurrent snapshot must not overwrite newer counts.
        db.execute(text("SELECT pg_advisory_xact_lock(4317461)"))
        day = cast(func.timezone("UTC", ClickEvent.clicked_at), Date)
        counts = select(ClickEvent.link_id, day, func.count()).group_by(ClickEvent.link_id, day)
        statement = insert(DailyLinkStat).from_select(["link_id", "day", "clicks"], counts)
        db.execute(
            statement.on_conflict_do_update(
                index_elements=[DailyLinkStat.link_id, DailyLinkStat.day],
                set_={"clicks": statement.excluded.clicks},
            )
        )
