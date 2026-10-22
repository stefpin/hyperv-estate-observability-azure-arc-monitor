$ErrorActionPreference = 'Stop'
$script:Subscription = '<SUBSCRIPTION_ID>'
$script:Group = 'rg-hyperv-arc-monitor-demo'
$script:Root = "/subscriptions/$Subscription/resourceGroups/$Group"
$script:Machine = "$Root/providers/Microsoft.HybridCompute/machines/SQL2019-GUEST"
$script:Configuration = "$Root/providers/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated"
$script:Account = "$Root/providers/Microsoft.Automation/automationAccounts/aa-hv-sql-maintenance"
$script:Scope = "$Root/providers/Microsoft.Maintenance/configurationAssignments/ca-hv-sql2019-approved"
$script:Evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'evidence'
[IO.Directory]::CreateDirectory($Evidence) | Out-Null

function Initialize-LabArm {
    $account = (& az account show --only-show-errors -o json | Out-String) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $account.id -ne $Subscription) {
        throw 'Select the authorized subscription in a visible Azure CLI session first.'
    }
    $token = (& az account get-access-token --subscription $Subscription --resource https://management.azure.com/ --only-show-errors -o json | Out-String) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $token.accessToken) { throw 'ARM token unavailable; a visible Azure sign-in may be required.' }
    $script:Headers = @{ Authorization = 'Bearer ' + $token.accessToken }
    $token = $null
}

function Assert-LabPath([string]$Path) {
    if (-not $Path.StartsWith($Root + '/', [StringComparison]::OrdinalIgnoreCase) -or
        $Path -match '(\.\.|%2f|%5c|#)' -or $Path.StartsWith('http', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Request is outside the authorized resource group or contains an unsafe path.'
    }
}

function Invoke-LabArm {
    param(
        [ValidateSet('GET','PUT','PATCH','POST','DELETE')][string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [string]$ContentType = 'application/json',
        [hashtable]$AdditionalHeaders = @{},
        [switch]$AllowNotFound
    )
    Assert-LabPath $Path
    if (-not $script:Headers) { Initialize-LabArm }
    $headers = @{} + $script:Headers + $AdditionalHeaders
    $arguments = @{
        Method = $Method
        Uri = 'https://management.azure.com' + $Path
        Headers = $headers
        ContentType = $ContentType
        TimeoutSec = 90
    }
    if ($null -ne $Body) {
        $arguments.Body = if ($ContentType -eq 'application/json') {
            ConvertTo-Json -InputObject $Body -Depth 80 -Compress
        } else { [Text.Encoding]::UTF8.GetBytes([string]$Body) }
    }
    for ($attempt = 0; $attempt -lt 4; $attempt++) {
        try { return Invoke-RestMethod @arguments }
        catch {
            $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
            if ($status -eq 404 -and $AllowNotFound) {
                return [pscustomobject]@{ HttpStatus = 404; NotFound = $true; Path = $Path }
            }
            if ($status -notin @(429,502,503,504) -or $attempt -eq 3) {
                throw "Scoped ARM $Method failed with HTTP $status at $Path. Request secrets are not logged."
            }
            Start-Sleep -Seconds (5 * ($attempt + 1))
        }
    }
}

function Save-LabEvidence([string]$Name, [object]$Value) {
    $path = Join-Path $Evidence $Name
    [IO.File]::WriteAllText($path, (ConvertTo-Json -InputObject $Value -Depth 80), (New-Object Text.UTF8Encoding($false)))
}

function Invoke-OwnedSqlCheck([string]$Script) {
    $id = "$Machine/runCommands/hv-ops-$([guid]::NewGuid().ToString('N').Substring(0,16))"
    $primaryError = $null
    $result = $null
    try {
        $null = Invoke-LabArm PUT "$id`?api-version=2025-01-13" @{
            location = 'southeastasia'
            properties = @{
                source = @{ script = $Script }
                timeoutInSeconds = 180
                asyncExecution = $false
            }
        }
        $deadline = [datetime]::UtcNow.AddMinutes(5)
        $notFoundReported = $false
        do {
            Start-Sleep -Seconds 5
            $status = Invoke-LabArm GET "$id`?api-version=2025-01-13" -AllowNotFound
            if ($status.NotFound) {
                if (-not $notFoundReported) { Write-Host 'Awaiting visibility of the newly created read-only Arc Run Command.'; $notFoundReported = $true }
                continue
            }
            if ($status.properties.instanceView.executionState -in @('Succeeded','Failed','TimedOut','Canceled')) { break }
        } while ([datetime]::UtcNow -lt $deadline)
        $view = $status.properties.instanceView
        if ($view.executionState -ne 'Succeeded' -or [int]$view.exitCode -ne 0) {
            throw "Read-only SQL check failed: $($view.executionState), exit $($view.exitCode)."
        }
        $result = $view.output | ConvertFrom-Json
    }
    catch { $primaryError = $_ }
    finally {
        try { $null = Invoke-LabArm DELETE "$id`?api-version=2025-01-13" }
        catch {
            if ($primaryError) { Write-Warning "Own Run Command cleanup also failed: $id" }
            else { $primaryError = $_ }
        }
    }
    if ($primaryError) { throw $primaryError }
    return $result
}
