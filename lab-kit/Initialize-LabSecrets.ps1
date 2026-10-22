$ErrorActionPreference = 'Stop'
$path = Join-Path (Split-Path $PSScriptRoot -Parent) 'ENVIRONMENT.txt'
if (Test-Path -LiteralPath $path) { throw 'Existing settings preserved: this script never overwrites them.' }
$settings = [ordered]@{
    SUBSCRIPTION_ID='<SUBSCRIPTION_ID>'
    TENANT_ID='<TENANT_ID>'
    RESOURCE_GROUP='rg-hyperv-arc-monitor-demo'
    LOCATION='<PRIMARY_REGION>'
    HOST_NAME='HV-HOST-01'
    HOST_IMAGE='MicrosoftWindowsServer:WindowsServer:2025-datacenter-g2:latest'
    HOST_ADMIN_USER='labadmin'
    SQL_GUEST_NAME='SQL2019-GUEST'
    SQL_GUEST_IP='192.168.100.15'
    SQL_GUEST_ARC_LOCATION='southeastasia'
    SQL_KEEP_RUNNING='true'
}
foreach ($key in 'HOST_ADMIN_PASSWORD','WIN2019_GUEST_PASSWORD','WIN2022_GUEST_PASSWORD',
    'WIN2025_GUEST_PASSWORD','RHEL_GUEST_PASSWORD','SQL_GUEST_PASSWORD','SQL_COLLECTOR_PASSWORD') {
    $secret = Read-Host "Enter private $key (not displayed)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        if ($value.Length -lt 16 -or $value -match "[`r`n]") { throw 'Use at least 16 characters and no newline.' }
        $settings[$key] = $value
    } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
$lines = @($settings.Keys | ForEach-Object { "$_=$($settings[$_])" })
$stream = [IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
$failed=$false
try {
    & icacls.exe $path /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" '*S-1-5-18:(F)' '*S-1-5-32-544:(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not secure settings file.' }
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($lines -join "`r`n")+"`r`n")
    $stream.Write($bytes,0,$bytes.Length)
} catch {$failed=$true;throw}
finally {
    $stream.Dispose()
    if($failed){Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue}
    $settings=$null; $lines=$null; $value=$null
}
Write-Output 'Private initial-build settings created; do not display/share/screenshot this file.'
