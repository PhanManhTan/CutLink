#Requires -Version 7.0
[CmdletBinding()]
param([string]$ReleaseFile = "$PSScriptRoot/../.deploy/previous-release.json", [string]$Profile)
. "$PSScriptRoot/common.ps1"
$root = Split-Path $PSScriptRoot -Parent
$lock = Enter-DeployLock (Join-Path $root '.deploy')
$oldRegion = $env:AWS_DEFAULT_REGION
$oldProfile = $env:AWS_PROFILE
try {
    $release = Get-Content -LiteralPath $ReleaseFile -Raw | ConvertFrom-Json
    $env:AWS_DEFAULT_REGION = $release.region
    if ($Profile) { $env:AWS_PROFILE = $Profile }
    $base = Get-StackOutputs $release.baseStack
    $app = Get-StackOutputs $release.appStack
    Invoke-Native aws @('ecs', 'update-service', '--cluster', $base.ClusterArn, '--service', $app.ServiceName, '--desired-count', '0')
    Wait-ServiceStopped $base.ClusterArn $app.ServiceName
    $template = Join-Path $root 'infra/app.yaml'
    Invoke-Native aws @('cloudformation', 'deploy', '--stack-name', $release.appStack, '--template-file', $template,
        '--parameter-overrides', "BaseStackName=$($release.baseStack)", "BackendImage=$($release.backendImage)",
        "AppOrigin=$($release.appOrigin)", 'DesiredCount=1', '--no-fail-on-empty-changeset')
    Invoke-Native aws @('ecs', 'wait', 'services-stable', '--cluster', $base.ClusterArn, '--services', $app.ServiceName)
    if ($release.indexVersion) {
        $source = "$($base.FrontendBucket)/index.html?versionId=$([uri]::EscapeDataString($release.indexVersion))"
        Get-AwsJson @('s3api', 'copy-object', '--bucket', $base.FrontendBucket, '--key', 'index.html',
            '--copy-source', $source, '--metadata-directive', 'REPLACE', '--cache-control', 'no-cache', '--content-type', 'text/html') | Out-Null
        $inv = Get-AwsJson @('cloudfront', 'create-invalidation', '--distribution-id', $base.DistributionId, '--paths', '/index.html')
        Invoke-Native aws @('cloudfront', 'wait', 'invalidation-completed', '--distribution-id', $base.DistributionId, '--id', $inv.Invalidation.Id)
    }
    & "$PSScriptRoot/smoke.ps1" -BaseUrl $base.SiteUrl
    Write-Host 'Application rollback completed. Database schema was not downgraded.'
} finally {
    $env:AWS_DEFAULT_REGION = $oldRegion
    $env:AWS_PROFILE = $oldProfile
    $lock.Dispose()
}
