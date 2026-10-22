param([Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$AlertGuid)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\context.ps1"
$alertId=$AlertGuid
$url="https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-hyperv-arc-monitor-demo/providers/Microsoft.AlertsManagement/alerts/$alertId`?api-version=2019-03-01"
$deadline=(Get-Date).AddMinutes(60)
do{
    $raw=Invoke-LabAz rest --method get --url $url -o json
    $object=($raw|Out-String)|ConvertFrom-Json
    $p=$object.properties.essentials
    "$([datetime]::UtcNow.ToString('o')) selected real alert=$($p.monitorCondition)."
    if($p.monitorCondition -eq 'Resolved'){
        $safe=@{AlertId=$object.id;Rule=$p.alertRule;MonitorCondition=$p.monitorCondition;StartUtc=$p.startDateTime;ModifiedUtc=$p.lastModifiedDateTime;CollectedUtc=[datetime]::UtcNow.ToString('o')}
        [IO.File]::WriteAllText("$PSScriptRoot\selected-alert-resolved.json",(ConvertTo-Json $safe -Depth 8),(New-Object Text.UTF8Encoding($false)))
        'Selected genuine alert resolved naturally; now verify its recovery email in Outlook.'
        return
    }
    Start-Sleep -Seconds 120
}while((Get-Date) -lt $deadline)
throw 'Selected real alert did not resolve within the monitoring window; thresholds were not changed.'
