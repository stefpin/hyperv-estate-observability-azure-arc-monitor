# 7. Build all five guests and verify identities

This chapter creates the Windows guest virtual machines used by the rest of the lab: the three noisy neighbours `WIN2019-GUEST`, `WIN2022-GUEST` and `WIN2025-GUEST-01`, and the dedicated SQL guest `SQL2019-GUEST`. The fifth guest, `RHEL94-GUEST`, is built in [Chapter 8](08-rhel-guest-and-linux-collectors.md). Take your time here. If the names, IP settings or operating system media are wrong now, the Azure Arc and Azure Monitor steps later will not line up correctly. Before you start, the host must have Hyper-V, the `VmNAT` switch and `LocalNAT` ([Chapter 6](06-host-os-hyper-v-and-guest-network.md)); to use the prepared automation, the lab kit must also be on the host at `F:\Build\lab-kit` (see [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)). The build steps are for the initial build only: do not recreate, or reduce the memory of, a guest that is already installed and live.

## 7.1 Windows media and three noisy neighbours

**What you are doing:** you are downloading the correct Windows installation media and building the three Windows guest virtual machines that will act as the noisy neighbours in the demo.

> **RUN ON - Hyper-V host, desktop and elevated PowerShell**
>
> Do this on: the Hyper-V host environment for this lab. Use the host desktop when you need a browser or Hyper-V Manager. Use an elevated PowerShell window on that same host when a PowerShell block appears.

For the Windows ISO downloads, do the following:

1. On the host desktop, open a browser.
2. Go to the official Microsoft Evaluation Center.
3. Download the Windows Server 2019, 2022 and 2025 x64 evaluation ISOs.
4. Save exactly `F:\ISO\WindowsServer2019.iso`, `F:\ISO\WindowsServer2022.iso` and `F:\ISO\WindowsServer2025.iso`.
5. Match the selected OS media with the corresponding guest; use Desktop Experience if following GUI steps.

If you ran `lab-kit/host-hyperv.ps1` in [section 6.3](06-host-os-hyper-v-and-guest-network.md#63-internal-switch-and-nat), the three ISOs are already in `F:\ISO` under exactly these names. In that case skip steps 1 to 4, run `Get-ChildItem F:\ISO` in the elevated PowerShell window and check that all three files are present.

For each Windows guest, use **Hyper-V Manager > New > Virtual Machine** and work through the wizard carefully:

1. Enter the guest name from the machine table in [Chapter 1](01-scope-architecture-and-success-criteria.md).
2. Set the location to `F:\VMs`.
3. Choose **Generation 2**.
4. Set Startup RAM to 8192 MB for the three noisy neighbours.
5. Make sure **Dynamic Memory** is unchecked.
6. Connect the VM to network `VmNAT`.
7. Create a dynamically expanding VHDX of 127 GB.
8. Attach the matching OS ISO for that guest.
9. Before you start the VM, open **Settings > Processor** and set four virtual processors.
10. In **Automatic Start Action**, set the VM to always start and add a delay of 30 seconds.
11. In **Automatic Stop Action**, select **Save the virtual machine state**. A restart of the host then saves and resumes the guests instead of rebooting them. [Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md) checks this setting and refuses to continue if a guest has another value.
12. Disable automatic checkpoints.
13. Click **Connect > Start**.
14. When prompted, press a key so the VM boots from the DVD.
15. In Windows Setup, choose English.
16. Select the matching **Standard Evaluation (Desktop Experience)** edition.
17. Accept the license terms.
18. Choose **Custom** installation.
19. Select the intended blank virtual disk.
20. Finish the setup and create the Administrator password privately.
21. After setup, create a local `labadmin` account and add it to Administrators.
22. Set the computer name before Arc onboarding.
23. Configure the IP address, gateway, and DNS from the machine table in [Chapter 1](01-scope-architecture-and-success-criteria.md).
24. Set notifications/manual update behavior for demo stability. The prepared builder sets the Windows Update policy to notify only (`AUOptions=2`, no automatic restart with signed-in users), so that updates are never installed by the guest itself; Azure Update Manager ([Chapter 20](20-update-manager.md)) is the only mechanism that patches the lab.
25. Set the time zone to `SE Asia Standard Time` (UTC+7).
26. Set the `labadmin` password to never expire.
27. Restart only during the initial installation.

If you use the prepared automation instead of clicking through the full Windows setup, use the lab kit exactly as provided. `build-guest.ps1` (part of the lab kit copied to `F:\Build\lab-kit`) applies the ISO image offline, creates a protected unattend file, creates `labadmin`, configures networking and removes first-boot answer files. Use `lab-kit/Build-LabWindowsGuest.ps1` on the host; it prompts for a guest password rather than printing it. For WIN2025, the full DNS/Hyper-V/Arc name is 16 characters; the Windows NetBIOS short name is `WIN2025-GUEST-0`. Do not rename the Arc resource to the truncated name. The script takes only `-GuestName` and chooses the matching ISO, address and memory itself: `WIN2019-GUEST` uses `WindowsServer2019.iso`, `192.168.100.11` and 8 GB; `WIN2022-GUEST` uses `WindowsServer2022.iso`, `192.168.100.12` and 8 GB; `WIN2025-GUEST-01` uses `WindowsServer2025.iso`, `192.168.100.13` and 8 GB; `SQL2019-GUEST` uses `WindowsServer2022.iso`, `192.168.100.15` and 12 GB. Every guest gets four vCPU, static memory, the `VmNAT` switch, automatic start with a 30-second delay, the stop action **Save** and no automatic checkpoints. The script stops with `Existing guest is preserved; do not rebuild.` if a VM of that name already exists.

> **RUN ON - Hyper-V host, elevated PowerShell, initial build only**
>
> Do this on: the Hyper-V host, in an elevated PowerShell window. Only do this during the initial build.

```powershell
Set-Location F:\Build\lab-kit
.\Build-LabWindowsGuest.ps1 -GuestName WIN2019-GUEST
.\Build-LabWindowsGuest.ps1 -GuestName WIN2022-GUEST
.\Build-LabWindowsGuest.ps1 -GuestName WIN2025-GUEST-01
```

**What you should see:** all three guests should be in the Running state. Each one should have four vCPU, eight GB memory, the correct IP address, and the correct DNS name. The builder refuses an existing VM rather than treating it as a disposable stale disk. Do not recreate or reduce memory on an already installed live guest.

### Manual guest identity and network details, including the 16-character Windows name

**What you are doing:** you are checking and, if needed, correcting the Windows computer name and static IPv4 settings inside each guest. This matters because Arc onboarding later depends on the right machine identity.

> **RUN ON - Windows guest, desktop**
>
> Do this on: the guest virtual machine itself. Sign in to the guest desktop first. For WIN2019-GUEST, WIN2022-GUEST, and SQL2019-GUEST, you can use the normal Windows rename dialog. For WIN2025-GUEST-01, you must also use the PowerShell step below to keep the full DNS hostname.

To set or verify the computer name in the Windows guest desktop:

1. Open **Server Manager**.
2. Click **Local Server**.
3. Next to **Computer name**, click the current name.
4. In System Properties, click **Change**.
5. Enter the computer name.
6. For WIN2019-GUEST, WIN2022-GUEST and SQL2019-GUEST, the full name fits normally.
7. **WIN2025-GUEST-01 is 16 characters**: enter short computer name **WIN2025-GUEST-0**, not an invalid 16-character value.

The Azure Portal and that dialog do not expose the full-name operation used here. Open elevated PowerShell in this guest and run the supported Windows API step below, exactly as the verified automated builder does; do not substitute direct registry edits. Restart that guest during initial setup, before Arc onboarding. Windows keeps the full DNS hostname and truncates its NetBIOS counterpart to 15 characters. Use the full name explicitly as Arc `--resource-name` and as the Hyper-V VM name.

To set the static IPv4 address in the Windows guest desktop:

1. Open **Control Panel**.
2. Click **Network and Internet**.
3. Click **Network and Sharing Center**.
4. Click **Change adapter settings**.
5. Right-click **Ethernet**, then click **Properties**.
6. Click **Internet Protocol Version 4 (TCP/IPv4)**, then click **Properties**.
7. Choose **Use the following IP address**.
8. Enter the guest's `.11`, `.12`, `.13` or `.15` address from the machine table in [Chapter 1](01-scope-architecture-and-success-criteria.md).
9. Enter the /24 subnet mask in the four boxes of the dialog: **255**, **255**, **255**, **0**.
10. Enter gateway **192.168.100.1**.
11. Enter preferred DNS **8.8.8.8**.
12. Enter alternate DNS **1.1.1.1**.
13. Click **OK**, then click **OK** again.

Do not use the outer Azure VNet's 10.50.x address inside the guest.

If you need the full DNS hostname operation for WIN2025-GUEST-01, do this:

> **RUN ON - Windows guest WIN2025-GUEST-01, elevated PowerShell, initial build only**
>
> Do this on: the `WIN2025-GUEST-01` guest itself, in an elevated PowerShell window, during the initial build.

```powershell
Add-Type -Namespace Hv -Name Native -MemberDefinition @'
[DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
public static extern bool SetComputerNameEx(int NameType, string lpBuffer);
'@
$ok = [Hv.Native]::SetComputerNameEx(5,'WIN2025-GUEST-01')
if (-not $ok) {
  throw "Hostname operation failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}
# Restart this guest only during initial setup, before Arc onboarding.
Restart-Computer
```

For command-line verification, the supplied builder performs the same static IPv4/DNS steps automatically. Read-only verification inside any Windows guest uses `Get-NetIPConfiguration` and `[Net.Dns]::GetHostName()`:

> **RUN ON - Windows guest, elevated PowerShell**
>
> Do this on: the guest virtual machine itself. These commands are read-only.

```powershell
Get-NetIPConfiguration
[Net.Dns]::GetHostName()
```

On WIN2025-GUEST-01, `$env:COMPUTERNAME` can remain `WIN2025-GUEST-0` while the DNS/Hyper-V/Arc name is `WIN2025-GUEST-01`; that distinction is expected, not a reason to delete the Arc machine.

## 7.2 Dedicated SQL guest

**What you are doing:** you are building the separate Windows guest that will later hold the SQL Server role for the demo.

> **RUN ON - Hyper-V host, Hyper-V Manager or elevated PowerShell**
>
> Do this on: the Hyper-V host environment for this lab. Use Hyper-V Manager for the wizard, or the elevated PowerShell window on the host for the prepared build command.

Build this VM the same way as the Windows Server 2022 guest, but use the SQL-specific values:

1. Create a guest named **SQL2019-GUEST**.
2. Assign 12288 MB static RAM.
3. Assign four vCPU.
4. Set the IP to `192.168.100.15`.
5. Use a separate guest for this role.
6. Do not install SQL Server on WIN2022-GUEST.
7. Use the same 127 GB OS VHDX.
8. The additional data and log disks are added later (see [Chapter 12](12-sql-server-installation.md)).

> **RUN ON - Hyper-V host, elevated PowerShell, initial build only**
>
> Do this on: the Hyper-V host, in an elevated PowerShell window. Only do this during the initial build.

```powershell
Set-Location F:\Build\lab-kit
.\Build-LabWindowsGuest.ps1 -GuestName SQL2019-GUEST
Get-VM | Select-Object Name,State,ProcessorCount,MemoryAssigned
```

**What you should see:** the SQL guest should be Running with 12 GB assigned, and it should be Windows Server 2022 Standard Evaluation. Its guest CPU is not capped and no Resource Governor pool is configured in this lab.

## 7.3 Verify and remove installation DVDs

**What you are doing:** you are performing a final check on the Windows guests and then removing the attached installation ISOs so the VMs do not keep booting from DVD media.

> **RUN ON - Each guest (manual checks) and the Hyper-V host (PowerShell block)**
>
> Do this on: each guest virtual machine for the manual checks, and on the Hyper-V host for the PowerShell block.

For the manual checks in each guest:

1. Sign in to the guest.
2. Open **Settings > System > About** or System Properties.
3. Confirm the hostname is correct.
4. Open **Network Connections**.
5. Open **Ethernet > IPv4**.
6. Confirm the IP address is correct.

For the DVD removal:

1. In Hyper-V Manager, select the VM.
2. Click **Settings**.
3. Click **DVD Drive**.
4. Change the media selection to **None** after setup.
5. Repeat for each Windows guest.

> **RUN ON - Hyper-V host, elevated PowerShell**
>
> Do this on: the Hyper-V host, in an elevated PowerShell window.

```powershell
Get-VM | Format-Table Name,State,ProcessorCount,MemoryAssigned
foreach ($n in 'WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','SQL2019-GUEST') {
  Get-VMDvdDrive -VMName $n | Set-VMDvdDrive -Path $null
}
Enter-PSSession -VMName SQL2019-GUEST -Credential (Get-Credential labadmin)
hostname
Get-NetIPConfiguration
Get-LocalUser labadmin | Select-Object Name,Enabled,PasswordExpires
Exit-PSSession
```

**What you should see:** each guest should show the correct name and IP address. The `labadmin` account should not show an unexpected expiring password. There should be no unattended file left by the builder.

Once the host is onboarded to Azure Arc ([Chapter 10](10-azure-arc-onboarding.md)), you can repeat these checks for all four Windows guests from your operator PC with `lab-kit/verify-guest.ps1`. The script runs on `HV-HOST-01` through Arc Run Command, signs in to each guest through PowerShell Direct (no guest network is needed) and reports the VM settings, the DNS and NetBIOS names, the address, gateway and DNS servers, internet access on port 443, the Windows licence state (it tries to activate an unlicensed guest), whether the first-boot marker is present and the answer file is gone, the Windows Update policy, the time zone and the `labadmin` password expiry. It also tests whether the guest can reach the Azure Instance Metadata Service at `169.254.169.254`, which must not be possible ([Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md)). Credential parameters belong in **protectedParameters**, not in the ordinary (non-protected) command parameters; `Invoke-LabArcScript` does this when you pass them with `-Protected`.

> **RUN ON - Operator PC, PowerShell in the lab-kit folder**
>
> Do this on: your own computer, in the `lab-kit` folder, after loading the lab context and signing in as described in [Chapter 2](02-tools-secrets-and-conventions.md). The host must be Arc-connected and the guest passwords must be in the private `ENVIRONMENT.txt` in the repository root (created with `lab-kit\Initialize-LabSecrets.ps1`, see [Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

```powershell
. .\context.ps1
$settings = Get-LabSettings
$guests = [ordered]@{
  'WIN2019-GUEST'    = $settings.WIN2019_GUEST_PASSWORD
  'WIN2022-GUEST'    = $settings.WIN2022_GUEST_PASSWORD
  'WIN2025-GUEST-01' = $settings.WIN2025_GUEST_PASSWORD
  'SQL2019-GUEST'    = $settings.SQL_GUEST_PASSWORD
}
foreach ($name in $guests.Keys) {
  Write-Host "=== $name"
  Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\verify-guest.ps1 `
    -Parameters @{ GuestName = $name } `
    -Protected @{ GuestPasswordHex = (ConvertTo-LabHex $guests[$name]) }
}
$settings = $null; $guests = $null
```

**What you should see:** for every guest the output ends with `VERIFY-DONE`. The line `Host name: DNS=<name> NetBIOS=<short name> expected=<name> match=True` confirms the identity (for `WIN2025-GUEST-01` the NetBIOS name is `WIN2025-GUEST-0`), `Network:` shows the guest's `192.168.100.x` address, the gateway `192.168.100.1` and `internet443=True`, `Azure metadata service 169.254.169.254: not reachable` confirms the block, and the last status line shows `First boot done=True answer_file_left=False WU_AUOptions=2 timezone=SE Asia Standard Time labadmin_password_expires=never`. If the metadata service is reachable the script stops with `The guest can reach the Azure metadata service - Azure Arc would refuse to onboard it`; complete [Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md) first.
