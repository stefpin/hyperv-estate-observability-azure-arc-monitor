# Reading the charts: CPU, memory and storage

This file shows how to read the charts that carry the technical story of the demo: a single line (host CPU), several lines (scheduling wait of every guest), a ceiling against real use (SQL memory, with a ledger you can check with a query), two lines with a gap (granted versus used), latency together with IOPS (storage) and bars (today's level for every machine). Each section describes a real recorded example (a recorded lab result), so you can read the same chart on the screen of the lab, and ends with the habits and mistakes to watch for. Use it with the five-step method of section 3.1. Times are written in UTC first, with local time (LT, UTC+7) in brackets because the dashboards show the time zone of the browser, which was UTC+7 in this lab.

## 3.3 A single line: the host CPU

The example is one line, the host CPU, during the recorded test. The chart has three things to read:

1. **Title and range:** "Host hypervisor processor utilization (%)", recorded window 04:15–04:50 UTC (11:15–11:50 LT). A recorded interval.
2. **The change:** the line jumps from about 14% to about 97% and stays there – a **plateau**.
3. **The recovery:** the line falls back to below 20%.

**How to read it.** The left part is the **baseline** (the normal level when nothing special happens). The plateau is the period when the load ran. The fall is the **recovery**. The length of the plateau (about 15 minutes) matches the 900-second test. A line that never comes back would be a warning sign.

**Common mistakes.** (a) Reading the plateau as "an outage": it only says the host was busy. (b) Comparing it with a different time range. (c) Forgetting that this host has **8 logical processors**: 97% means all eight were nearly fully used.

## 3.4 Several lines: who is affected?

The example is the scheduling wait of the five guests: several lines and a table. The parts are:

1. **Legend:** one colour per guest.
2. **The plateau (during the test):** WIN2019 and WIN2022 wait most – around 800K ns. WIN2025 (teal) waits less, around 300–450K ns.
3. **Near-zero lines:** the SQL and RHEL guests stay almost flat, before, during and after.
4. **The table:** Mean, P95 and Peak wait of every guest, in nanoseconds.

**How to read it.** The **height** shows how much a guest waited. When you see many lines, find the **highest** ones first, then ask "was it busy at that time too?". Here the busy Windows guests waited the most, while the light guests did not. This is exactly what the test was designed to show.

**The numbers table.** Mean is the average, P95 means "95 out of 100 samples were lower than this" (a good way to describe the "bad but not extreme" level) and Peak is the highest single sample. A big gap between Mean and Peak means the wait was **spiky**.

**Common mistakes.** (a) Reading 800K as 800 – it is 800 thousand nanoseconds. (b) Saying "the Linux guest is the victim with highest wait" – in this test it is not. (c) Comparing nanoseconds with a percentage.

## 3.5 A ceiling and what is really used: SQL memory

SQL memory is shown in **three charts** that sit one below the other in the Workbook (the section that starts with the heading "SQL memory: allocated is not the same as executing-query use"): **chart 1** "Configured ceiling, SQL-manager committed and process footprint (MiB)", **chart 2** "SQL-manager free, database cache and other/internal memory (MiB)" and **chart 3** "Query workspace: peak granted and paired actual-use snapshot per time bucket (MiB)". They describe the **same memory from three angles**. This section shows how the three fit together – with formulas you can check yourself.

The example is the first recorded query test (**run 1**), shown for the recorded window 04:08–04:25 UTC (11:08–11:25 LT). The three charts share the same time axis, so the same minutes sit directly above each other. What you see:

1. **Chart 1 – the ceiling** (MaxMemoryMB, about 9,829 MiB): the flat line at the top. It is a **setting**, not a measurement.
2. **Chart 1 – committed and process** (CommittedMB and ProcessMB, about 1,100–1,200 MiB): the two flat lines near the bottom. This is the memory SQL really holds. In this run they **do not move**.
3. **Chart 2 – FreeMB:** the empty space inside SQL's memory. It sinks from about 330 to about 44 MiB between 04:12 and 04:17 UTC (11:12 and 11:17 LT) and then recovers.
4. **Chart 2 – OtherInternalMB:** rises from about 455 to about 744 MiB in the same minutes. This is where the query's workspace is counted. CacheMB stays flat at about 350 MiB.
5. **Chart 3 – GrantedMB and UsedMB:** both rise in the same minutes (peak 480.9 and 288.6 MiB).

### How to read the three charts together

Read them from the **bottom up: chart 3, then 2, then 1**. Each chart answers one question.

| **Order** | **Chart** | **Question it answers** | **Answer in this example** |
|---|---|---|---|
| 1st | **Chart 3** – grants | Is a query using workspace memory? | Yes. Granted **480.9** MiB, used **288.6** MiB, from about 04:13 to 04:16 UTC (11:13 to 11:16 LT). |
| 2nd | **Chart 2** – free, cache, other | Where did that memory come from? | **Free** fell by about 287 MiB and **OtherInternal** rose by about 289 MiB – almost the same amount as the **Used** workspace. |
| 3rd | **Chart 1** – ceiling, committed, process | Did SQL have to grow? How far is it from its ceiling? | No. Committed and process moved by only about 3 MiB. The ceiling is more than 8,000 MiB away. |

### The memory ledger: formulas that tie the charts together

These relations come from the way SQL Server counts its memory. We checked every one against the recorded data. The numbers are from the sample at 04:14:23 UTC (11:14:23 LT) of run 1, in the middle of the query. All values are in **MiB**.

| **Formula** | **In plain words** | **Check with the numbers** |
|---|---|---|
| **Committed = Free + Cache + OtherInternal** | The memory SQL holds is exactly the sum of its three zones: empty space, cached data pages, and everything else (working memory, plans, locks, query workspace). This is the **one "add up" rule** you need. | 1,136.4 = 43.5 + 348.7 + 744.3 (the sum is 1,136.5; rounding) |
| **NonFreeCommitted = Committed - Free**, which equals **Cache + OtherInternal** | The part of the committed memory that is **not empty**. It is **not** "memory used by queries". | 1,093.0 = 348.7 + 744.3 |
| **Process - Committed** is about **40 to 75** | Memory the SQL program holds **outside** the managed zones (for example thread stacks and program files). The ceiling does not limit it. | 1,207.5 - 1,136.4 = 71.1 |
| **Used ≤ Granted**; **Granted - Used** = unused grant | A query's workspace is reserved (granted) before it runs. The part not yet used is "reserved but unused". SQL's own counter **Reserved Server Memory** reports the same number. | 480.9 - 288.6 = **192.3** (the counter shows 192.3) |
| **Headroom = MaxMemory - Committed** | How far SQL is from its ceiling. | 9,829 - 1,136 = 8,693, that is **88%** of the ceiling still free |
| During a query, **OtherInternal rises by about Used** | The workspace in use is counted inside OtherInternal. This is a **pattern seen in both recorded runs**, not an exact law. | +289 (run 1) and +295 (run 2), against Used 288.6 |

### The same query, two different patterns

The same test query (it used **288.6 MiB** of workspace both times) was recorded in two runs on different days. The ledger held both times, but **chart 1 looked different**.

| **MiB** | **Run 1 before** | **Run 1 during** | **Run 2 before** | **Run 2 during** |
|---|---|---|---|---|
| **Free** | 330.9 | 43.5 | 15.2 | 8.5 |
| **Cache** | 347.3 | 348.7 | 332.1 | 332.1 |
| **OtherInternal** | 455.1 | 744.3 | 554.4 | 849.8 |
| **Committed** | 1,133.3 | 1,136.4 | 901.6 | 1,190.4 |
| **Process** | 1,204.3 | 1,207.5 | 964.4 | 1,253.5 |
| **Granted / Used** | 0 / 0 | 480.9 / 288.6 | 0 / 0 | 489.9 / 288.6 |

**Run 1:** SQL already held plenty of empty space (Free about 331 MiB). The query took its workspace from that space: **Free went down, OtherInternal went up, and Committed and Process hardly moved** – chart 1 stays flat. **Run 2:** the empty space was almost gone (Free about 15 MiB), so SQL had to **ask Windows for more memory**: Committed and Process **stepped up by about 289 MiB** and stayed up. Both are normal SQL behaviour, and the numbers fit this explanation.

In run 2, shown for the recorded window 04:08–04:22 UTC (11:08–11:22 LT), chart 1 rises. What you see:

1. **Chart 1 – the ceiling** is flat, as before.
2. **Chart 1 – committed and process** **step up** at about 04:13–04:14 UTC (11:13–11:14 LT), committed from about 902 to about 1,190 MiB, and **stay up**.
3. **Chart 2 – FreeMB** was already tiny (about 15 MiB). **After** the query it rises to about 297 MiB: memory that SQL kept and now has free again.
4. **Chart 2 – OtherInternalMB** goes from about 554 to about 850 MiB and back to about 561 MiB.
5. **Chart 3 – grants** peak at 489.9 and 288.6 MiB.

> **Beginner tip:** **Chart 1 rising or staying flat during a query tells you nothing about the size of the query.** Look at chart 3 (is there a grant?) and chart 2 (where did the memory come from?). After the query, committed memory **stays high** and Free refills. SQL keeps what it has grown to so it can reuse it – this is not a leak.

### Cautions

- **Add only parts to their own whole.** Free + Cache + OtherInternal = Committed is correct. Committed + Cache, Granted + Used or Process + Committed are **wrong**: they count the same memory twice. The note under the Workbook heading ("These categories overlap: do not sum them") warns about exactly this.

- **Charts 1 and 2 are averages per time bucket. Chart 3 is the peak grant in the bucket together with its paired Used value.** Compare them in the same bucket and allow a few MiB of difference.

- **"MB" in the field names means MiB.** The values are kilobytes divided by 1,024.

- **Colours change from chart to chart.** Blue is MaxMemoryMB in chart 1, FreeMB in chart 2 and GrantedMB in chart 3. Read each legend.

- **OsAvailableMB and PhysicalMB are Windows values.** They are **not** part of this ledger. Use the chart "SQL guest OS headroom (MiB) and grant-pressure count" for them.

### Check the ledger yourself (optional)

> **Where to run it:** **Azure Portal** → Log Analytics workspace `law-arc-monitor-lab` → **Logs**, in **KQL mode**. The times in the query are **UTC** (LT = UTC + 7). The query only reads.

Check the ledger on the first recorded test. Replace `<INCIDENT_DATE>` with the date of the recorded test in the form `YYYY-MM-DD` before you run the query.

```kql
HvSqlMemory_CL
| where TimeGenerated between (datetime(<INCIDENT_DATE>T04:10:00Z) .. datetime(<INCIDENT_DATE>T04:26:00Z))
| extend LedgerGapMiB = round(TotalMemoryMB - (FreeMemoryMB + CacheMemoryMB + StolenMemoryMB), 2),
         ProcessExtraMiB = round(ProcessMB - TotalMemoryMB, 1),
         UnusedGrantMiB = round(GrantAllocatedMB - GrantUsedMB, 1)
| project TimeGenerated, Stage, TotalMemoryMB, FreeMemoryMB, CacheMemoryMB, StolenMemoryMB,
          LedgerGapMiB, ProcessExtraMiB, GrantAllocatedMB, GrantUsedMB, UnusedGrantMiB
| order by TimeGenerated asc
```

The three new columns test three rows of the ledger table above: `LedgerGapMiB` tests the first formula, `ProcessExtraMiB` tests "Process - Committed" and `UnusedGrantMiB` tests "Granted - Used".

> **What you should see:** **64 rows.** **LedgerGapMiB** stays within **0.01** (it is 0 in almost every row). **ProcessExtraMiB** is about **68–71**. **UnusedGrantMiB** is **192.3** in the middle of the query (rows from about 04:13:53 to 04:15:54 UTC). Across all 32,000+ recorded samples the largest ledger gap was **1.7 MiB**, during a cache warm-up.

> **Say this:** "Think of SQL's memory as a **rented warehouse**. The ceiling is the biggest warehouse the lease allows – nearly ten gigabytes. SQL rents only what it needs – here about one gigabyte. Inside the rented space there are three zones: empty floor, shelves with cached data, and a working area. The three zones always add up to the rented space. When a query arrives it takes a workbench from the empty floor: you see the empty floor shrink and the working area grow. If the floor is already full, SQL rents a little more space. Both are normal."

## 3.6 Two lines with a gap: granted versus used

The example is two lines that rise together, with a gap between them:

1. **Granted** (upper line): memory reserved for a query – 480.9 MiB.
2. **Used** (lower line): memory really in use – 288.6 MiB.
3. The stage table (idle, query-grants, recovery): Granted and Used are 0.0 before and after, while Committed (about 1,134 MiB) and Cache (about 350 MiB) stay almost the same.

**How to read it.** The **gap** between the lines is memory reserved but not used at that moment – not a problem, but useful for tuning. Here it is 480.9 - 288.6 = **192.3 MiB**, the "unused grant" of the ledger in 3.5. The lines return to zero because the query ended. The cache **stays** because SQL keeps useful data pages in memory: this is a feature.

## 3.7 Latency together with IOPS: storage

The example is latency (top chart) and IOPS (lower chart), which must be read together:

1. The pink line is the SQL data drive E:. Its **latency** (top) rises from about 0.5 ms to about 1.9 ms.
2. The legend has one line per volume.
3. Below it, the **IOPS** chart (800 operations per second at the same time).

**How to read it.** Step 1: find the time when IOPS rise (the disk is busy). Step 2: look at the latency at that time. If latency rises when IOPS rise, the disk is **under load**. If a disk has **no** IOPS, its latency is **not** a measurement. That is why empty or N/A is not zero.

**Look at the end of the pink line.** It drops to 0 when the test stops. That does **not** mean the disk became "infinitely fast": no I/O happened, so there was nothing to measure. Also note the honest conclusion of this scene: 800 IOPS is far below the disk's 2,300 IOPS baseline, so the disk was **not saturated**.

## 3.8 Bars: today's level for every machine

The example is bars for the P95 sampled dispatch wait, with a table and a time chart:

1. One **bar** per guest, longest bar = longest wait. The value is shown on the right (µs).
2. The **table** gives mean, P95 and peak for each guest, shown in **µs** (microseconds).
3. A **time chart** whose legend shows **Last** (latest value) and **Max** (highest value in the range).

**How to read it.** Bars are for **comparison**: which machine is highest right now? Compare the bars with each other, not with a threshold of another product. In quiet time they are all short and similar (here about 19–25 µs). The field name still says "Ns" (nanoseconds); Grafana only **displays** it in friendlier units – 24,600 ns is shown as 24.6 µs.
