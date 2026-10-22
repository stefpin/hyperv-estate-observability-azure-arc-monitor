. "$PSScriptRoot\context.ps1"
foreach($machine in 'HV-HOST-01','WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','RHEL94-GUEST','SQL2019-GUEST'){
    $loc=& az connectedmachine show -g $RG -n $machine --subscription $SUB --query location -o tsv --only-show-errors
    if($LASTEXITCODE -ne 0){throw 'Machine region lookup failed.'}
    $type=if($machine -eq 'RHEL94-GUEST'){'AzureMonitorLinuxAgent'}else{'AzureMonitorWindowsAgent'}
    $existing=& az connectedmachine extension list -g $RG --machine-name $machine --subscription $SUB -o json --only-show-errors
    if($LASTEXITCODE -ne 0){throw 'Existing extension lookup failed.'}
    $installed=@($existing | ConvertFrom-Json | Where-Object name -eq $type)
    if($installed.Count){
        if($installed[0].provisioningState -ne 'Succeeded'){throw "Existing AMA on $machine is not Succeeded; investigate rather than blindly reinstall."}
        Write-Output "Verified existing AMA on $machine; no extension update."
        continue
    }
    Invoke-LabAz connectedmachine extension create -g $RG --machine-name $machine `
        --location $loc --name $type --publisher Microsoft.Azure.Monitor --type $type `
        --enable-auto-upgrade true -o none
}
