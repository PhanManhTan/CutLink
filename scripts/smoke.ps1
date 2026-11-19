#Requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory)][string]$BaseUrl)
. "$PSScriptRoot/common.ps1"
Import-Module Microsoft.PowerShell.Utility
$BaseUrl = $BaseUrl.TrimEnd('/')
$session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$origin = ([uri]$BaseUrl).GetLeftPart([System.UriPartial]::Authority)
$headers = @{ Origin = $origin }
$linkId = $null
$email = "smoke-$([Guid]::NewGuid().ToString('N'))@example.com"
$password = [Guid]::NewGuid().ToString('N') + '!A1'

function Request {
    param([string]$Path, [string]$Method = 'GET', $Body = $null)
    $options = @{
        Uri = "$BaseUrl$Path"; Method = $Method; WebSession = $session; Headers = $headers
        SkipHttpErrorCheck = $true; TimeoutSec = 20; MaximumRedirection = 0
    }
    if ($null -ne $Body) { $options.Body = ($Body | ConvertTo-Json); $options.ContentType = 'application/json' }
    # 302 is intentionally inspected instead of followed.
    return Invoke-WebRequest @options -ErrorAction SilentlyContinue
}
function Assert-Status($Response, [int]$Expected, [string]$Label) {
    if ($null -eq $Response -or [int]$Response.StatusCode -ne $Expected) {
        throw "$Label failed: expected HTTP $Expected, got $($Response.StatusCode)"
    }
}
function Assert-Uncached($Response) {
    if (($Response.Headers['Cache-Control'] -join ',') -notmatch 'no-store') { throw 'Missing no-store response' }
    if (($Response.Headers['X-Cache'] -join ',') -match '^Hit') { throw 'CloudFront cached a private response' }
}
try {
    Assert-Status (Request '/api/health/live') 200 'Liveness'
    Assert-Status (Request '/api/health/ready') 200 'Database readiness'
    Assert-Status (Request '/api/links') 401 'Anonymous access'
    $register = Request '/api/auth/register' 'POST' @{email = $email; password = $password}
    Assert-Status $register 201 'Registration'
    Assert-Uncached $register
    if (($register.Headers['Set-Cookie'] -join ',') -notmatch 'HttpOnly') { throw 'Session cookie is not HttpOnly' }
    if ($BaseUrl.StartsWith('https://') -and ($register.Headers['Set-Cookie'] -join ',') -notmatch 'Secure') { throw 'Missing Secure cookie' }
    Assert-Status (Request '/api/auth/logout' 'POST') 204 'Logout'
    Assert-Status (Request '/api/auth/login' 'POST' @{email = $email; password = $password}) 200 'Login'
    Assert-Status (Request '/api/auth/me') 200 'Session cookie round trip'
    $customCode = "smoke-$([Guid]::NewGuid().ToString('N'))"
    Assert-Status (Request '/api/links' 'POST' @{name = 'Invalid URL'; target_url = 'javascript:alert(1)'}) 422 'URL validation'
    $create = Request '/api/links' 'POST' @{name = 'Smoke test'; target_url = 'https://example.com/?cutlink=smoke'; custom_code = $customCode}
    Assert-Status $create 201 'Create'
    $link = $create.Content | ConvertFrom-Json
    $linkId = $link.id
    if ($link.code -ne $customCode) { throw 'Custom ending was not preserved' }
    Assert-Status (Request '/api/links' 'POST' @{name = 'Duplicate ending'; target_url = 'https://example.com'; custom_code = $customCode}) 409 'Custom ending uniqueness'
    $redirect = Request "/r/$($link.code)"
    Assert-Status $redirect 302 'Redirect'
    Assert-Uncached $redirect
    if (($redirect.Headers.Location -join '') -ne 'https://example.com/?cutlink=smoke') { throw 'Wrong redirect destination' }
    Assert-Status (Request "/api/links/$linkId" 'PATCH' @{target_url = 'https://example.org/updated'}) 200 'Update'
    $updated = Request "/r/$($link.code)"
    Assert-Status $updated 302 'Updated redirect'
    if (($updated.Headers.Location -join '') -ne 'https://example.org/updated') { throw 'Stale redirect cache' }
    Assert-Status (Request "/api/links/$linkId" 'PATCH' @{enabled = $false}) 200 'Pause'
    Assert-Status (Request "/r/$($link.code)") 404 'Paused redirect'
    Assert-Status (Request "/api/links/$linkId/stats") 200 'Statistics'
    Assert-Status (Request '/api/does-not-exist') 404 'API errors are not rewritten to HTML'
    $dashboard = Request '/dashboard'
    Assert-Status $dashboard 200 'SPA deep link refresh'
    if ($dashboard.Content -notmatch '<div id="root">') { throw 'Dashboard did not return the SPA' }
    Assert-Status (Request "/api/links/$linkId" 'DELETE') 204 'Delete'
    $linkId = $null
    Assert-Status (Request "/r/$($link.code)") 404 'Deleted redirect'
    Write-Host "Smoke checks passed: $BaseUrl (test account: $email)"
} finally {
    if ($linkId) { Request "/api/links/$linkId" 'DELETE' | Out-Null }
    Request '/api/auth/logout' 'POST' | Out-Null
}
