# host-prepare.ps1 - runs ON THE HYPER-V HOST (operator guide chapter 6).
#   1 formats the 512 GB data disk as F: (label HyperV) and creates F:\VMs, F:\ISO and F:\Build
#   2 sets the time zone to SE Asia Standard Time (UTC+7)
#   3 checks the host can reach the internet through the NAT gateway
#   4 stops the labadmin password from expiring before the lab is removed
#   5 installs the Hyper-V role - the host must be restarted afterwards
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'HV-HOST-01') { throw 'Run only on the intended Hyper-V host.' }

$existing = Get-Volume -DriveLetter F -ErrorAction SilentlyContinue
if (-not $existing) {
    $raw = @(Get-Disk | Where-Object { $_.PartitionStyle -eq 'RAW' -and [math]::Abs($_.Size / 1GB - 512) -lt 1 })
    if ($raw.Count -ne 1) { throw 'Expected exactly one blank 512 GB data disk; inspect Disk Management before formatting.' }
    $raw | Initialize-Disk -PartitionStyle GPT -PassThru |
        New-Partition -DriveLetter F -UseMaximumSize |
        Format-Volume -FileSystem NTFS -NewFileSystemLabel 'HyperV' -Confirm:$false | Out-Null
}
elseif ($existing.FileSystem -ne 'NTFS' -or $existing.FileSystemLabel -ne 'HyperV') {
    throw 'Existing F: is not the expected HyperV NTFS volume; no format performed.'
}
New-Item -ItemType Directory -Force -Path 'F:\VMs', 'F:\ISO', 'F:\Build' | Out-Null
$v = Get-Volume -DriveLetter F
"F: label={0} free={1:N0} GB" -f $v.FileSystemLabel, ($v.SizeRemaining / 1GB)

Set-TimeZone -Id 'SE Asia Standard Time'
"TimeZone: " + (Get-TimeZone).Id

foreach ($h in 'login.microsoftonline.com', 'software-static.download.prss.microsoft.com') {
    "{0}:443 reachable={1}" -f $h, (Test-NetConnection -ComputerName $h -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)
}

Set-LocalUser -Name 'labadmin' -PasswordNeverExpires $true
"labadmin password expires: " + $(if ((Get-LocalUser -Name 'labadmin').PasswordExpires) { (Get-LocalUser -Name 'labadmin').PasswordExpires } else { 'never' })

$r = Install-WindowsFeature -Name Hyper-V -IncludeManagementTools
"Hyper-V install: Success={0} RestartNeeded={1}" -f $r.Success, $r.RestartNeeded
