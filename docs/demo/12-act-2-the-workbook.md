# Act 2. One report to see it all – the Azure Workbook

Act 2 covers minutes 10–18 of the storyline (about 8 minutes). Its goal is to introduce the Workbook as the **single technical report**, show how to move around it, and teach the time-range picker that you will use in the next acts. Before you start, the Workbook `Hyper-V and SQL Estate Report` (definition version 2.2, see [setup chapter 18](../setup/18-workbook.md)) must be saved in the lab resource group and be reachable from the Log Analytics workspace `law-arc-monitor-lab`. You open it in **Read** mode and never edit it during a session.

> **Say this:** "Instead of ten different tools, we built one report: 31 charts and tables over the same data. You will see everything – CPU, storage, SQL, changes, updates – on one scrolling page."

## 2.1 Open the Workbook

> **Where to run it:** **Azure Portal**.

> **Do this:** In the top search box type `law-arc-monitor-lab`. Click the **Log Analytics workspace** result. In the left menu click **Workbooks**. Click **Hyper-V and SQL Estate Report**. (If you see several workbooks, choose the one saved in the lab resource group.) Keep it in **Read mode**. Do not click **Edit**.

The Workbook opens on the host CPU chart and shows these parts in reading order:

- **(1)** Header: the report title "Hyper-V and SQL estate report - v2.2" and a short note that this is a demonstration lab, not a production architecture.

- **(2)** **Time range** menu (here "Last 4 hours"). All charts follow this setting.

- **(3)** Toolbar with **Edit** and **Save**. Stay away from them: this is the live report.

- **(4)** First chart: **Host hypervisor processor utilization (%)**. This is a live chart.

## 2.2 What is on the page – scroll order

| **#** | **Section** | **What it tells you** | **Used in** |
|---|---|---|---|
| 1 | Host hypervisor CPU and **per-guest scheduling wait** | How busy the host is and who waits for a processor. | Act 3 |
| 2 | Guest CPU and **WIN-CLUSTER-01** (CPU, memory, wait) | Each guest and the logical Windows group. | Act 3 |
| 3 | **SQL memory**: ceiling, committed, cache, query grants, headroom | How SQL really uses its memory. | Act 5 |
| 4 | **Storage by layer**: host disks, virtual disks (VHDX), Windows volumes, SQL counters | IOPS and latency at each layer. | Act 4 |
| 5 | **SQL database inventory** (from Azure Arc) | The seven databases. | Act 5 |
| 6 | **Arc inventory** and **heartbeat** table | Regions, tags, last seen time of every machine. | Act 1 |
| 7 | **RHEL** device IOPS/latency and device-to-mount mapping | Linux disk behaviour. | Act 4 |
| 8 | Windows and RHEL **memory** | Physical memory in use. | Act 3 |
| 9 | **Change Tracking** file change and SQL services | What changed on the SQL server. | Act 7 |
| 10 | **Update Manager** missing updates and install history | Patch status. | Act 7 |

> **Beginner tip:** Every result table in the Workbook can be exported with its **Export to Excel** menu (a small icon at the right of the table title; hover over the table to find it). The Workbook's own notes say the same.

## 2.3 Teach the time-range picker

You will use this in every Workbook act. Learn it now.

> **Do this:** Click the **Time range** pill (the blue rounded box). Choose **Last hour**, **Last 4 hours**, **Last 24 hours**, **Last 7 days** or **Custom**. For a **recorded** scene choose **Custom**, type the **Start** and **End** dates and times and click **OK**. The Portal shows the time zone of the browser (UTC+7 on the presenter PC). See "Time zones" in [About this guide](00-about-this-guide.md) for the UTC and LT conversion.

The time-range menu shows:

- **(1)** The **Time range** pill. After you choose Custom it shows your exact interval.

- **(2)** The five choices. Use **Custom** for recorded scenes.

> **If something goes wrong:** The Workbook is slow to refresh because it runs many queries. After you press **OK**, wait 10–15 seconds. If a chart looks empty or "old", wait first, then scroll away and back. Do not press the browser refresh button repeatedly.

> **Say this:** "Everything on this page follows one time range. Live data uses Last hour. For a real past event, we pick a custom time range and replay it exactly. We will always tell you which one we are using."
