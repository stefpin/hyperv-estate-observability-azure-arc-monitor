# Architecture notes

This page summarises how the pieces fit together. The operator guide ([docs/setup](setup/)) is the authority for exact
steps; the [lab kit reference](setup/26-lab-kit-reference.md) maps every file.

![Architecture overview](../diagrams/architecture-overview.png)

## Components

| Layer | Component | Notes |
|---|---|---|
| Estate | `HV-HOST-01`, an Azure VM (Windows Server 2025, `Standard_E8s_v5`: 8 logical processors, 64 GB) running **nested Hyper-V** | Simulates an on-premises host; no public IP, administered through Bastion, outbound through a NAT gateway |
| Estate | Five Gen 2 guests with 4 vCPU each: three Windows "noisy neighbours", one RHEL 9.4 web server, one SQL Server 2019 guest | 20 assigned vCPUs on 8 logical processors (2.5:1). Three Windows guests tagged `cluster=WIN-CLUSTER-01` (a monitoring group, not failover clustering) |
| Connect | **Azure Arc** Connected Machine agent on the host and every guest | Six Arc machines. The SQL guest is registered in a secondary region together with **SQL Server enabled by Azure Arc** |
| Collect | **Azure Monitor Agent** with four data collection rules (host, Windows guests, Linux guests, SQL servers) and a fifth for Change Tracking | Rules are associated to the Arc machines; see the table below |
| Custom signals | A 15-second SQL memory collector (scheduled task, least-privilege account) and a RHEL block-device observer | Both write local files that a collection rule ships to custom tables |
| Store | Log Analytics workspaces `law-arc-monitor-lab` (primary region) and `law-arc-ct-sea` (Change Tracking, secondary region) | Custom tables `HvSqlMemory_CL` and `HvLinuxDisk_CL` |
| See | One-page **Azure Workbook** (31 charts and tables), **Azure Managed Grafana** dashboards (11), Azure Resource Graph panels | Dashboards are read-only |
| Detect | **17 scheduled-query alert rules**, one action group, e-mail | Thresholds are relative to quiet baselines (see chapter 19) |
| Manage | **Update Manager** (tag-gated dynamic scope) with an **Automation** guard runbook triggered by **Event Grid** and webhooks | Patching stays gated; arming is a tag change |
| Track | **Change Tracking and Inventory** with a dedicated rule and workspace | Benign file and registry fixture for demonstration |
| Report | **Azure Functions** producer and dispatcher, private storage, **Azure Communication Services** e-mail | Three attachments, exactly-once dispatch ([shift-report](../shift-report/)) |
| Ask | Azure Copilot and the Observability Agent | Documented in Act 8B of the storyline; nothing here depends on them |

## Signals and where they come from

| Signal | Source | Interval | Lands in |
|---|---|---|---|
| Host saturation: logical-processor total, guest and hypervisor run time | Hypervisor counters on the host | 60 s | `Perf` |
| Guest scheduling wait: `CPU Wait Time Per Dispatch` (nanoseconds per dispatch) and root-partition contention | Hypervisor virtual-processor counters | 60 s | `Perf` |
| Run share per vCPU: `% Total Run Time` per virtual processor | Hypervisor virtual-processor counters | 60 s | `Perf` |
| Hyper-V storage: virtual storage device latency and I/O, host physical disks, virtual switch throughput, Dynamic Memory | Hyper-V and `PhysicalDisk` counters | 60 s | `Perf` |
| Hyper-V VMMS and worker errors and warnings | Windows event logs | event | `Event` |
| Windows guest CPU, queue length, memory, process, logical disk and network | Windows counters | 60 s | `Perf` |
| RHEL CPU, memory, swap, file systems, network and selected syslog facilities | Linux counters and syslog | 60 s | `Perf`, `Syslog` |
| RHEL per-device block I/O | Local observer writing `/var/log/hv-storage/disk-*.log` | collector cycle | `HvLinuxDisk_CL` |
| SQL Server memory manager, buffer manager, statistics and `sqlservr` process counters | SQL performance counters | 15 s | `Perf` |
| SQL memory ledger: ceiling, total, free, cache, stolen, grants allocated, used, count and pending, process and OS available memory | Custom collector writing `C:\HV-Demo\logs\sql-memory-*.json` | 15 s | `HvSqlMemory_CL` |
| Changes to a demo file, a registry value, installed software and services, plus inventory | Change Tracking rule on the SQL guest | every 10 minutes to 10 hours, depending on the type | `ConfigurationChange`, `ConfigurationData` |
| Update assessment, Arc inventory, SQL on Arc inventory | Azure Resource Graph | on query | n/a |

Heartbeat, Arc extension health and Azure Monitor Agent status complete the picture for "is data still arriving".

## Regions and identities

The resource group and most monitoring data live in the *primary region*. Some management features (SQL on Arc, Change
Tracking and Update Manager) are not available in every region, so the SQL guest and its management resources use a
secondary region (Southeast Asia in this lab kit). Do not claim that all data stays in one region
([section 1.3](setup/01-scope-architecture-and-success-criteria.md)).

| Identity | Used for |
|---|---|
| Human operator (Azure CLI / portal) | Deployment and evidence queries inside one resource group |
| Arc machine identity | Agent registration; Azure Monitor Agent authenticates through it and the rule association |
| SQL collector account | A local Windows account with `VIEW SERVER STATE` (not sysadmin) that runs the memory collector |
| Grafana managed identity | Read access to workspaces and the resource group |
| Automation account system identity | Guard runbook, with a scoped custom role for cancellation and checkpoint tags |
| Producer and dispatcher Function identities | Separate system-assigned identities with disjoint data-plane roles |

## Design rules that run through the repository

1. **Prove it arrived.** An agent, an extension and a rule association are not evidence of data. Every chapter ends with a
   query that shows recent rows.
2. **Say what the counter is.** Wait is nanoseconds per dispatch, not CPU-ready percent; storage layers are not additive;
   SQL memory categories overlap unless added to their own whole; a Windows monitoring group is not a cluster.
3. **Never turn missing data into green.** Stale or absent telemetry is *insufficient evidence*.
4. **Stay inside the lab.** Helpers enforce one resource group and exclude subscription-wide changes; mutation needs an
   explicit switch; patching, reboots and notifications are gated.
5. **Keep secrets out.** Private settings live in a git-ignored file, are prompted for, and are passed to guests as
   protected parameters.
6. **Prefer reviewable automation.** The shift report pins the exact bytes it was reviewed with and refuses to send
   otherwise.

## Known limits

The estate is simulated on an Azure VM, so contention below the Azure host is invisible; counters are minute averages
unless noted; no application-level response time is collected for the guests; and the lab is a teaching environment,
not a hardened production design.
