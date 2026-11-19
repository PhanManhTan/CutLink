"""Verify PostgreSQL outage/recovery against the local Compose stack."""

import argparse
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--wsl", action="store_true")
    args = parser.parse_args()

    def status(path):
        try:
            with urllib.request.urlopen(
                args.base_url.rstrip("/") + path, timeout=7
            ) as response:
                return response.status
        except urllib.error.HTTPError as error:
            error.close()
            return error.code

    def compose(*arguments):
        command = (["wsl", "-e"] if args.wsl else []) + [
            "docker",
            "compose",
            *arguments,
        ]
        subprocess.run(command, check=True, cwd=Path(__file__).resolve().parent.parent)

    try:
        compose("stop", "db")
        assert status("/api/health/live") == 200
        start = time.monotonic()
        assert status("/api/health/ready") == 503
        assert time.monotonic() - start < 5
        assert status("/r/database-outage-check") == 503
    finally:
        compose("up", "-d", "--wait", "--wait-timeout", "30", "db")
    assert status("/api/health/ready") == 200
    print("SQL outage: live=200, ready/redirect=503; readiness recovers to 200.")


if __name__ == "__main__":
    main()
