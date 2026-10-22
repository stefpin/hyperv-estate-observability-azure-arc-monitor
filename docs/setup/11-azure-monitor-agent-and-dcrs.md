# 11. Azure Monitor Agent and base collection rules

This chapter installs Azure Monitor Agent (AMA) on the Arc machines, confirms that the Data Collection Rules (DCRs) have the correct scope, data sources, destination workspace and resource associations, and verifies the first Heartbeat data in the Log Analytics workspace. Heartbeat is the basic "machine checked in" signal from the agent. Use this chapter after Arc onboarding ([chapter 10](10-azure-arc-onboarding.md)) and before the SQL-specific collection work ([chapter 15](15-sql-custom-log-table-and-dcr.md)).

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables (such as `$RG` and `$ArcPrefix`) and the `Invoke-Lab*` helpers that it provides.

## 11.1 Install AMA on the Arc resources

**What you are doing:** you install or verify Azure Monitor Agent on the Arc machines. Install it only once per machine.

In the Azure Portal, for each required Arc machine:

1. Go to **Azure Arc**.
2. Click **Machines**.
3. Open the Arc machine.
4. Click **Extensions**.
5. Click **Add**.
6. Choose Azure Monitor Agent appropriate to the operating system.
7. Create the extension.
8. Make sure automatic extension upgrade is on.
9. Repeat for the host and the five guests as needed.

An existing AMA is verified, not installed twice. The extension location must match that machine's Arc location.

`Install-LabAma.ps1` does the same for all six machines in one run. It reads each machine's own Arc location, creates `AzureMonitorWindowsAgent` (or `AzureMonitorLinuxAgent` on `RHEL94-GUEST`) with automatic upgrade on, and only verifies a machine that already has the extension (`Verified existing AMA on <machine>; no extension update.`). It stops with an error if an existing AMA is not in the state **Succeeded**: investigate before reinstalling.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
.\Install-LabAma.ps1
az connectedmachine extension list -g $RG --machine-name SQL2019-GUEST `
  --query "[].{Name:name,Publisher:publisher,Type:type,State:provisioningState}" -o table
```

**What you should see:** AMA shows provisioning state **Succeeded**. In the Portal, the **Extensions** page of a Windows Arc machine lists `AzureMonitorWindowsAgent` with the status Succeeded. Extension presence alone does not prove data ingestion; the association, the stream and destination, and fresh rows must also be checked.

## 11.2 DCR source/destination/association are three separate settings

**What you are doing:** you check that each Data Collection Rule has the correct scope, data sources, destination workspace and resource associations. These are separate settings and all of them must be right.

The lab uses four DCRs:

| DCR | Payload in the lab kit | Used for |
|---|---|---|
| `dcr-hyperv-host` | `lab-kit/dcr/dcr-hyperv-host.json` | the `HV-HOST-01` Arc resource: 29 Hyper-V, virtual-storage and physical-disk counters every 60 seconds, plus the Hyper-V VMMS and Worker admin events (levels critical, error and warning) |
| `dcr-windows-guests` | `lab-kit/dcr/dcr-windows-guests.json` | the three noisy-neighbour Windows guests, and Windows OS monitoring on the SQL guest: 46 counters every 60 seconds, plus System and Application events (critical, error and warning) and Service Control Manager events 7031, 7034 and 7036 |
| `dcr-linux-guests` | `lab-kit/dcr/dcr-linux-guests.json` | `RHEL94-GUEST`: 31 counters every 60 seconds, warning-and-above Syslog messages from selected facilities, and the storage observer text log `/var/log/hv-storage/disk-*.log` (table `HvLinuxDisk_CL`) |
| `dcr-sql-servers` | `lab-kit/dcr/dcr-sql-servers.json` | `SQL2019-GUEST`: 17 SQL Server counters every 15 seconds and the custom memory log `C:\HV-Demo\logs\sql-memory-*.json` (table `HvSqlMemory_CL`) |

In the Azure Portal, verify `dcr-hyperv-host` first:

1. Go to **Monitor**.
2. Open **Data Collection Rules**.
3. Open `dcr-hyperv-host` (in the primary region).
4. Click **Resources** and confirm the `HV-HOST-01` Arc resource is listed.
5. Click **Data sources** and confirm Windows performance counters with a sampling interval of 60 seconds, including the host Hyper-V counters and the Windows OS/disk counters, and the two Hyper-V event logs.
6. Click **Destinations** and confirm `law-arc-monitor-lab`.

Then verify the other rules:

1. Open `dcr-windows-guests` and confirm it is used for the three noisy neighbours and for Windows OS monitoring on the SQL guest.
2. Open `dcr-linux-guests` and confirm it is used for `RHEL94-GUEST`.
3. Confirm the SQL-specific rule adds SQL counters and the custom memory log and does not duplicate the generic CPU/disk counters.
4. Save if required.
5. After several minutes, open the workspace **Logs**.

> **Warning:** A saved DCR does not backfill old data.

If you are deploying the prepared payloads instead of only inspecting, use `lab-kit/Deploy-LabMonitoring.ps1`, which reads the DCR payloads in `lab-kit/dcr` and the custom table schemas in `lab-kit/schema`. Every time it runs, it creates or updates both custom tables (`HvSqlMemory_CL` from `memory-table.json`, `HvLinuxDisk_CL` from `linux-disk-table.json`) and all four DCR definitions, which overwrites changes that you made to those definitions in the Portal. It then creates an association (`assoc-<machine>-<dcr>`) only for machines that do not have that rule yet: `dcr-hyperv-host` for `HV-HOST-01`, `dcr-windows-guests` for the three noisy neighbours and `SQL2019-GUEST`, `dcr-linux-guests` for `RHEL94-GUEST` and `dcr-sql-servers` for `SQL2019-GUEST`. Run it only when a definition is missing or when you deliberately intend to change one. The payloads carry the `<PRIMARY_REGION>` location and the workspace resource ID with your subscription ID ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
.\Deploy-LabMonitoring.ps1
az monitor data-collection rule association list `
  --resource "$ArcPrefix/SQL2019-GUEST" -o json
```

**What you should see:** the script ends with `Definitions/associations deployed. Verify actual rows in both Portal and CLI.` The host, Windows and Linux rules route `Microsoft-Perf` to the monitor workspace. The correct Arc resources have associations, and the SQL guest also has `dcr-sql-servers`. A DCR's destination workspace may differ from the Arc machine region. Do not declare a successful upload as proof that every configured counter exists.

## 11.3 First heartbeat and time range

**What you are doing:** you check that the first Heartbeat records have arrived in the Log Analytics workspace and that you are using the right time range.

In the Azure Portal:

1. Open workspace `law-arc-monitor-lab`.
2. Click **Logs**.
3. If the workspace opens in simplified mode, switch to KQL/query mode.
4. Set the time range to **Last 30 minutes**.
5. Paste the query below.
6. Click **Run**.
7. Expand the result rows.
8. Check that `_ResourceId` points to this resource group.

For the CLI-based export, `Invoke-LabQuery` uses the workspace GUID discovered from its resource-group-scoped resource.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
Invoke-LabQuery -QueryFile .\queries\heartbeat.kql -OutputPath .\exports\heartbeat.json
```

KQL means Kusto Query Language, the query language used in Azure Monitor Logs.

> **PASTE INTO - law-arc-monitor-lab, Logs, KQL**

```kql
Heartbeat
| where TimeGenerated > ago(30m)
| where _ResourceId contains "/resourceGroups/rg-hyperv-arc-monitor-demo/"
| summarize LastSeen=max(TimeGenerated),
    Environment=any(ComputerEnvironment) by Computer,_ResourceId
| extend AgeMinutes=datetime_diff("minute",now(),LastSeen)
| order by Computer asc
```

**What you should see:** six recent machine rows. The host may show Azure as its environment because it is an Azure VM that simulates an on-premises host.

> **Warning:** KQL times are UTC. Convert to local time (UTC+7, abbreviated LT) only when you label a displayed or exported report, for example `23:00 UTC = 06:00 LT`. Never mix local and UTC boundaries in a replay window.
