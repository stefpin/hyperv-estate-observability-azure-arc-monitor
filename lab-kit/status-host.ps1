# status-host.ps1 - runs ON THE HYPER-V HOST (operator guide chapter 6). Read-only.
# Reports the host, the switch and NAT, every guest (state, size, address, auto-start, checkpoints),
# the vCPU-to-logical-processor ratio and the ISO files.
$ErrorActionPreference = 'Stop'
$h = Get-VMHost
$os = Get-CimInstance Win32_OperatingSystem
$lp = $h.LogicalProcessorCount
"Host {0}: {1} LP, {2:N1} GB RAM, {3:N1} GB free, uptime {4:N1} h" -f $env:COMPUTERNAME, $lp, ($os.TotalVisibleMemorySize / 1MB), ($os.FreePhysicalMemory / 1MB), (((Get-Date) - $os.LastBootUpTime).TotalHours)
$f = Get-Volume -DriveLetter F
"F: {0:N0} GB free of {1:N0} GB" -f ($f.SizeRemaining / 1GB), ($f.Size / 1GB)
"Switch: " + ((Get-VMSwitch | ForEach-Object { "{0}/{1}" -f $_.Name, $_.SwitchType }) -join ', ') + "; NAT: " + ((Get-NetNat | ForEach-Object { "{0} {1}" -f $_.Name, $_.InternalIPInterfaceAddressPrefix }) -join ', ')
$vms = Get-VM | Sort-Object Name
$total = 0
foreach ($v in $vms) {
    $total += $v.ProcessorCount
    $ip = ($v | Get-VMNetworkAdapter).IPAddresses | Where-Object { $_ -like '192.168.100.*' }
    $cp = @(Get-VMSnapshot -VMName $v.Name -ErrorAction SilentlyContinue).Count
    "{0,-17} {1,-8} vCPU {2}  RAM {3} GB  IP {4,-15} gen {5}  autostart {6}  checkpoints {7}  up {8:N0} min" -f $v.Name, $v.State, $v.ProcessorCount, ($v.MemoryStartup / 1GB), ($ip -join ','), $v.Generation, $v.AutomaticStartAction, $cp, $v.Uptime.TotalMinutes
}
"vCPU {0} on {1} LP = {2:N2}:1" -f $total, $lp, ($total / $lp)
"ISOs: " + ((Get-ChildItem F:\ISO -Filter *.iso | ForEach-Object { "{0} ({1:N2} GB)" -f $_.Name, ($_.Length / 1GB) }) -join ', ')
$isoFiles = @(Get-ChildItem F:\ISO -Filter *.iso -ErrorAction SilentlyContinue)
"Stray mounted images: " + $(if ($isoFiles.Count) { @(Get-DiskImage -ImagePath $isoFiles.FullName | Where-Object Attached).Count } else { 0 })
