. "$PSScriptRoot\context.ps1"
Set-Location $PSScriptRoot
foreach($schema in Get-ChildItem .\schema\*-table.json){
    $payload=Get-Content $schema.FullName -Raw | ConvertFrom-Json
    $table=$payload.properties.schema.name
    if($table -notmatch '^Hv[A-Za-z0-9_]+_CL$'){throw 'Unexpected custom table name.'}
    $law="$ResourcePrefix/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab"
    Invoke-LabAz rest --method put --url "https://management.azure.com$law/tables/$table`?api-version=2022-10-01" --body "@$($schema.FullName)" -o none
}
$mapping=@{
    'dcr-hyperv-host'=@('HV-HOST-01')
    'dcr-windows-guests'=@('WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','SQL2019-GUEST')
    'dcr-linux-guests'=@('RHEL94-GUEST')
    'dcr-sql-servers'=@('SQL2019-GUEST')
}
foreach($name in $mapping.Keys){
    $file=Join-Path $PSScriptRoot "dcr\$name.json"
    if(-not(Test-Path $file)){throw "DCR source file absent: $name"}
    $body=Get-Content $file -Raw | ConvertFrom-Json
    foreach($destination in $body.properties.destinations.logAnalytics){Assert-LabResourceId $destination.workspaceResourceId}
    Invoke-LabAz monitor data-collection rule create -g $RG --name $name --rule-file $file -o none
    $id="$ResourcePrefix/providers/Microsoft.Insights/dataCollectionRules/$name"
    foreach($machine in $mapping[$name]){
        $raw=Invoke-LabAz monitor data-collection rule association list --resource "$ArcPrefix/$machine" -o json
        $existing=($raw | Out-String) | ConvertFrom-Json
        if(@($existing | Where-Object {$_.dataCollectionRuleId -eq $id -or $_.properties.dataCollectionRuleId -eq $id}).Count -gt 0){continue}
        Invoke-LabAz monitor data-collection rule association create `
            --resource "$ArcPrefix/$machine" --name "assoc-$machine-$name" --rule-id $id -o none
    }
}
Write-Output 'Definitions/associations deployed. Verify actual rows in both Portal and CLI.'
