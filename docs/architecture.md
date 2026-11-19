# Architecture

```text
Browser → FastAPI → PostgreSQL
```

Locally, Vite serves React and proxies API/redirect requests. On AWS:

```text
User → CloudFront ┬→ private S3 (frontend, OAC)
                  └→ ALB → Fargate API → RDS PostgreSQL
```

The minimal ALB/RDS network has two public and two private subnets across two AZs. The API and database run in the primary AZ:

| Subnet | AZ | Resources |
| --- | --- | --- |
| PublicA | Primary | ALB node and one NAT gateway |
| PublicB | Secondary | ALB node; required by ALB |
| PrivateA | Primary | One API task and one Single-AZ RDS instance |
| PrivateB | Secondary | Empty; required by the RDS DB subnet group |

The API task uses 0.25 vCPU / 512 MB and has no public IP. A separate migration task runs only during releases. Both tasks use PrivateA. PrivateB has no task or standby database. There is no autoscaling, read replica or second NAT gateway. This is not a highly available application deployment.

ALB accepts port 80 only from the regional CloudFront origin-facing managed prefix list. Its listener forwards requests only when `X-Cutlink-Origin` matches this distribution's secret; other requests receive 403. The API accepts port 8000 only from ALB. PostgreSQL accepts port 5432 only from the task security group. Tasks use one NAT gateway for outbound HTTPS, including pulling the public GHCR image.

CloudFront serves static files with caching; API and redirect behaviors disable caching. CloudFront-to-ALB uses HTTP in this minimal setup; viewer-to-CloudFront uses HTTPS. See [AWS setup](aws.md) for the separate CloudFront Free plan enrollment step.

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

References: [ALB subnet requirements](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html), [RDS subnet requirements](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html), [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html), [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/).
