# 6. Host operating system, Hyper-V and guest network

This chapter prepares the host operating system on `HV-HOST-01`: it initializes the blank data disk as `F:`, installs the Hyper-V role, and builds the internal virtual switch and NAT that give the nested guests their `192.168.100.0/24` network. Before you start, `HV-HOST-01` must be running and you must be able to connect to it through Bastion ([Chapter 5](05-create-the-hyper-v-host.md)). The steps that format a disk and restart the host are for the initial build only. Nothing in this chapter changes an Azure resource: in Azure Portal the host's Networking page keeps showing its private IP address.

## 6.1 Initialize only the intended blank data disk

This section prepares the host's extra data disk for VM files. Be very careful here, because the goal is to touch only the blank `512 GB` data disk and not the OS disk.

**Portal path:** in the Bastion host desktop, right-click Start > **Disk Management**. Identify the blank **512 GB** data disk, not the OS disk. Initialize GPT, create a simple volume using the whole disk, NTFS, label HyperV, letter F:. Existing formatted disks are not initialized again. Create `F:\VMs`, `F:\ISO`, `F:\Build`.

To make that more explicit for a beginner, use these clicks:

1. Connect to `HV-HOST-01` through Bastion first.
2. Inside the remote desktop session, right-click the `Start` button.
3. Click `Disk Management`.
4. Wait for the disk list to load.
5. Identify the blank **512 GB** data disk, not the OS disk.
6. If Windows prompts you to initialize the disk, choose `GPT`.
7. Create a simple volume that uses the whole disk.
8. Format it as `NTFS`.
9. Set the volume label to `HyperV`.
10. Assign drive letter `F:`.
11. Do not re-initialize any disk that is already formatted.
12. Create the folders `F:\VMs`, `F:\ISO`, `F:\Build`.

**CLI/terminal path:** in an elevated PowerShell window on the host, `lab-kit/host-prepare.ps1` automates this section and the Hyper-V installation of section 6.2. It runs only on `HV-HOST-01` and stops with a message anywhere else. If an `F:` volume already exists, it must be the NTFS volume labelled `HyperV`; otherwise the script stops without formatting anything. If there is no `F:`, it requires exactly one blank (RAW) data disk of about 512 GB, initializes it as GPT and creates the `HyperV` volume as `F:`. It then creates `F:\VMs`, `F:\ISO` and `F:\Build`, sets the time zone, tests that the host reaches `login.microsoftonline.com` and `software-static.download.prss.microsoft.com` on port 443 through the NAT gateway, stops the `labadmin` password from expiring and installs the Hyper-V role. Read its code before a fresh build; do not run it on an arbitrary server. It does not need an Azure CLI inside the host. Before Azure Arc exists the script is not on the host yet, so paste its text into the elevated PowerShell window through the Bastion clipboard, or type the checks below by hand:

> **RUN ON - Hyper-V host, elevated PowerShell, fresh build only**
>
> Do this on: the `HV-HOST-01` virtual machine itself, after you have connected to it through Azure Bastion. Open an elevated PowerShell window on `HV-HOST-01` by clicking Start, typing `Windows PowerShell`, right-clicking it, and choosing **Run as administrator**. Make sure the title bar starts with `Administrator` before you type anything.

```powershell
Get-Disk | Format-Table Number,FriendlyName,PartitionStyle,Size
Get-Volume | Format-Table DriveLetter,FileSystemLabel,FileSystem,SizeRemaining
New-Item -ItemType Directory -Path F:\VMs,F:\ISO,F:\Build -Force | Out-Null
Set-TimeZone -Id 'SE Asia Standard Time'
Set-LocalUser -Name labadmin -PasswordNeverExpires $true
```

**What you should see:** `F:` `NTFS`, approximately `512 GB` before guests and media; the OS disk and any unrelated disks untouched. Password-never-expires is a demo safety choice for the lifetime of the lab, not a recommended production password policy. If you ran `host-prepare.ps1`, its output lists `F: label=HyperV free=<n> GB`, `TimeZone: SE Asia Standard Time`, `<name>:443 reachable=True` for both addresses, `labadmin password expires: never` and `Hyper-V install: Success=True RestartNeeded=Yes`; restart the host as described in section 6.2.

The Windows time zone `SE Asia Standard Time` is UTC+7. This guide calls that the lab's local time (LT) and states UTC alongside it whenever a time matters, for example `23:00 UTC = 06:00 LT`.

## 6.2 Install Hyper-V and restart once during initial build

This section installs the Hyper-V role on the outer host. This restart is allowed only during the initial build, before live guests are in use.

**Portal path:** Bastion > host **Server Manager > Manage > Add Roles and Features**. Role-based installation, local server, select **Hyper-V**, include management tools, no external switch, accept defaults, install. Only on the initial build, with no live guests, choose **Restart** when required. Reconnect Bastion after the host returns.

To make the Portal and host-desktop flow clearer, use these exact actions:

1. Connect to `HV-HOST-01` through Bastion.
2. In the host desktop session, open `Server Manager` if it is not already open.
3. In the top-right area, click `Manage`.
4. Click `Add Roles and Features`.
5. Choose `Role-based or feature-based installation`.
6. Choose the local server.
7. In the server roles list, select `Hyper-V`.
8. When asked, include the management tools.
9. Do not create an external switch.
10. Accept the remaining defaults.
11. Start the installation.
12. Only on the initial build, with no live guests, choose `Restart` when required.
13. Wait for the host to come back.
14. Reconnect Bastion after the host returns.

**CLI/terminal path, fresh host only:** if you ran `host-prepare.ps1` in section 6.1, the Hyper-V role is already installed and only the restart below remains.

> **RUN ON - Hyper-V host, elevated PowerShell, initial build**
>
> Do this on: the `HV-HOST-01` virtual machine itself, in an elevated PowerShell window opened on the host.

```powershell
Install-WindowsFeature -Name Hyper-V -IncludeManagementTools
# INITIAL BUILD ONLY: any later host restart must be planned as a maintenance action.
Restart-Computer
```

After reconnecting, verify rather than repeating the install:

> **RUN ON - Hyper-V host, elevated PowerShell**
>
> Do this on: the `HV-HOST-01` virtual machine itself, after it has restarted and you have connected again through Bastion. Open an elevated PowerShell window again if needed.

```powershell
Get-WindowsFeature Hyper-V
Get-CimInstance Win32_ComputerSystem |
  Select-Object Name,HypervisorPresent,NumberOfLogicalProcessors,TotalPhysicalMemory
```

**What you should see:** `Installed`, `HypervisorPresent True`, eight logical processors, approximately `64 GB`. A BIOS virtualization error on this Azure size usually means an incompatible host setting (see the prerequisites in [section 5.1](05-create-the-hyper-v-host.md#51-host-creation-settings)), not something a novice should attempt to change in a nonexistent guest BIOS menu.

## 6.3 Internal switch and NAT

This section builds the private virtual network inside Hyper-V. This is separate from the Azure virtual network. The Azure VNet is the outer cloud network. `VmNAT` is the inner guest network on the host.

**Portal path:** Bastion > host **Hyper-V Manager > Virtual Switch Manager > New virtual network switch > Internal > Create Virtual Switch**. Name `VmNAT`, Apply. Azure Portal's VNet subnet is not this Hyper-V switch. Set the host's `vEthernet (VmNAT)` IPv4 to `192.168.100.1/24` with **no gateway**; use the terminal command below to create the local NAT. Hyper-V Manager > host **Hyper-V Settings**: VM/VHD paths `F:\VMs`; enable Enhanced Session Mode Policy and Enhanced Session Mode.

To make the host-side clicks clearer, do this:

1. Connect to `HV-HOST-01` through Bastion.
2. In the host session, open `Hyper-V Manager`.
3. In the right-hand `Actions` pane, click `Virtual Switch Manager`.
4. Under `New virtual network switch`, select `Internal`.
5. Click `Create Virtual Switch`.
6. In the name box, type `VmNAT`.
7. Click `Apply`.
8. Remember that Azure Portal's VNet subnet is not this Hyper-V switch.
9. Set the host's `vEthernet (VmNAT)` IPv4 to `192.168.100.1/24` with **no gateway**.
10. Use the PowerShell commands below to create the local NAT.
11. In `Hyper-V Manager`, open the host `Hyper-V Settings`.
12. Set both VM and VHD paths to `F:\VMs`.
13. Enable `Enhanced Session Mode Policy`.
14. Enable `Enhanced Session Mode`.

**CLI/terminal path:** `lab-kit/host-hyperv.ps1` performs the network steps below in one run after the restart of section 6.2 (it can be run again: anything already in place is left alone). It stops with `Nested virtualization is unavailable; no network/media changes performed.` if the hypervisor is not running. It sets the Hyper-V VM and VHD paths to `F:\VMs` and turns on Enhanced Session Mode, creates `VmNAT`, the host address `192.168.100.1/24` and `LocalNAT` only if they are missing, and then downloads the three Windows Server evaluation ISOs from the Microsoft Evaluation Center into `F:\ISO` as `WindowsServer2019.iso`, `WindowsServer2022.iso` and `WindowsServer2025.iso` (about 17.5 GB in total, usually 5 to 15 minutes; files that already exist are skipped), so that [Chapter 7](07-build-the-guests.md) can start without a manual download. As in section 6.1, paste the script text into the elevated PowerShell window if the lab kit is not on the host yet. To type the same network steps by hand:

> **RUN ON - Hyper-V host, elevated PowerShell**
>
> Do this on: the `HV-HOST-01` virtual machine itself, in an elevated PowerShell window on the host.

```powershell
if (-not (Get-VMSwitch -Name VmNAT -ErrorAction SilentlyContinue)) {
  New-VMSwitch -Name VmNAT -SwitchType Internal | Out-Null
}
if (-not (Get-NetIPAddress -InterfaceAlias 'vEthernet (VmNAT)' `
    -IPAddress 192.168.100.1 -ErrorAction SilentlyContinue)) {
  New-NetIPAddress -InterfaceAlias 'vEthernet (VmNAT)' `
    -IPAddress 192.168.100.1 -PrefixLength 24 | Out-Null
}
if (-not (Get-NetNat -Name LocalNAT -ErrorAction SilentlyContinue)) {
  New-NetNat -Name LocalNAT -InternalIPInterfaceAddressPrefix 192.168.100.0/24 | Out-Null
}
Set-VMHost -VirtualHardDiskPath F:\VMs -VirtualMachinePath F:\VMs `
  -EnableEnhancedSessionMode $true
Get-VMSwitch -Name VmNAT
Get-NetNat -Name LocalNAT
```

**What you should see:** `Internal` switch type for `VmNAT`, and `LocalNAT` for `192.168.100.0/24`. Do not bridge an external switch to the Azure NIC; unrecognized nested MAC traffic is not a working alternative here. Keep the Azure host NIC's DHCP/configuration unchanged. If you ran `host-hyperv.ps1`, it also prints the switch, the NAT, the host address on `vEthernet (VmNAT)` and the Enhanced Session Mode setting, followed by one line per ISO file.

To check the host at any time without changing anything, run `lab-kit/status-host.ps1` on the host. It is read-only and reports the host, `F:`, `VmNAT`, `LocalNAT`, every guest (state, vCPU, memory, address, automatic start action, checkpoints, uptime), the vCPU-to-logical-processor ratio and the files in `F:\ISO`.
