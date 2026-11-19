from fastapi.responses import HTMLResponse


def unavailable_link() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link unavailable · Cutlink</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
padding:24px;background:#f4f7f1;color:#203b2b;font:16px/1.7 system-ui,sans-serif}
main{width:min(100%,480px);padding:36px;border:1px solid #dfe7da;
border-radius:20px;background:white}
.brand{font-size:24px;font-weight:800;letter-spacing:-1px}small{display:block;color:#697b61;margin-top:28px}
h1{font-size:clamp(26px,6vw,34px);line-height:1.25;letter-spacing:-1px}p{color:#63735c}
a{display:inline-block;padding:12px 20px;background:#244e37;color:white;
border-radius:9px;text-decoration:none}
a:focus-visible{outline:3px solid #8aaf60;outline-offset:4px}
</style></head><body><main><div class="brand">cutlink.</div><small>LINK UNAVAILABLE</small>
<h1>This link doesn’t lead anywhere.</h1>
<p>The address may be incorrect, or the link may have been paused or deleted.
Check the URL or ask the sender for a new link.</p>
<a href="/">Open Cutlink</a></main></body></html>""",
        status_code=404,
        headers={"Cache-Control": "no-store"},
    )
