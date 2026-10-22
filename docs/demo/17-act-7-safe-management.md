# Act 7. Safe management – patching and change history

Act 7 covers minutes 65–73 of the storyline (about 8 minutes). Its goal is to show control: what is missing, what is scheduled, what changed – without installing or changing anything during the demonstration. Before you start, the **Machine – Azure Arc** page of `SQL2019-GUEST` must be reachable and the Workbook from Act 2 must be open in Read mode. For the optional step in section 7.4, Windows PowerShell with Azure CLI and its Resource Graph extension must be ready, and the variable `$SUB` from Act 0 must still be defined. Nothing in this act changes the lab: you only read.

## 7.1 Update Manager – what is missing

> **Where to run it:** **Azure Portal**.

> **Do this:** Open **SQL2019-GUEST** (the **Machine – Azure Arc** page). In the left menu click **Operations → Updates**. Read **Periodic assessment**, the four numbers and **Last assessed**. Do **not** click **Check for updates**, **One-time update**, **Schedule updates** or **Update settings**.

The Updates page for `SQL2019-GUEST` shows these parts in reading order:

- **(1)** **Periodic assessment: Yes.** Azure re-checks the server automatically.

- **(2)** **Total updates 4** (recorded lab result): critical 0, security 2, other 2.

- **(3)** **Last assessed** time. The check runs by itself.

- **(4)** The list of missing updates with KB number and "Can request reboot".

- **(5)** Toolbar buttons that **change** things. Do not click them.

> **Say this:** "Azure continuously checks what is missing. In our recorded lab result there were four updates, two of them security. We **read** this; we do not install anything in this demonstration."

## 7.2 The safe maintenance schedule

> **Do this:** Top search box → type `Maintenance configurations` → open it. Click `mc-hv-sql2019-definitions-gated`. Read the **Overview**. Then read **Schedule**, **Updates** and **Dynamic scopes** (names can differ slightly between Portal versions). Do **not** edit.

The maintenance configuration shows this in its Overview:

- **(1)** **Maintenance scope: Guest.** **Reboot setting: Never reboot.** One pre-task and one post-task (the safety guard).

| **Setting** | **Value** |
|---|---|
| Schedule | Weekly, **Monday 12:00–13:30 UTC (19:00–20:30 LT)**, starting on the first Monday after the schedule was created and ending about six weeks later |
| What it may install | **Only one** Microsoft Defender definition update (KB2267602) |
| Reboot | **Never reboot.** Updates that need a reboot are excluded. |
| Who it applies to | **Only SQL2019-GUEST**, chosen by the tags `HvUmTarget=SQL2019-GUEST` and `HvUmApproval=Approved` (while `HvUmApproval` is `Pending`, the schedule is paused and selects no machine) |
| Safety guard | A small automation checks that SQL is healthy before the window and can cancel the occurrence. |

The configuration is created by `lab-kit\management\provision-maintenance.ps1`; the build steps, the guard and the arming tag are explained in [setup chapter 20](../setup/20-update-manager.md).

> **Be honest:** "This is a **configuration**. We do not claim that a scheduled run has completed. Disruptive operating-system or SQL patches and reboots are outside this configuration and would be planned as a separate change."

## 7.3 Change Tracking and the Operations menu

> **Do this:** On the same **SQL2019-GUEST (Machine – Azure Arc)** page, click **Operations** in the left menu. Look at the list. Click **Change tracking**. Wait up to 20 seconds.

The Operations menu of an Arc machine shows:

- **(1)** **Operations** group: **Policies**, **Machine Configuration**, **Run command**, **SQL Server Configuration**, **Updates**, **Inventory**, **Change tracking**. One menu for management.

The Change tracking page for `SQL2019-GUEST` (last 24 hours) shows these parts in reading order:

- **(1)** Tabs **Changes** and **Events**; filters for time span and change type.

- **(2)** Totals: **414 changes** (recorded lab result: 2 added, 412 modified, 0 removed).

- **(3)** The list: what changed, change type, machine and **time generated**. The link **View** shows the change history.

> **Say this:** "Change Tracking records what changed on the server – services, files, software. Most of these entries are normal Windows service updates. We also recorded a deliberate, harmless file change during the recorded window: it was detected at 04:13 UTC (11:13 LT) and restored three minutes later."

> **Be honest:** "Change Tracking is **operating-system and file** change evidence. It is **not** SQL row-level change tracking, and file contents are not uploaded. A change list near an incident helps investigation but does **not prove** the cause."

The collection setup and the harmless test change are described in [setup chapter 21](../setup/21-change-tracking-and-inventory.md).

## 7.4 The same evidence inside the Workbook

The Workbook already holds **four panels at the very bottom** for this topic. They let you tell the whole management story from **one page**.

> **Where to run it:** **Azure Portal → Workbook** (Tab 2 of Act 0).

> **Do this:** Click the **Time range** pill → **Custom**. Start: the date of the recording (`<INCIDENT_DATE>`, typed in the format the box shows) and `11:00:00 AM`. End: the same date and `11:30:00 AM` (local time, LT; the Workbook shows the time zone of the browser, UTC+7 on the Operator PC). Click **OK** and wait 15 seconds. Press the **End** key (or scroll to the bottom) to reach the last four panels. Read **Change Tracking - real reversible file change (Southeast Asia workspace)**: the harmless test file, the change type and the time generated. Read **Change Tracking - latest SQL service inventory**: the services MSSQLSERVER, SQLSERVERAGENT and SqlServerExtension with their state and startup type. Read **Update Manager - missing update inventory (SQL Arc guest only)** and **Update Manager - actual installation history (not a scheduled-run claim)**. These two panels do not use the time range: they show the latest Azure assessment and what Azure has recorded as installed.

> **Say this:** "Inside one report we can see what changed on the SQL server, which SQL services are running, which updates are missing and what Azure recorded as installed. This is the evidence a change review asks for."

> **Be honest:** The first two panels depend on the time range. If a table is empty, say **"no record in this window"** and do not guess. The installation-history panel shows what Azure **recorded**; it is **not** a promise that the scheduled Monday window has run.

> **Where to run it:** **Optional PowerShell** (Operator PC, read-only): the Update Manager assessment using Azure Resource Graph.

**Missing updates of SQL2019-GUEST**

```powershell
Set-Location '<REPO_ROOT>\lab-kit'
$argQuery = Get-Content -LiteralPath .\queries\update-assessment.arg.kql -Raw
az graph query --subscriptions $SUB --graph-query $argQuery --first 100 -o table
```

> **If something goes wrong:** If `az graph` is not available, skip this. The Portal page already shows the same result.
