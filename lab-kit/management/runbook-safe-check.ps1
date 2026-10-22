param(
    [object]$WebhookData,
    [ValidateSet('Pre','Post')][string]$Phase = 'Pre',
    [bool]$DemoOnly = $false
)
$ErrorActionPreference = 'Stop'
$subscription = '<SUBSCRIPTION_ID>'
$group = 'rg-hyperv-arc-monitor-demo'
$machine = "/subscriptions/$subscription/resourceGroups/$group/providers/Microsoft.HybridCompute/machines/SQL2019-GUEST"
$configuration = "/subscriptions/$subscription/resourceGroups/$group/providers/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated"
if ($WebhookData) {
    $events = @($WebhookData.RequestBody | ConvertFrom-Json)
    $expected = "Microsoft.Maintenance.$($Phase)MaintenanceEvent"
    $valid = @($events | Where-Object { $_.eventType -eq $expected -and $_.data.MaintenanceConfigurationId -eq $configuration })
    if ($valid.Count -ne 1) {
        Write-Output 'Ignored: payload is not the expected scoped pre/post maintenance event.'
        return
    }
    if (@($valid[0].data.ResourceSubscriptionIds) -notcontains $subscription) { throw 'Unexpected maintenance subscription' }
    $correlation = $valid[0].data.CorrelationId
}
elseif (-not $DemoOnly) { throw 'Manual runs require DemoOnly=true; no patch installation is performed.' }
else { $correlation = "independent-safe-demo-$Phase" }
Disable-AzContextAutosave -Scope Process | Out-Null
$context = (Connect-AzAccount -Identity -SkipContextPopulation).Context
Set-AzContext -Subscription $subscription -DefaultProfile $context | Out-Null
$serverResponse = Invoke-AzRestMethod -Path "$machine`?api-version=2025-01-13" -Method GET
if ($serverResponse.StatusCode -ne 200) { throw 'Could not read the explicitly scoped Arc machine' }
$server = $serverResponse.Content | ConvertFrom-Json
if ($server.location -ne 'southeastasia' -or $server.properties.status -ne 'Connected') { throw 'Arc machine disconnected or in wrong region' }
$check = @'
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Wrong computer' }
$s = Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER'"
$o = Get-CimInstance Win32_OperatingSystem
$result = [ordered]@{ Utc = [datetime]::UtcNow.ToString('o'); Machine = $env:COMPUTERNAME; SqlState = $s.State; SqlStartMode = $s.StartMode; LastBootUtc = $o.LastBootUpTime.ToUniversalTime().ToString('o'); NoSqlStop = $true; NoReboot = $true }
$result | ConvertTo-Json -Compress
if ($s.State -ne 'Running' -or $s.StartMode -ne 'Auto') { throw 'SQL availability check failed' }
'@
$command = "$machine/runCommands/hv-prepost-$([guid]::NewGuid().ToString('N').Substring(0,12))"
$payload = @{
    location = 'southeastasia'
    properties = @{ source = @{ script = $check }; timeoutInSeconds = 120; asyncExecution = $false }
} | ConvertTo-Json -Depth 10
try {
    $response = Invoke-AzRestMethod -Path "$command`?api-version=2025-01-13" -Method PUT -Payload $payload
    if ($response.StatusCode -notin @(200,201,202)) { throw "Run Command request failed: $($response.StatusCode)" }
    $state = $null
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 10
        $status = Invoke-AzRestMethod -Path "$command`?api-version=2025-01-13" -Method GET
        if ($status.StatusCode -ne 200) { continue }
        $state = $status.Content | ConvertFrom-Json
        if ($state.properties.instanceView.executionState -in @('Succeeded','Failed','TimedOut','Canceled')) { break }
    }
    if ($state.properties.instanceView.executionState -ne 'Succeeded' -or $state.properties.instanceView.exitCode -ne 0) {
        throw 'Guest availability check did not succeed.'
    }
    [ordered]@{
        Phase = $Phase; CorrelationId = $correlation; DemoOnly = $DemoOnly
        ArcStatus = $server.properties.status
        Guest = ($state.properties.instanceView.output | ConvertFrom-Json)
        PatchInstallRequested = $false; EmailSent = $false
    } | ConvertTo-Json -Depth 10
}
finally {
    $deleted = Invoke-AzRestMethod -Path "$command`?api-version=2025-01-13" -Method DELETE
    if ($deleted.StatusCode -notin @(200,202,204,404)) { Write-Warning "Own Run Command cleanup returned $($deleted.StatusCode)" }
}
