# 1. Scope, architecture and success criteria

This chapter describes what the lab is and how to tell that it is complete: the machines and their sizing, the network and storage layers, where each kind of data lives (the region and identity map) and the completion checks. It is the reference for every later chapter. Nothing has to be built before you read it. To run the verification commands in section 1.2 the lab must already exist and your operator PC must be set up as described in [Chapter 2](02-tools-secrets-and-conventions.md); on a new build, return to those checks once the Azure foundation and the host are in place.

## 1.1 What exists

This section explains what this demonstration lab really is, so that it can be described honestly and consistently.

The outer host is an **Azure Windows Server 2025 virtual machine**, `HV-HOST-01`, in the primary region, size `Standard_E8s_v5`: eight logical processors (LP) and 64 GB RAM. It runs five nested Hyper-V guests. The lab simulates the monitoring of an on-premises estate; it is not physically an on-premises host. Its Azure Arc resource does not change that fact. Heartbeat can label this host `ComputerEnvironment=Azure`; do not hide that fact through a false physical-location claim.

The **primary region** is the Azure region that holds the resource group, the virtual network, the host VM and most of the monitoring data. Commands in this guide write it as `<PRIMARY_REGION>`; replace it with the region code you chose (for example a value from the `Name` column of `az account list-locations -o table`). Choose a region where your subscription can create the `Standard_E8s_v5` size. A **secondary region** is used for the management features that are not available in every region (see section 1.3); the lab kit names it literally as Southeast Asia (`southeastasia`).

Use the table below as the exact reference for the machines in scope.

| Machine / role | Guest OS | CPU / RAM | IP | Arc resource region |
|---|---|---|---|---|
| HV-HOST-01 / outer host | Windows Server 2025 | 8 LP / 64 GB | 10.50.1.4; internal 192.168.100.1 | Primary region |
| WIN2019-GUEST / noisy neighbour | Windows Server 2019 | 4 vCPU / 8 GB | 192.168.100.11 | Primary region |
| WIN2022-GUEST / noisy neighbour | Windows Server 2022 | 4 vCPU / 8 GB | 192.168.100.12 | Primary region |
| WIN2025-GUEST-01 / noisy neighbour | Windows Server 2025 | 4 vCPU / 8 GB | 192.168.100.13 | Primary region |
| RHEL94-GUEST / light nginx victim | RHEL 9.4 | 4 vCPU / 8 GB | 192.168.100.14 | Primary region |
| SQL2019-GUEST / separate SQL role | Windows Server 2022 Standard Evaluation | 4 vCPU / 12 GB | 192.168.100.15 | Southeast Asia (secondary region) |

The following details matter when you explain sizing and performance. Keep them exact.

All guests are Generation 2. Their internal subnet is `192.168.100.0/24`, gateway `192.168.100.1`, DNS `8.8.8.8` and `1.1.1.1`. Windows VM settings use static memory, not Dynamic Memory. Total assigned guest RAM is 44 GB; that is not measured physical RAM usage. Total configured guest CPU is 20 vCPU on eight LP, a **2.5:1 assigned ratio**. During the CPU scene, only the three Windows noisy neighbours burn all four vCPUs: **12 busy vCPUs**, not 20. There is no universal safe 2:1 consolidation guarantee.

## 1.2 Network and storage layers

Here you are checking the Azure-side network and the host-side storage layout. This tells you where traffic flows and where the nested VHDX files really live.

**Azure Portal check.** Follow these exact clicks:

1. Open a web browser and go to `https://portal.azure.com`.
2. Sign in with an account that can read the lab subscription.
3. In the search box at the very top, type `rg-hyperv-arc-monitor-demo` and press Enter.
4. Click the resource group named `rg-hyperv-arc-monitor-demo`.
5. In the resource list, click `vnet-arc-lab`.
6. In the left-hand menu of `vnet-arc-lab`, click `Subnets`.
7. Confirm that `snet-lab` exists, that its address range is `10.50.1.0/24`, and that it is attached to `natgw-arc-lab`.
8. Confirm that `AzureBastionSubnet` exists and that its address range is `10.50.250.0/26`.
9. Go back to the resource group.
10. In the resource list, click `HV-HOST-01` under **Virtual machines**.
11. In the left-hand menu of `HV-HOST-01`, click `Networking`.
12. Confirm the VM uses a private NIC and has no host public IP.
13. In the left-hand menu of `HV-HOST-01`, click `Disks`.
14. Confirm there is an OS disk and a `512 GB` Premium SSD P20 data disk.
15. Confirm the data disk caching is `Read/write`.

**CLI path, operator PC PowerShell.** Set up the operator PC session first (see [Chapter 2](02-tools-secrets-and-conventions.md)), then run the following commands in the same PowerShell window.

> **RUN ON - Operator PC, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in a Windows PowerShell window where you have already opened the `lab-kit` folder and loaded `context.ps1` as described in [Chapter 2](02-tools-secrets-and-conventions.md). Do not switch to Bash, Cloud Shell, the Hyper-V host, or a guest VM for this step.

```powershell
az network vnet subnet show -g $RG --vnet-name vnet-arc-lab `
  -n snet-lab --query "{Prefix:addressPrefix,NAT:natGateway.id}" -o json
az vm show -g $RG -n HV-HOST-01 --show-details `
  --query "{Size:hardwareProfile.vmSize,IP:privateIps,Disks:storageProfile.dataDisks}" -o json
```

**What you should see:** in the first command output, the NAT ID should be in this resource group. In the second command output, the host size should be `E8s_v5` and the data disk should be `512 GB`. Inside the host, `F:\VMs` contains thin-provisioned VHDX files. SQL's data VHDX is 64 GB and becomes E:; its log VHDX is 32 GB and becomes L:. Both use NTFS with 64 KB allocation units. These are nested files on the same outer F: disk, not independent Azure storage arrays. The P20 baseline is 2,300 IOPS / 150 MB/s; caching and other limits can affect observations. Do not translate a guest's latency directly into an Azure disk SLA.

## 1.3 Regional and identity boundaries

This section helps you explain why different parts of the lab appear in different Azure regions. It also tells you which identity is doing which job.

Use the table below as the region map.

| Data / feature | Intended location | Important distinction |
|---|---|---|
| Arc metadata of the host and four guests | Primary region | Arc machine resource region |
| SQL guest Arc + SQL Arc resource | Southeast Asia | Same region required for Arc machine and SQL instance |
| OS, Hyper-V, SQL Perf and precise SQL memory custom logs | `law-arc-monitor-lab`, primary region | Workspace location controls this monitoring data |
| SQL Arc performance dashboard and DB inventory | Southeast Asia service region | Separate from the custom Log Analytics memory view |
| Change Tracking and Inventory for SQL guest | `law-arc-ct-sea`, Southeast Asia | Dedicated supported-region workspace and DCR |
| Update Manager for SQL guest | Southeast Asia Arc machine | Not inherited from the resource group's region |

Read the points below carefully before you describe where the lab's data lives.

The resource group's region does not force every resource into that region. Some management features are not available in every region: a region that does not support them returns `RegionNotEnabled`. That is why a secondary region (Southeast Asia, `southeastasia`, in this lab kit) is used for SQL on Arc, Change Tracking and Inventory, and Update Manager. Do not relocate the existing five Arc records merely to make a Portal demonstration look uniform. Do not claim that all data stays in the primary region.

Azure CLI authentication is the **human operator's** identity. Arc machine identity is created by the Connected Machine agent; the Azure Monitor Agent (AMA) uses the Arc identity and its data collection rule (DCR) association. A short-lived onboarding access token is not a permanent machine identity or a SQL password. SQL uses Windows authentication; `SQL2019-GUEST\labadmin` is the setup administrator; services use virtual accounts. The memory collector uses a separate local Windows account with `VIEW SERVER STATE`, not sysadmin.

## 1.4 Completion checks

This section tells you what "done" means for the lab. You are checking that each required proof point is actually present.

For the Azure Portal checks, open the specific resources exactly where the later chapters tell you to go: Arc Machines, workbook, SQL Arc resource, Update Manager and Change Tracking. When you reach those chapters, confirm six Arc machines, three tagged cluster members, recent monitoring, correct SQL ceiling/allocated/used definitions, DB inventory, report export and management results.

For command-line evidence, use the supplied evidence tools exactly as directed in the later chapters.

**CLI path:** run `lab-kit/Get-LabEvidence.ps1` and the `.kql` files in `lab-kit/queries/`. The script is read-only: it writes the Arc machine list, the resource list, the alert rules, five standard query results and a UTC `snapshot-time.txt` to `lab-kit\exports\preflight` (or to the folder you pass as `-OutputDirectory`). Chapter 23 ([Reports and export](23-reports-and-export.md)) describes the export and the [lab kit reference](26-lab-kit-reference.md) lists every query. Save the query result and the UTC time, not just a screenshot. Expected: every required observation has a result or an explicit note that it is still pending.

When you describe the cluster tag, use the wording below exactly.

> **Say this:** `cluster=WIN-CLUSTER-01` identifies the three Windows guests only. It is a monitoring group, **not Windows Server Failover Clustering**, not SQL FCI and not a high-availability demonstration. No WSFC role or cluster network is installed.

## 1.5 Safety rules that apply throughout

These rules protect a running lab. They are repeated where they matter in the later chapters.

1. **Keep SQL Server running.** SQL Server on `SQL2019-GUEST` must stay available through every scene, test and maintenance step. Stop temporary test load when you have finished with it, but leave SQL Server running.
2. **Never expose secrets.** Passwords live only in the private, git-ignored `ENVIRONMENT.txt` (created once by `lab-kit\Initialize-LabSecrets.ps1`) and are entered only into sign-in dialogs or private prompts. Never print, paste, screenshot or upload them (see [section 2.3](02-tools-secrets-and-conventions.md#23-secrets-and-media-prerequisites)).
3. **Inspect before you change.** Check whether the live lab is already in the required state before you create, delete, restart or reinstall anything, and continue at the first incomplete chapter instead of rebuilding from the top (see [section 3.1](03-build-order-and-change-gates.md)).
4. **Stay inside the lab resource group.** Create or change resources only in `rg-hyperv-arc-monitor-demo`. Do not attach resources from another resource group, and do not create a Storage account or Cloud Shell storage outside it.

## 1.6 Related material in the repository

This guide builds and checks the lab itself. The Grafana dashboards and the automated shift report read the telemetry that the later chapters put into the workspaces `law-arc-monitor-lab` and `law-arc-ct-sea`. They are optional additions that are not built step by step here. Use the table below to find the rest of the repository.

| Topic | Where to read |
|---|---|
| Overview, quick start and limitations of the repository | [README](../../README.md) |
| Documentation index and architecture notes (diagram: [architecture-overview.png](../../diagrams/architecture-overview.png)) | [docs/README.md](../README.md) and [docs/architecture.md](../architecture.md) |
| Every lab kit file, script and query | [Chapter 26](26-lab-kit-reference.md) and [lab-kit/README.md](../../lab-kit/README.md) |
| Managed Grafana dashboards (11 dashboards in four folders) | [monitoring/README.md](../../monitoring/README.md) |
| Automated shift-report e-mail with three attachments | [shift-report/README.md](../../shift-report/README.md) and [Chapter 23](23-reports-and-export.md) |
| Presenter storyline for the finished lab | [docs/demo](../demo/00-about-this-guide.md) |
