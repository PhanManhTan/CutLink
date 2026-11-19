# AWS setup

Set up infrastructure once. Routine CD reuses it.

## 1. Bootstrap

Prerequisites: AWS CLI v2 authenticated to your account, PowerShell 7, Docker/buildx, npm, and `docker login ghcr.io`. Choose an AWS region with two AZs and `db.t4g.micro` support.

If AWS CLI is not authenticated yet, follow [AWS CLI authentication](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) first. Confirm the intended account with `aws sts get-caller-identity --profile YOUR_PROFILE`.

From a committed checkout:

```powershell
pwsh -File scripts/deploy.ps1 `
  -ProjectName cutlink -Region ap-southeast-1 -Profile YOUR_PROFILE `
  -ImageRepository ghcr.io/phanmanhtan/cutlink
```

The script creates base/app stacks, builds the initial image, migrates the database, starts Fargate, uploads frontend and checks the app. If the first GHCR push creates a private package, make it public and rerun. Anonymous-pull validation happens before replacing an existing service.

The demo uses a NAT gateway, ALB, private Fargate, private PostgreSQL RDS, private S3 and CloudFront. These incur AWS charges while they exist. The first setup is slower than subsequent image releases.

Read the outputs:

```powershell
aws cloudformation describe-stacks --stack-name cutlink-base --query 'Stacks[0].Outputs' --profile YOUR_PROFILE --region ap-southeast-1
aws cloudformation describe-stacks --stack-name cutlink-app --query 'Stacks[0].Outputs' --profile YOUR_PROFILE --region ap-southeast-1
```

Record base outputs `FrontendBucket`, `DistributionId`, `SiteUrl` and app output `ServiceName`.

## 2. Allow GitHub releases

In IAM, create the OIDC provider if absent: URL `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`. Use its ARN below:

```powershell
aws cloudformation deploy --stack-name cutlink-github `
  --template-file infra/github-actions.yaml --capabilities CAPABILITY_IAM `
  --profile YOUR_PROFILE --region ap-southeast-1 `
  --parameter-overrides BaseStackName=cutlink-base AppStackName=cutlink-app `
  ServiceName=SERVICE_NAME FrontendBucket=BUCKET_NAME DistributionId=DISTRIBUTION_ID `
  OidcProviderArn=arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

Copy its `RoleArn` output into the [GitHub production variables](github-actions.md#configure-production-once). Merge both workflows into main. No AWS keys are committed.

Task families are `cutlink-app-application` and `cutlink-app-migration`. If an older deployment used generated families, update the app stack to the current template before using the restricted role.

## 3. Routine deploy

Push a feature branch, open a PR and merge after CI. Main CI runs again, then CD publishes the tested image, migrates, updates Fargate and uploads frontend.

For a CLI release of an existing public digest:

```powershell
$env:AWS_PROFILE = 'YOUR_PROFILE'
$env:AWS_DEFAULT_REGION = 'ap-southeast-1'
python scripts/release_fargate.py --base-stack cutlink-base --app-stack cutlink-app --image ghcr.io/phanmanhtan/cutlink@sha256:FULL_DIGEST
```

Do not run manual and automatic releases together. This script needs an existing service; bootstrap creates it.

CloudFormation owns infrastructure. After CD starts managing releases, the live ECS service is the source of truth for its current task definition; app stack outputs still describe the bootstrap revision. Schedule infrastructure stack updates separately, then release the intended digest again if needed.

## Recovery and teardown

View logs:

```powershell
aws logs tail /ecs/cutlink --follow --profile YOUR_PROFILE --region ap-southeast-1
```

Migration failed: the app stays stopped. Inspect migration logs, fix and release again. Never automatically downgrade the database.

Application rollback: download `fargate-release-state` from CD. Stop the service with desired count 0, wait for its tasks to become `STOPPED`, then set the saved `previousTaskDefinition` with desired count 1. Wait for ECS stability and ALB health. Database changes must support the previous image.

Frontend rollback: restore an earlier S3 index.html version and invalidate `/index.html`. Old hashed assets remain available.

Delete stacks in order: `cutlink-github`, `cutlink-app`, `cutlink-base`. Wait for each deletion. The base retains a final RDS snapshot, S3 bucket and logs; record them before teardown. Retained storage continues to incur charges until explicitly removed.

References: [CloudFormation stacks](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacks.html), [ECS task definitions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html), [ECS update-service](https://docs.aws.amazon.com/cli/latest/reference/ecs/update-service.html).
