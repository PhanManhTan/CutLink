# GitHub Actions

## What runs

| Event | CI | CD |
| --- | --- | --- |
| Push to `feat/**` | Tests and builds | No |
| PR targeting `main` | Tests and builds | No |
| Push/merge to `main` | Tests, builds, release artifacts | After CI succeeds |
| Manual CI | Tests and builds | No |
| Manual CD | Validates a supplied main CI run ID | Publishes that tested release |

`ci.yml` is named **CI**. `cd.yml` listens for its completed `workflow_run` on main. CD verifies the run succeeded, came from this repository's main push, and matches the current main SHA. Superseded runs are skipped. Both files must be on the default branch before this chain can run. See [GitHub workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run).

## Release sequence

1. CI exports the tested backend image and frontend build on main pushes.
2. CD loads the image, tags it with the CI commit SHA, and pushes it to GHCR. There is no second build.
3. CD checks anonymous pull access. Make the GHCR package public for this demo.
4. New application and migration task revisions use the same image digest.
5. The old task stops completely, including Beat. A separate private Fargate task runs migration.
6. Only exit code `0` permits application startup. CD waits for ECS stability and ALB readiness.
7. CD uploads frontend assets, then index.html, and invalidates the CloudFront index.

Migration failure leaves the app stopped and prevents frontend publication. The `fargate-release-state` artifact records the previous task definition. CD runs are serialized and never canceled midway by a newer CI run. Artifact download and checkout use the verified CI run ID and SHA, never PR/feature artifacts.

## Configure production once

Complete [AWS setup](aws.md). In **Repository Settings → Environments**, create `production`, restrict deployments to main, and add:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | Region of your stacks |
| `AWS_ROLE_ARN` | `RoleArn` from `cutlink-github` |
| `BASE_STACK_NAME` | `cutlink-base` |
| `APP_STACK_NAME` | `cutlink-app` |
| `FRONTEND_BUCKET` | Base stack `FrontendBucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | Base stack `DistributionId`; enables invalidation |
| `SITE_URL` | Base stack `SiteUrl`; enables final smoke test |

OIDC replaces long-lived AWS keys. The IAM template grants release access to the existing ECS service, task roles, bucket and distribution. It cannot create VPC/RDS infrastructure or read application secrets. Its default subject is:

```text
repo:PhanManhTan@150802908/CutLink@1464239414:environment:production
```

If you customized the OIDC subject, set `RepositorySubject` to the exact issued value. The legacy name-only subject applies only if explicitly configured. See [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

GHCR uses `GITHUB_TOKEN` with package write permission. An existing package must grant this repository Actions access. Make it public before the first Fargate release. See [GitHub container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Trigger or retry

- Normal release: merge to main; CI runs, then CD.
- Retry: rerun failed CD jobs after correcting configuration.
- Manual CD: enter a successful CI run ID from a push to the current main commit. Manual CI runs do not export the release image and are rejected.

Without production variables, CD fails before assuming an AWS role. Feature CI never publishes. A feature test cannot verify a real AWS release.

## Release speed

The backend image and frontend are built once, tested, and promoted unchanged. CD updates task revisions and the existing service; it does not rebuild or redeploy CloudFormation/RDS/VPC. Image pull, startup, migration and health checks still determine duration.

This single-task demo accepts downtime to keep one Beat running. Health grace is tolerance for startup errors, not a mandatory delay before healthy traffic. See [ECS service updates](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-parameters.html).
