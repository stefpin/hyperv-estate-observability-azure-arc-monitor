$ErrorActionPreference='Stop'
$sub='<SUBSCRIPTION_ID>';$rg='rg-hyperv-arc-monitor-demo'
$id='00000000-0000-0000-0000-000000000005'
$file="$PSScriptRoot\workbook-resource.json"
& az rest --method put --url "https://management.azure.com/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/workbooks/$id`?api-version=2022-04-01" --body "@$file" --only-show-errors -o none
if($LASTEXITCODE -ne 0){throw 'Publishing workbook failed'}
& az resource show --ids "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/workbooks/$id" --api-version 2022-04-01 --query '{name:properties.displayName,location:location,source:properties.sourceId}' -o json --only-show-errors
if($LASTEXITCODE -ne 0){throw 'Reading published workbook failed'}
