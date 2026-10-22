. "$PSScriptRoot\..\context.ps1"
Invoke-LabAz rest --method get `
    --url "https://management.azure.com$ResourcePrefix/providers/Microsoft.AlertsManagement/alerts?api-version=2019-03-01" `
    -o json
