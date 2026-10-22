# add-sql-disks.ps1 - runs ON THE HYPER-V HOST (Arc Run Command). Adds the SQL Server data and log disks to a
# running Windows guest and prepares them inside the guest through PowerShell Direct:
#   host : F:\VMs\<guest>-data.vhdx and -log.vhdx (dynamic), hot-added to the VM's SCSI controller
#   guest: GPT, NTFS with 64 KB allocation units, E: = SQLDATA (E:\SQLData, E:\TempDB), L: = SQLLOG (L:\SQLLog),
#          High performance power plan; reports the sector size SQL Server will see (must be 512 B or 4 KB)
# Safe to run again: existing disks, volumes and folders are kept.
param(
    [string]$GuestName,
    [string]$GuestPasswordHex = '',
    [int]$DataGB = 64,
    [int]$LogGB = 32
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'HV-HOST-01' -or $GuestName -ne 'SQL2019-GUEST') { throw 'Only SQL2019-GUEST on HV-HOST-01 is permitted.' }
function Log([string]$m) { "{0:HH:mm:ss} {1}" -f (Get-Date), $m }
if ($GuestPasswordHex -notmatch '^x([0-9a-f]{2})+$') { throw 'GuestPasswordHex missing - nothing changed' }
$h = $GuestPasswordHex.Substring(1); $bb = New-Object byte[] ($h.Length / 2)
for ($i = 0; $i -lt $bb.Length; $i++) { $bb[$i] = [Convert]::ToByte($h.Substring($i * 2, 2), 16) }
$cred = New-Object System.Management.Automation.PSCredential('labadmin', (ConvertTo-SecureString ([Text.Encoding]::ASCII.GetString($bb)) -AsPlainText -Force))
$vm = Get-VM -Name $GuestName
if ($vm.State -ne 'Running') { throw "$GuestName is not running - nothing changed" }

# 1. Host: create and hot-add the two virtual disks
$disks = [ordered]@{
    data = @{ Path = "F:\VMs\$GuestName-data.vhdx"; GB = $DataGB }
    log  = @{ Path = "F:\VMs\$GuestName-log.vhdx"; GB = $LogGB }
}
foreach ($k in $disks.Keys) {
    $d = $disks[$k]
    if (-not (Test-Path $d.Path)) { New-VHD -Path $d.Path -SizeBytes ([int64]$d.GB * 1GB) -Dynamic | Out-Null; Log ("Created {0} ({1} GB dynamic)" -f $d.Path, $d.GB) }
    else { Log ("Exists  {0}" -f $d.Path) }
    $v = Get-VHD -Path $d.Path
    Log ("  VHDX sector size: logical {0} B, physical {1} B" -f $v.LogicalSectorSize, $v.PhysicalSectorSize)
    if (-not (Get-VMHardDiskDrive -VMName $GuestName | Where-Object Path -eq $d.Path)) {
        Add-VMHardDiskDrive -VMName $GuestName -ControllerType SCSI -Path $d.Path
        Log ("  Attached to {0} (SCSI, hot-add)" -f $GuestName)
    }
    else { Log '  Already attached' }
}
"VM disks: " + ((Get-VMHardDiskDrive -VMName $GuestName | ForEach-Object { "{0} {1}:{2} {3}" -f $_.ControllerType, $_.ControllerNumber, $_.ControllerLocation, (Split-Path $_.Path -Leaf) }) -join ' | ')

# 2. Guest: initialise, format, folders, power plan
$r = Invoke-Command -VMName $GuestName -Credential $cred -ArgumentList $DataGB, $LogGB -ScriptBlock {
    param([int]$DataGB, [int]$LogGB)
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    $out = New-Object System.Collections.Generic.List[string]
    $plan = @(
        @{ Letter = 'E'; Label = 'SQLDATA'; GB = $DataGB; Folders = @('E:\SQLData', 'E:\TempDB') },
        @{ Letter = 'L'; Label = 'SQLLOG'; GB = $LogGB; Folders = @('L:\SQLLog') }
    )
    for ($i = 0; $i -lt 30; $i++) {
        Update-HostStorageCache
        $sizes = @(Get-Disk | ForEach-Object { [math]::Round($_.Size / 1GB) })
        if ($sizes -contains $DataGB -and $sizes -contains $LogGB) { break }
        Start-Sleep -Seconds 2
    }
    foreach ($p in $plan) {
        $vol = Get-Volume -DriveLetter $p.Letter -ErrorAction SilentlyContinue
        if (-not $vol) {
            $disk = Get-Disk | Where-Object { $_.PartitionStyle -eq 'RAW' -and [math]::Round($_.Size / 1GB) -eq $p.GB } | Select-Object -First 1
            if (-not $disk) { throw ("No new {0} GB disk found for {1}:" -f $p.GB, $p.Letter) }
            if ($disk.IsOffline) { Set-Disk -Number $disk.Number -IsOffline $false }
            Initialize-Disk -Number $disk.Number -PartitionStyle GPT
            $part = New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter $p.Letter
            $vol = Format-Volume -Partition $part -FileSystem NTFS -AllocationUnitSize 65536 -NewFileSystemLabel $p.Label -Confirm:$false -Force
            $out.Add(("{0}: created on disk {1} ({2} GB)" -f $p.Letter, $disk.Number, $p.GB))
        }
        else { $out.Add(("{0}: already exists ({1})" -f $p.Letter, $vol.FileSystemLabel)) }
        foreach ($f in $p.Folders) { New-Item -ItemType Directory -Force -Path $f | Out-Null }
        $wv = Get-CimInstance Win32_Volume -Filter ("DriveLetter='{0}:'" -f $p.Letter)
        $si = (& fsutil.exe fsinfo sectorinfo ("{0}:" -f $p.Letter)) -join ' '
        $phys = if ($si -match 'PhysicalBytesPerSectorForPerformance\s*:\s*(\d+)') { [int]$matches[1] } else { -1 }
        $atom = if ($si -match 'PhysicalBytesPerSectorForAtomicity\s*:\s*(\d+)') { [int]$matches[1] } else { -1 }
        $out.Add(("{0}: label {1}, {2:N1} GB, NTFS cluster {3} KB, sector size for SQL Server {4} B (atomicity {5} B), folders {6}" -f $p.Letter, $wv.Label, ($wv.Capacity / 1GB), ($wv.BlockSize / 1KB), [Math]::Max($phys, $atom), $atom, (($p.Folders | Where-Object { Test-Path $_ }) -join ', ')))
    }
    & powercfg.exe /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c | Out-Null
    $out.Add(("Power plan: " + ((& powercfg.exe /getactivescheme) -join ' ').Trim()))
    $out
}
$r | ForEach-Object { Log ("guest " + $_) }
$bad = @($r | Where-Object { $_ -match 'sector size for SQL Server (\d+) B' -and [int]$matches[1] -gt 4096 })
if ($bad.Count) { throw 'A SQL Server disk reports a sector size above 4 KB - SQL Server would not start' }
Log 'SQL-DISKS-DONE'
