# Act 5. SQL Server – the data tier

Act 5 covers minutes 42–57 of the storyline (about 15 minutes). Its goal is to show that SQL Server is **first-class** in this solution: inventory, licensing, health checks, performance and a clear explanation of SQL memory. Before you start, the Azure Portal tab for the SQL Server instance `SQL2019-GUEST` (Tab 3 of Act 0) must be open and the Workbook from Act 2 must be open in Read mode. For the optional section 5.6 the PowerShell variables `$SUB` and `$RG` from Act 0 must still be defined. The SQL memory scene is a recording; say "Recorded" when you show it.

## 5.1 The SQL Server instance in Azure Arc

> **Where to run it:** **Azure Portal**.

> **Do this:** In the top search box type `SQL2019-GUEST`. In the results choose the item of type **SQL Server instance** (not the "Machine – Azure Arc" one). On **Overview**, read **Mode**, **Location**, **Version**, **Edition**, and under **Properties** the **License type**.

The Overview page of the SQL Server instance shows these parts in reading order:

- **(1)** **Mode: Connected. Location: Southeast Asia.**

- **(2)** **Version SQL Server 2019. Edition Enterprise.**

- **(3)** **License type: Pay-as-you-go.** SQL licensing is billed through Azure; the lab uses this model.

- **(4)** Menu group **Monitoring**, where the Performance Dashboard lives.

> **Say this:** "SQL Server is registered as an Azure resource of its own. Azure knows its version, edition and licence model, and the same page leads to performance, databases, best practices, backups and updates."

## 5.2 Native performance dashboard

> **Do this:** In the left menu, click **Monitoring → Performance Dashboard (preview)**. Look at the controls at the top: **Time Range**, **Time Interval**, **Databases**, **UTC Time**.

The Performance Dashboard (preview) shows these parts in reading order:

- **(1)** Menu path: **Monitoring → Performance Dashboard (preview)**.

- **(2)** Controls: Time Range (Last Hour), Time Interval (1 Minute), Databases (all), UTC switch.

- **(3)** **Memory Utilization** chart for instance MSSQLSERVER.

- **(4)** **CPU Utilization (%)** of the SQL Server process. Near zero means SQL is idle.

> **Beginner tip:** This dashboard is Microsoft's **native** one. The Workbook uses a **separate, custom** SQL memory table. Both are shown on purpose: native for convenience, custom for the precise memory story.

## 5.3 Database inventory

> **Do this:** In the left menu, click **Data management → Databases**.

The Databases page of `SQL2019-GUEST` as Azure Arc sees it shows these parts in reading order:

- **(1)** **Last collected time** and **Upload status: Success**. This is an inventory that updates every few minutes, not a live query.

- **(2)** Seven databases: `model`, `msdb`, `master`, `tempdb` (system) and `BillingDemo`, `OrdersDemo`, `ReportingDemo`.

- **(3)** **Status: Online** for all.

> **Be honest:** "`OrdersDemo`, `BillingDemo` and `ReportingDemo` are **synthetic demonstration databases** created for this lab. They contain no real data."

## 5.4 Best Practices Assessment

> **Do this:** In the left menu, click **Settings → Best practices assessment**. Read the status. In the **Assessment results** table, click the date link of the latest completed run. A report page opens.

The assessment page shows these parts in reading order:

- **(1)** **Assessment status: Enabled**; results are stored in the Log Analytics workspace `law-arc-ct-sea`.

- **(2)** **Run assessment** – **do not click.** A scan reads the server and uses some CPU.

- **(3)** The previous run, **Completed**. Click its date to see the report.

The report page shows these parts in reading order:

- **(1)** **396 checks** in the recorded lab result: 376 passed, 9 low, 6 informational, 5 medium.

- **(2)** By category: Administration 264, General 109, System 15, Application 5, other categories 3.

- **(3)** The **Recommendation details** list names the database and says what to do, for example "Create full backup. Last full backup is over 7 days old" and "Change recovery model to FULL or BULK_LOGGED".

> **Say this:** "Azure also checks SQL Server for best practices automatically. In our recorded run, 376 of 396 checks passed; the five medium findings are things a DBA would want to know – old backups and recovery model – and each one says exactly which database and what to do."

> **If something goes wrong:** The page may print a default weekly **Sunday 00:00** schedule text. In this lab the scan is **not** scheduled; the result you see is from the one scan that was run. If asked, say: "The page shows default text; we ran the scan once and it is not scheduled."

## 5.5 SQL memory – the number everybody misunderstands

This is the most valuable explanation for anyone who runs SQL Server. Practise it twice.

> **Where to run it:** **Azure Portal → Workbook** (Act 2).

> **Do this:** Set the **Time range** to **Custom**: the date of the recording (`<INCIDENT_DATE>`, typed in the format the box shows) and `11:10:00 AM` to the same date and `11:26:00 AM`. Click **OK**. Wait 15 seconds. Scroll to the chart **Configured ceiling, SQL-manager committed and process footprint (MiB)**. The Portal uses the time zone of the browser, UTC+7 (LT) on the Operator PC, so the times you type are local time: 11:10–11:26 LT is 04:10–04:26 UTC.

The memory chart shows these parts in reading order:

- **(1)** **MaxMemoryMB ≈ 9,829** (almost 10,000). This is the **configured ceiling**.

- **(2)** **CommittedMB** and **ProcessMB**, about 1,100–1,200 MiB. This is what SQL actually holds.

- **(3)** Legend of the three lines.

- **(4)** The next chart splits SQL memory into **free**, **database cache** and **other/internal** memory.

> **Say this:** "SQL's memory ceiling is 9,829 megabytes – 80% of the 12,287 megabytes that Windows sees. But SQL is using about 1.1 gigabytes. **The ceiling is not a reservation and not the current usage.** It is the maximum SQL is allowed to grow to."

> **Beginner tip:** **Want the formulas behind the three SQL memory charts?** Section 3.5 of the [chart-reading guide](03-reading-charts-cpu-memory-storage.md) shows the **memory ledger** (Free + Cache + OtherInternal = Committed, Process − Committed, Granted − Used, headroom) with the recorded run and a second recorded run, and a query to check it yourself. How the 9,829 MiB ceiling is calculated is in [setup chapter 14](../setup/14-sql-memory-ceiling-and-what-it-means.md).

> **Do this:** Scroll to the chart **Query workspace: peak granted and paired actual-use snapshot per time bucket (MiB)** and the table **Memory stages and observed allocation/use**.

The query-grant chart and the stage table show these parts in reading order:

- **(1)** **Granted** (blue) rises to **480.9 MiB** between 11:13 and 11:17 LT (04:13–04:17 UTC). **Used** (pink) rises to **288.6 MiB**.

- **(2)** The gap is memory that SQL **reserved for a query** but the query did not need at that moment.

- **(3)** The table by stage: **idle**, **query-grants**, **recovery**. Notice that committed memory and cache stay about the same in every stage.

> **Say this:** "When a query needs memory to sort or join data, SQL **grants** it a workspace first. Here SQL granted about 481 megabytes and the query really used about 289. And after the query finished, the grants went back to zero **but the cache stayed**. That is normal caching – not a memory leak."

| **Term** | **Plain meaning** | **Do not say** |
|---|---|---|
| MaxMemoryMB (ceiling) | The maximum memory SQL is allowed to use for its main memory manager. | "SQL has reserved this memory." |
| Committed (TotalMemoryMB) | Memory the SQL memory manager currently holds. | "This is all Windows memory." |
| Free inside SQL (FreeMemoryMB) | Memory SQL holds but is not using right now. | "Free memory of the server." |
| Cache (CacheMemoryMB) | Data pages kept in memory to make queries faster. | "Cache plus committed is the total." Cache is a **part of** committed (Free + Cache + Other = Committed, see section 3.5 of the [chart-reading guide](03-reading-charts-cpu-memory-storage.md)). |
| Granted / Used | Query workspace reserved / really used right now. | "All SQL memory." |
| Process (ProcessMB) | What the SQL Server program occupies in Windows. | "Same as committed." |

> **Good to know:** This lab shows Arc-native licensing, inventory and best-practice assessment **together with** a plain-language memory explanation, in the same place as the host and storage data. It does not cover SQL waits, blocking chains or query text (see the next box).

> **Be honest:** "We **do not** collect SQL query text, blocking chains or wait statistics in this lab. We show memory, capacity and best-practice evidence."

## 5.6 The same facts from PowerShell (optional)

> **Where to run it:** **Operator PC → Windows PowerShell**. Read-only. Use the variables from Act 0.

**List the databases that Azure Arc knows**

```powershell
$SqlArcId = "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.AzureArcData/SqlServerInstances/SQL2019-GUEST"
az rest --subscription $SUB --method get --url "https://management.azure.com$SqlArcId/databases?api-version=2026-01-01" `
  --query "value[].{Name:name,Properties:properties}" -o json
```

> **What you should see:** A JSON list with seven databases and their properties (state, size, recovery mode).
