param([ValidateSet('Firing','Recovery','Final')][string]$Phase='Firing',
    [datetime]$SinceUtc=([datetime]::UtcNow.AddHours(-1)))
$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\context.ps1"
$url='https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-hyperv-arc-monitor-demo/providers/Microsoft.AlertsManagement/alerts?api-version=2019-03-01'
$raw=Invoke-LabAz rest --method get --url $url -o json
$collection=(($raw|Out-String)|ConvertFrom-Json)
if($collection.nextLink){throw 'Paged alert history requires further RG-scoped reads; refusing incomplete evidence.'}
$results=@()
foreach($alert in $collection.value){
    $p=$alert.properties.essentials
    if([datetime]$p.startDateTime -lt $SinceUtc.ToUniversalTime()){continue}
    $results+=@{
        AlertId=$alert.id; RuleId=$p.alertRule; Name=($p.alertRule -split '/')[-1]
        MonitorCondition=$p.monitorCondition; State=$p.alertState
        StartUtc=$p.startDateTime; ModifiedUtc=$p.lastModifiedDateTime
        Severity=$p.severity
    }
}
$snapshot=@{Phase=$Phase;CollectedUtc=[datetime]::UtcNow.ToString('o');Alerts=$results}
[IO.File]::WriteAllText("$PSScriptRoot\alerts-$($Phase.ToLowerInvariant()).json",(ConvertTo-Json $snapshot -Depth 12),(New-Object Text.UTF8Encoding($false)))
$results|ForEach-Object{"$($_.Name): $($_.MonitorCondition); start=$($_.StartUtc); updated=$($_.ModifiedUtc)"}
