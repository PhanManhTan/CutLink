"""Verify a failing Compose migration cannot start the API; restore the local stack."""

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent

    def compose(*args, check=True, capture=False):
        return subprocess.run(
            ["docker", "compose", *args],
            cwd=root,
            check=check,
            capture_output=capture,
            text=True,
        )

    compose("stop", "api", "frontend")
    try:
        result = compose(
            "-f",
            "compose.yaml",
            "-f",
            "scripts/compose.migration-failure.yaml",
            "up",
            "-d",
            "api",
            check=False,
        )
        assert result.returncode != 0, (
            "Expected startup to reject the failing migration"
        )
        state = compose("ps", "--status", "running", "-q", "api", capture=True)
        assert not state.stdout.strip(), (
            "API incorrectly started after a failed migration"
        )
        print("Migration failure kept API stopped.")
    finally:
        compose("up", "-d", "--wait", "--wait-timeout", "180")


if __name__ == "__main__":
    main()
