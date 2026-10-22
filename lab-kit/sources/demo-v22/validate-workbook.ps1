$ErrorActionPreference='Stop'
$queries=Get-Content "$PSScriptRoot\workbook-queries.json" -Raw|ConvertFrom-Json
$results=@()
foreach($property in $queries.PSObject.Properties){
    $value=$property.Value
    $query=$value.query.Replace('TimeGenerated {TimeRange}','TimeGenerated > ago(6h)').Replace('{TimeRange:grain}','1m')
    if($value.arm){
        $raw=& az rest --method get --url ("https://management.azure.com"+$query) -o json --only-show-errors
        if($LASTEXITCODE -ne 0){throw 'Reading live ARM database inventory failed'}
        $rows=@((($raw|Out-String)|ConvertFrom-Json).value)
    }
    elseif($value.arg){
        $query=$query.Replace('"',"'").Replace("`r",' ').Replace("`n",' ')
        $ErrorActionPreference='Continue'
        $raw= & az graph query --subscriptions '<SUBSCRIPTION_ID>' -q $query --first 100 --query data -o json --only-show-errors 2>&1|Out-String
        $ErrorActionPreference='Stop'
        if($LASTEXITCODE -ne 0){throw "Workbook query $($property.Name) failed: $raw"}
        $rows=@(foreach($row in ($raw|ConvertFrom-Json)){$row})
    }
    else {
        if($value.workspace -like '*law-arc-ct-sea'){
            $ctId=& az monitor log-analytics workspace show --subscription '<SUBSCRIPTION_ID>' -g rg-hyperv-arc-monitor-demo -n law-arc-ct-sea --query customerId -o tsv --only-show-errors
            if($LASTEXITCODE -ne 0){throw 'Reading Change Tracking workspace ID failed'}
            $rows=@(& "$PSScriptRoot\query-la.ps1" -Query $query -WorkspaceId $ctId)
        }
        else{$rows=@(& "$PSScriptRoot\query-la.ps1" -Query $query)}
    }
    $results+=@{Name=$property.Name;Rows=$rows.Count;Valid=$true}
    "Validated $($property.Name): $($rows.Count) rows."
}
[IO.File]::WriteAllText("$PSScriptRoot\workbook-validation.json",(ConvertTo-Json -InputObject $results -Depth 8),(New-Object Text.UTF8Encoding($false)))
