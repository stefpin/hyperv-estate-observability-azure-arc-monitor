$ErrorActionPreference = 'Stop'
$script:StorageWork = $PSScriptRoot
$script:StorageSubscription = '<SUBSCRIPTION_ID>'
$script:StorageGroup = 'rg-hyperv-arc-monitor-demo'
$script:StoragePrefix = "/subscriptions/$script:StorageSubscription/resourceGroups/$script:StorageGroup/"
$script:StorageWorkspace = '00000000-0000-0000-0000-000000000009'
if ($script:StorageWorkspace -match '^0{8}-0{4}-0{4}-0{4}-0{10}[0-9]{2}$') { throw 'Set the Log Analytics workspace ID in this file (tools\Set-RepoContext.ps1 -WorkspaceId) first.' }
function Write-StorageJson($Object, [string]$Name) {
    [IO.File]::WriteAllText((Join-Path $script:StorageWork $Name), (ConvertTo-Json -InputObject $Object -Depth 100), (New-Object Text.UTF8Encoding($false)))
}
function Invoke-StorageRest([string]$Method, [string]$ResourcePath, $Body = $null) {
    if (-not $ResourcePath.StartsWith($script:StoragePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Resource outside storage task scope' }
    $url = '"https://management.azure.com' + $ResourcePath + '"'
    $args = @('rest', '--method', $Method, '--url', $url, '--only-show-errors', '-o', 'json')
    if ($null -ne $Body) {
        $file = 'rest-body-' + [guid]::NewGuid().ToString('N') + '.json'
        $secured = Join-Path $script:StorageWork $file
        [IO.File]::WriteAllText($secured, '', (New-Object Text.UTF8Encoding($false)))
        & icacls.exe $secured /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" '*S-1-5-18:(F)' '*S-1-5-32-544:(F)' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not secure request body' }
        Write-StorageJson $Body $file
        $args += @('--body', ('@' + (Join-Path $script:StorageWork $file)))
    }
    try {
        $ErrorActionPreference = 'Continue'
        $raw = & az @args 2>&1 | Out-String
        $ErrorActionPreference = 'Stop'
        if ($LASTEXITCODE -ne 0) { throw $raw }
        if ($raw.Trim()) { $raw | ConvertFrom-Json }
    } finally {
        if ($file) { Remove-Item -LiteralPath (Join-Path $script:StorageWork $file) -Force -ErrorAction SilentlyContinue }
    }
}
function Get-StorageEnvironment {
    $e = @{}
    foreach ($line in Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\..\ENVIRONMENT.txt')) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') { $e[$matches[1]] = $matches[2].Trim() }
    }
    $e
}
function ConvertTo-StorageHex([string]$Value) {
    'x' + (([Text.Encoding]::ASCII.GetBytes($Value) | ForEach-Object { $_.ToString('x2') }) -join '')
}
function Invoke-StorageArc([string]$ScriptPath, [string]$Label, [System.Collections.IDictionary]$Protected = @{}, [System.Collections.IDictionary]$Parameters = @{}, [int]$Timeout = 600) {
    $machine = 'HV-HOST-01'
    $name = 'storage-v22-' + $Label + '-' + (Get-Date -Format 'MMddHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
    $resource = $script:StoragePrefix + "providers/Microsoft.HybridCompute/machines/$machine/runCommands/$name"
    $record = @{name=$name; machine=$machine; resourceId=$resource; createdUtc=[DateTime]::UtcNow.ToString('o')}
    Write-StorageJson $record ("runcommand-$name.json")
    $body = @{location='<PRIMARY_REGION>'; properties=@{
        source=@{script=[IO.File]::ReadAllText($ScriptPath)}
        timeoutInSeconds=$Timeout
        asyncExecution=$false
        parameters=@($Parameters.Keys | ForEach-Object { @{name=$_;value=[string]$Parameters[$_]} })
        protectedParameters=@($Protected.Keys | ForEach-Object { @{name=$_;value=[string]$Protected[$_]} })
    }}
    try {
        $null = Invoke-StorageRest PUT ($resource + '?api-version=2024-07-10') $body
        $end = (Get-Date).AddSeconds($Timeout + 180)
        do {
            Start-Sleep -Seconds 10
            try {
                $r = Invoke-StorageRest GET ($resource + '?api-version=2024-07-10')
            } catch {
                if ([string]$_ -match 'HCRP404|Not Found') { continue }
                throw
            }
            $iv = $r.properties.instanceView
            if ($iv.executionState -in @('Succeeded','Failed','TimedOut','Canceled')) { break }
        } while ((Get-Date) -lt $end)
        Write-StorageJson $r ("arc-result-$Label-$name.json")
        if ($iv.executionState -ne 'Succeeded' -or [int]$iv.exitCode -ne 0) { throw ("Arc failed: " + ($iv | ConvertTo-Json -Depth 10)) }
        $iv.output
    } finally {
        try {
            $null = Invoke-StorageRest DELETE ($resource + '?api-version=2024-07-10')
            $record.deletedUtc = [DateTime]::UtcNow.ToString('o')
        } catch {
            $record.cleanupError = [string]$_
        }
        Write-StorageJson $record ("runcommand-$name.json")
    }
}
function Invoke-StorageQuery([string]$Kql, [string]$Evidence) {
    $file = Join-Path $script:StorageWork ($Evidence + '.kql')
    [IO.File]::WriteAllText($file, $Kql, (New-Object Text.UTF8Encoding($false)))
    for ($try = 0; $try -lt 4; $try++) {
        $ErrorActionPreference = 'Continue'
        $raw = & az monitor log-analytics query --workspace $script:StorageWorkspace --analytics-query "@$file" --only-show-errors -o json 2>&1 | Out-String
        $ErrorActionPreference = 'Stop'
        if ($LASTEXITCODE -eq 0) {
            $r = $raw | ConvertFrom-Json
            Write-StorageJson @($r) ($Evidence + '.json')
            return $r
        }
        Start-Sleep -Seconds (5 * ($try + 1))
    }
    throw $raw
}
