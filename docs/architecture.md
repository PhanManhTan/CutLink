# Architecture

```text
Browser → FastAPI → PostgreSQL
```

Locally, Vite serves React and proxies API/redirect requests. On AWS, CloudFront serves private S3 assets and sends `/api/*` and `/r/*` to ALB/Fargate. The application task contains one API container (0.25 vCPU / 512 MB).

## Clicks

1. Backend finds an enabled short code in PostgreSQL.
2. It inserts one click event and commits the transaction.
3. It returns HTTP 302 to the destination.

Totals and the last 30 UTC days are queried from stored click events. There is no scheduled rollup or background consumer. Missing/paused links return the Cutlink 404 page and do not create a click. Database failure returns 503 rather than reporting a successful redirect without its click.

Clicks are redirect requests, not unique visitors or proof that the destination finished loading. Refreshes and bots may count. The dashboard updates after actions, when the window regains focus, or via Refresh; it does not poll while idle.

## Code organization

- **Transaction Script:** each auth/link operation is a small function with an explicit transaction. FastAPI injects a SQLAlchemy session. No generic CRUD framework is needed.
- **Container/presentation:** `useLinks` handles requests and state; Dashboard and LinkTable render the workspace and collect user actions.
- CSS is grouped by base, workspace, forms, auth and responsive behavior.

The active data model is users, links and click_events. Earlier migrations retain the old daily_link_stats table so existing databases and older release rollback remain compatible; current code never reads it. Existing user/link/click data is not reset by this refactor.

## Constraints

- Custom codes: 3–64 case-sensitive letters/numbers/hyphens/underscores; blank means a random eight-character code. Unique across accounts.
- Destination validation checks HTTP/HTTPS URL structure, not whether the website is currently online.
- Passwords use Argon2. Login uses an eight-hour HttpOnly, SameSite=Lax JWT cookie, Secure on AWS. Mutations require an allowed Origin. Logout clears the cookie; there is no token revocation table.
- Single-task Fargate and Single-AZ RDS accept deployment downtime. Infrastructure and release operations are described in [AWS setup](aws.md).

References: [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html), [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/), [ECS health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html).
