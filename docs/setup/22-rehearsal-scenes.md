# 22. Rehearsal - four separate scenes, real exports and recovery

This document is the rehearsal guide for the lab: the read-only starting checks, then separate CPU, storage and SQL memory scenes, and a closing pass over the management, alert and report results. Each scene is bounded, ends with a clean stop, and is followed by real exports and proof of recovery. Use it before presenting or reproducing the lab, so that every observation can be tied to a start time, an end time and a recovery.

Commands in this document are written to run from the `lab-kit` folder (`cd lab-kit`) on the operator PC, in a PowerShell session where the lab context has been loaded with `. .\context.ps1`, unless a block says that it runs on the Hyper-V host (`F:\Build\lab-kit`) or inside the SQL guest (`C:\lab-kit`); [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest) explains how the kit gets there. The genuine alert-e-mail variant of the CPU scene is described in [section 19.8 of the Alerts guide](19-alerts.md#198-genuine-end-to-end-cpu-rehearsal-then-automatic-recovery).

## 22.1 Read-only starting checks

**What you are doing:** These are the preflight checks before any rehearsal scene. The goal is to prove the lab is healthy before you create any load.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visual checks, and on the operator PC in PowerShell with Azure CLI for the read-only evidence export and host status call.

Portal checks:

1. Verify the Arc machine list shows Connected.
2. Verify the host Azure VM shows Running.
3. Verify SQL Arc shows Connected.
4. Verify the workbook timestamp is recent.
5. Verify CPU is near quiet baseline.
6. Verify the collector task is healthy.
7. Verify the current storage free space.
8. Verify the management last result.
9. Close secret files and credential dialogs.
10. Do **not** start an assessment or install during an unrelated live load scene.

> **Do this on:** your operator PC, in PowerShell with Azure CLI. Run the exact commands below.

```powershell
.\Get-LabEvidence.ps1 -OutputDirectory .\exports\preflight
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\status-host.ps1
```

**What you should see:** six recent heartbeats, correct SQL configuration, no pending unexpected reboot and no workload leftovers. `Get-LabEvidence.ps1` is read-only: it writes the Arc machine, resource and alert-rule inventories, the five query results (`heartbeat`, `counter-inventory`, `sql-memory`, `storage-windows` and `cpu-wait`) and `snapshot-time.txt` into `.\exports\preflight`, and ends with `Read-only public evidence export completed; no guest commands or Azure writes.` A failed query is captured as failure; never export an empty success file after swallowing the exception.

## 22.2 CPU scene, then stop and prove recovery

**What you are doing:** This scene drives CPU on the intended Windows guests, then you let the scene stop and you show recovery evidence. This is also the basis for the genuine alert-e-mail route in [section 19.8](19-alerts.md#198-genuine-end-to-end-cpu-rehearsal-then-automatic-recovery).

> **Do this on:** the Azure portal in a web browser on the operator PC for workbook monitoring, the RHEL terminal for local HTTP statistics, and the host terminal for the bounded workload launch.

Portal and observation steps:

1. Open the workbook's live CPU and wait sections.
2. Keep the RHEL terminal visible for local HTTP statistics.
3. Note the baseline UTC time.
4. Start the bounded load on the three Windows guests via the host terminal.
5. Note the scene start time.
6. Use the bounded **900-second** scene and recovery in [section 19.8](19-alerts.md#198-genuine-end-to-end-cpu-rehearsal-then-automatic-recovery) when demonstrating genuine alert e-mail.
7. Remember that a shorter visualization scene is not equivalent evidence of a ten-minute query condition.
8. Wait for the deadline and PID-specific cleanup.
9. Wait for quiet trends and automatic Resolved/mail evidence.
10. Do **not** reboot.

CLI path: on the host, run the wrapper `Start-LabCpuScene.ps1 -Seconds 900` as in [section 19.8](19-alerts.md#198-genuine-end-to-end-cpu-rehearsal-then-automatic-recovery); it prompts privately for the credentials of only the three Windows guests. The two other ways of starting the same bounded scene (through Arc Run Command from the operator PC, and the script inside one guest) are described in [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene). Save the KQL results for baseline, load and recovery, and the actual alert and received-e-mail UTC times, separately. Keep SQL idle-but-running throughout.

> **Do this on:** the Hyper-V host (`HV-HOST-01`), in an elevated PowerShell window (reach it through Bastion). Run the exact commands below; the wrapper asks for the three guest passwords.

```powershell
Set-Location F:\Build\lab-kit
.\Start-LabCpuScene.ps1 -Seconds 900
```

**What you should see:** `Started bounded workers on <guest>; SQL guest not loaded.` for each of the three guests and, when the scene has finished, `Only recorded bounded CPU worker PIDs cleaned up; SQL remains running.`

From the operator PC, `lab-kit/sources/demo-v22/run-cpu-storage-rehearsal.ps1` runs the Arc version of the 900-second CPU scene and then, after a 90-second pause, the 180-second storage scene of [section 22.3](#223-storage-scene-then-stop) on `SQL2019-GUEST`. It reads the three guest passwords from `ENVIRONMENT.txt` at the repository root ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) and sends them only as protected parameters, it needs the one-time SSH preparation described in [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene), and it saves the start and end UTC times and the console output of each scene in `cpu-storage-rehearsal.json` next to itself.

**Expected:** 12 busy Windows vCPUs, no extra SQL worker, and the collector and AMA do not lose health. Host CPU recovery is a measurement, not a forced host restart.

## 22.3 Storage scene, then stop

**What you are doing:** This scene creates bounded storage activity and then stops it cleanly.

> **Do this on:** the Azure portal in a web browser on the operator PC for workbook review, and on the operator PC (through Arc Run Command) or inside **SQL2019-GUEST** for the bounded storage script.

Portal steps:

1. Open the workbook storage section.
2. Execute only the bounded storage script (`lab-kit/demo/guest-storage-rehearsal.ps1`); it runs only on `SQL2019-GUEST`.
3. Compare meaningful I/O and latency at the guest, VHDX and host layers.
4. Record the exact start time and end time.
5. Record the affected files (`E:\HV-IO-Demo\worker-0.bin` to `worker-3.bin`) and the volume (`E:`).
6. Stop and clean the designated test files: the script removes only those four files itself once its workers have finished.

CLI path: run the same scripted scene as in [section 16.4](16-storage-telemetry.md#164-a-safe-storage-only-demonstration), with no simultaneous CPU burn, and export the guest and host I/O queries. If the bounded test source or the data evidence is missing, do not substitute a dangerous script; mark the missing demonstration.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder with the lab context loaded. Run it there so that Arc Run Command executes the script on `SQL2019-GUEST`.

```powershell
Invoke-LabArcScript -Machine SQL2019-GUEST -ScriptPath .\demo\guest-storage-rehearsal.ps1 `
  -Parameters @{ Seconds = '180' } -TimeoutSeconds 900
```

To work on the guest console instead, open an elevated PowerShell window on `SQL2019-GUEST`, run `Set-Location C:\lab-kit` and then `.\demo\guest-storage-rehearsal.ps1 -Seconds 180`.

**What you should see:** four lines `Storage worker operations=<n>; duration=180s; bounded random 8KiB write-through.` followed by `Storage rehearsal finished; SQL=Running; only dedicated test files removed.`

**Expected:** actual I/O and units, no raw-disk writes, and every volume retains headroom.

## 22.4 SQL memory scene, then retained cache

**What you are doing:** This scene shows SQL memory behavior across idle, warm cache, active grants and recovery. The point is to explain the difference between the SQL ceiling, committed memory, cache and query workspace grants.

> **Do this on:** the Azure portal in a web browser on the operator PC for the workbook and SQL Arc dashboard views, and on **SQL2019-GUEST** in an elevated PowerShell window for the synthetic workload.

Portal and demo steps:

1. Open the workbook SQL memory section.
2. Open the SQL Arc dashboard in another tab.
3. In the guest SSMS or terminal, run the synthetic workload against **OrdersDemo** only.
4. Stage the scene as idle, then workload, then recovery.
5. Show ceiling versus committed memory.
6. While queries exist, separately show allocated and used workspace grants.
7. Afterward, explain retained cache.

CLI path: the supplied workload is `lab-kit/demo/guest-workload.ps1`. It runs only on `SQL2019-GUEST` and works in the **OrdersDemo** database, which the installation in [section 14.4](14-sql-memory-ceiling-and-what-it-means.md#144-create-only-demo-databases-and-the-least-privilege-collector) creates, through a Windows-authenticated connection to `localhost`. It prepares **250,000 synthetic rows** in OrdersDemo; warm-cache uses MAXDOP 1; the final bounded grant sort uses MAXDOP 1 plus **MIN_GRANT_PERCENT=30 / MAX_GRANT_PERCENT=40** query hints. These deliberately generous synthetic workspace grants are **not production tuning advice**, a server CPU cap or a Resource Governor pool. The query reader throttles result consumption to keep the grant observable, then cancels and releases it. The observer continues; SQL services are not stopped. Each stage also writes its name (`prepare`, `baseline`, `warm-cache`, `query-grants` or `recovery`, and `idle` when the stage ends) to `C:\HV-Demo\stage.txt`; the memory collector copies that name into the `Stage` column of every sample, which is how the workbook and the exported tables separate the stages.

> **Do this on:** **SQL2019-GUEST**, in elevated PowerShell, synthetic rehearsal workload. Run the exact commands below. `-Seconds` defaults to 180; `Prepare` does not use it.

```powershell
Set-Location C:\lab-kit
.\demo\guest-workload.ps1 -Stage Prepare
.\demo\guest-workload.ps1 -Stage Baseline -Seconds 180
.\demo\guest-workload.ps1 -Stage WarmCache -Seconds 180
.\demo\guest-workload.ps1 -Stage GrantLoad -Seconds 180
.\demo\guest-workload.ps1 -Stage Recovery -Seconds 180
```

**What you should see:** `Synthetic OrderLines rows=250000; no business data.` for `Prepare` (the table is filled only when it is empty, so a repeat adds no rows), `Bounded sort query returned <n> rows; grant is now released.` for `GrantLoad`, and `Completed stage <Stage>; SQL service=Running.` at the end of every stage. The exact ceiling persists, and you should have real committed, cache and grant samples and the database inventory. A tiny or no-load database can yield low committed memory and no grants; that is still accurate but not a fully proven allocated-versus-used workload comparison. Do not label non-free committed memory as all active queries. No cache clear is performed.

The same five stages can be run from the operator PC through Arc Run Command, without opening the guest. `lab-kit/sources/demo-v22/rehearse-memory.ps1` runs `Prepare`, `Baseline`, `WarmCache`, `GrantLoad` and `Recovery` one after the other, 180 seconds each, with the identical `guest-workload.ps1`. Pass `-StartAt <Stage>` to resume at a later stage after a failure; the earlier entries are kept.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder, after `tools\Set-RepoContext.ps1 -Apply` has replaced the placeholders ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

```powershell
.\sources\demo-v22\rehearse-memory.ps1
```

**What you should see:** a line `Running memory-<stage>-<MMddHHmmss> on SQL2019-GUEST` for each stage, followed by the stage output listed above. The script saves each stage's start and end UTC time and its output in `memory-rehearsal.json` next to itself and deletes each finished Run Command.

## 22.5 Management, alerts and report scenes

**What you are doing:** This is the closing evidence pass for the rehearsal. You show what is actually complete, what is configured only, and what is still pending.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visual demo, and on the operator PC for the prepared evidence excerpts.

Portal steps:

1. Show the completed Update Manager assessment or install result if present ([Chapter 20](20-update-manager.md)).
2. Show the configured maintenance, dynamic scope and pre/post workflow ([Chapter 20](20-update-manager.md)) only with their explicit configured/pending status.
3. Show CT real inventory/change ([Chapter 21](21-change-tracking-and-inventory.md)).
4. Show real fired alerts if any ([Chapter 19](19-alerts.md)).
5. Export the report ([Chapter 23](23-reports-and-export.md)).

CLI path: copy the non-secret evidence excerpts from the storage and management evidence exports, with their timestamps and results. The management scripts leave the Azure responses next to themselves and in `lab-kit/management/evidence/` (both git-ignored); the query results you saved with `Invoke-LabQuery` and `Get-LabEvidence.ps1` are under `lab-kit/exports/` (also git-ignored). A rehearsal is complete when every checklist item has evidence, a documented limitation or a pending status. It does not mean every intended feature was executed.
