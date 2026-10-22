# 26. Lab kit reference

This document is a reference for the lab kit (`lab-kit/`): how it is laid out, what each file or file family is for, where each script is meant to run, and which files are executable configuration rather than notes. Use it to find the exact source that matches a step in the guides, and to check that a script runs in the right place before you start it. [`lab-kit/README.md`](../../lab-kit/README.md) is the short version of this chapter.

Commands marked as running on your own computer are written to run from the `lab-kit` folder (`cd lab-kit`) in a PowerShell session where the lab context has been loaded with `. .\context.ps1` ([section 2.2](02-tools-secrets-and-conventions.md#22-open-the-lab-kit-on-the-operator-pc)). Commands marked as running on the host or in a guest use the copies of the lab kit that [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest) puts on the host (`F:\Build\lab-kit`) and on the SQL guest (`C:\lab-kit`).

## 26.1 How to find the exact source

**What you are doing:** This section shows where the public lab kit lives and how to identify the exact file that matches a guide step.

> **Do this on:** File Explorer (or your Git client) on the operator PC for the lab kit view, and on the operator PC for the script inspection.

File Explorer route:

1. Open your clone of the repository.
2. Open the `lab-kit` folder and its [README](../../lab-kit/README.md).
3. Confirm you are looking only at public files.
4. Verify that `ENVIRONMENT.txt` is not inside the lab kit. It is created in the repository root, next to `lab-kit`, by `lab-kit/Initialize-LabSecrets.ps1` ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), and Git ignores it.
5. To put the lab kit on the host and on the SQL guest, use `lab-kit/Copy-LabPublicSources.ps1` as described in [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest). It sends the whole lab kit as one archive through Arc Run Command and extracts it to `F:\Build\lab-kit` on the host (`-Target Host`, the default); with `-Target SqlGuest` it then also copies it from the host to `C:\lab-kit` on `SQL2019-GUEST` through PowerShell Direct. It copies no single files, it runs no guest script, and it stops before sending anything if the folder contains a file that does not belong in a public bundle.

CLI path: the tables below list each file family and where it runs. `lab-kit/context.ps1` holds the fixed scope constants (subscription, tenant, resource group) and the reader of the private `ENVIRONMENT.txt`. A script that loads it stops at its scope check while the placeholders of [section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt) are still in place. Fresh-build scripts are initial-build only; deployment scripts require an explicit confirmation switch; evidence and query scripts are read-only. No automatic "run everything" command is included, because a live lab must not be rebuilt accidentally.

### Layout

```text
lab-kit/
  README.md                                   how the kit is organised and what protects a live lab
  context.ps1, Deploy-*.ps1, Install-*.ps1    top-level scripts (see the next table)
  alerts/                                     17 alert rule payloads (hv-*.json)
  dcr/                                        four data collection rule definitions
  demo/                                       bounded rehearsal workloads
  email/                                      action group, attachment and end-to-end alert helpers
  management/                                 Update Manager, Change Tracking, Automation and event wiring
    guard/                                    maintenance guard runbook and its offline tests
    operations/                               guard publication and validation helpers
  queries/                                    47 KQL and Resource Graph queries and two helper scripts
  schema/                                     custom table, SQL extension and Change Tracking DCR schemas
  sources/                                    build sources for the workbook, the collectors and the report export
  storage/                                    RHEL disk observer and a storage helper library
  workbook-*.json                             saved workbook definition, query set and resource settings
```

The scripts also write files at run time that are not part of the kit: Azure responses and request bodies next to the script (for example `workbook-put.json` and `alerts/put-<rule>.json`, and the files described under [The management folder](#the-management-folder)), query results and evidence exports in `exports/` (the default output folder of `Get-LabEvidence.ps1`), and evidence under `management/evidence/`. Do not treat them as source files and do not commit them.

### Top-level scripts

The **Run on** column names the machine where the script executes. A script that executes on the host or on the SQL guest can be typed there, from that machine's copy of the lab kit, or started from the operator PC with `Invoke-LabArcScript -Machine <name> -ScriptPath <file>`, which sends the file through Arc Run Command.

| File / family | Run on | Purpose |
|---|---|---|
| `context.ps1`, `Copy-LabPublicSources.ps1` | Operator PC | `context.ps1` is the scope guard that almost every operator-PC script loads with `. .\context.ps1`. It checks the signed-in subscription and tenant, allows one resource group, refuses provider registration, Azure Policy, `az vm run-command`, security pricing changes and resource group deletion, and provides `Assert-LabContext`, `Invoke-LabAz`, `Invoke-LabArcScript`, `Invoke-LabQuery` and the reader of the private `ENVIRONMENT.txt`. `Copy-LabPublicSources.ps1` sends the lab kit to the host or the SQL guest ([section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)) |
| `Initialize-LabSecrets.ps1` | Operator PC, new build only | Creates the private `ENVIRONMENT.txt` in the repository root. It asks for the seven passwords without echo (at least 16 characters each), restricts access to the file and never overwrites an existing one ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) |
| `New-LabHost.ps1` | Operator PC | Creates the Azure host VM only (`Standard_E8s_v5`, 128 GB OS disk, 512 GB data disk, subnet `snet-lab`), with no provider registrations ([chapter 5](05-create-the-hyper-v-host.md)) |
| `host-prepare.ps1`, `host-hyperv.ps1` | Host | `host-prepare.ps1` formats the 512 GB data disk as `F:` (with `F:\VMs`, `F:\ISO` and `F:\Build`), sets the time zone to SE Asia Standard Time (UTC+7), checks internet access through the NAT gateway, stops the `labadmin` password from expiring and installs the Hyper-V role. `host-hyperv.ps1` creates the internal switch `VmNAT`, the `LocalNAT` network (192.168.100.0/24) and enhanced session mode, and downloads the three Windows evaluation ISOs to `F:\ISO` ([chapter 6](06-host-os-hyper-v-and-guest-network.md)). Inspect before running |
| `host-azure-vm-disguise.ps1` | Host | Last step of the lab-only Azure VM disguise ([chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md)). It stops without changes unless every guest is set to save and restart with the host, the machine variable `MSFT_ARC_TEST` is `true` and the firewall rule `BlockAzureIMDS` exists. It then disables the Azure guest agent (Arc Run Command and Bastion remain) and schedules a host restart 90 seconds later. It does not create the variable or the rule. Inspect before running |
| `host-patch.ps1` | Host | Downloads the two Microsoft-signed SQL Server 2019 updates to `F:\Build\sql2019-updates` and verifies their signature and published SHA-256 value (`-Stage Download`, the default). `-Stage Apply` installs them on `SQL2019-GUEST` through PowerShell Direct and needs `-GuestPasswordHex` and `-InitialBuildMaintenanceApproved yes`, because SQL patches can restart services ([chapter 12](12-sql-server-installation.md)) |
| `Build-LabWindowsGuest.ps1`, `build-guest.ps1` | Host | `Build-LabWindowsGuest.ps1 -GuestName <name>` builds one of the four Windows guests with its ISO, address and static memory. It asks for the guest's `labadmin` password privately and refuses to rebuild an existing guest. It calls `build-guest.ps1`, which applies the evaluation image offline, writes the answer file and creates the Generation 2 VM on the `VmNAT` switch ([chapter 7](07-build-the-guests.md)) |
| `add-sql-disks.ps1` | Host | Adds the SQL data and log disks to `SQL2019-GUEST`: two dynamic VHDX files on `F:\VMs`, formatted in the guest as `E:` (`SQLDATA`) and `L:` (`SQLLOG`) with 64 KB allocation units. Safe to run again ([chapter 12](12-sql-server-installation.md)) |
| `verify-guest.ps1` | Host | Checks one Windows guest through PowerShell Direct: name, address, internet access, Windows activation (it activates the guest if needed), answer-file removal, Windows Update policy, time zone, `labadmin` password expiry, and that the Azure metadata service is not reachable ([section 7.3](07-build-the-guests.md#73-verify-and-remove-installation-dvds)) |
| `status-host.ps1` | Host | Read-only host report: logical processors, memory and uptime of the host, free space on `F:`, switch and NAT, every guest (state, vCPU, memory, address, generation, automatic start action, checkpoints), the vCPU-to-logical-processor ratio, the files in `F:\ISO` and any stray mounted image ([chapter 6](06-host-os-hyper-v-and-guest-network.md)) |
| `guest-sql.ps1`, `Install-LabSql2019.ps1` | SQL guest | `guest-sql.ps1` is the helper library (`Invoke-LabSql`) that SQL guest scripts load, and it stops unless the computer is `SQL2019-GUEST`. `Install-LabSql2019.ps1 -MediaPath <folder>` installs SQL Server 2019 after checking the Microsoft signature and the major version of `setup.exe`, and does nothing if SQL Server is already installed ([chapter 12](12-sql-server-installation.md)) |
| `Install-LabSqlMemoryCollector.ps1`, `memory-collector.ps1` | SQL guest | `Install-LabSqlMemoryCollector.ps1` creates the local account `HvSqlCollector` (it asks for the password), its least-privilege SQL login (`CONNECT SQL` and `VIEW SERVER STATE`), the demo databases `OrdersDemo`, `BillingDemo` and `ReportingDemo`, the max server memory ceiling (80 % of the guest's memory, after a headroom check) and the scheduled task `HV-SQL-Memory-Collector`. `memory-collector.ps1` is the observer that the task runs: one JSON record every 15 seconds in `C:\HV-Demo\logs\sql-memory-<yyyymmdd>.json` ([chapter 14](14-sql-memory-ceiling-and-what-it-means.md)) |
| `Install-LabAma.ps1` | Operator PC | Installs the Azure Monitor Agent extension on the six Arc machines, each in its own region (`AzureMonitorWindowsAgent`, or `AzureMonitorLinuxAgent` on `RHEL94-GUEST`). It only verifies a machine that already has the extension ([chapter 11](11-azure-monitor-agent-and-dcrs.md)) |
| `Enable-LabSqlArc.ps1` | Operator PC | Adds the SQL Server extension `WindowsAgent.SqlServer` to `SQL2019-GUEST` with `schema/sql-extension-settings.json`, and stops unless the machine is in `southeastasia` ([chapter 13](13-sql-server-enabled-by-azure-arc.md)) |
| `Deploy-LabMonitoring.ps1` | Operator PC | Applies both custom tables from `schema/*-table.json` and the four data collection rules from `dcr/`, and adds the rule associations that do not exist yet ([chapter 11](11-azure-monitor-agent-and-dcrs.md)) |
| `Deploy-LabWorkbook.ps1` | Operator PC | Saves the workbook from `workbook-resource.json` under its fixed workbook ID and writes the request body to `workbook-put.json` beside itself ([chapter 18](18-workbook.md)) |
| `Deploy-LabAlerts.ps1` | Operator PC | Creates a missing rule from `alerts/` only when you pass `-InitialBuildApproved`. An existing rule is left unchanged to preserve its live e-mail actions and conditions, and a payload that names an action group is refused ([chapter 19](19-alerts.md)) |
| `Deploy-LabManagement.ps1` | Operator PC | `-ConfigurationOnly` (required) applies only the workspace, data collection rule and association files that a reviewed `management/deployment-index.json` lists, and does not execute guest changes. The kit carries a one-entry example index for the Change Tracking rule, and a fresh build uses `management/provision-ct.ps1` instead ([chapter 21](21-change-tracking-and-inventory.md)) |
| `cpu-burn.ps1` | One of the three noisy-neighbour Windows guests | Bounded synthetic CPU workload for one guest (`-Seconds` 30 to 600, default 300): four hidden worker processes that end at the deadline, and a `finally` block that stops the recorded PIDs. It refuses to run on any other computer ([section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene)) |
| `Start-LabCpuScene.ps1` | Host | Starts four bounded CPU workers on each of the three Windows guests through PowerShell Direct (`-Seconds` 30 to 900, default 240), asks privately for their `labadmin` passwords, leaves SQL alone and stops only the recorded worker PIDs at the end ([section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene)) |
| `install-rhel-observers.sh`, `http-latency-live.sh`, `http-latency-stats.sh` | RHEL guest | `install-rhel-observers.sh` (run it with `sudo`) installs the persistent HTTP observer `hv-http-latency`: one sample per second in `/var/log/hv-demo/http-latency.json`, rotated by logrotate. `http-latency-live.sh [samples]` takes 5 to 300 live one-second samples. `http-latency-stats.sh` summarises the last 300 observer samples (mean, P95, maximum, failures). The first two stop unless the host name is `RHEL94-GUEST`. The guides copy the files from the host with `scp` ([section 8.3](08-rhel-guest-and-linux-collectors.md#83-http-victim-and-persistent-response-time-collection), [section 17.4](17-cpu-contention-and-response-time.md#174-cluster-summary-and-per-machine-detail)) |
| `Get-LabEvidence.ps1`, `Convert-LabQueryToCsv.ps1` | Operator PC | `Get-LabEvidence.ps1 [-OutputDirectory <folder>]` is the read-only evidence export: the Arc machines, the resource inventory, the alert rules, five query results and `snapshot-time.txt` (default folder `exports\preflight`). `Convert-LabQueryToCsv.ps1 -JsonPath <file> -CsvPath <file>` turns a saved query result into CSV and refuses an empty result ([section 23.1](23-reports-and-export.md#231-build-a-report-with-reproducible-boundaries)) |

### Folders

| Folder | Run on | Contents and purpose |
|---|---|---|
| `alerts/` | Operator PC | One JSON payload per alert rule (17 rules): CPU (`hv-host-cpu-high`, `hv-host-cpu-critical`, `hv-guest-cpu-high`, `hv-guest-cpu-critical`, `hv-cluster-cpu-high`, `hv-cluster-cpu-critical`), memory (`hv-windows-memory-high`, `hv-windows-memory-critical`, `hv-cluster-memory-high`, `hv-cluster-memory-critical`), wait (`hv-guest-contention-high`, `hv-cluster-contention-high`), disk (`hv-disk-latency-high`, `hv-disk-latency-critical`), heartbeat (`hv-heartbeat-missing`) and SQL (`hv-sql-grants-pending`, `hv-sql-os-memory-low`). `Deploy-LabAlerts.ps1` reads these files. The action group is `ag-hv-demo-email` |
| `dcr/` | Operator PC | The four data collection rules `dcr-hyperv-host.json`, `dcr-windows-guests.json`, `dcr-linux-guests.json` and `dcr-sql-servers.json`. `Deploy-LabMonitoring.ps1` associates `dcr-hyperv-host` with `HV-HOST-01`, `dcr-windows-guests` with the three Windows guests and `SQL2019-GUEST`, `dcr-linux-guests` with `RHEL94-GUEST` and `dcr-sql-servers` with `SQL2019-GUEST` |
| `schema/` | Operator PC | Custom table schemas (`memory-table.json` for `HvSqlMemory_CL`, `linux-disk-table.json` for `HvLinuxDisk_CL`), `sql-extension-settings.json` (the settings of the SQL Server extension: license type `PAYG`, SQL management on) and `CtDcrCreation.json` (the Change Tracking rule template that `management/provision-ct.ps1` adapts) |
| `demo/` | Host or SQL guest, as listed | Bounded synthetic scenes: `guest-workload.ps1` (SQL guest: the SQL memory scene with the stages `Prepare`, `Baseline`, `WarmCache`, `GrantLoad` and `Recovery`, `-Seconds` default 180), `guest-storage-rehearsal.ps1` (SQL guest: the storage scene, 30 to 600 seconds, test files on `E:\HV-IO-Demo`), `host-cpu-rehearsal.ps1` (host: the CPU scene, 240 to 900 seconds, with the three Windows guest passwords as protected parameters and the SSH key files of [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene)) and `guest-collector-status.ps1` (SQL guest: read-only status of the memory collector and of the batch-logon right of its account). Every scene is bounded: the CPU workers end themselves at their deadline, `guest-storage-rehearsal.ps1` deletes its test files in a `finally` block and `guest-workload.ps1` sets `C:\HV-Demo\stage.txt` back to `idle` in a `finally` block |
| `email/` | Operator PC | E-mail alert helpers. None runs automatically, and the four that change something need an explicit switch: `activate-email.ps1` (inspects the action group, or creates it with `-ApprovedReceiverCreation`), `attach-email.ps1` (`-ApprovedAttachment`: actions-only attachment to the existing rules), `test-channel.ps1` (`-ApprovedSampleTest`: sample notification) and `real-alert-test.ps1` (`-ApprovedCpuTest`: genuine CPU scene through Arc). The read-only helpers are `read-alert-evidence.ps1` (alert evidence), `wait-real-recovery.ps1` (waits for the automatic recovery of one Alert ID) and `verify-sql-continuity.ps1` (runs the SQL guest health check) |
| `management/` | Operator PC, SQL guest or Azure Automation, as listed | Update Manager, Change Tracking, Automation and Event Grid scripts (see [The management folder](#the-management-folder)) |
| `management/guard/` | Operator PC (the runbook runs in Azure Automation) | `runbook-maintenance-guard.ps1`, the scoped Pre/Post maintenance guard runbook source, and `test-maintenance-guard.ps1`, its offline tests |
| `management/operations/` | Operator PC | Before-state capture, guard roles, guard publication and cloud validation for the maintenance guard (see [The management folder](#the-management-folder)) |
| `queries/` | Operator PC / Log Analytics | Read-only KQL and Resource Graph files and two helper scripts (see [The queries folder](#the-queries-folder)) |
| `storage/` | RHEL guest and operator PC | `hv-storage-collector.py` and its `hv-storage-collector.service` unit: the RHEL disk observer that writes `/var/log/hv-storage/disk-<yyyymmdd>.log` for `HvLinuxDisk_CL` ([chapter 16](16-storage-telemetry.md)). `storage-local.ps1` is a function library for operator-PC storage evidence tasks (scoped REST calls, an Arc Run Command helper and Log Analytics queries); it reads `ENVIRONMENT.txt`, writes its evidence files next to itself and holds a workspace ID that you replace first ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) |
| `sources/` | Operator PC | `sources/demo-v22/` holds the scripts that the workbook, the SQL memory collector, the rehearsal scenes and the report export were built and rehearsed with: `build_workbook.py`, `publish-workbook.ps1`, `validate-workbook.ps1`, `workbook-extra-panels.json`, `install-memory.ps1`, `guest-memory-setup.ps1`, `deploy-memory.ps1`, `rehearse-memory.ps1`, `run-cpu-storage-rehearsal.ps1`, `guest-final-health.ps1`, `export-report.ps1`, `query-la.ps1` and `deploy-alerts.ps1`, plus identical copies of the `demo/` scripts, `memory-collector.ps1`, `workbook-queries.json` and `workbook-resource.json`. `sources/sql-install/arc-run.ps1` defines `Invoke-HvArc`, which these scripts use to run a script on `HV-HOST-01` or `SQL2019-GUEST` through Arc Run Command. Do not run `sources/demo-v22/deploy-alerts.ps1` on a live lab: it writes all 17 rules with an empty action list, which detaches the e-mail action group. Use `Deploy-LabAlerts.ps1`, which leaves existing rules unchanged |
| `workbook-*.json` | Operator PC | `workbook-hyperv-estate-v2.2.json` (the saved workbook definition), `workbook-queries.json` (its query set) and `workbook-resource.json` (the resource settings that `Deploy-LabWorkbook.ps1` sends) |

### The management folder

The folder holds the scripts for Update Manager, Change Tracking, Automation and Event Grid, and two subfolders for the maintenance guard. In the folder itself only the `*-request.json` files, `CT-TABLE-SCHEMAS.json` and `deployment-index.json` are committed JSON files. The scripts write Azure response files next to themselves at run time (for example `maintenance-config.json`, `ct-workspace.json`, `eventgrid-topic.json` and `periodic-assessment-result.json`), and the scripts in `operations/` write their evidence to `management/evidence/`. Git ignores all of these, so do not look for them in a fresh clone. A script that needs one (for example `query-ct.ps1`, which reads `ct-workspace.json`) fails with a file-not-found error until you have run the script that creates it. The chapters that use these scripts are [chapter 20](20-update-manager.md) and [chapter 21](21-change-tracking-and-inventory.md).

| File | Run on | Purpose |
|---|---|---|
| `common.ps1` | Loaded by the other scripts | Shared helpers: loads `context.ps1`, fixes the scope (subscription, resource group and the machine `SQL2019-GUEST`), `Save-HvJson` (saves JSON next to the scripts), `Invoke-HvRest` (REST calls that must stay inside the lab resource group) and `Invoke-HvOwnedCommand` (runs a script of this folder on `SQL2019-GUEST` or `HV-HOST-01` as an Arc run command and deletes the run command afterwards) |
| `enable-assess.ps1`, `periodic-assessment-request.json` | Operator PC | Sets periodic assessment to `AutomaticByPlatform` on `SQL2019-GUEST` and submits one assessment ([section 20.2](20-update-manager.md#202-periodic-assessment)). The JSON file is the request that the script sends |
| `provision-maintenance.ps1`, `maintenance-config-request.json`, `maintenance-dynamic-scope-request.json` | Operator PC | Creates the weekly maintenance configuration `mc-hv-sql2019-definitions-gated` and the dynamic scope. The window is computed when the script runs: the next Monday at 19:00 SE Asia Standard Time (UTC+7), 90 minutes, only KB2267602, never reboot. The scope selects only machines tagged `HvUmTarget=SQL2019-GUEST` and `HvUmApproval=Approved`, and the script sets `HvUmApproval=Pending`, so nothing is selected until you arm it ([section 20.3](20-update-manager.md#203-maintenance-configuration-and-dynamic-scope)). The JSON files are the payloads that the script sends, and it overwrites them |
| `provision-automation.ps1`, `runbook-safe-check.ps1` | Operator PC (the runbook runs in Azure Automation) | Creates the Automation account `aa-hv-sql-maintenance` with a system-assigned managed identity, the custom role "SQL Maintenance Availability Checker" at the `SQL2019-GUEST` machine scope, the runtime environment `ps74-safe-checks` and the runbook `Test-HvSqlMaintenanceAvailability`. The runbook is published with `runbook-safe-check.ps1`, a read-only check of the guest, as its first content (section 20.5 in [chapter 20](20-update-manager.md)) |
| `provision-events.ps1` | Operator PC | Creates the Event Grid system topic `eg-hv-sql-maintenance`, the webhooks `wh-hv-sql-pre` and `wh-hv-sql-post` and their event subscriptions, and sends one independent test event to each. It needs `-EnvironmentPath <path of ENVIRONMENT.txt> -ConfigureAndTest yes`, and it appends the webhook addresses (secrets, never printed) to `ENVIRONMENT.txt` (section 20.5 in [chapter 20](20-update-manager.md)) |
| `provision-ct.ps1`, `ct-dcr-request.json`, `CT-TABLE-SCHEMAS.json` | Operator PC | Change Tracking in the secondary region: the workspace `law-arc-ct-sea`, the ChangeTracking solution, the dedicated rule `dcr-sql2019-change-tracking` (built from `schema/CtDcrCreation.json`), its association and the `ChangeTracking-Windows` extension on `SQL2019-GUEST` ([section 21.1](21-change-tracking-and-inventory.md#211-workspace-dcr-and-extension)). `ct-dcr-request.json` is the rule payload that the script sends, and it overwrites it. `CT-TABLE-SCHEMAS.json` is a reference copy of the Change Tracking table schemas |
| `query-ct.ps1` | Operator PC | Counts the Change Tracking rows that arrived for `SQL2019-GUEST` in the last two hours by table and data type, or runs your own `-Query`, against `law-arc-ct-sea`. It needs `ct-workspace.json`, which `provision-ct.ps1` writes, and saves `ct-ingestion-counts.json` |
| `guest-ct-baseline.ps1` | SQL guest | Creates the benign Change Tracking fixture once: the folder `C:\HV-Demo\ChangeTracking-v22` with `fixture-demo.txt` and the registry value `DemoState`. It stops if the fixture already exists ([section 21.2](21-change-tracking-and-inventory.md#212-observe-an-intentional-benign-change)) |
| `guest-final-safety.ps1` | SQL guest | Read-only check after a maintenance test. It fails unless SQL Server is running with automatic start and the guest did not restart (it compares the last boot time with `$ExpectedBootUtc`, which you must set first). It also reports the SQL Agent state, the Windows Update policy, the pending-reboot flags, the Defender signature, the KB2267602 history, the fixture hash and the `DemoState` value ([section 20.7](20-update-manager.md#207-final-safety-check-after-a-maintenance-test)) |

The `operations/` subfolder serves the maintenance guard ([chapter 20](20-update-manager.md), section 20.5). Its scripts do not load `context.ps1`: they take an ARM token from your Azure CLI sign-in through the `common.ps1` of that folder, which checks the subscription and keeps every call inside the lab resource group, and they write their evidence files to `management/evidence/`.

| File (`operations/`) | Run on | Purpose |
|---|---|---|
| `common.ps1` | Loaded by the other scripts | Shared helpers: `Initialize-LabArm` (needs the authorised subscription and an Azure CLI sign-in), `Assert-LabPath` and `Invoke-LabArm` (ARM calls that must stay inside the lab resource group), `Save-LabEvidence` (writes to `management/evidence/`) and `Invoke-OwnedSqlCheck` (a read-only SQL check through a short-lived run command) |
| `capture-baseline.ps1` | Operator PC | Saves the before-state before the guard replaces the first runbook: the maintenance configuration, the dynamic scope, the Arc machines and their assignments, the resource inventory, the role assignments, the Automation account and the published runbook (as `original-published-runbook.ps1`). It runs `guest-baseline.ps1` and writes `baseline-resources.json` and `baseline-sql-health.json` |
| `guest-baseline.ps1` | SQL guest (sent by `capture-baseline.ps1`) | Read-only health snapshot of `SQL2019-GUEST`: services, a real SQL query, max server memory, databases that are not online, Defender signature age, pending-reboot flags and the last boot time. It fails with `SQL availability baseline failed.` |
| `grant-guard-roles.ps1`, `cancellation-role-cli.json`, `checkpoint-role-cli.json` | Operator PC | Creates the two custom roles that the guard needs and assigns them to the Automation account's managed identity: "SQL Scheduled Maintenance Cancellation" (read the maintenance configuration, read and write `applyUpdates`) at the exact configuration scope, and "SQL Maintenance Run Checkpoints" (read and write Automation variables) at the exact account scope. It refuses wildcard actions and any other scope, and it reads every role back. Replace the sentinel principal ID in the script first ([section 20.6](20-update-manager.md#206-inspect-the-actual-safe-chain-and-its-permission-scopes)). The two JSON files are the same role definitions in Azure CLI format, for review; the script does not read them |
| `publish-guard.ps1` | Operator PC | `-GuardPath <file>` replaces the first runbook with the reviewed guard. It checks that the file parses, that `HvUmApproval` is `Pending` and that the published runbook is still the one that `capture-baseline.ps1` saved (or already your file). It imports the guard as the draft (`az automation runbook replace-content`, which needs the `automation` Azure CLI extension), publishes it, reads the published content back and writes `published-guard.json` |
| `test-cloud-guard.ps1` | Operator PC | Starts independent `Pre` and `Post` jobs of the published runbook with `DemoOnly=true` and checks that they return the exact healthy, no-patch, no-cancellation and no-state-write result. It writes `guard-independent-jobs.json`, `guard-independent-<phase>-output.txt` and `guard-cloud-validation.json`, and it does not exercise a real scheduled installation or a real cancellation |

The `guard/` subfolder holds the guard itself.

| File (`guard/`) | Run on | Purpose |
|---|---|---|
| `runbook-maintenance-guard.ps1` | Azure Automation (PowerShell 7.4, Az 12.3) | The Pre/Post maintenance guard runbook source. A real Pre run needs the tags `HvUmApproval=Approved` and `HvUmTarget=SQL2019-GUEST` and a guest policy that disables automatic installation or is notify-only. The guard keeps the earliest healthy Pre result as the baseline in append-only, non-secret Automation variables, and it cancels the exact maintenance occurrence when a real Pre check fails. It never installs updates, changes SQL Server, changes services or reboots |
| `test-maintenance-guard.ps1` | Operator PC | Offline test runner for the guard (Windows PowerShell 5.1 or PowerShell 7): every Azure, sign-in and sleep call is mocked, and nothing touches Azure or a guest. It prints one `PASS` or `FAIL` line per test and ends with `OFFLINE ONLY: <n> passed; <m> failed. No Azure or guest execution occurred.` |

### The queries folder

`queries/` holds 47 query files and two helper scripts, all read-only. The three `*.arg.kql` files are Azure Resource Graph queries: paste them into Resource Graph Explorer in the Portal, or run them with `az graph query` after you have added the `resource-graph` extension ([section 2.2](02-tools-secrets-and-conventions.md#22-open-the-lab-kit-on-the-operator-pc)). The other `.kql` files are Log Analytics queries for the Logs blade or `Invoke-LabQuery`; `ct-file-changes.kql` and `ct-sql-services.kql` run against the Change Tracking workspace `law-arc-ct-sea`, the others against `law-arc-monitor-lab`. `sql-databases.kql` is not a query: it holds only the REST address of the SQL database inventory (kept for reference), and `sql-databases.ps1` makes the REST call itself, so use the script.

| Topic | Files |
|---|---|
| CPU and wait | `host-cpu.kql`, `guest-cpu.kql`, `cluster-cpu.kql`, `cpu-wait.kql`, `wait.kql`, `wait-summary.kql`, `cluster-contention.kql` |
| Memory | `windows-guest-memory.kql`, `rhel-guest-memory.kql`, `cluster-memory.kql` |
| SQL | `sql-memory.kql`, `memory-cap.kql`, `memory-breakdown.kql`, `memory-headroom.kql`, `memory-evidence.kql`, `query-grants.kql`, `sql-counters.kql`, `sql-databases.kql`, `sql-databases.ps1` |
| Storage | `windows-iops.kql`, `windows-latency.kql`, `vhdx-iops.kql`, `vhdx-latency.kql`, `host-storage-iops.kql`, `host-storage-latency.kql`, `rhel-device-detail.kql`, `rhel-device-iops.kql`, `rhel-device-latency.kql` and the 13 `storage-*.kql` validation queries (duplicate Windows and RHEL points, heartbeat, host device IOPS and latency, Hyper-V VHDX only, the `HvLinuxDisk_CL` rows, RHEL filesystem space, latest and weighted five-minute values, Windows latency and volume space) |
| Inventory and health | `heartbeat.kql`, `counter-inventory.kql`, `arc.arg.kql` |
| Management | `update-assessment.arg.kql`, `update-history.arg.kql`, `ct-file-changes.kql`, `ct-sql-services.kql` |
| Alert history | `alert-history.ps1` (Monitor alert-management REST scoped to the resource group) |

Evidence and query files are read-only: they export monitoring data and configuration and never change the lab.

## 26.2 Generated JSON files are executable configuration

**What you are doing:** This section reminds the reader that generated JSON files are not just notes. They are live configuration payloads and should be compared carefully with Azure GET output.

> **Do this on:** the Azure portal in a web browser on the operator PC for the deployed settings check, and on the operator PC for the source comparison.

Portal steps:

1. Inspect the DCR settings after deployment.
2. Inspect the workbook settings after deployment.
3. Inspect the rule settings after deployment.
4. Do not assume that a file in `lab-kit/` is deployed just because it exists.

CLI path: each source file refers to Azure resource identifiers only and contains no literal secrets; compare each file with a read-only Azure GET of the deployed resource. Use the exact schema that accompanies the actual collector. Some payloads are examples of what a script writes when it runs: `maintenance-config-request.json`, `maintenance-dynamic-scope-request.json`, `periodic-assessment-request.json` and `ct-dcr-request.json` in `management/` are overwritten by their scripts, so compare them with the deployed resource, not with the date or the values of a previous run. `protected-*.json` files, guest-password files, media-key transfer helpers and `ENVIRONMENT.txt` are deliberately **not part of the lab kit**. `Copy-LabPublicSources.ps1` stops before sending anything if a file name contains `ENVIRONMENT` or `webhook`, starts with `protected-` or `parameter-`, or has an extension other than `.ps1`, `.py`, `.json`, `.kql`, `.sh`, `.txt`, `.service` or `.md`.

## 26.3 Definitions and unit quick reference

**What you are doing:** Use these definitions to keep units and terms consistent while presenting the demo.

> **Do this on:** the Azure portal in a web browser on the operator PC for workbook legends and resource properties, and on the operator PC for counter inventory and schema review.

| Term | Meaning |
|---|---|
| Arc | Connected Machine metadata/management plane |
| AMA | Azure Monitor Agent |
| DCR | Data collection rule: source/destination/association rule |
| LAW | Log Analytics workspace |
| LP | Host logical processor |
| vCPU | Guest virtual processor |
| VHDX | Nested disk file |
| IOPS | I/O operations per second |
| ms | Milliseconds |
| MiB/s | Bytes per second divided by 1,048,576 |
| DMV | SQL dynamic management view |
| max server memory | SQL managed-memory ceiling |
| query grant | Workspace allocation, not buffer pool |
| UTC | Query and evidence time standard |
| LT | Local time of the lab (UTC+7, Windows time zone `SE Asia Standard Time`); always shown next to UTC |

When a unit is not verified, label it **raw/unverified** rather than presenting a persuasive but wrong conversion.
