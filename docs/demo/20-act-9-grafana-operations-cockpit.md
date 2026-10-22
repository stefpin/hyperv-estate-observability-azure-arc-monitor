# Act 9. The Grafana Operations Cockpit (minutes 93–101)

This is the presenter's script for Act 9 of the demo storyline. Use it to present, or rehearse, the "Infrastructure & SQL Operations Cockpit" dashboard in Azure Managed Grafana. **Goal:** show the same data in a dashboard built for **daily operations**: dark, fast to read, with clear sections and one-click report downloads.

## 9.1 Open it

> **Where to run it:** Grafana (browser). The dashboard address is `https://<GRAFANA_ENDPOINT>/d/hv-operations-cockpit`. Replace `<GRAFANA_ENDPOINT>` with the endpoint shown on the **Overview** page of your Azure Managed Grafana instance in the Azure portal. The [dashboard list](../../monitoring/README.md) shows how the four dashboard families map to Grafana instances (one instance per family, as in the reference lab, or one instance with four data sources).

> **Do this:** Open the cockpit link. If a Microsoft **Pick an account** window appears, click **your own lab account** – the same account you use to sign in to the Azure portal. **Never** click another account. Wait about 20 seconds until the banner and the tiles appear.

> **If something goes wrong:** If your dashboards are spread over several Grafana instances, each instance has its **own** sign-in. The first open of each takes about 20–30 seconds. Open them **before** the demo (Act 0).

**What you should see (top of the page):**

1. Two **selectors**: "Selected machines" and "Selected Windows members" (the labels continue with "OS metrics only" and "detail only"). They only change panels whose title starts with **SELECTED**.
2. Four **buttons**: **Download native PDF**, **PDF & Excel evidence**, **Original Azure workbook**, **Existing alert rules - unchanged**.
3. The **banner** image "Hyper-V Estate Observability; monitored with Azure Monitor". The dashboard title, "Infrastructure & SQL Operations Cockpit", is in the Grafana header.
4. The tiles of **ALL SIX EXPECTED - Reporting counts at interval end**: **Fresh 6 · Stale 0 · Missing 0 · Expected 6.** All six machines reported recently.
5. **Time range** "Last 1 hour" (displayed in the time zone of the browser, UTC+7 on the presenter PC) and **Refresh** with auto-refresh every **2 minutes**.

> **Say this:** "This is the operations cockpit. Even before I scroll, it answers the first question of every shift: do I have fresh data from all six machines? Yes – six fresh, none stale, none missing."

## 9.2 Scroll: freshness, host CPU and memory, and the five sections

> **Do this:** Scroll down with the mouse wheel. (Keep the mouse over a blank area; a chart may capture the wheel.)

**What you should see:**

1. **ALL SIX EXPECTED - Reporting freshness at interval end.** Green **FRESH** for every machine, with last-seen time, age in minutes, samples and ingestion lag.
2. **HOST - Hypervisor CPU** for the last hour (low and calm now).
3. **HOST - Physical RAM in use - Baseline 64 GiB.**
4. Five **sections** (Grafana rows), collapsed: **01 - ESTATE & CAPACITY**, **02 - CPU CONTENTION**, **03 - SQL MEMORY & ACTIVITY**, **04 - STORAGE LAYERS**, **05 - ARC, MANAGEMENT & DATA QUALITY**. Each title ends with a short subtitle. Click a title to open it. The grey text shows how many panels it holds.

## 9.3 Open the sections one by one

> **Do this:** Click **02 - CPU CONTENTION**. Look. Click the title again to close it. Then open **03 - SQL MEMORY & ACTIVITY**, then **04 - STORAGE LAYERS** the same way.

**Section 02 – CPU contention (live, last hour):**

1. **HOST-SIDE - All five guests - P95 sampled dispatch wait** per guest as bars. The unit is nanoseconds per dispatch; Grafana shows it as microseconds (µs). Quiet now: about 19–29 µs (recorded lab values).
2. The table **HOST-SIDE - All five guests - Contention evidence**: mean, P95 and peak (in nanoseconds) for each guest.
3. **HOST-SIDE - All five guests - Mean dispatch wait** over time for all guests.

> **Say this:** "Same idea as the Workbook, but now as a bar for each guest. In quiet time all five guests wait only about twenty microseconds. During the recorded test they waited up to eight hundred thousand nanoseconds – more than thirty times longer."

**Section 03 – SQL memory and activity (live):**

1. **SQL FIXED SCOPE - Ceiling, manager committed & process** (ceiling 9.6 GiB = 9,829 MiB, committed 1.1 GiB).
2. **SQL FIXED SCOPE - Manager memory components (overlap)**: free, cache and other/internal SQL memory. They are the **parts** of the committed memory (Free + Cache + Other = Committed, see section 3.5 of the [chart-reading guide](03-reading-charts-cpu-memory-storage.md)); read them next to the first chart, never stack them on top of it. The panel also draws non-free committed memory, which already contains the cache and the other/internal part, so never add all the lines.
3. **SQL FIXED SCOPE - Peak grant & paired workspace use.** A short spike shows a real query grant.
4. **SQL FIXED SCOPE - OS headroom & grant counts.** About 8 GB of Windows memory stays available (recorded lab result).

**Section 04 – Storage layers (live):**

1. **ALL LAYERS - Storage comparison - Never add layers or aliases**: a comparison table of **all layers**: host physical disk, Hyper-V virtual disks, Windows volumes. The title warns: "never add layers".
2. **LOGICAL WINDOWS GROUP - Distinct guest-volume IOPS & sampled latency** of the logical Windows group.
3. **HOST - Physical disk IOPS.** Tens of operations per second: a quiet lab.
4. **HOST - Physical disk latency - Active I/O only.** A few milliseconds; idle times are not drawn as zero.

## 9.4 The other two sections (same method)

- **01 Estate & capacity:** selected machines' CPU, Windows and Linux memory, network bytes and errors, the logical Windows group, and the three expected members with coverage.
- **05 Arc, management & data quality:** Arc inventory with regions and tags, heartbeat sample coverage in completed time buckets, **existing** Change Tracking evidence, missing updates and the recorded installation history. "No assessment initiated" is written in the title because the cockpit only **reads**.

> **Why:** The cockpit is a daily "heat and health" view, and every panel is a visible query on your own data. Nothing is a black box.

> **Be honest - say exactly this:** "The cockpit reads existing data only. It does not run SQL queries, it does not send commands to machines and it does not change alerts."
