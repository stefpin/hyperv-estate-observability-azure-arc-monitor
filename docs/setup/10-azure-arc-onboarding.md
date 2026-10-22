# 10. Azure Arc onboarding, resource tags and Arc Run Command

This chapter connects the lab machines to Azure Arc, applies the correct resource tags and verifies Arc Run Command. Azure Arc lets you manage non-Azure or edge servers as Azure resources. Arc Run Command is different from Azure VM Run Command, so keep the two planes separate. Use this chapter after the host and the guests are running and before you install Azure Monitor Agent ([chapter 11](11-azure-monitor-agent-and-dcrs.md)). When onboarding is complete, the Azure Arc **Machines** list shows all six lab machines with the status **Connected**.

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables (such as `$RG`) and the `Invoke-Lab*` helpers that it provides.

## 10.1 Generate and execute the correct regional onboarding script

**What you are doing:** you generate the correct onboarding script in the Azure Portal and then run it on the target machine itself. The region and resource name must match the intended Arc machine exactly.

| Machine | Operating system in the script generator | Location |
|---|---|---|
| `HV-HOST-01` | Windows | the primary region (`<PRIMARY_REGION>`) |
| `WIN2019-GUEST`, `WIN2022-GUEST`, `WIN2025-GUEST-01` | Windows | the primary region |
| `RHEL94-GUEST` | Linux | the primary region |
| `SQL2019-GUEST` | Windows | Southeast Asia (separate script) |

> **Why:** `SQL2019-GUEST` is onboarded into a secondary region (Southeast Asia, `southeastasia`, in this lab kit) because some management features are not available in every region. This lab uses that region for SQL Server enabled by Azure Arc, Change Tracking and Update Manager.

In the Azure Portal, generate the script:

1. Go to the Azure portal.
2. In the search box, open **Azure Arc**.
3. Click **Machines**.
4. Click **Add/Create**.
5. Click **Add a single server**.
6. Click **Generate script**.
7. Choose the lab subscription and resource group.
8. Choose operating system **Windows** for the host and the Windows guests.
9. Choose operating system **Linux** for RHEL.
10. Set Location to the primary region for the host and the four original guests.
11. For `SQL2019-GUEST`, generate a separate script with **Southeast Asia**.
12. Do not add the cluster tag to a shared script.
13. Review the script carefully.
14. Download it to an administrator-only folder on the guest or host.
15. Run it from that machine's elevated PowerShell window on Windows, or with `sudo bash` on RHEL.
16. Complete the prompted operator sign-in.
17. Give `--resource-name` explicitly if the machine's short hostname differs.
18. Go back to **Arc > Machines**.
19. Filter to this resource group.
20. Click **Refresh** until the machine shows Connected.

> **Warning:** The portal script is only a convenience for installing the agent. Keep the lab resource group; do not select a different one.

> **Fresh build only:** the host and the nested guests must be protected from the Azure Instance Metadata Service before you run the installation script, or the Azure Connected Machine agent refuses to onboard them. Complete sections [9.2](09-lab-only-azure-vm-disguise-and-imds-protection.md#92-host-and-windows-nested-guest-metadata-reachability) and [9.3](09-lab-only-azure-vm-disguise-and-imds-protection.md#93-rhel-can-reach-host-routed-imds-unless-explicitly-blocked) first. Disabling the Azure VM guest agent on the host ([section 9.4](09-lab-only-azure-vm-disguise-and-imds-protection.md#94-disable-the-azure-vm-guest-agent-on-the-host-fresh-build-after-arc-onboarding)) comes after the host is Connected.

The Windows example below onboards `SQL2019-GUEST`.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** Run it on the guest itself, not on your own computer.

```powershell
$Arc = "$env:ProgramFiles\AzureConnectedMachineAgent\azcmagent.exe"
& $Arc check --location southeastasia
& $Arc connect --resource-name SQL2019-GUEST `
  --resource-group rg-hyperv-arc-monitor-demo `
  --tenant-id <TENANT_ID> `
  --subscription-id <SUBSCRIPTION_ID> `
  --location southeastasia --cloud AzureCloud
& $Arc show
```

Replace `<TENANT_ID>` and `<SUBSCRIPTION_ID>` with the tenant ID and subscription ID of your lab.

**What you should see:** the check shows that all required endpoints are reachable, and the agent ends in Agent Status **Connected** with the correct resource name, resource group and location. Do not reconnect an already Connected machine. For the host and the other Windows guests, substitute their exact names and use `<PRIMARY_REGION>` as the location. For RHEL use `sudo azcmagent check --location <PRIMARY_REGION>`, then the same resolved identifiers and name with `sudo azcmagent connect`.

> **Warning:** Short-lived-token automation uses a protected configuration file with an administrator-only ACL and removes it immediately. Do not put tokens on a command line that others can see (for example in a screen share), and do not leave a protected-parameter JSON file in a cloud-synced folder. Interactive onboarding is the safer route when you are not familiar with token lifecycle handling.

## 10.2 Machine list and cluster tag

**What you are doing:** you confirm the Arc machine list and tag only the three cluster-member Windows guests with the cluster tag.

In the Azure Portal:

1. Go to **Arc > Machines**.
2. Filter to the correct resource group.
3. Select `WIN2019-GUEST`, `WIN2022-GUEST` and `WIN2025-GUEST-01` only.
4. Click **Assign tags**.
5. Add `cluster` = `WIN-CLUSTER-01`.
6. Click **Save**.

If you prefer, you can also open each machine individually and use **Tags > Apply**.

> **Warning:** Do not tag the host, the RHEL guest or the SQL guest as cluster members.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
foreach ($n in 'WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01') {
  $id = az connectedmachine show -g $RG -n $n --query id -o tsv
  Invoke-LabAz tag update --resource-id $id --operation Merge `
    --tags cluster=WIN-CLUSTER-01 -o none
}
az connectedmachine list -g $RG `
  --query "[].{Name:name,Region:location,Status:status,Cluster:tags.cluster}" -o table
```

**What you should see:** six Connected Arc machines in total, exactly three of them with the cluster tag value, and the SQL machine in Southeast Asia. Names align with the Hyper-V VM names; resource-name filtering is case-insensitive.

## 10.3 Arc Run Command, not Azure VM Run Command

**What you are doing:** you verify Arc Run Command on the Arc machine, not Azure VM Run Command on the Azure VM plane.

In the Azure Portal, when the feature is available, use the Arc path only:

1. Go to **Azure Arc**.
2. Click **Machines**.
3. Open `HV-HOST-01`.
4. Click **Run command**.
5. Select only the script you intend to inspect or run.
6. Verify that the parameters contain no secret in an ordinary field.

Bastion is the manual equivalent when an Arc Run Command editor is unavailable.

For the helper-based check, initialize the lab-kit context and call the supplied scoped helper. It resolves **the machine's actual Arc location**, creates a `Microsoft.HybridCompute` runCommands child resource, passes protected parameters through a private file that is not synced anywhere, polls the instance state, checks the exit code, and deletes the run-command record and the parameter file.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
Invoke-LabArcScript -Machine HV-HOST-01 `
  -ScriptPath .\status-host.ps1 -TimeoutSeconds 600
```

**What you should see:** a short host inventory and a successful result. The helper does not infer the machine region from the resource group. A command on `SQL2019-GUEST` uses Southeast Asia (the location of that Arc machine) even though the resource group's own location is the primary region. Do not run a guest-changing script merely to test this transport. On a fresh build, `HV-HOST-01` is now ready for `host-azure-vm-disguise.ps1`, which is run through the same helper in [section 9.4](09-lab-only-azure-vm-disguise-and-imds-protection.md#94-disable-the-azure-vm-guest-agent-on-the-host-fresh-build-after-arc-onboarding).
