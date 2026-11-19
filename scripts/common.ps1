Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Native {
    param([Parameter(Mandatory)][string]$File, [Parameter()][string[]]$Arguments = @())
    & $File @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
}

function Get-AwsJson {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $result = & aws @Arguments --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI failed: $($Arguments[0..1] -join ' ')" }
    return ($result -join "`n") | ConvertFrom-Json
}

function Get-StackOutputs {
    param([Parameter(Mandatory)][string]$Name)
    $stack = Get-AwsJson -Arguments @('cloudformation', 'describe-stacks', '--stack-name', $Name)
    $outputs = @{}
    foreach ($item in $stack.Stacks[0].Outputs) { $outputs[$item.OutputKey] = $item.OutputValue }
    return $outputs
}

function Wait-ServiceStopped {
    param([string]$Cluster, [string]$Service)
    Invoke-Native aws @('ecs', 'wait', 'services-stable', '--cluster', $Cluster, '--services', $Service)
    $state = Get-AwsJson @('ecs', 'describe-services', '--cluster', $Cluster, '--services', $Service)
    if ($state.services[0].runningCount -ne 0 -or $state.services[0].pendingCount -ne 0) {
        throw 'Previous release has not stopped. Refusing to overlap releases.'
    }
}

function Enter-DeployLock {
    param([string]$Directory)
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    # Hold an exclusive file handle, released even if deployment throws.
    return [System.IO.File]::Open((Join-Path $Directory 'deploy.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
}
