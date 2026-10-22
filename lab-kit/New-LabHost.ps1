. "$PSScriptRoot\context.ps1"
$E = Get-LabSettings
$existing = & az vm list -g $RG --subscription $SUB --query "[?name=='HV-HOST-01'].name" -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Host existence lookup failed.' }
if ($existing) { Write-Output 'Host exists: no create, delete or restart performed.'; return }
if (-not $E.HOST_IMAGE -or -not $E.HOST_ADMIN_PASSWORD) { throw 'Image/host credential missing in private settings.' }
Invoke-LabAz network nic create -g $RG -n HV-HOST-01-nic -l '<PRIMARY_REGION>' `
    --vnet-name vnet-arc-lab --subnet snet-lab --accelerated-networking false -o none
Invoke-LabAz vm create -g $RG -n HV-HOST-01 -l '<PRIMARY_REGION>' `
    --nics HV-HOST-01-nic --image $E.HOST_IMAGE --size Standard_E8s_v5 `
    --security-type Standard --patch-mode Manual --enable-auto-update false `
    --os-disk-name HV-HOST-01-osdisk --os-disk-size-gb 128 --storage-sku Premium_LRS `
    --admin-username labadmin --admin-password $E.HOST_ADMIN_PASSWORD -o none
Invoke-LabAz vm disk attach -g $RG --vm-name HV-HOST-01 --name HV-HOST-01-data `
    --new --size-gb 512 --sku Premium_LRS --caching ReadWrite -o none
Invoke-LabAz vm boot-diagnostics enable -g $RG -n HV-HOST-01 -o none
$E = $null
Write-Output 'Host created; proceed through Bastion, not Azure VM Run Command.'
