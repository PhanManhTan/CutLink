#Requires -Version 7.0
[CmdletBinding()]
param(
    [string]$ProjectName = 'cutlink',
    [Parameter(Mandatory)][string]$Region,
    [Parameter(Mandatory)][ValidatePattern('^ghcr\.io/[a-z0-9._/-]+$')][string]$ImageRepository,
    [string]$Profile
)
. "$PSScriptRoot/common.ps1"
$root = Split-Path $PSScriptRoot -Parent
$stateDirectory = Join-Path $root '.deploy'
$lock = Enter-DeployLock $stateDirectory
$previousRegion = $env:AWS_DEFAULT_REGION
$previousProfile = $env:AWS_PROFILE
try {
    $env:AWS_DEFAULT_REGION = $Region
    if ($Profile) { $env:AWS_PROFILE = $Profile }
    Push-Location $root
    try {
        Get-AwsJson @('sts', 'get-caller-identity') | Select-Object Account, Arn | Format-List | Out-Host
        foreach ($tool in @('docker', 'npm', 'git')) { Get-Command $tool -ErrorAction Stop | Out-Null }
        $dirty = & git status --porcelain
        if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit all changes before deploying a commit-SHA release.' }
        $sha = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Could not read commit SHA' }
        # Checks run before any infrastructure changes.
        Invoke-Native aws @('cloudformation', 'validate-template', '--template-body', 'file://infra/base.yaml')
        Invoke-Native aws @('cloudformation', 'validate-template', '--template-body', 'file://infra/app.yaml')
        Push-Location frontend
        try { Invoke-Native npm @('ci'); Invoke-Native npm @('run', 'build') } finally { Pop-Location }

        $baseName = "$ProjectName-base"
        $appName = "$ProjectName-app"
        Invoke-Native aws @('cloudformation', 'deploy', '--stack-name', $baseName,
            '--template-file', 'infra/base.yaml', '--capabilities', 'CAPABILITY_IAM',
            '--parameter-overrides', "ProjectName=$ProjectName", '--no-fail-on-empty-changeset')
        $base = Get-StackOutputs $baseName

        $tag = "${ImageRepository}:$sha"
        Invoke-Native docker @('buildx', 'build', '--platform', 'linux/amd64', '--push', '--tag', $tag, './backend')
        # GHCR must be public. A pull without credentials detects a private package before stopping ECS.
        $dockerConfig = Join-Path $stateDirectory 'anonymous-docker'
        New-Item -ItemType Directory -Path $dockerConfig -Force | Out-Null
        $digestJson = & docker --config $dockerConfig buildx imagetools inspect $tag --format '{{json .Manifest}}'
        if ($LASTEXITCODE -ne 0) { throw 'GHCR image is not publicly readable. Set the package visibility to public and rerun.' }
        $digest = (($digestJson -join "`n") | ConvertFrom-Json).digest
        if ($digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Cannot determine backend digest' }
        $image = "${ImageRepository}@$digest"

        # A first deployment has no app stack. All other errors remain fatal.
        $stacks = Get-AwsJson @('cloudformation', 'list-stacks', '--stack-status-filter',
            'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE')
        $existing = @($stacks.StackSummaries | Where-Object StackName -eq $appName)
        $previous = $null
        if ($existing.Count -gt 0) {
            $old = Get-StackOutputs $appName
            $task = Get-AwsJson @('ecs', 'describe-task-definition', '--task-definition', $old.ApplicationTaskArn)
            $previousImage = @($task.taskDefinition.containerDefinitions | Where-Object name -eq 'api')[0].image
            $versions = Get-AwsJson @('s3api', 'list-object-versions', '--bucket', $base.FrontendBucket, '--prefix', 'index.html')
            $indexVersion = @($versions.Versions | Where-Object { $_.Key -eq 'index.html' -and $_.IsLatest }) | Select-Object -First 1
            $previous = @{
                backendImage = $previousImage; baseStack = $baseName; appStack = $appName
                region = $Region; appOrigin = $base.SiteUrl
                indexVersion = if ($indexVersion) { $indexVersion.VersionId } else { $null }
                capturedAt = [DateTime]::UtcNow.ToString('o')
            }
            $previousFile = Join-Path $stateDirectory 'previous-release.json'
            $oldService = Get-AwsJson @('ecs', 'describe-services', '--cluster', $base.ClusterArn, '--services', $old.ServiceName)
            # A rerun after migration failure sees the failed task definition and desired=0.
            # Preserve the captured running release instead of replacing it with that failed image.
            if ($oldService.services[0].runningCount -gt 0 -or -not (Test-Path -LiteralPath $previousFile)) {
                $previous | ConvertTo-Json | Set-Content $previousFile
            }
            # Stop the old service BEFORE switching task definitions; also stops the old Beat.
            Invoke-Native aws @('ecs', 'update-service', '--cluster', $base.ClusterArn,
                '--service', $old.ServiceName, '--desired-count', '0')
            Wait-ServiceStopped $base.ClusterArn $old.ServiceName
        }
        Invoke-Native aws @('cloudformation', 'deploy', '--stack-name', $appName,
            '--template-file', 'infra/app.yaml', '--parameter-overrides',
            "BaseStackName=$baseName", "BackendImage=$image", "AppOrigin=$($base.SiteUrl)",
            'DesiredCount=0', '--no-fail-on-empty-changeset')
        $app = Get-StackOutputs $appName
        Wait-ServiceStopped $base.ClusterArn $app.ServiceName

        $network = @{ awsvpcConfiguration = @{
            subnets = @($base.PrivateSubnets -split ',')
            securityGroups = @($base.TaskSecurityGroup); assignPublicIp = 'DISABLED'
        }} | ConvertTo-Json -Depth 5 -Compress
        $networkFile = Join-Path $stateDirectory 'network.json'
        $network | Set-Content $networkFile
        $run = Get-AwsJson @('ecs', 'run-task', '--cluster', $base.ClusterArn,
            '--task-definition', $app.MigrationTaskArn, '--launch-type', 'FARGATE',
            '--network-configuration', "file://$networkFile")
        if (@($run.failures).Count -gt 0 -or @($run.tasks).Count -ne 1) { throw 'Migration task could not start' }
        $migrationArn = $run.tasks[0].taskArn
        Invoke-Native aws @('ecs', 'wait', 'tasks-stopped', '--cluster', $base.ClusterArn, '--tasks', $migrationArn)
        $result = Get-AwsJson @('ecs', 'describe-tasks', '--cluster', $base.ClusterArn, '--tasks', $migrationArn)
        $container = @($result.tasks[0].containers | Where-Object name -eq 'migration')[0]
        if (-not ($container.PSObject.Properties.Name -contains 'exitCode') -or $container.exitCode -ne 0) {
            throw "Migration failed. Service stays at 0. Inspect CloudWatch migration logs: $migrationArn"
        }
        # Only this successfully completed migration permits service startup.
        Invoke-Native aws @('cloudformation', 'deploy', '--stack-name', $appName,
            '--template-file', 'infra/app.yaml', '--parameter-overrides',
            "BaseStackName=$baseName", "BackendImage=$image", "AppOrigin=$($base.SiteUrl)",
            'DesiredCount=1', '--no-fail-on-empty-changeset')
        Invoke-Native aws @('ecs', 'wait', 'services-stable', '--cluster', $base.ClusterArn, '--services', $app.ServiceName)
        $service = Get-AwsJson @('ecs', 'describe-services', '--cluster', $base.ClusterArn, '--services', $app.ServiceName)
        if ($service.services[0].runningCount -ne 1 -or $service.services[0].taskDefinition -ne $app.ApplicationTaskArn) {
            throw 'Expected application task is not running (possibly circuit-breaker rollback)'
        }
        $health = Get-AwsJson @('elbv2', 'describe-target-health', '--target-group-arn', $base.TargetGroupArn)
        if (@($health.TargetHealthDescriptions | Where-Object { $_.TargetHealth.State -eq 'healthy' }).Count -lt 1) {
            throw 'ALB did not report a healthy database-ready target'
        }
        # Assets first, index last. No --delete: old hashed assets remain available for rollback.
        Invoke-Native aws @('s3', 'sync', 'frontend/dist/assets', "s3://$($base.FrontendBucket)/assets",
            '--cache-control', 'public,max-age=31536000,immutable')
        Invoke-Native aws @('s3', 'cp', 'frontend/dist/favicon.svg', "s3://$($base.FrontendBucket)/favicon.svg", '--cache-control', 'no-cache')
        Invoke-Native aws @('s3', 'cp', 'frontend/dist/index.html', "s3://$($base.FrontendBucket)/index.html", '--cache-control', 'no-cache', '--content-type', 'text/html')
        $invalidation = Get-AwsJson @('cloudfront', 'create-invalidation', '--distribution-id', $base.DistributionId, '--paths', '/index.html')
        Invoke-Native aws @('cloudfront', 'wait', 'invalidation-completed', '--distribution-id', $base.DistributionId, '--id', $invalidation.Invalidation.Id)
        & "$PSScriptRoot/smoke.ps1" -BaseUrl $base.SiteUrl
        @{ backendImage = $image; commit = $sha; siteUrl = $base.SiteUrl } |
            ConvertTo-Json | Set-Content (Join-Path $stateDirectory 'current-release.json')
        Write-Host "Deployed $($base.SiteUrl)"
    } finally { Pop-Location }
} finally {
    $env:AWS_DEFAULT_REGION = $previousRegion
    $env:AWS_PROFILE = $previousProfile
    $lock.Dispose()
}
