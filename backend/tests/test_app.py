import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app import cache
from app.auth import settings
from app.database import SessionLocal
from app.main import app
from app.models import ClickEvent, DailyLinkStat
from app.tasks import aggregate_clicks, record_click


def test_auth_cookie_and_duplicate_email(client):
    body = {"email": "HELLO@example.com", "password": "long-enough-password"}
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201
    assert response.json()["email"] == "hello@example.com"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=28800" in cookie
    assert client.post("/api/auth/register", json=body).status_code == 409
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post("/api/auth/login", json={**body, "password": "wrong-password"}).status_code
        == 401
    )
    assert client.post("/api/auth/login", json=body).status_code == 200


def test_expired_session_and_secure_cookie(client):
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=9),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret,
    )
    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/auth/me").status_code == 401
    with patch.object(settings, "cookie_secure", True):
        response = client.post(
            "/api/auth/register",
            json={
                "email": "secure@example.com",
                "password": "long-enough-password",
            },
        )
    assert "Secure" in response.headers["set-cookie"]


def test_origin_and_unauthenticated_access(client):
    assert client.get("/api/links").status_code == 401
    assert (
        client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    with TestClient(app) as bare:
        assert bare.post("/api/auth/logout").status_code == 403


def test_user_isolation(logged_in, link):
    with TestClient(app, headers={"Origin": "http://testserver"}) as other:
        other.post(
            "/api/auth/register",
            json={
                "email": "other@example.com",
                "password": "other-password-123",
            },
        )
        assert other.get("/api/links").json()["total"] == 0
        for method, suffix, body in [
            ("GET", "", None),
            ("PATCH", "", {"name": "Stolen"}),
            ("DELETE", "", None),
            ("GET", "/stats", None),
        ]:
            assert (
                other.request(method, f"/api/links/{link['id']}{suffix}", json=body).status_code
                == 404
            )


def test_crud_redirect_and_cache_invalidation(logged_in, link):
    path = f"/r/{link['code']}"
    with patch("app.links.record_click.apply_async"):
        assert len(link["code"]) == 8
        response = logged_in.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "https://example.com/work?ref=short"
        assert response.headers["cache-control"] == "no-store"
        updated = logged_in.patch(
            f"/api/links/{link['id']}",
            json={
                "target_url": "https://example.org/new",
                "name": "Renamed",
            },
        )
        assert updated.status_code == 200
        assert (
            logged_in.get(path, follow_redirects=False).headers["location"]
            == "https://example.org/new"
        )
        logged_in.patch(f"/api/links/{link['id']}", json={"enabled": False})
        assert logged_in.get(path).status_code == 404
        logged_in.patch(f"/api/links/{link['id']}", json={"enabled": True})
        assert logged_in.get(path, follow_redirects=False).status_code == 302
        assert logged_in.delete(f"/api/links/{link['id']}").status_code == 204
        assert logged_in.get(path).status_code == 404


def test_url_validation(logged_in):
    for url in ["javascript:alert(1)", "ftp://example.com", "not-a-url"]:
        assert (
            logged_in.post("/api/links", json={"name": "Test", "target_url": url}).status_code
            == 422
        )
    assert (
        logged_in.post(
            "/api/links", json={"name": "   ", "target_url": "https://example.com"}
        ).status_code
        == 422
    )


def test_patch_rejects_null(logged_in, link):
    for field in ["name", "target_url", "enabled"]:
        assert logged_in.patch(f"/api/links/{link['id']}", json={field: None}).status_code == 422


@pytest.mark.parametrize("ending", [None, "", "   "])
def test_empty_custom_ending_is_random(logged_in, ending):
    response = logged_in.post(
        "/api/links",
        json={
            "name": "Random ending",
            "target_url": "https://example.com",
            "custom_code": ending,
        },
    )
    assert response.status_code == 201
    assert len(response.json()["code"]) == 8
    assert response.json()["code"].isalnum()


@pytest.mark.parametrize("ending", ["my-portfolio", "My_custom-link", "abc", "z" * 64])
def test_custom_ending_redirect_and_crud(logged_in, ending):
    response = logged_in.post(
        "/api/links",
        json={
            "name": "Custom ending",
            "target_url": "https://example.com/custom",
            "custom_code": ending,
        },
    )
    assert response.status_code == 201
    link_id = response.json()["id"]
    assert response.json()["code"] == ending
    with patch("app.links.record_click.apply_async"):
        redirect = logged_in.get(f"/r/{ending}", follow_redirects=False)
        assert redirect.status_code == 302
        assert redirect.headers["location"] == "https://example.com/custom"
        assert (
            logged_in.patch(
                f"/api/links/{link_id}",
                json={
                    "target_url": "https://example.org/changed",
                },
            ).status_code
            == 200
        )
        assert logged_in.get(f"/r/{ending}", follow_redirects=False).headers["location"] == (
            "https://example.org/changed"
        )
        assert logged_in.patch(f"/api/links/{link_id}", json={"enabled": False}).status_code == 200
        assert logged_in.get(f"/r/{ending}").status_code == 404
        assert logged_in.delete(f"/api/links/{link_id}").status_code == 204
        assert logged_in.get(f"/r/{ending}").status_code == 404


def test_custom_ending_is_unique_across_users(logged_in):
    body = {"name": "Custom", "target_url": "https://example.com", "custom_code": "my-custom"}
    assert logged_in.post("/api/links", json=body).status_code == 201
    assert logged_in.post("/api/links", json=body).status_code == 409
    with TestClient(app, headers={"Origin": "http://testserver"}) as other:
        assert (
            other.post(
                "/api/auth/register",
                json={
                    "email": "other@example.com",
                    "password": "another-password-123",
                },
            ).status_code
            == 201
        )
        assert other.post("/api/links", json=body).status_code == 409
        # Endings are explicitly case-sensitive, just like existing random codes.
        assert (
            other.post("/api/links", json={**body, "custom_code": "My-Custom"}).status_code == 201
        )


@pytest.mark.parametrize(
    "ending",
    [
        "a",
        "ab",
        "a" * 65,
        "my link",
        "my/link",
        "?query",
        "#hash",
        "_start",
        "mã-link",
        "https://example.com",
    ],
)
def test_invalid_custom_endings_are_rejected(logged_in, ending):
    assert (
        logged_in.post(
            "/api/links",
            json={
                "name": "Invalid ending",
                "target_url": "https://example.com",
                "custom_code": ending,
            },
        ).status_code
        == 422
    )
    assert logged_in.get("/api/links").json()["total"] == 0


def test_short_code_cannot_be_changed_by_patch(logged_in, link):
    for field in ["code", "custom_code"]:
        assert (
            logged_in.patch(f"/api/links/{link['id']}", json={field: "new-ending"}).status_code
            == 422
        )
    assert logged_in.get(f"/api/links/{link['id']}").json()["code"] == link["code"]


@pytest.mark.parametrize(
    "url",
    [
        "https:/example.com",
        "http://",
        "https://exa mple.com",
        "https://example.com:99999",
        "https://user:password@example.com",
        "https://example.com/\r\nnext",
    ],
)
def test_invalid_destinations_on_create_and_update(logged_in, link, url):
    assert (
        logged_in.post("/api/links", json={"name": "Invalid", "target_url": url}).status_code == 422
    )
    assert logged_in.patch(f"/api/links/{link['id']}", json={"target_url": url}).status_code == 422
    assert logged_in.get(f"/api/links/{link['id']}").json()["target_url"] == link["target_url"]


def test_valid_destination_is_normalized(logged_in):
    response = logged_in.post(
        "/api/links",
        json={
            "name": "Valid",
            "target_url": "  HTTPS://EXAMPLE.COM/path?q=value#section  ",
            "custom_code": "  my-link  ",
        },
    )
    assert response.status_code == 201
    assert response.json()["target_url"] == "https://example.com/path?q=value#section"
    assert response.json()["code"] == "my-link"


def test_code_collision_retries(logged_in):
    with patch("app.links.secrets.choice", return_value="a"):
        assert (
            logged_in.post(
                "/api/links",
                json={
                    "name": "First",
                    "target_url": "https://example.com",
                },
            ).status_code
            == 201
        )
    with patch("app.links.secrets.choice", side_effect=list("aaaaaaaaBBBBBBBB")):
        response = logged_in.post(
            "/api/links",
            json={
                "name": "Collision",
                "target_url": "https://example.com",
            },
        )
    assert response.status_code == 201
    assert response.json()["code"] == "BBBBBBBB"


def test_redis_and_publisher_failure_do_not_block_redirect(logged_in, link):
    with (
        patch.object(cache.cache, "get", side_effect=RedisConnectionError),
        patch.object(cache.cache, "setex", side_effect=RedisConnectionError),
        patch("app.links.record_click.apply_async", side_effect=RedisConnectionError),
    ):
        response = logged_in.get(f"/r/{link['code']}", follow_redirects=False)
    assert response.status_code == 302


def test_actual_dead_broker_has_short_publish_deadline():
    from app.tasks import celery

    # An actual refused TCP connection exercises Kombu/Redis retry configuration.
    start = time.monotonic()
    with celery.connection_for_write(url="redis://127.0.0.1:1/0") as connection:
        try:
            record_click.apply_async(args=["unused"] * 3, connection=connection, retry=False)
        except Exception:
            pass
        else:
            raise AssertionError("Dead broker unexpectedly accepted a task")
    assert time.monotonic() - start < 1.5


def test_event_and_rollup_idempotency(logged_in, link):
    event = str(uuid.uuid4())
    timestamp = datetime.now(UTC).replace(hour=12).isoformat()
    record_click.run(event, link["id"], timestamp)
    record_click.run(event, link["id"], timestamp)
    aggregate_clicks.run()
    aggregate_clicks.run()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ClickEvent)) == 1
        assert db.scalar(select(DailyLinkStat.clicks)) == 1
    response = logged_in.get(f"/api/links/{link['id']}/stats").json()
    assert response["total_clicks"] == 1
    assert len(response["days"]) == 30
    assert sum(day["clicks"] for day in response["days"]) == 1
    assert logged_in.get("/api/links").json()["total_clicks"] == 1
    assert logged_in.get("/api/links").json()["items"][0]["total_clicks"] == 1
    logged_in.delete(f"/api/links/{link['id']}")
    record_click.run(str(uuid.uuid4()), link["id"], timestamp)  # Late delivery after delete.
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ClickEvent)) == 0


def test_utc_rollup(logged_in, link):
    record_click.run(str(uuid.uuid4()), link["id"], "2026-01-02T00:30:00+07:00")
    aggregate_clicks.run()
    with SessionLocal() as db:
        assert str(db.scalar(select(DailyLinkStat.day))) == "2026-01-01"


def test_liveness_readiness_and_recovery(client):
    assert client.get("/api/health/live").status_code == 200
    assert client.get("/api/health/ready").status_code == 200
    with patch(
        "app.health.health_engine.connect", side_effect=OperationalError("", {}, Exception())
    ):
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/health/ready").status_code == 503
    assert client.get("/api/health/ready").status_code == 200


def test_missing_short_link_has_a_readable_page(client):
    response = client.get("/r/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "ask the sender for a new link" in response.text
    # API errors stay JSON with their original status.
    assert (
        client.get("/api/no-such-endpoint").headers["content-type"].startswith("application/json")
    )
