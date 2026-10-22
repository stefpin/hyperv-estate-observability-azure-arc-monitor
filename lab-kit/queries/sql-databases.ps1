. "$PSScriptRoot\..\context.ps1"
$id="$ResourcePrefix/providers/Microsoft.AzureArcData/SqlServerInstances/SQL2019-GUEST"
Invoke-LabAz rest --method get --url "https://management.azure.com$id/databases?api-version=2026-01-01" -o json
