#Requires -Version 7.0
[CmdletBinding()]
param([switch]$Build)
. "$PSScriptRoot/common.ps1"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $arguments = @('compose', 'up', '-d', '--wait', '--wait-timeout', '180')
    if ($Build) { $arguments += '--build' }
    Invoke-Native docker $arguments
    Invoke-Native docker @('compose', 'exec', '-T', 'db', 'sh', '-c',
        'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname=''cutlink_test''" | grep -q 1 || createdb -U "$POSTGRES_USER" cutlink_test')
    # The host venv is used for pytest. PostgreSQL/Redis remain real Compose services.
    Push-Location backend
    try { Invoke-Native '.\.venv\Scripts\python.exe' @('-m', 'pytest', '-q') } finally { Pop-Location }
    & "$PSScriptRoot/smoke.ps1" -BaseUrl 'http://localhost:5173'
} finally { Pop-Location }
