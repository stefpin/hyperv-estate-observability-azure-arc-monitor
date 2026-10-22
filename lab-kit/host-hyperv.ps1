# host-hyperv.ps1 - runs ON THE HYPER-V HOST after its restart (operator guide chapter 6).
#   1 confirms the hypervisor is running (proves nested virtualisation works on this VM size)
#   2 switches on enhanced session mode (copy and paste into guests) and puts all guest files on F:\VMs
#   3 creates the internal switch VmNAT, gives the host 192.168.100.1 on it, and creates NAT LocalNAT
#   4 downloads the three Windows Server evaluation ISOs into F:\ISO (about 17.5 GB, 5 to 15 minutes)
# Safe to run again: anything already in place is left alone.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'HV-HOST-01') { throw 'Run only on the intended Hyper-V host.' }
if (-not (Get-CimInstance Win32_ComputerSystem).HypervisorPresent) { throw 'Nested virtualization is unavailable; no network/media changes performed.' }
"Uptime (min): {0:N1}" -f ((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes
"Hyper-V role: " + (Get-WindowsFeature -Name Hyper-V).InstallState
"HypervisorPresent: " + (Get-CimInstance Win32_ComputerSystem).HypervisorPresent

Set-VMHost -EnableEnhancedSessionMode $true -VirtualHardDiskPath 'F:\VMs' -VirtualMachinePath 'F:\VMs'
if (-not (Get-VMSwitch -Name 'VmNAT' -ErrorAction SilentlyContinue)) {
    New-VMSwitch -Name 'VmNAT' -SwitchType Internal | Out-Null
}
if (-not (Get-NetIPAddress -InterfaceAlias 'vEthernet (VmNAT)' -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object IPAddress -eq '192.168.100.1')) {
    New-NetIPAddress -IPAddress 192.168.100.1 -PrefixLength 24 -InterfaceAlias 'vEthernet (VmNAT)' | Out-Null
}
if (-not (Get-NetNat -Name 'LocalNAT' -ErrorAction SilentlyContinue)) {
    New-NetNat -Name 'LocalNAT' -InternalIPInterfaceAddressPrefix '192.168.100.0/24' | Out-Null
}
"Switch: " + ((Get-VMSwitch | ForEach-Object { "$($_.Name)/$($_.SwitchType)" }) -join ', ')
"NAT: " + ((Get-NetNat | ForEach-Object { "$($_.Name) $($_.InternalIPInterfaceAddressPrefix)" }) -join ', ')
"Host vNIC IP: " + ((Get-NetIPAddress -InterfaceAlias 'vEthernet (VmNAT)' -AddressFamily IPv4).IPAddress)
$h = Get-VMHost
"Enhanced session: {0}  VHD path: {1}  VM path: {2}  LPs: {3}" -f $h.EnableEnhancedSessionMode, $h.VirtualHardDiskPath, $h.VirtualMachinePath, $h.LogicalProcessorCount

# Windows Server evaluation media (English, United States). Microsoft's Evaluation Center links.
$links = [ordered]@{
    'WindowsServer2025.iso' = 'https://go.microsoft.com/fwlink/?linkid=2345730&clcid=0x409&culture=en-us&country=us'
    'WindowsServer2022.iso' = 'https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US'
    'WindowsServer2019.iso' = 'https://go.microsoft.com/fwlink/p/?LinkID=2195167&clcid=0x409&culture=en-us&country=US'
}
foreach ($n in $links.Keys) {
    $dest = "F:\ISO\$n"
    if (-not (Test-Path $dest)) {
        $t = Get-Date
        & curl.exe -L --fail --retry 3 --silent --show-error -o $dest $links[$n]
        if ($LASTEXITCODE -ne 0) { Remove-Item $dest -Force -ErrorAction SilentlyContinue; throw "download failed: $n (curl exit $LASTEXITCODE)" }
        "{0} {1:N2} GB in {2:N0}s" -f $n, ((Get-Item $dest).Length / 1GB), ((Get-Date) - $t).TotalSeconds
    } else { "{0} already present ({1:N2} GB)" -f $n, ((Get-Item $dest).Length / 1GB) }
}
