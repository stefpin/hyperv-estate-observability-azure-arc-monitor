# 14. SQL memory ceiling - what allocated versus active means

This chapter defines the SQL memory cap used in this lab, shows how to configure it safely, explains every memory line the workbook shows without double counting, and creates only the demo databases and the least-privilege collector that feeds the custom SQL memory table. Use it before you read or explain any SQL memory chart. The cap is **SQL max server memory** only; it is not a CPU cap. The SQL guest has 12 GB of static memory and four vCPUs, and the ceiling is 80% of the detected physical memory (9,829 MB in this lab).

> **Before you start:** commands marked as running inside the SQL guest assume that the lab-kit scripts they call (`guest-sql.ps1`, `Install-LabSqlMemoryCollector.ps1` and the `memory-collector.ps1` it installs) are in `C:\lab-kit` on `SQL2019-GUEST`. They are copied there with `Copy-LabPublicSources.ps1 -Target SqlGuest` ([section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)), and the guest commands start with `Set-Location C:\lab-kit`. Commands marked "your own computer" run from the `lab-kit` folder of the repository with `context.ps1` loaded.

## 14.1 Cap is only max server memory, not CPU

**What you are doing:** you define what "usage capping" means in this lab. It means **SQL max server memory** only. It does not mean CPU capping.

Be explicit about what is **not** being changed:

- No CPU cap is applied.
- No Resource Governor pool is used.
- No Hyper-V processor limit is set.
- The OS memory limit is not changed.
- The SQL guest remains at 12 GB static memory and four vCPUs.

If you want to show the setting in the SQL Server UI:

> **RUN ON - SQL2019-GUEST (inside the guest), SSMS with Windows authentication**

1. In SSMS, right-click the server.
2. Click **Properties**.
3. Click **Memory**.
4. Look at **Maximum server memory**.

Explain this clearly: the final maximum server memory value is the calculated 80% value of the detected physical memory, not a fixed generic 8 GB value (the 8192 MB set during installation is only a safe initial value). At the same time, the workbook displays the real DMV and Perf values. A DMV is a Dynamic Management View, which is a built-in SQL Server view that shows internal state. The Azure Portal cannot edit this guest-local SQL configuration directly.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell**

```powershell
Set-Location C:\lab-kit
. .\guest-sql.ps1
Invoke-LabSql "SELECT total_physical_memory_kb/1024 AS PhysicalMB
 FROM sys.dm_os_sys_memory;
 SELECT value,value_in_use FROM sys.configurations
 WHERE name='max server memory (MB)';"
```

**What you should see:** the detected physical memory and an **integer floor of 80%** of it as the configured value. The verified whole-MB detection is **12,287 MB**, so floor(12,287 x 0.8) = **9,829 MB**, and `value_in_use` is 9,829. The nominal 12 GB assigned to the VM is not a substitute for this detected calculation. This demo rounds physical KB down to whole MB first, then floors the 80% ceiling:

```text
ceiling (MB) = floor( floor(total_physical_memory_kb / 1024) x 0.8 )
```

## 14.2 Configure a ceiling safely

**What you are doing:** you set the SQL memory ceiling safely. You check OS headroom first, then apply the exact calculated cap. No restart is required for this setting.

If you use the SQL Server UI:

> **RUN ON - SQL2019-GUEST (inside the guest), SSMS with Windows authentication**

1. Read the current physical RAM and OS available memory with the query above.
2. Check that at least 3 GB is currently available before raising the initial ceiling.
3. In SSMS, open **Server Properties**.
4. Click **Memory**.
5. Set the calculated maximum.
6. Click **OK**.
7. Record the old value, the new value and the time.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** This is the configuration step.

```powershell
Set-Location C:\lab-kit
. .\guest-sql.ps1
$ram = [int](Invoke-LabSqlScalar "SELECT total_physical_memory_kb/1024 FROM sys.dm_os_sys_memory")
$free = [double](Invoke-LabSqlScalar "SELECT available_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory")
if ($free -lt 3072) { throw 'Investigate OS headroom before raising SQL memory ceiling' }
$cap = [int][Math]::Floor($ram * 0.8)
Invoke-LabSql "EXEC sp_configure 'show advanced options',1; RECONFIGURE;
 EXEC sp_configure 'max server memory (MB)',$cap; RECONFIGURE;"
Write-Output "Configured ceiling $cap MB from detected physical RAM $ram MB"
```

**What you should see:** `value_in_use` matches the calculated cap.

> **Warning:** This 80% is a demo comparison, **not universal SQL capacity-sizing advice**. `max server memory` does not bound every allocation in the SQL process: thread stacks and other allocations can make the process footprint exceed the managed-memory ceiling. Maintain OS headroom and review the real workload, concurrency and other agents.

## 14.3 Explain all the lines without double counting

**What you are doing:** you explain the memory lines in plain language so readers do not confuse "allocated" with "active", and does not add together values that overlap.

Use these simple meanings when you explain the chart:

- **Max server memory (MB)** is the configured ceiling for SQL Server managed memory. It is a limit, not a preallocated amount.
- **Allocated** does not automatically mean "actively used right now".
- **Used** means the part currently being consumed inside a specific allocation category.
- **Query workspace grants** are memory reservations for query work areas such as sorts and hashes. SQL can allocate a larger workspace grant than the query is using at that instant.
- **Cache** is memory SQL keeps so it can reuse data quickly. Cache remaining after activity ends is normal and does not prove a leak or active query work.

Most importantly, keep these distinctions clear:

- `TotalMemoryMB` is managed memory currently committed by the SQL memory manager.
- `FreeMemoryMB` is unused space inside that already committed managed memory.
- `TotalMemoryMB - FreeMemoryMB` is non-free committed managed memory. That includes cache and other consumers. It is **not** the same thing as "active query memory".
- `GrantAllocatedMB` is only the sum of currently granted query workspace memory.
- `GrantUsedMB` is only the sum of current workspace actually used within those grants.
- A gap between `GrantAllocatedMB` and `GrantUsedMB` is allowed and can be completely normal while a query is running.
- `ProcessMB` can be larger than the managed-memory ceiling because some SQL process memory is outside `max server memory`.
- `OsAvailableMB` is Windows available memory, which is different from SQL free committed memory.

The two identities that the workbook relies on are:

```text
non-free committed memory = TotalMemoryMB - FreeMemoryMB
unused grant difference   = GrantAllocatedMB - GrantUsedMB
```

Use the reference table below, unchanged, when you present the field meanings:

| Workbook / collector field | Meaning | What it is not |
|---|---|---|
| MaxMemoryMB | Configured maximum managed-memory ceiling | Not the amount preallocated, currently committed or actively used by queries |
| Target memory Perf counter | SQL memory manager's desired managed-memory amount | Not automatically the cap or current committed amount |
| TotalMemoryMB | Managed memory currently committed by SQL memory manager | Not necessarily all SQL process/private bytes |
| FreeMemoryMB | Unused portion within currently committed managed memory | Not Windows free physical memory |
| TotalMemoryMB - FreeMemoryMB | Non-free committed managed memory, including cache and other consumers | **Not "active query memory"** |
| CacheMemoryMB / StolenMemoryMB | Explanatory SQL managed-memory components | Do not add to Total again; component definitions are not separate process totals |
| GrantAllocatedMB | Sum of currently granted query workspace memory | Not all SQL allocated memory; not buffer cache |
| GrantUsedMB | Sum of current workspace used memory in those grants | Not all actively used SQL memory; sampled instantaneous value |
| PendingGrants | Queries still waiting for workspace grants | Not all waiting SQL sessions or CPU queue depth |
| ProcessMB | SQL process physical memory footprint | Can include memory outside max server memory |
| OsAvailableMB / PhysicalMB | Windows available / detected physical RAM | Not SQL's free committed memory |

In the workbook, in the Azure Portal:

1. Open the workbook.
2. Go to the **SQL memory** section.
3. Select **SQL2019-GUEST**.
4. Select the time window that covers the memory test you want to explain.
5. Read the legend line by line.
6. Point to the grant comparison separately.

A workbook is an Azure Monitor dashboard/report made from queries and visuals.

If you use the query route, run it on the operator machine with the supplied `lab-kit/queries/sql-memory.kql` and the guest DMV query in the lab kit. KQL means Kusto Query Language, the query language used in Azure Monitor Logs.

Remember these sampling rules and warnings:

- The custom collector samples every **15 seconds**, so a short grant can start and finish between samples.
- Zero grants at idle are valid.
- Retained cache after completion is valid behavior.
- Do not run `DBCC DROPCLEANBUFFERS`, `FREEPROCCACHE` or force an artificial decommit to manufacture a satisfying chart.

**Worked example.** The following values were recorded at one sampled instant during a memory test:

| Measure | Value |
|---|---|
| SQL managed committed memory | 1,136.45 MB |
| Cache | 347.60 MB |
| Query grants allocated | 480.91 MB |
| Query grants actually used | 288.60 MB |
| Unused grant difference (480.91 - 288.60) | 192.31 MB |
| Windows available memory | 8,369.14 MB |

The grant pair is the precise workspace allocated-versus-used comparison; **1,136.45 MB** is not "all active queries". In the recovery window the averages show grants allocated and used both at zero while cache remains about **347.9 MB** and committed memory about **1,133.4 MB**. That retained memory is valid cache, not a leaked query or a failure to stop SQL. Values are sampled and rounded and must not be added together as independent memory totals.

## 14.4 Create only demo databases and the least-privilege collector

**What you are doing:** you create only the demo databases and a least-privilege local collector account. Least-privilege means the account gets only the minimum permissions it needs.

> **Note:** `ENVIRONMENT.txt` is the private settings file of the lab. It lives in the repository root, one folder above `lab-kit/`, and is git-ignored. If you created it with `lab-kit/Initialize-LabSecrets.ps1` ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), it holds the `SQL_COLLECTOR_PASSWORD` that you entered there (at least 16 characters). Never commit it, print it or paste it into a document.

On the guest, follow these UI steps:

1. Open **Computer Management**.
2. Open **Local Users and Groups**.
3. Click **Users**.
4. Click **New User**.
5. Create `HvSqlCollector`.
6. Use a private password (at least 16 characters) that is recorded only in the private settings file (`ENVIRONMENT.txt`, key `SQL_COLLECTOR_PASSWORD`).
7. Make sure the account is **not** a member of the Administrators group.

Then in SSMS:

1. Create the Windows login `SQL2019-GUEST\HvSqlCollector`.
2. Grant CONNECT SQL.
3. Grant VIEW SERVER STATE only.
4. Create `OrdersDemo`, `BillingDemo` and `ReportingDemo` in the specified SQL data and log directories.
5. Use the simple recovery model for this synthetic lab.

`Install-LabSqlMemoryCollector.ps1` performs these same guest-local steps on the SQL guest. It prompts privately for the `HvSqlCollector` password (type the same value as `SQL_COLLECTOR_PASSWORD` in `ENVIRONMENT.txt`; an existing account must keep its existing password), creates the local account if it is missing (password never expires, the account cannot change it), grants it CONNECT SQL and VIEW SERVER STATE, and creates `OrdersDemo`, `BillingDemo` and `ReportingDemo` if they do not exist (32 MB data and log files in `E:\SQLData` and `L:\SQLLog`, simple recovery model). It also sets the SQL ceiling with the calculation and the 3 GB free-memory check of section 14.2, so running section 14.2 first is harmless. Finally it installs `C:\HV-Demo\memory-collector.ps1` and a startup-trigger scheduled task named **HV-SQL-Memory-Collector**, which runs a 15-second loop without administrator rights, starts the task, waits 30 seconds and verifies that the task is running and a log file exists. The script directory is read-only to the collector; the logs directory grants it Modify; SYSTEM and Administrators retain Full Control. The task password belongs only in Windows task credential storage and the private settings file, never in a lab kit file.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell**

```powershell
Set-Location C:\lab-kit
.\Install-LabSqlMemoryCollector.ps1
Get-ScheduledTask -TaskName HV-SQL-Memory-Collector | Select-Object TaskName,State
Get-ChildItem C:\HV-Demo\logs\sql-memory-*.json |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 Name,LastWriteTime
```

**What you should see:** the script ends with `Collector Running; ceiling=<n> MB; log timestamp=<UTC time>` (it stops with `Collector verification failed.` otherwise), the task is Running, and the newest date-named file contains one compact JSON object per line. The most recent timestamp should be no older than about 30 seconds on the guest's clock. Collector errors are written separately. A missing current log is an error, not SQL being idle.

You can run the same setup from your own computer without opening the guest. `lab-kit/sources/demo-v22/install-memory.ps1` reads `SQL_COLLECTOR_PASSWORD` from `ENVIRONMENT.txt` in the repository root (it generates the password and appends the key only if it is missing), checks the PowerShell syntax of the scripts in its folder, and sends `guest-memory-setup.ps1` to `SQL2019-GUEST` through Arc Run Command with the password as a protected value. That script also grants the collector account the "Log on as a batch job" right and creates `OrdersDemo` with a 256 MB data file and a 128 MB log. Both routes can be repeated safely; use one of them.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder (the script loads `context.ps1` itself). Use it instead of the guest route above.

```powershell
.\sources\demo-v22\install-memory.ps1
```

**What you should see:** the Arc run command name `sql-memory-setup-<time>`, then the output of the guest script: `SQL memory ceiling=<n> MB (80% of detected <n> MB physical RAM)`, a `Collector=Running; total=...` line, and `SQL-MEMORY-SETUP-DONE`.
