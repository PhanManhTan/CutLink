"""Stop real Compose dependencies and verify redirect/readiness fallback and recovery."""

import argparse
import subprocess
import time
import uuid
from pathlib import Path

from check_background import make_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument(
        "--wsl", action="store_true", help="Run Docker via wsl.exe from Windows"
    )
    args = parser.parse_args()
    request = make_client(args.base_url.rstrip("/"))

    def compose(*arguments):
        command = (["wsl", "-e"] if args.wsl else []) + [
            "docker",
            "compose",
            *arguments,
        ]
        subprocess.run(command, check=True, cwd=Path(__file__).resolve().parent.parent)

    status, _, _ = request(
        "/api/auth/register",
        "POST",
        {
            "email": f"outage-{uuid.uuid4().hex}@example.com",
            "password": uuid.uuid4().hex,
        },
    )
    assert status == 201
    status, _, link = request(
        "/api/links",
        "POST",
        {
            "name": "Outage fallback",
            "target_url": "https://example.com/fallback",
        },
    )
    assert status == 201
    try:
        compose("stop", "redis")
        start = time.monotonic()
        status, headers, _ = request(f"/r/{link['code']}")
        assert status == 302 and headers["Location"] == "https://example.com/fallback"
        assert time.monotonic() - start < 2, "Failed Redis blocked the redirect"
        assert request("/api/health/ready")[0] == 200
        compose("start", "redis")
        compose("stop", "db")
        assert request("/api/health/live")[0] == 200
        start = time.monotonic()
        assert request("/api/health/ready")[0] == 503
        assert time.monotonic() - start < 5, "Readiness exceeded database deadlines"
        compose("start", "db")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if request("/api/health/ready")[0] == 200:
                print("Redis fallback, SQL outage and SQL recovery all passed.")
                break
            time.sleep(1)
        else:
            raise AssertionError("Database readiness did not recover")
    finally:
        compose("start", "db", "redis")
        request(f"/api/links/{link['id']}", "DELETE")


if __name__ == "__main__":
    main()
