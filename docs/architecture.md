# Architecture and limits

- Codes can be random (eight characters) or custom (3–64 characters), with a shared database uniqueness constraint. Random collisions retry; duplicate custom endings return `409`. Migration `0002` widens the column without changing existing links.
- Sessions are eight-hour HS256 JWTs in HttpOnly, SameSite=Lax cookies (Secure on AWS). Logout clears the browser cookie; there is no token revocation table, password reset, email verification or refresh token flow in this version.
- Redirects are direct HTTP 302 with `Cache-Control: no-store`. Cache entries live for 30 seconds; updates/deletes invalidate after commit. If invalidation fails or races another request, an old destination can remain visible for up to the cache TTL.
- Publishing uses short Redis socket deadlines and no request-side publish retry. Failed publishes do not block redirects. Click UUIDs deduplicate worker retries. Rollups upsert absolute UTC daily counts under a transaction advisory lock, so repeated runs do not add counts twice.
- Daily charts show the last 30 UTC days from the rollup table and refresh about once per minute; total clicks count processed events. Redis and queued events are ephemeral and may be lost on task replacement. Processed clicks, users and links persist in RDS.
- One tiny Fargate task and Single-AZ RDS favor a small demo. This setup accepts downtime and has no horizontal scaling or high availability. Search filters the current 20-link page and pagination covers the full account.


Missing short links return HTTP 404 with a Cutlink page. API errors remain JSON; form errors appear inline.

References: [ECS container health](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html), [Celery configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html).
