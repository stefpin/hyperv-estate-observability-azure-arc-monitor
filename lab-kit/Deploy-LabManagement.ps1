param([switch]$ConfigurationOnly)
. "$PSScriptRoot\context.ps1"
if(-not $ConfigurationOnly){throw 'This bundle has no patch/reboot/notification execution mode.'}
$itemsFile=Join-Path $PSScriptRoot 'management\deployment-index.json'
if(-not(Test-Path $itemsFile)){throw 'management\deployment-index.json not found.'}
$items=Get-Content $itemsFile -Raw | ConvertFrom-Json
foreach($item in $items){
    Assert-LabResourceId $item.resourceId
    if($item.resourceId -notmatch '/providers/(Microsoft.Insights/dataCollectionRules|Microsoft.Insights/dataCollectionRuleAssociations|Microsoft.OperationalInsights/workspaces)'){
        throw 'Only CT workspace/DCR/association allowed here; future patch schedules require separate maintenance review.'
    }
    $path=Join-Path "$PSScriptRoot\management" $item.file
    Invoke-LabAz rest --method put --url "https://management.azure.com$($item.resourceId)?api-version=$($item.apiVersion)" --body "@$path" -o none
}
Write-Output 'CT configuration applied only. No patch install, workflow trigger, reboot or email.'
