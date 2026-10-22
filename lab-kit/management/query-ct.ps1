param(
    [string]$Query = 'union isfuzzy=true ConfigurationData, ConfigurationChange, ConfigurationChangeV2 | where TimeGenerated > ago(2h) and Computer =~ "SQL2019-GUEST" | summarize Rows=count() by Type, ConfigDataType',
    [string]$Evidence = 'ct-ingestion-counts.json'
)
. "$PSScriptRoot\common.ps1"
$workspace = Get-Content -LiteralPath "$PSScriptRoot\ct-workspace.json" -Raw | ConvertFrom-Json
$id = $workspace.properties.customerId
if ($workspace.id -ne "$HvRoot/providers/Microsoft.OperationalInsights/workspaces/law-arc-ct-sea" -or -not $id) { throw 'Unexpected CT workspace' }
$token = & az account get-access-token --subscription $HvSub --resource https://api.loganalytics.io --query accessToken -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Log Analytics token unavailable' }
try {
    $result = Invoke-RestMethod -Method POST -Uri "https://api.loganalytics.azure.com/v1/workspaces/$id/query" `
        -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' `
        -Body (@{ query = $Query; timespan = 'PT2H' } | ConvertTo-Json) -TimeoutSec 120
    Save-HvJson $Evidence $result
    $result | ConvertTo-Json -Depth 30
}
finally { $token = $null }
