# Reading cards, a worked incident and practice

The earlier files showed kinds of charts; this file shows whole dashboards. It has a reading card for every dashboard (which panel to read first, what is normal in this quiet lab and what needs attention), one worked incident that applies the whole method to four charts, a cheat sheet of "if you see ... then ..." and practice questions with answers. Use the cards next to the open dashboard during a demo, and use the cheat sheet and the practice questions to train yourself before you present. The text uses the short dashboard names (Operations Cockpit, Evidence Report, Shift Report, Command Center V1, V2 and V3 Core). Times are written in UTC first, with local time (LT, UTC+7) in brackets because the dashboards show the time zone of the browser, which was UTC+7 in this lab.

## 3.14 Reading cards: how to read each dashboard, step by step

The sections before showed **kinds of charts**. A reading card shows **one whole dashboard**: which panel to read **first**, what is **normal** in this lab, and what would **need attention**. Open the dashboard, put the card next to it and go down the table from step 1. Every card has the same four columns.

> **Beginner tip:** **How to use a card in the demo:** read step 1 aloud ("the first thing I check is ..."), show it, say what you see, then go to step 2. The audience learns the **habit** – not only the numbers. "Normal" means normal **for this quiet lab**; it is not a universal limit.

### Card 1 – The Azure Workbook (Hyper-V and SQL Estate Report, definition version 2.2)

**Question it answers:** What happened on the host, the guests, SQL memory and storage in the period I choose?

**Open it:** Azure Portal → resource group `rg-hyperv-arc-monitor-demo` → the Workbook (Act 2). **Set the Time range first** (3.0.1).

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **Time range** (top of the page) | "Last 4 hours" for live data. **Custom** for a recorded scene, for example 04:15–04:50 UTC (11:15–11:50 LT) on `<INCIDENT_DATE>` for the CPU test. | A range that does not contain the event: the charts look flat and you think nothing happened. |
| 2 | **Host hypervisor processor utilization (%)** – one line (3.3) | Quiet: a few percent up to about 25%. | A **plateau** near 100% for many minutes. In the CPU test: about 14% → about 97% for 15 minutes → below 20%. |
| 3 | **Per-guest scheduling wait (nanoseconds per dispatch, not CPU-ready %)** – five lines, and the table **Per-guest contention evidence** (3.4) | All five lines low and close together, about 20,000–50,000 ns per dispatch. | Some lines jump to hundreds of thousands of ns (about 800,000 in the test). Read the table: mean, P95, peak. |
| 4 | **Guest-reported processor utilization (%)** and the **WIN-CLUSTER-01** charts | Low and similar for the three Windows guests. | The guests are busy **at the same time** as the host plateau. |
| 5 | **Windows physical memory in use per machine (%)** and **RHEL guest-reported used memory (%)** | Steady lines well below 85%. | A line climbing towards 85–90%. |
| 6 | **SQL memory**: three charts, the stage table, OS headroom (3.5) | Committed about 1.1 GiB far below the 9.6 GiB ceiling; grants 0 / 0; pending grants 0. | Committed close to the ceiling, or **pending grants above 0**. |
| 7 | **Storage layers**: host disks, virtual disks, Windows volumes (3.7) | Latency about 2 ms or less with small IOPS. | Latency rising **together with** IOPS, or above the 20 ms warning level of the lab's alert rules. |
| 8 | **Tables**: "Reporting health - all six machines", "Arc inventory and region/cluster membership", "Live SQL database inventory (Arc ARM API)" | Six machines listed; "last seen" within a minute or two; status Connected; seven databases. | A machine with an old "last seen" time, or missing from the list. |

> **Say this:** "A good engineer reads a Workbook in the same order every time: **when** (the time range), **how busy** (CPU), **who waits** (scheduling wait), **memory**, **storage**, and finally **is everything reporting**. We will do exactly that."

### Card 2 – The Infrastructure & SQL Operations Cockpit (Grafana)

**Question it answers:** Is everything reporting, and where do I look first this shift?

**Open it:** Grafana → Operations Cockpit (its address is in the [dashboard list](../../monitoring/README.md); [Act 9](20-act-9-grafana-operations-cockpit.md)). Wait about 20 seconds for the banner and tiles.

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **Tiles** "Fresh · Stale · Missing · Expected" (the tile "ALL SIX EXPECTED - Reporting counts at interval end") | Fresh **6**, Stale **0**, Missing **0**, Expected **6**. | Stale or Missing above 0: a machine is not reporting – its other charts cannot be trusted. |
| 2 | **Reporting freshness table** (green FRESH cells) | Every row **FRESH**, last seen within about a minute, ingestion lag of seconds. | A row that is not green, an old "LastSeen", a large "AgeMinutes". |
| 3 | **HOST - Hypervisor CPU** and **HOST - Physical RAM in use** (last hour) | Low, calm lines. RAM against the 64 GiB baseline. | CPU high for many minutes. |
| 4 | Open the row **02 - CPU CONTENTION**: bars, "Contention evidence" table, mean wait over time | Five short bars of about 19–29 µs. | One or more long bars. In the recorded test the waits were more than 30 times longer. |
| 5 | Open the row **03 - SQL MEMORY & ACTIVITY** | Ceiling 9.6 GiB, committed 1.1 GiB, no grant spike, about 8 GB of Windows memory available. | Committed near the ceiling; repeated grant spikes. |
| 6 | Open the row **04 - STORAGE LAYERS** | Host disk IOPS in the tens per second; latency a few milliseconds. | Latency rising together with IOPS. |
| 7 | The two **selectors** at the top | "All" machines selected. | A selector left on one machine: panels titled SELECTED show only that machine. |

> **Say this:** "Before I scroll, the cockpit already answers the first question of every shift: do I have fresh data from all six machines? Then I open the sections one by one."

### Card 3 – The PDF & Excel Evidence Report and the Frozen shift health report (Grafana)

**Question it answers:** Can I hand this evidence to someone who was not in the room, and is it really the period I think it is?

**Open it:** Cockpit → **PDF & Excel evidence** (the link in the top row of the Cockpit opens the Evidence Report). The Frozen shift health report is saved under the fixed address `https://<GRAFANA_ENDPOINT>/d/hv-shift-health-report` by the [shift-report app](../../shift-report/README.md) each time it builds a report, and it always shows the latest report ([Act 10](21-act-10-reports-that-arrive-by-themselves.md)).

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **Time range** at the top | A **fixed** range for the shift, for example 23:00–06:55 UTC (06:00–13:55 LT). It never moves. | A moving "Last 1 hour" on a page that should be frozen. |
| 2 | **Freshness tiles** | Fresh 6, Missing 0. | Missing above 0 – say so before you show any chart. |
| 3 | **CPU** of the selected machines together with the host | Low lines for every machine. | A plateau – compare the time with the clock in the report title. |
| 4 | **Host-side P95 dispatch wait** of the five guests | Short, similar lines. | A guest far above the others. |
| 5 | **Physical memory** of Windows and RHEL | Steady lines. | A rising line. |
| 6 | Scroll down: SQL memory, query grants, Windows group IOPS, scheduling wait, storage rates, SQL activity | Same patterns as the cockpit. | Anything that differs from the e-mail of the same shift. |
| 7 | The **Download native PDF** button | A PDF with one panel per page. For the shift report: a summary plus eight chart pages, and an Excel workbook with 20 sheets (Act 10). | A PDF labelled 1970 or with an unexpected interval – do not accept it (Act 10). |

> **Say this:** "Each shift report is built from one frozen set of evidence, so the numbers can be checked later. The PDF charts, the Excel workbook and the Grafana page all come from the same frozen data."

> **Beginner tip:** The Evidence Report is the live, filterable page. The Frozen shift health report has only the eight chart pages (no tiles and no selectors) and is rewritten for every report, so open it right after the report you want to check.

### Card 4 – The shift-report e-mail

**Question it answers:** What was the state of the estate during the last shift, in two minutes?

**Open it:** The mailbox that receives the shift report, three times a day (23:00, 07:00 and 15:00 UTC = 06:00, 14:00 and 22:00 LT). The layout of the e-mail is described in Act 10.

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **Subject line:** "Hyper-V Estate - Shift Report - `<DD Mon YYYY>` - Cutoff `<HH:mm>` LT" (rehearsals add " [TEST]") | The cutoff is **5 minutes before** the shift boundary: 05:55, 13:55 or 21:55 LT (22:55, 06:55 or 14:55 UTC). | A cutoff much older than that – the data is stale. |
| 2 | The **banner** and the line "Required signals: 14/14 fresh; expected machines: 6/6 fresh" | "MONITORED SIGNALS NORMAL", 14/14, 6/6. | Fewer than 14 or 6, or the words "insufficient evidence". Read the lines below the banner first. |
| 3 | "No evaluated condition exceeded its threshold" and "Evidence gaps: 0 ..." | No threshold exceeded; 0 gaps. | A condition listed, or gaps above 0. |
| 4 | **Estate health table** (freshness, average CPU, peak 5-minute CPU, latest RAM) | Every machine FRESH; CPU of a few percent; the host RAM higher than the guests. | A machine that is not FRESH, or a high "peak 5m CPU". |
| 5 | **SQL memory table** (cap, committed, process, cache, OS headroom, grants) | Cap 9,829 MiB; committed about 1.2 GiB; grants 0.0 / 0.0. | Grants above 0 or a small OS headroom. |
| 6 | **CPU contention** and **storage** tables, **open items** | Short waits; no open items. | A guest with a long P95 wait. |
| 7 | The **three attachments** | Summary and chart PDF, Excel workbook and workbook-content PDF. | An attachment missing. |

> **Beginner tip:** The e-mail's SQL table says "SQL cache (overlaps)" and "Values overlap: do not add". Read it with the **memory ledger** of 3.5: cache is a **part of** the committed memory – do not add it on top.

> **Say this:** "A busy reader does not have to open a dashboard. The e-mail starts with the answer – fresh and normal, or not – and then shows the tables."

### Card 5 – Command Center V1: Estate → Workload → Incident

**Question it answers:** Which machine needs a look, what does its detail say, and how do I form a hypothesis?

**Open it:** Grafana V1 (its address is in the [dashboard list](../../monitoring/README.md); [Act 11.2](22-act-11-command-center-v1-v2-v3-core.md)).

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **01 Estate Overview** tiles | **14** fresh streams, 0 stale, 0 missing; 6 expected machines (5 guests, 1 host). | Stale or missing above 0. |
| 2 | The **six-machine table** | Every machine has a recent heartbeat and latest values. | A machine with an old heartbeat or a high CPU. |
| 3 | Click **Deep dive** → **02 Workload** | OS CPU low next to the fixed host; low per-vCPU run time. | A guest at 100% while the host line is also high. |
| 4 | Click **Investigate** → **03 Incident**: "Form a hypothesis" | A table of lenses (dispatch wait, OS CPU, RAM) with value, samples and **Next check**. | A lens with a high value – the **Next check** says what a person should do. |

> **Say this:** "V1 teaches the path: look at the estate, pick a machine, then form a hypothesis. It guides – it does not diagnose."

### Card 6 – Command Center V2: three separate questions

**Question it answers:** Is something wrong? How sure are we? What does Azure itself say?

**Open it:** Grafana V2 (its address is in the [dashboard list](../../monitoring/README.md); [Act 11.3](22-act-11-command-center-v1-v2-v3-core.md)).

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **Window guard** tile | **EVALUABLE WINDOW** (a range between 1 minute and 4 hours). | "NoEvaluableWindow": the range is too long or too short. Fix the range. |
| 2 | The **three tiles**: Attention, Confidence, Native alerts | No observed breach · Adequate · alert counts by severity (an empty answer means "no evidence", **not** "healthy"). | Warning or Critical; Insufficient or Unknown (3.9). |
| 3 | Table **OPERATIONAL ATTENTION** (all six expected machines) | Each row "No observed breach" and "Adequate". | A row with Warning, or with coverage below 90%. |
| 4 | **Native alerts**, **relationship graph**, **Arc inventory** | Resolved alerts with fired and resolved times; a graph of the host and five guests ("configured, not discovery"); inventory of **now**. | An alert still **Fired**; a machine missing from the inventory. |
| 5 | **02 Workload evidence** (selected machine) | Per-vCPU run matrix low; storage layers calm; SQL grants 0. | A busy matrix, rising latency, grants above 0. |
| 6 | **03 Incident** (selected machine and time) | Tiles, strip, chronology, charts (3.9, 3.15). | Orange blocks in the strip. |

> **Say this:** "V2 separates three questions that other tools squeeze into one red or green light: what we saw, how sure we are, and what Azure itself reports."

### Card 7 – Command Center V3 Core: guided investigation

**Question it answers:** What does the evidence support, what contradicts it, what is missing, and what should a person check next?

**Open it:** Grafana V3 Core (its address is in the [dashboard list](../../monitoring/README.md); [Act 11.4](22-act-11-command-center-v1-v2-v3-core.md)).

| **#** | **Look at** | **Normal looks like (this lab)** | **Needs attention looks like** |
|---|---|---|---|
| 1 | **01 Estate attention**: tiles, "WINDOW ATTENTION" (all six expected machines), coverage of the **14** expected streams | Fresh streams **14**; every machine "No observed breach" + "Adequate". | Warning, Critical or Unknown; "Insufficient signal evidence" above 0. |
| 2 | **Native alerts** table with **Attribution** | "0 returned ... not health", or alerts marked **Unattributed** when no exact machine is named. | An alert attributed to one machine that is still Fired. |
| 3 | **02 Guided workload evidence**: pick a machine, read the **six hypotheses** | Most rows "No sustained aggregate signal" or "NotCollected" / "NotApplicable". | A row "Supporting sampled signal" with Adequate confidence (3.10). |
| 4 | **03 Incident replay**: set the machine and the time range (3.0.5) | Tiles, hypotheses, SEQUENCE, LONGEST REAL EPISODE and SAMPLED STATES all agree. | Orange blocks – then read SEQUENCE for the start and the length. |
| 5 | Click **Zoom episode** | A shorter range of about episode ± 5 minutes; the before / during / after table. | A clear step in the "during" value. |
| 6 | **Read-only handoff bookmark** and **RETURN TO LIVE** | The same machine and range in a link for a colleague. | – |

> **Say this:** "V3 gives you the evidence, the contradicting evidence, what is missing and a next check. It never claims a root cause."

## 3.15 Worked example: read one incident in four charts

This is the whole method on **one real incident**: `WIN2022-GUEST` on `<INCIDENT_DATE>`, recorded window 07:30–08:30 UTC (14:30–15:30 LT) – the afternoon (LT) of the real alert in Act 6. The page is the Command Center V2 incident view, scrolled down. Open it by setting the machine and the time range yourself (see 3.0.5) and follow along.

The page shows four charts. The parts are numbered 1 to 5 here because item 2 is the legend table of the CPU chart. What you see:

1. **CPU chart:** the guest's own CPU (green), the host's hypervisor total (blue) and the host's own Windows (yellow).
2. The **legend table** of that chart. **Max:** guest OS CPU 100.0%, host root OS 7.1%, host hypervisor total 97.9%.
3. **RAM chart:** RAM % on the left axis (green) and processor queue in threads on the **right** axis (yellow). Max: RAM 25.7%, queue 29.0 threads.
4. **Dispatch wait and run time:** two vertical axes. Wait in **ns per dispatch** on the left, CPU **%** on the right.
5. **Storage chart:** latency in ms (left axis) and queue (right axis). Short spikes only.

- **Find the biggest change.** In the CPU chart (item 1) the green line is calm, then jumps to **100%** at about **07:45 UTC (14:45 LT)**, stays there until about **08:00 UTC (15:00 LT)**, and falls back. That is a **plateau of about 15 minutes** – exactly the 15 orange blocks of 3.9.

- **Ask: is the host busy too?** The blue line rises at the same time to **97.9%**. The host's processors were nearly full. The yellow line (the host's own Windows) stays at about 7% or less, because it does not see the guests' work. Three kinds of "CPU", three stories (3.0.3).

- **Check memory (item 3).** RAM stays between about 22.5% and 26%. The queue (right axis, yellow) rises to **29 threads** during the plateau and returns to 0 – tasks were waiting for a processor, but memory is not the story.

- **Check the waiting (item 4).** Remember the two axes. In the alert investigation of Act 8B the 95th-percentile wait of the three Windows guests rose from about **17,000–34,000 ns** to between about **555,000 and 898,000 ns** in the same minutes – **more than 15 times** longer. The guests wanted the processor and had to **wait**.

- **Check storage (item 5).** Latency shows short spikes of about 2 ms or less, with no plateau. The lab's alert rules warn at **20 ms**. Storage does not match the event.

> **What you should see:** **What the evidence supports:** for 15 minutes the guest's CPU was at 100% while the host's processors were almost fully used and the guests waited much longer than usual. RAM and storage do **not** show a matching event. This points to **CPU contention on the host**. It is **sampled evidence, not a proven root cause** – the V3 hypothesis table (3.10) says the same and lists what is still missing.

> **Be honest:** "We can see **what** happened and **where** to look. We cannot see **why** the load started – that is not collected."

## 3.16 Cheat sheet: if you see … then …

| **If you see …** | **It usually means …** | **Check next** | **Do not say …** |
|---|---|---|---|
| A line at about **100% for 15 minutes** | A sustained CPU episode. | Host hypervisor total and the scheduling wait at the same time (3.15). | "An outage." |
| Guest CPU high, **host total also high**, waits high | CPU contention: the shared processors are the limit. | Which other guests were busy (WIN-CLUSTER-01 charts). | "The guest is broken." |
| Guest CPU high, **host total low** | The load is **inside** that guest. | The guest's processes (outside this demo). | "The host is overloaded." |
| SQL **committed** rises, ceiling flat | SQL grew into free space. | Headroom = ceiling - committed (3.5). | "SQL is out of memory." |
| **Granted** far above **Used** | Workspace reserved but not yet used. | **Pending grants** above 0 means real pressure. | "A memory leak." |
| **Latency** up while **IOPS** up | The disk is under load. | Both layers: virtual disk and Windows volume (3.7). | "The disk is slow" without IOPS. |
| Latency 0 or empty, **IOPS about 0** | No I/O – nothing to measure. | Another period with I/O. | "The disk is infinitely fast." |
| A **line ends** or a **gap** | No data (machine off, agent stopped, wrong range). | The freshness table; the range. | "Zero." |
| **Warning + Adequate** | A real sustained signal, complete data. | SEQUENCE for the start and length; the hypothesis table. | "Root cause found." |
| **No observed breach + Adequate** | Nothing found in CPU, RAM (and SQL grants). | The "NotMonitored" line: application, SQL waits, storage health are not evaluated. | "Everything is healthy." |
| **Insufficient** or **Unknown** | Minutes are missing. | Freshness; choose a period that has data (3.9). | "Azure Monitor cannot collect data." |

## 3.17 Practice: read it yourself

Cover the answer table with a sheet of paper. Open the recorded scene named in each question in the Workbook or in Grafana (the recorded windows are in section 1.5 of [About this guide](00-about-this-guide.md)), or re-read the section named, then answer and check. These questions take about ten minutes and make the method automatic.

| **#** | **Where to look** | **Question** |
|---|---|---|
| 1 | 3.3 – host CPU line | What was the highest level? How long was the plateau? Did the line recover? |
| 2 | 3.4 – scheduling wait | Which guests waited most? In which unit is the axis? Which two guests stayed low? |
| 3 | 3.5 – the ledger | In the sample of run 1 at 04:14:23 UTC (11:14:23 LT): Free 43.5, Cache 348.7, OtherInternal 744.3. What is Committed? What is NonFreeCommitted? How much headroom does SQL have against the 9,829 MiB ceiling? |
| 4 | 3.7 – latency and IOPS | The latency line drops to 0 when the test stops. Is the disk now extremely fast? |
| 5 | 3.9 – tiles and strip | Attention Warning, Confidence Adequate (100%), 15 orange blocks from 07:45 to 08:00 UTC (14:45 to 15:00 LT). What can you conclude? What can you **not** conclude? |
| 6 | 3.0.3 – the tooltip | At 07:53 UTC (14:53 LT): hypervisor total 97.8%, guest run time 94.4%, hypervisor run time 3.4%, host root OS 1.0%. What is 94.4 + 3.4? Which number is the host's own Windows? |
| 7 | 3.9 – colours | A strip row is dark orange for 21 minutes in a row. What does it mean, and which Confidence word do you expect? |

### Answers

| **#** | **Answer** |
|---|---|
| 1 | About **97%**. The plateau lasted about **15 minutes** (roughly 04:24 to 04:39 UTC, which is 11:24 to 11:39 LT), matching the 900-second test. Yes, it **recovered** to below 20%. |
| 2 | **WIN2019-GUEST** and **WIN2022-GUEST** waited most (about 800,000 ns), then WIN2025-GUEST-01 (about 300,000–450,000 ns). The unit is **nanoseconds** (800,000 ns = 0.8 ms). **SQL2019-GUEST** and **RHEL94-GUEST** stayed low. |
| 3 | Committed = 43.5 + 348.7 + 744.3 = **1,136.5 MiB** (the chart says 1,136.4: rounding). NonFreeCommitted = Cache + OtherInternal = **1,093.0 MiB**. Headroom = 9,829 - 1,136 = about **8,693 MiB (88%)**. |
| 4 | **No.** No I/O happened, so there was nothing to measure. Latency is only meaningful while IOPS are meaningful. |
| 5 | You **can** say: a sustained CPU episode of 15 minutes, and the data is complete, so you can trust it. You **cannot** say: that it was an outage, or what caused it – the dashboard gives sampled evidence, not a root cause. RAM stayed blue. |
| 6 | 94.4 + 3.4 = **97.8%**, the hypervisor total. The host's own Windows ("root OS") is the **1.0%**. |
| 7 | **No data** in those minutes (machine off or still starting). It is not "high" and not "healthy". Expect **Insufficient** (or Unknown). |
