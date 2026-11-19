"""Exercise API -> Redis -> worker -> PostgreSQL -> Beat using the standard library."""

import argparse
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_client(base_url):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect()
    )

    def request(path, method="GET", body=None):
        headers = {"Origin": base_url, "Content-Type": "application/json"}
        req = urllib.request.Request(
            base_url + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            content = response.read()
            return (
                response.status,
                response.headers,
                json.loads(content) if content else None,
            )

    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    args = parser.parse_args()
    request = make_client(args.base_url.rstrip("/"))
    status, _, _ = request(
        "/api/auth/register",
        "POST",
        {
            "email": f"background-{uuid.uuid4().hex}@example.com",
            "password": uuid.uuid4().hex,
        },
    )
    assert status == 201, f"Registration: {status}"
    status, _, link = request(
        "/api/links",
        "POST",
        {
            "name": "Background pipeline test",
            "target_url": "https://example.com/background",
        },
    )
    assert status == 201, f"Create: {status}"
    try:
        status, headers, _ = request(f"/r/{link['code']}")
        assert status == 302, status
        assert headers["Location"] == "https://example.com/background"
        deadline = time.monotonic() + 85
        while time.monotonic() < deadline:
            status, _, stats = request(f"/api/links/{link['id']}/stats")
            assert status == 200, status
            if (
                stats["total_clicks"] == 1
                and sum(day["clicks"] for day in stats["days"]) == 1
            ):
                print("Real worker saved one click; Beat rolled it up exactly once.")
                break
            time.sleep(1)
        else:
            raise AssertionError(f"Background processing deadline exceeded: {stats}")
    finally:
        request(f"/api/links/{link['id']}", "DELETE")


if __name__ == "__main__":
    main()
