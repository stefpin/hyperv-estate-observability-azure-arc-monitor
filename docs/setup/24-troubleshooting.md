# 24. Troubleshooting - diagnose before changing

This document gives troubleshooting recipes for the lab, one section for each kind of problem. Each recipe starts with a read-only diagnosis (a Portal check and a CLI check) and only then suggests a change. Use it when something looks wrong: work through the matching section, and recover only the scene or component that failed, never the whole environment.

## 24.1 Wrong subscription, expired login or hidden interactive dialog

**What you are doing:** This check confirms that you are operating in the correct Azure context before you change anything. Many failed demos are just the wrong subscription or a hidden login prompt.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal checks, and on the operator PC in PowerShell for the CLI checks.

Portal steps:

1. Look at the top directory and subscription filter.
2. Verify the exact subscription ID.
3. Do not rely on a similar display name.
4. If needed, open a visible operator login window.
5. Do not repeatedly click **Create** against the wrong subscription.

CLI path: run `az account show`, compare the IDs with your `<SUBSCRIPTION_ID>` and `<TENANT_ID>`, run `az login --tenant <TENANT_ID>` in a visible window, then set the account (`az account set --subscription <SUBSCRIPTION_ID>`) and reload the lab context. **What you should see:** the context check passes. A hung background `az` process may be awaiting interactive authentication, not performing an Azure deployment; stop only the task's known process PID and retry in a visible window.

The lab scripts stop on purpose with a short message when the context is not right. `Azure CLI sign-in required in a visible operator window.` means that `az login` is needed. `Wrong subscription or tenant; no changes are permitted.` means that the signed-in account differs from the IDs in `lab-kit/context.ps1`, or that the placeholders in that file have not been replaced yet: run `tools/Set-RepoContext.ps1` as described in [Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt). `ENVIRONMENT.txt not found in the repository root.` means that the file is missing (create it with `lab-kit/Initialize-LabSecrets.ps1`), and `Private settings name another scope.` means that its `SUBSCRIPTION_ID` or `RESOURCE_GROUP` differs from `context.ps1`. `Resource is outside the authorized group.` and `Wrong resource group.` mean that a command named a resource outside the lab resource group; correct the name instead of bypassing the helper.

## 24.2 No guest internet or DNS

**What you are doing:** This section helps you prove whether the problem is guest DNS/routing, host NAT, or Azure-side network attachment.

> **Do this on:** the Azure portal in a web browser on the operator PC for Azure and host-path inspection, and on the guest OS for the local network commands.

Portal and host checks:

1. Open the VNet.
2. Inspect the NAT gateway association of **snet-lab** (`natgw-arc-lab`, [section 4.3](04-azure-foundation.md#43-explicit-outbound-route)).
3. Through Bastion on the host, open Hyper-V Manager.
4. Inspect **VmNAT**.
5. Inspect the guest IPv4 adapter properties.
6. Do **not** add a public IP to each nested guest.

> **Do this on:** the Windows guest, in elevated PowerShell. Run the exact commands below.

```powershell
Get-NetIPConfiguration
Resolve-DnsName login.microsoftonline.com
Test-NetConnection login.microsoftonline.com -Port 443
```

RHEL equivalents:

```bash
ip route
getent hosts login.microsoftonline.com
curl --max-time 10 -I https://login.microsoftonline.com
```

If the guests look correct, check the NAT on the Hyper-V host itself.

> **Do this on:** the Hyper-V host (`HV-HOST-01`), in elevated PowerShell (through Bastion). Run the exact commands below.

```powershell
Get-NetNat
Get-NetIPAddress -InterfaceAlias 'vEthernet (VmNAT)' -AddressFamily IPv4
```

**What you should see:** on the guests, DNS and TLS succeed and the Azure instance metadata endpoint remains blocked ([Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md)). On the host, a NAT named `LocalNAT` with the internal prefix `192.168.100.0/24` and the address `192.168.100.1` on `vEthernet (VmNAT)`. A gateway or DNS error is fixed at the guest; a NAT attachment error is fixed at the Azure subnet or the host. Missing host-side pieces are re-created by `lab-kit/host-hyperv.ps1`, which leaves anything already in place alone ([section 6.3](06-host-os-hyper-v-and-guest-network.md#63-internal-switch-and-nat)).

## 24.3 Arc connected but monitoring blank

**What you are doing:** This check distinguishes Arc connectivity from monitoring data flow. A machine can be Arc-connected while the data collection path is still wrong or incomplete.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visual inspection, and on the operator PC for the association and query review.

Portal steps:

1. Open the Arc machine.
2. Inspect the Arc extension state.
3. Open the DCR.
4. Inspect **Resources**, **Data sources**, and **Destinations**.
5. Open the workspace **Logs** view.
6. Check the time range.
7. Verify `_ResourceId`, stream/output table, and the actual file path/schema.
8. Do **not** reinstall everything first.

CLI path: use the association list, the extension list, the heartbeat and counter-inventory queries and the local collector files. AMA only collects configured sources that exist; old data is not backfilled. Allow for ingestion, verify new timestamps, and capture any extension or DCR error rather than silently deleting and reconnecting Arc.

> **Do this on:** your own computer, in the `lab-kit` folder of a PowerShell window where `context.ps1` is loaded ([section 2.2](02-tools-secrets-and-conventions.md#22-open-the-lab-kit-on-the-operator-pc)). Replace `SQL2019-GUEST` with the affected machine.

```powershell
az monitor data-collection rule association list `
  --resource "$ArcPrefix/SQL2019-GUEST" --query "[].{Name:name,Rule:dataCollectionRuleId}" -o table
az connectedmachine extension list -g $RG --machine-name SQL2019-GUEST `
  --query "[].{Name:name,Type:type,State:provisioningState}" -o table
Invoke-LabQuery -QueryFile .\queries\heartbeat.kql -OutputPath .\exports\heartbeat.json
Invoke-LabQuery -QueryFile .\queries\counter-inventory.kql -OutputPath .\exports\counter-inventory.json
```

**What you should see:** the association names follow the pattern `assoc-<machine>-<dcr>` ([section 11.2](11-azure-monitor-agent-and-dcrs.md#112-dcr-sourcedestinationassociation-are-three-separate-settings)), the Azure Monitor agent extension is **Succeeded**, `heartbeat.kql` returns one row per machine with an `AgeMinutes` of a few minutes, and `counter-inventory.kql` lists object and counter names with a recent `LastSeen`. Each query prints `Query saved: <OutputPath>`. If a counter you expect is missing, compare it with the DCR payload in `lab-kit/dcr`.

Then check that the collectors on the machines are still writing. On `RHEL94-GUEST`, `tail -5 /var/log/hv-demo/http-latency.json` and `sudo tail -2 /var/log/hv-storage/disk-$(date -u +%Y%m%d).log` must show timestamps from the last minutes ([section 8.3](08-rhel-guest-and-linux-collectors.md#83-http-victim-and-persistent-response-time-collection) and [section 16.3](16-storage-telemetry.md#163-rhel-iostat-custom-schema-and-validation)). On `SQL2019-GUEST`, the newest `C:\HV-Demo\logs\sql-memory-<yyyymmdd>.json` must grow every 15 seconds (next section).

## 24.4 SQL memory confusion or collector failure

**What you are doing:** This section helps you tell the difference between a real SQL memory observation and a broken collector or permissions issue.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visible checks, and on the SQL guest for the local SQL/task evidence.

Portal and guest checks:

1. Compare the correct SQL default instance.
2. Compare the actual memory cap.
3. Review the custom log fields.
4. On the guest, open Task Scheduler.
5. Inspect **HV-SQL-Memory-Collector**.
6. Inspect **History** and **State**.
7. Inspect the collector error log (`C:\HV-Demo\logs\collector-errors.log`).
8. Do **not** fix an idle grant reading by restarting SQL.

CLI/terminal path: query max memory, process and system memory, and grants; verify the local account permissions, the task credential and the log ACL. `VIEW SERVER STATE` is correct for SQL2019; an access error is not a reason to grant sysadmin. Retained cache after load is expected. The ceiling, the target, the committed memory and the query workspace are four different numbers. A task State of Running with stale or no files still requires diagnosis.

> **Do this on:** the SQL guest (`SQL2019-GUEST`), in elevated PowerShell. These commands only read; run the exact commands below.

```powershell
Get-ScheduledTask -TaskName HV-SQL-Memory-Collector | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName HV-SQL-Memory-Collector | Select-Object LastRunTime,LastTaskResult
Get-ChildItem C:\HV-Demo\logs | Sort-Object LastWriteTime -Descending |
  Select-Object -First 5 Name,Length,LastWriteTime
Get-Content C:\HV-Demo\logs\collector-errors.log -Tail 10 -ErrorAction SilentlyContinue
Get-Content (Get-ChildItem C:\HV-Demo\logs\sql-memory-*.json |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName -Tail 1
```

**What you should see:** the task is `Running`, the newest `sql-memory-<yyyymmdd>.json` (the date is the UTC date) was written within the last minute, and its last line is one JSON object with the fields `TimeGenerated`, `Computer`, `Instance`, `Stage`, `MaxMemoryMB`, `TotalMemoryMB`, `FreeMemoryMB`, `CacheMemoryMB`, `StolenMemoryMB`, `GrantAllocatedMB`, `GrantUsedMB`, `GrantCount`, `PendingGrants`, `ProcessMB`, `OsAvailableMB` and `PhysicalMB`. `collector-errors.log` is absent or its last entry is old. When the collector fails, it appends one line (`<UTC time> <message>`) to that file and stops, and the task restarts it up to three times at one-minute intervals; after that the task stays stopped until the next start of the guest or a manual start. The collector also stops when `C:\HV-Demo\stage.txt` is missing, because every record carries the current stage; the installers create that file with the value `idle` ([section 14.4](14-sql-memory-ceiling-and-what-it-means.md#144-create-only-demo-databases-and-the-least-privilege-collector)).

## 24.5 Storage counter units, duplicates or silent devices

**What you are doing:** This section keeps you from misreading storage metrics. Units and duplicated series can make a chart look persuasive but wrong.

> **Do this on:** the Azure portal in a web browser on the operator PC for the DCR and workbook checks, and on the monitored systems for the local counters.

Portal steps:

1. Open the DCR.
2. Inspect the exact object and counter names.
3. Open the workbook legend.
4. Confirm the units for ms, IOPS and MiB/s.
5. Filter to the real device or volume.

CLI path: use local `Get-Counter` / `iostat` and the Log Analytics inventory ([Chapter 16](16-storage-telemetry.md) lists the verified counters, queries and units for the host VHDX files, the Windows volumes and the RHEL devices). Windows "sec" counters are multiplied by 1,000; `iostat` awaits are already in ms; Hyper-V units follow verified evidence. Never multiply every numeric field indiscriminately. `_Total` plus its members doubles data; latency should not be summed.

## 24.6 Update Manager / CT RegionNotEnabled

**What you are doing:** This check verifies region support. The resource group location is not enough; the feature and the target resource locations must also be supported. Some management features are not available in every region, which is why the SQL guest is registered in a secondary region (Southeast Asia in this lab, see [Chapter 10](10-azure-arc-onboarding.md)).

> **Do this on:** the Azure portal in a web browser on the operator PC for the machine, workspace and DCR review, and on the operator PC for the machine-location and assessment checks.

Portal steps:

1. Open the SQL Arc machine.
2. Verify the machine region is Southeast Asia.
3. Open the CT workspace and DCR.
4. Verify they use a supported region.
5. Do **not** infer region from the resource group.

CLI path: check the machine location (`az connectedmachine show`), the dedicated CT association and extension ([section 21.1](21-change-tracking-and-inventory.md#211-workspace-dcr-and-extension)), and the assessment result ([Chapter 20](20-update-manager.md)). The other lab machines stay in the primary region. A resource-provider failure must be resolved by whoever owns the subscription prerequisites, not by registering providers without authorization. Windows Server 2022 Arc Hotpatch is not supported by this lab's hotpatch benefit, which applies to Windows Server 2025 only.

## 24.7 No fired alert or no CT change yet

**What you are doing:** This section reminds you to prove the condition and timing, not to force a result.

> **Do this on:** the Azure portal in a web browser on the operator PC for the alert or CT view, and on the operator PC for the exact KQL validation.

Portal steps:

1. For alerts, inspect the rule lookback, frequency, dimensions, state and actual condition query ([Chapter 19](19-alerts.md)).
2. Compare the observed load length.
3. For CT, verify that a baseline exists (`lab-kit/management/guest-ct-baseline.ps1` creates the fixture; [section 21.2](21-change-tracking-and-inventory.md#212-observe-an-intentional-benign-change)).
4. Verify the configured tracked path (`C:\HV-Demo\ChangeTracking-v22`, which must match `lab-kit/management/ct-dcr-request.json`).
5. Verify the collection frequency (the tracked files are collected every 1,800 seconds, so allow at least 30 minutes after a change).

CLI path: execute the exact KQL and inspect the real timestamps. For fired alerts, `lab-kit/queries/alert-history.ps1` reads the alert history of the resource group; for CT, run the queries of [section 21.2](21-change-tracking-and-inventory.md#212-observe-an-intentional-benign-change) against the CT workspace. Configured is not fired; inventory is not change-detected. Do not lower thresholds unnoticed, create a fake alert or edit a production service to force CT activity.

## 24.8 Recover from a failed scene safely

**What you are doing:** If a rehearsal scene fails, recover only the scene itself. Do not disrupt the whole environment.

> **Do this on:** the Azure portal in a web browser on the operator PC for evidence review, and on the workload location for the scoped cleanup.

Portal steps:

1. In the guest workload console, press Ctrl+C if that is the documented stop path for the scene.
2. Record the failure.
3. Show the baseline recorded evidence as recorded.
4. Do **not** reboot the host; all five guests, including SQL Server, would be disrupted.

CLI path: terminate only the stored workload PIDs and connections using the script's finalizer, delete only the designated scratch workload files, restore a changed stage label or threshold if applicable, and verify that SQL and the SQL Agent are Automatic/Running and that recent collector data exists. A dropped terminal does not automatically stop a detached guest workload; deadlines must be built into the workload. The scene scripts of [Chapter 22](22-rehearsal-scenes.md) already follow this rule:

- The CPU scene (`lab-kit/Start-LabCpuScene.ps1`, [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene)) starts workers that exit by themselves after the requested seconds (30 to 900). Its `finally` block stops only the recorded worker processes and prints `Only recorded bounded CPU worker PIDs cleaned up; SQL remains running.` The SQL guest is never loaded.
- The storage scene (`lab-kit/demo/guest-storage-rehearsal.ps1`, [section 22.3](22-rehearsal-scenes.md#223-storage-scene-then-stop)) deletes its scratch files `E:\HV-IO-Demo\worker-0.bin` to `worker-3.bin` in its `finally` block.
- The SQL memory scene (`lab-kit/demo/guest-workload.ps1`, [section 22.4](22-rehearsal-scenes.md#224-sql-memory-scene-then-retained-cache)) returns the stage label to `idle` in its `finally` block, except after `-Stage Prepare`.

If a script was killed before its `finally` block ran, check the result on the SQL guest.

> **Do this on:** the SQL guest (`SQL2019-GUEST`), in elevated PowerShell. These commands only read; run the exact commands below.

```powershell
Get-Service MSSQLSERVER,SQLSERVERAGENT | Select-Object Name,Status,StartType
Get-Content C:\HV-Demo\stage.txt
Get-ChildItem E:\HV-IO-Demo -ErrorAction SilentlyContinue
```

**What you should see:** both services `Running` with start type `Automatic`, the stage label `idle`, and no `worker-*.bin` files in `E:\HV-IO-Demo`. If the stage label is not `idle` after the scene has ended, write it back (`[IO.File]::WriteAllText('C:\HV-Demo\stage.txt','idle')`). Then confirm with [section 24.4](#244-sql-memory-confusion-or-collector-failure) that the memory collector is still writing.

## 24.9 Grafana dashboards or the shift report show no data

**What you are doing:** This section separates a missing data source, permission or setting from missing telemetry. The Grafana dashboards in `monitoring/` and the optional shift-report application read the same Log Analytics workspaces as the workbook, so prove first that the data exists ([section 24.3](#243-arc-connected-but-monitoring-blank)) before you change anything in Grafana or in the application. Both parts are described in [monitoring/README.md](../../monitoring/README.md) and [shift-report/README.md](../../shift-report/README.md).

> **Do this on:** the Azure Managed Grafana page in a web browser on the operator PC for the dashboard checks, and on the operator PC in PowerShell with Azure CLI for the read-only commands.

Portal steps:

1. Set the dashboard time range first. Panels and links labelled "Recorded replay", "Recorded incident window", "Recorded CPU episode context" or "HISTORICAL REPLAY" point at time windows that were recorded in the reference lab and show no data until you record your own scenes; change the `from` and `to` values in the link or use the time picker.
2. Open the panel menu, choose **Inspect**, then **Query**, and confirm that the panel uses the Azure Monitor data source whose uid the dashboard family expects: `hv-azure-monitor` (Operations), `hv-cc-azure-monitor` (Command Center V1), `hv-cc-v2-azure-monitor` (Command Center V2) or `hv-cc-v3-core-azure-monitor` (Command Center V3 Core).
3. Check the `machine` variable (on the Operations dashboards also `member`). It is a custom variable that holds the six lab machine names; edit it if your machines are called something else.
4. Check that the Grafana managed identity can read both Log Analytics workspaces and the resource group (for example *Log Analytics Reader* and *Reader*).
5. Dashboards use the browser time zone, while this guide shows local time (UTC+7) next to UTC. Set the display time zone in Grafana if you want the same reading.

CLI path: list what the Grafana instance really holds. Replace the two placeholders with the name and the resource group of your Grafana instance.

```powershell
az extension add --name amg
az grafana data-source list -n <your-grafana-name> -g <your-resource-group> `
  --query "[].{Name:name,Uid:uid,Type:type}" -o table
az grafana dashboard list -n <your-grafana-name> -g <your-resource-group> `
  --query "[].{Title:title,Uid:uid}" -o table
```

**What you should see:** an Azure Monitor data source with the uid of each family that you imported and the dashboards of that family. If the data source with the expected uid is missing, create it and import the dashboards as described in the [Import section of monitoring/README.md](../../monitoring/README.md#import).

The automated shift e-mail ([section 23.4](23-reports-and-export.md#234-automated-shift-report-by-e-mail-optional)) is silent by design: nothing is sent until its gates are open and the scheduled-send policy is pinned, and a missed timer is never back-filled. Check in this order:

1. `GET /api/automation` on both Function apps is read-only and needs a function key. It returns `status` (`Disabled`, `Gated`, `Enabled` or `InvalidPolicy`), the gates (`scheduleEnabled`, `sendEnabled`, `autoSendEnabled`, `effectiveAutoSend`), `policyVerified` and the next eligible times (`nextCollection`, `nextDispatch`, in UTC and local time). Both apps must be configured identically.
2. `InvalidPolicy` (HTTP 409) means that a pinned input changed after the policy was pinned, or that `AUTO_SEND_POLICY_SHA256` on the app does not match the pin. Review the change first, then re-pin deliberately with `python tools/pin_policy.py` in the `shift-report` folder and set the printed value on both apps. Do not re-pin only to make the message disappear.
3. A report with the status *INSUFFICIENT EVIDENCE* is not a software fault. One of the 14 required telemetry pairs (`Heartbeat` and `Perf` for the six machines, SQL memory from `HvSqlMemory_CL` for `SQL2019-GUEST`, Linux disk from `HvLinuxDisk_CL` for `RHEL94-GUEST`) had no raw sample within five minutes of the source cutoff, or less than 90 percent bucket coverage. Repair the collection first ([section 24.3](#243-arc-connected-but-monitoring-blank) and [section 24.4](#244-sql-memory-confusion-or-collector-failure)).
4. A Function app that fails to start with "access denied" on `host.json` was deployed from a ZIP whose root files had mode 0600. Rebuild the package so that every file is readable (mode 0644), as described in the [Deploy section of shift-report/README.md](../../shift-report/README.md#deploy).

**What you should see:** a read-only `/api/automation` answer on both apps, the same policy hash on both, and `INSUFFICIENT EVIDENCE` only while one of the required telemetry pairs is genuinely missing. The complete list of routes, ledger states and settings is in [shift-report/app/CONTRACT.txt](../../shift-report/app/CONTRACT.txt).
