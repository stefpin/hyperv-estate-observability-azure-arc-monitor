. "$PSScriptRoot\context.ps1"
$loc=& az connectedmachine show -g $RG -n SQL2019-GUEST --subscription $SUB --query location -o tsv --only-show-errors
if($LASTEXITCODE -ne 0 -or $loc -ne 'southeastasia'){throw 'SQL Arc requires the selected Southeast Asia machine.'}
Invoke-LabAz connectedmachine extension create -g $RG --machine-name SQL2019-GUEST `
    --location $loc --name WindowsAgent.SqlServer --publisher Microsoft.AzureData `
    --type WindowsAgent.SqlServer --enable-auto-upgrade true `
    --settings '@schema\sql-extension-settings.json' -o none
