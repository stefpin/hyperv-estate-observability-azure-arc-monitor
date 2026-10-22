# 5. Create and access the Azure Hyper-V host

This chapter creates the Azure VM `HV-HOST-01`, which acts as the outer Hyper-V host, and shows how to reach it and its nested guests. Before you start, the Azure foundation from [Chapter 4](04-azure-foundation.md) must exist (`vnet-arc-lab` with `snet-lab`, the NAT gateway and Bastion) and the host administrator password (`HOST_ADMIN_PASSWORD`) and the host image (`HOST_IMAGE`) must be available in your private `ENVIRONMENT.txt`, which `lab-kit\Initialize-LabSecrets.ps1` creates (see [Placeholders and ENVIRONMENT.txt](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt) in Chapter 2). If `HV-HOST-01` already exists, only verify it.

## 5.1 Host creation settings

This section creates the Azure VM that will act as the outer Hyper-V host, but only when that host does not already exist. When the VM is created, its Overview page shows the power state `Running` and the size `Standard_E8s_v5`, and its Disks page shows the 128 GiB Premium SSD OS disk and the 512 GiB data disk.

**Portal path, only when the host does not exist:**

1. Open `https://portal.azure.com`.
2. In the top search box, type `Virtual machines` and press Enter.
3. Click `Virtual machines`.
4. Click `Create`.
5. Click `Azure virtual machine`.
6. Choose the resource group `rg-hyperv-arc-monitor-demo`.
7. In the `Virtual machine name` box, type `HV-HOST-01`.
8. In the `Region` box, choose your primary region.
9. On the `Basics` tab, do not select redundancy that is not required.
10. Set **Security type** to `Standard`, not Trusted Launch.
11. For the image, choose **Windows Server 2025 Datacenter - x64 Gen2**, not Azure Edition or Server Core.
12. For the size, choose **Standard_E8s_v5**.
13. For the administrator account, use username `labadmin`; enter the host password privately (it is the value of `HOST_ADMIN_PASSWORD` in your private `ENVIRONMENT.txt`).
14. Set public inbound ports to `None`.
15. Do not claim Azure Hybrid Benefit without entitlement.
16. Go to `Disks`.
17. Use a `128 GiB` Premium SSD OS disk.
18. Add a `512 GiB` Premium SSD data disk named `HV-HOST-01-data`.
19. Set the data disk caching to `Read/write`.
20. Go to `Networking`.
21. Select virtual network `vnet-arc-lab`.
22. Select subnet `snet-lab`.
23. Set public IP to `None`.
24. Set NIC NSG to `None` for this isolated lab.
25. Do not create an internet-exposed RDP rule.
26. Go to `Management`.
27. Set patch orchestration to `Manual updates`.
28. Turn automatic updates off.
29. Turn auto-shutdown off.
30. Under monitoring, leave managed boot diagnostics on.
31. Review carefully: Standard security and E8s_v5 are the nested-virtualization prerequisites.
32. Create the VM.
33. Wait until the VM power state is `Running`.

**CLI path:** use `lab-kit/New-LabHost.ps1`. It loads the host password and the image name from `ENVIRONMENT.txt` in memory (`HOST_ADMIN_PASSWORD`, `HOST_IMAGE`; it stops if either is missing), verifies the account scope, uses the same image and settings, and skips an existing host rather than deleting it. It creates the network interface `HV-HOST-01-nic` on `vnet-arc-lab`/`snet-lab` (no public IP, no NSG, accelerated networking off), the VM `HV-HOST-01` (`Standard_E8s_v5`, security type `Standard`, patch mode `Manual`, automatic updates off, administrator `labadmin`), the 128 GiB Premium SSD OS disk `HV-HOST-01-osdisk`, the 512 GiB Premium SSD data disk `HV-HOST-01-data` with `ReadWrite` caching, and managed boot diagnostics:

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI, in the `lab-kit` folder, after the [Chapter 2](02-tools-secrets-and-conventions.md) setup has been completed.

```powershell
.\New-LabHost.ps1
az vm show -g $RG -n HV-HOST-01 --show-details `
  --query "{Size:hardwareProfile.vmSize,Security:securityProfile.securityType,Patch:osProfile.windowsConfiguration.patchSettings.patchMode,AutoUpdate:osProfile.windowsConfiguration.enableAutomaticUpdates,Power:powerState,IP:privateIps}" -o json
```

**What you should see:** the script prints `Host created; proceed through Bastion, not Azure VM Run Command.` (or `Host exists: no create, delete or restart performed.` if the host is already there). The query shows `E8s_v5`, `Standard`, `Manual`, `false`, `running`, `10.50.1.4`. If the host was already built with an unsuitable security type or size, do not delete it spontaneously: record its current settings and write down a rebuild plan before you change anything. A setting that is fixed at VM creation (size, security type) cannot be adjusted later.

## 5.2 Bastion and a guest terminal

This section shows you how to reach the host VM and, from there, how to reach the nested guest VMs. The first connection is through Azure Bastion in the browser.

**Portal path:**

1. Open `https://portal.azure.com`.
2. In the top search box, type `HV-HOST-01` and press Enter.
3. Click the **Azure VM** `HV-HOST-01` (not its Arc record).
4. In the top menu or left-hand menu, click **Connect > Bastion**. The Connect page offers the Bastion option with a **Go to Bastion** button.
5. Set authentication to `Password`.
6. Enter username `labadmin`.
7. Enter the host password privately.
8. Click **Connect**.
9. Allow the browser popup if your browser asks.
10. After the remote desktop opens, go to the host desktop.
11. Click `Start`, type `Windows PowerShell`, right-click it, then click **Run as administrator**.
12. Click **Yes** on the UAC prompt.
13. Confirm the window title begins with `Administrator`.
14. For a Windows guest console, run `vmconnect.exe localhost SQL2019-GUEST`, select **Connect**, and sign in as `labadmin`.
15. Use enhanced session if available.
16. For command-line work inside a Windows guest, use PowerShell Direct from the host PowerShell window: `Enter-PSSession -VMName SQL2019-GUEST -Credential (Get-Credential labadmin)`.
17. When prompted, enter the guest's password, not the host's.
18. Confirm the prompt changes to `[SQL2019-GUEST]:`.
19. Run `hostname` before making changes, so you know you are in the guest and not the host.
20. Leave that guest session with `Exit-PSSession`.
21. For RHEL, in host PowerShell run `ssh -l labadmin 192.168.100.14` (`-l` sets the user name).
22. Verify the fingerprint on first use.
23. Enter the RHEL password.
24. Confirm the prompt is now Bash.

**CLI path:** Azure CLI cannot directly open a Basic Bastion browser desktop by executing a guest command. Query the host private address, then use the Portal access path above:

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI. This command is only to confirm the host details before you open Bastion in the browser.

```powershell
az vm show -g $RG -n HV-HOST-01 --show-details `
  --query "{Name:name,PrivateIP:privateIps,Power:powerState}" -o table
```

For automation on the existing Arc-connected host, use **Arc Run Command** with `Invoke-LabArcScript` (see [Chapter 10](10-azure-arc-onboarding.md)). Do not use `az vm run-command invoke/create`: the Azure VM agent was intentionally disabled for this lab and that path is unavailable. For an entirely new host before Arc exists, configure it through Bastion; do not assume Arc Run Command can run before onboarding.
