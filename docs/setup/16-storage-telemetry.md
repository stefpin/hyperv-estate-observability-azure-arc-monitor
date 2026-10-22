# 16. Storage telemetry - host, per-VHDX and per-volume views

This chapter verifies the three storage views of the lab so you can show them separately and correctly: the Hyper-V host's physical disks and virtual storage devices (VHDX files), the Windows guests' per-volume disks, and the RHEL guest's block-device statistics collected by a custom JSON collector. It ends with a safe, bounded storage-only demonstration. Use it after the Azure Monitor Agent and the DCRs are deployed ([chapter 11](11-azure-monitor-agent-and-dcrs.md)). Keep the three views apart: they describe overlapping layers of the same I/O path, so they are never added together.

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. Commands marked as running on the host or in a guest are typed there: the host commands of section 16.1 need no lab-kit file, and the SQL guest copy of the lab kit is `C:\lab-kit` ([section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)). The HTTP observer is installed by `install-rhel-observers.sh` ([section 8.3](08-rhel-guest-and-linux-collectors.md#83-http-victim-and-persistent-response-time-collection)); the Linux disk collector is installed by hand ([section 8.4](08-rhel-guest-and-linux-collectors.md#84-linux-disk-latency-is-not-a-classic-ama-perf-counter)).

## 16.1 Host physical disk and Hyper-V virtual storage

**What you are doing:** you verify the host-side storage telemetry so you can show physical disk and Hyper-V virtual storage views separately and correctly.

In the Azure Portal, follow these steps. The payload `lab-kit/dcr/dcr-hyperv-host.json` already contains every counter listed in steps 7 and 8 (29 counters in total, sampled every 60 seconds), so on a deployed lab these steps verify the rule; use them to add a counter only if one is missing in your copy:

1. Open `dcr-hyperv-host`.
2. Click **Data sources**.
3. Open **Windows Performance Counters**.
4. Open **Custom**.
5. Inspect the source payload in `lab-kit/dcr/dcr-hyperv-host.json`.
6. Retain the existing CPU and Hyper-V counters.
7. Add these `PhysicalDisk(*)` counters:
   - `Avg. Disk sec/Read`
   - `Avg. Disk sec/Write`
   - `Disk Reads/sec`
   - `Disk Writes/sec`
   - `Disk Read Bytes/sec`
   - `Disk Write Bytes/sec`
   - `Current Disk Queue Length`
8. Add these `Hyper-V Virtual Storage Device(*)` counters when those counter names exist on this installed host:
   - `Latency`
   - `Read Operations/Sec`
   - `Write Operations/Sec`
   - `Read Bytes/sec`
   - `Write Bytes/sec`
9. Add host LogicalDisk F: capacity/free-space counters only if they are not already collected by the applicable Windows DCR.
10. Avoid duplicate samples.
11. Set destination `law-arc-monitor-lab`.
12. Keep the rule's existing 60-second sampling.
13. Associate the rule with the host Arc resource.
14. Save.
15. In host **Performance Monitor** (`perfmon`) > **Add Counters**, confirm the installed names and instances, because the Portal cannot validate every guest counter at rule-save time.

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell.** This is read-only local verification.

```powershell
Get-Counter -ListSet 'Hyper-V Virtual Storage Device' |
  Select-Object -ExpandProperty PathsWithInstances
Get-Counter '\PhysicalDisk(*)\Avg. Disk sec/Read',
  '\PhysicalDisk(*)\Avg. Disk sec/Write' -SampleInterval 2 -MaxSamples 2
Get-VMHardDiskDrive -VMName SQL2019-GUEST |
  Select-Object VMName,ControllerNumber,ControllerLocation,Path
```

**What you should see:** concrete VHDX instances and actual disk paths. On the reference host, Hyper-V storage `Latency` is a cooked seconds value: the supplied validated query multiplies it by **1,000 for milliseconds** and includes only instances ending `.vhdx`, excluding companion `.iso` rows (see `lab-kit/queries/vhdx-latency.kql` and `lab-kit/queries/storage-hyperv_vhdx_only.kql`). Keep the raw counter and the conversion together when you report a result, and check the installed counter help if you reproduce this on another Windows version.

> **Warning:** Never add host physical-disk latency to guest or VHDX latency. These are overlapping views of the same I/O path, not independent delays to sum.

## 16.2 Windows guest per-volume disks

**What you are doing:** you verify guest-side per-volume disk telemetry so you can show C:, E: and L: separately instead of only `_Total`.

In the Azure Portal, follow these steps:

1. Open `dcr-windows-guests`.
2. Click **Data sources**.
3. Open **Performance counters**.
4. Open **Custom**.
5. Add or verify `LogicalDisk (*)`, including E: and L: on the SQL guest.
6. Verify these counters:
   - `Avg. Disk sec/Read`
   - `Avg. Disk sec/Write`
   - `Disk Reads/sec`
   - `Disk Writes/sec`
   - `Disk Read Bytes/sec`
   - `Disk Write Bytes/sec`
   - `Avg. Disk Queue Length`
   - `% Free Space`
   - `Free Megabytes`
7. Keep CPU and memory counters.
8. Preserve event sources.
9. Save.
10. Wait for new rows before validating.

The query must be per volume, not `_Total`.

> **PASTE INTO - law-arc-monitor-lab, Logs, KQL**

```kql
Perf
| where TimeGenerated > ago(30m)
| where _ResourceId contains "/resourceGroups/rg-hyperv-arc-monitor-demo/"
| where ObjectName == "LogicalDisk"
| where CounterName in ("Avg. Disk sec/Read","Avg. Disk sec/Write")
| where InstanceName != "_Total"
| summarize LatencyMs=avg(CounterValue)*1000
    by bin(TimeGenerated,1m),Computer,InstanceName,CounterName
| order by TimeGenerated asc
```

**What you should see:** separate C:, E: and L: where present, with latency shown in milliseconds. Never sum latency across drives, or sum `_Total` with its members. Match latency with the corresponding I/O rate; a reading from a silent disk is not a storage saturation diagnosis. The supplied equivalents are `lab-kit/queries/storage-windows_volume_latency_ms.kql` (read, write and transfer latency per volume) and `lab-kit/queries/storage-windows_volume_space.kql` (free space per volume).

## 16.3 RHEL iostat custom schema and validation

**What you are doing:** you keep the Linux storage data aligned with the actual custom schema and the actual collector path. Do not guess any path or table definition.

In the Azure Portal, follow this inspection route:

1. Open the workspace.
2. Click **Tables**.
3. Find the Linux custom table `HvLinuxDisk_CL`.
4. Inspect the exact numeric, device and time schema.
5. Verify that the Linux DCR source reads the collector's real JSON path, not a guessed path.
6. Open **Logs**.
7. Run the supplied `lab-kit/queries/storage-linux.kql`.
8. Keep the nginx response-time table separate from disk `await`.

The lab kit carries the Linux collector script (`lab-kit/storage/hv-storage-collector.py`) and its service unit (`lab-kit/storage/hv-storage-collector.service`), the DCR (`lab-kit/dcr/dcr-linux-guests.json`), the query (`lab-kit/queries/storage-linux.kql`) and the table schema (`lab-kit/schema/linux-disk-table.json`). The enabled `hv-storage-collector.service` writes one block-device row per **60 seconds** to `/var/log/hv-storage/disk-YYYYMMDD.log`; the JSON has `ReadIOPS`, `WriteIOPS`, `ReadAwaitMs`, `WriteAwaitMs`, `ReadKiBps`, `WriteKiBps`, `AvgQueueDepth`, `UtilizationPct`, `IntervalSeconds`, `MountedVolumes` and `AccountingScope`. The DCR stream is `Custom-HvLinuxDiskText` and the destination is **HvLinuxDisk_CL**. The current `dcr-linux-guests` carries this source; there is no separate custom DCR for it. Use `lab-kit/queries/storage-rhel_weighted_five_minute.kql` for operation-weighted averages, excluding zero-I/O directions rather than calling them zero-millisecond measured latency. The local comparison remains `iostat -x -y 15 2` on the RHEL guest.

**Reference verification result.** A completed storage verification showed all six heartbeats, eight Windows drive-letter volumes, 18 counters per Windows volume, 11 validated sample queries, and zero duplicate Perf or Linux points. In that run the RHEL guest's `sda` showed read 0.05 IOPS / 0.33 ms and write 9.68 IOPS / 1.71 ms, which is not saturation.

> **Warning:** the initial custom-stream ingestion attempts can fail with HTTP 400 and be retried, which can drop early rows before later rows flow successfully. The root cause was not established. If rows are missing at the start of a window, state that ingestion gap openly; never conceal it.

Interpretation reminders:

- Reads/writes per second are IOPS.
- Bytes/sec divided by 1,048,576 is MiB/s, not Mb/s.
- `await` is milliseconds per completed I/O over an interval.
- `%util` on virtual/block devices is an indicator, not a universally meaningful percent of an Azure disk throughput ceiling.
- Log ingestion can lag the local display.

## 16.4 A safe storage-only demonstration

**What you are doing:** you run only the bounded storage script from the lab kit. The goal is to create visible storage activity without risking the VM, the SQL files or the host.

Follow this order:

1. Open the workbook and go to the **Storage** section.
2. Open the Bastion host or guest console as required.
3. Stop the CPU scene first.
4. Run only the bounded storage script supplied in the lab kit (`lab-kit/demo/guest-storage-rehearsal.ps1`).
5. Use the target that the script fixes, exactly: it runs only on `SQL2019-GUEST`, writes four disposable 128 MiB files `E:\HV-IO-Demo\worker-0.bin` to `worker-3.bin`, and accepts 30 to 600 seconds (default 180). It waits 60 seconds before and 60 seconds after the load, so a run takes the load time plus about two minutes.
6. Use a disposable demo file only.
7. Never use a database MDF/LDF or a raw disk.
8. Watch host F:, the affected VHDX and guest E:/L: together.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder with the lab context loaded. Run it from there so that Arc Run Command executes the script on `SQL2019-GUEST`.

```powershell
Invoke-LabArcScript -Machine SQL2019-GUEST -ScriptPath .\demo\guest-storage-rehearsal.ps1 `
  -Parameters @{ Seconds = '180' } -TimeoutSeconds 900
```

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** Use this instead of the Arc command if you work on the guest console.

```powershell
Set-Location C:\lab-kit
.\demo\guest-storage-rehearsal.ps1 -Seconds 180
```

**What you should see in the console:** four lines `Storage worker operations=<n>; duration=180s; bounded random 8KiB write-through.` followed by `Storage rehearsal finished; SQL=Running; only dedicated test files removed.` The script stops with `Only SQL2019-GUEST and 30-600 seconds are permitted.` on any other machine or duration.

If you inspect the source first, use `Get-Content` **only for the non-secret workload source**, then execute it using the guest terminal or the Arc helper. Do not substitute unbounded `fsutil file createnew`, a full-disk fill, arbitrary write loops or a tool downloaded from an unknown source. If the script is absent, or the counters do not show meaningful I/O, show the real counters and the low-I/O limitation, and mark the load test pending.

**What you should see in the workbook and the metrics:** the bounded workload starts and stops cleanly, the metrics show corresponding throughput, IOPS and latency, and there is no guest volume exhaustion. SQL remains running. Cleanup deletes only the four test files after the workers have closed them. Do not delete SQL files or all of `F:\VMs`.

**Reference result.** A reference run used four 128 MiB disposable E: files and four 180-second synchronous random 8 KiB write-through jobs, then removed only those files. The loaded E: volume showed **800.80-811.48 IOPS** and **1.670-1.899 ms**, versus **0.291-0.533 ms** quiet measured I/O latency. This did **not** saturate the P20 disk's 2,300-IOPS baseline and does not prove a storage-induced slowdown of another application. Zero latency when IOPS is zero is not a service-latency measurement.
