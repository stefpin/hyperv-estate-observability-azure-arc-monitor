param([Parameter(Mandatory=$true)][string]$EnvironmentPath,
 [ValidateSet('no','yes')][string]$ConfigureAndTest='no')
if($ConfigureAndTest -ne 'yes'){throw 'Pass -ConfigureAndTest yes after reviewing the setup; this creates webhook delivery and independent read-only tests.'}
. "$PSScriptRoot\common.ps1"
$account = "$HvRoot/providers/Microsoft.Automation/automationAccounts/aa-hv-sql-maintenance"
$config = "$HvRoot/providers/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated"
$topic = "$HvRoot/providers/Microsoft.EventGrid/systemTopics/eg-hv-sql-maintenance"
$envFile = $EnvironmentPath
Invoke-HvRest PUT "$topic`?api-version=2022-06-15" @{
    location = 'southeastasia'
    properties = @{ source = $config; topicType = 'Microsoft.Maintenance.MaintenanceConfigurations' }
    tags = @{ purpose = 'HV-pre-post-checks' }
} 'eventgrid-topic.json' | Out-Null
$token = & az account get-access-token --subscription $HvSub --resource https://management.azure.com/ --query accessToken -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'ARM token unavailable' }
$headers = @{ Authorization = "Bearer $token" }
function Invoke-PrivateArm([string]$Method, [string]$Path, [object]$Body) {
    if ($Path -notlike "$HvRoot/*") { throw 'Resource-group scope violation' }
    $params = @{ Method=$Method; Uri="https://management.azure.com$Path"; Headers=$headers; ContentType='application/json'; TimeoutSec=120 }
    if ($null -ne $Body) { $params.Body = ConvertTo-Json -InputObject $Body -Depth 20 -Compress }
    try { Invoke-RestMethod @params }
    catch { throw "Private ARM request failed at $Path; sensitive endpoint details suppressed." }
}
function Get-OrAppendWebhook([string]$Key) {
    $stat = Get-Item -LiteralPath $envFile
    Start-Sleep -Seconds 2
    $current = Get-Item -LiteralPath $envFile
    if ($stat.Length -ne $current.Length -or $stat.LastWriteTimeUtc -ne $current.LastWriteTimeUtc) { throw 'Environment file is currently being modified; retry later' }
    $handle = [IO.File]::Open($envFile, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $bytes = New-Object byte[] $handle.Length
        $null = $handle.Read($bytes,0,$bytes.Length)
        $text = [Text.Encoding]::UTF8.GetString($bytes)
        $match = [regex]::Match($text, "(?m)^$Key=(.+)\r?$")
        if ($match.Success) { return $match.Groups[1].Value.Trim() }
        $uri = Invoke-PrivateArm POST "$account/webhooks/generateUri`?api-version=2024-10-23" $null
        if ($uri -notlike 'https://*.azure-automation.net/webhooks?token=*') { throw 'Unexpected generated webhook URI; not displayed' }
        $append = [Text.Encoding]::UTF8.GetBytes("`r`n$Key=$uri`r`n")
        $null = $handle.Seek(0,[IO.SeekOrigin]::End)
        $handle.Write($append,0,$append.Length)
        $handle.Flush($true)
        return $uri
    }
    finally { $handle.Dispose() }
}
try {
    foreach ($phase in @('Pre','Post')) {
        $uri = Get-OrAppendWebhook "HV_UM_${phase}_WEBHOOK_URI"
        $webhookName = "wh-hv-sql-$($phase.ToLowerInvariant())"
        $webhook = Invoke-PrivateArm PUT "$account/webhooks/$webhookName`?api-version=2024-10-23" @{
            name = $webhookName
            properties = @{
                expiryTime = (Get-Date).ToUniversalTime().AddDays(45).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", [Globalization.CultureInfo]::InvariantCulture); isEnabled = $true; uri = $uri
                runbook = @{ name = 'Test-HvSqlMaintenanceAvailability' }
                parameters = @{ Phase = $phase; DemoOnly = 'false' }
            }
        }
        $safeWebhook = @{ id=$webhook.id; name=$webhook.name; expiryTime=$webhook.properties.expiryTime; isEnabled=$webhook.properties.isEnabled; runbook=$webhook.properties.runbook; uri='REDACTED-existing-ENVIRONMENT-only' }
        Save-HvJson "automation-webhook-$phase.json" $safeWebhook
        $event = Invoke-PrivateArm PUT "$topic/eventSubscriptions/es-hv-sql-$($phase.ToLowerInvariant())`?api-version=2022-06-15" @{
            properties = @{
                destination = @{ endpointType = 'WebHook'; properties = @{ endpointUrl = $uri } }
                filter = @{ includedEventTypes = @("Microsoft.Maintenance.$($phase)MaintenanceEvent") }
                eventDeliverySchema = 'EventGridSchema'
                retryPolicy = @{ maxDeliveryAttempts = 5; eventTimeToLiveInMinutes = 60 }
            }
        }
        Save-HvJson "eventgrid-subscription-$phase.json" @{
            id=$event.id; name=$event.name; provisioningState=$event.properties.provisioningState
            filter=$event.properties.filter; destinationType='WebHook'; endpoint='REDACTED-existing-ENVIRONMENT-only'
        }
        $payload = @(@{
            id=[guid]::NewGuid().ToString(); topic=$config; subject='mc-hv-sql2019-definitions-gated'
            eventType="Microsoft.Maintenance.$($phase)MaintenanceEvent"; eventTime=[datetime]::UtcNow.ToString('o')
            dataVersion='1.0'; metadataVersion='1'
            data=@{ MaintenanceConfigurationId=$config; ResourceSubscriptionIds=@($HvSub); CorrelationId="independent-webhook-safe-demo-$phase" }
        })
        try {
            $test = Invoke-RestMethod -Method POST -Uri $uri -ContentType 'application/json' -Body (ConvertTo-Json -InputObject $payload -Depth 20)
        }
        catch { throw 'Webhook independent check failed; secret URI suppressed.' }
        Save-HvJson "webhook-demo-$phase-submit.json" $test
        $uri = $null
        Write-Output "$phase webhook and Event Grid subscription configured; independent check submitted."
    }
}
finally { $token=$null; $headers=$null; $uri=$null }
