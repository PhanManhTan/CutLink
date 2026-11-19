# CI and publication setup

The workflow in `.github/workflows/ci.yml` has two publication jobs after all tests pass:

| Event | CI tests and builds | Upload frontend to S3 | Publish backend to GHCR | Deploy backend to ECS |
| --- | --- | --- | --- | --- |
| Feature branch push / pull request | Yes | No | No | No |
| Push / merge to `main` | Yes | Yes | Yes | No |
| Manual run on `main`, `publish_release=false` | Yes | No | No | No |
| Manual run on `main`, `publish_release=true` | Yes | Yes | Yes | No |

Frontend publication reuses the `frontend-dist` artifact produced by the frontend CI job. Hashed assets are uploaded first, other public files next, and `index.html` last. Existing assets are retained for rollback. The index has `Cache-Control: no-cache`; hashed assets have a one-year immutable cache policy. Main workflows finish in sequence so a newer run cannot cancel an upload halfway through.

Backend publication builds the `production` Dockerfile target for Linux AMD64, pushes `ghcr.io/phanmanhtan/cutlink:<full-commit-sha>` and `:latest`, and uploads a `backend-image.txt` artifact containing the immutable `image@sha256:...` reference. It uses the built-in `GITHUB_TOKEN`. There are no ECS, migration, or CloudFormation deployment commands in these publication jobs. Backend deployment and migration remain a separate operator action. Frontend changes must support the currently deployed API; deploy a required backend capability before publishing a frontend that depends on it.

## 1. Prepare AWS hosting

No AWS resources are created by the workflow. Use an existing frontend bucket, or provision the hosting infrastructure separately using `infra/base.yaml` when ready. For the bundled architecture use its `FrontendBucket` and `DistributionId` outputs. The bucket stays private; CloudFront reads it using OAC. S3 versioning preserves previous index versions. The distribution routes `/api/*` and `/r/*` to the API origin.

## 2. Add GitHub's OIDC provider to AWS

In AWS IAM, add an OpenID Connect identity provider if the account does not already have one:

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Create an IAM role for the frontend publication job. Its trust policy should restrict the repository and production environment:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:PhanManhTan@150802908/CutLink@1464239414:environment:production"
      }
    }
  }]
}
```

This repository was created after July 15, 2026, so the example uses GitHub's default immutable subject format with owner/repository IDs. If you have explicitly changed the repository's OIDC subject configuration, match that configuration instead. The legacy name-only format is `repo:PhanManhTan/CutLink:environment:production`; use it only when the repository is configured to issue that subject. Do not replace the repository/environment restriction with a wildcard.

Attach this permissions policy, replacing the account, bucket and distribution IDs. Omit the CloudFront statement if you will not configure invalidation:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::YOUR_FRONTEND_BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::YOUR_FRONTEND_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"],
      "Resource": "arn:aws:cloudfront::YOUR_ACCOUNT_ID:distribution/YOUR_DISTRIBUTION_ID"
    }
  ]
}
```

The bundled bucket uses SSE-S3 encryption. A custom bucket using a customer-managed KMS key also needs the corresponding KMS permissions. The role above cannot delete S3 objects, update ECS, change CloudFormation stacks, or read application secrets.

## 3. Configure GitHub's production environment

Go to **Repository Settings → Environments → New environment**, name it `production`, and restrict deployment branches to `main`. Add these **environment variables**:

| Variable | Required | Example / source |
| --- | --- | --- |
| `AWS_REGION` | Yes | `ap-southeast-1` |
| `AWS_ROLE_ARN` | Yes | `arn:aws:iam::123456789012:role/cutlink-frontend-publisher` |
| `FRONTEND_BUCKET` | Yes | Bucket name only, without `s3://`; use base stack `FrontendBucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | Optional | Use base stack `DistributionId`; enables index invalidation and wait |

No long-lived AWS access key is needed. The workflow requests a short-lived identity using OIDC. Until the required variables exist, feature branch/PR CI still works; a main release's frontend publication fails with an explicit missing-variable message. The backend publishing job is independent and can still publish its image.

For GHCR, GitHub's automatic token needs package write permission, which is declared only on the backend publication job. If an existing package belongs to this repository, ensure the repository has Actions access to that package. After the first publish, make the package public in GitHub package settings if ECS will pull without registry credentials, as the bundled infrastructure expects.

## 4. Run and inspect

Merge a tested change into `main`, or use **Actions → CI / CD → Run workflow**, choose `main` and enable `publish_release`. Inspect both CD jobs and their summaries. Download `backend-image` for the immutable image digest. If tests fail, neither publication job runs. If publishing frontend fails, fix the AWS environment configuration and rerun the failed job. Restore an earlier S3 index version and invalidate `/index.html` to roll back the frontend; old hashed assets remain available.

Official references: [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [Publishing Docker images](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
