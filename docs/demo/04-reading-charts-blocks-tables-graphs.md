# Reading the charts: coloured blocks, tables, graphs, traps and AI answers

This file covers the dashboard elements that carry a verdict rather than a curve: the tiles and the one-minute status strip with their colour dictionary and rules, the hypothesis and freshness tables, the alert table with the relationship graph, the seven traps to avoid when you present, and the six-question check for an AI answer. Use it whenever a dashboard shows a word or a colour instead of a number, and before you present anything that an AI assistant wrote. Times are written in UTC first, with local time (LT, UTC+7) in brackets because the dashboards show the time zone of the browser, which was UTC+7 in this lab.

## 3.9 Coloured blocks and tiles

The example is a Warning with Adequate confidence: the tiles and the status strip of Command Center V2 for `WIN2022-GUEST`, for the recorded window 07:30–08:30 UTC (14:30–15:30 LT). The parts are:

1. The **time range**: one recorded hour, 07:30–08:30 UTC (14:30–15:30 LT) – the same afternoon (LT) as the real alert of Act 6.
2. **Tiles:** the two tiles "OPERATIONAL ATTENTION" ("Attention **Warning**") and "EVIDENCE CONFIDENCE" ("Confidence **Adequate** – minimum signal coverage **100%**"); in V3 Core they are called "WINDOW ATTENTION" and "SIGNAL CONFIDENCE". Two different questions, two different tiles.
3. The **status strip** (the panel "sampled-minute timeline" on page 03): each small block is **one minute**. The rows are CpuState, RamState and SqlGrantState. The CpuState row has **15 orange blocks** from 07:45 to 08:00 UTC (14:45 to 15:00 LT); everything else is blue or grey.
4. The **chronology table**: first symptom **14:45:00 LT** (07:45:00 UTC), duration **15.0** minutes, and the link **Zoom episode**.

### How to read these tiles and blocks, step by step

- **Check the time range** (item 1). Is it the period you mean?

- **Read Attention** (left tile). It answers: did the rules see anything wrong? The words are **Critical**, **Warning**, **Unknown** or **No observed breach**.

- **Read Confidence** (right tile). It answers: is the data complete enough to trust the answer? The words are **Adequate** or **Insufficient**. The percentage is the **lowest coverage** of any evaluated signal: the share of minutes that have data.

- **Look at the strip.** Find the orange blocks, **count them** and read the clock under them: 15 blocks = 15 minutes, from 07:45 to 08:00 UTC (14:45 to 15:00 LT).

- **Compare the rows.** CPU was busy; RAM stayed blue the whole hour; the SQL row is grey because this is not the SQL guest.

- **Read the chronology table** for the start time and the duration. Click **Zoom episode** to look closer (Act 11).

### The colour dictionary

The colour comes from the **state word**, not from a number. Hover over a block to read its state and time.

| **Colour** | **Words you see** | **Meaning** | **Example** |
|---|---|---|---|
| **Blue** | Observed · Adequate · No observed breach · Fresh | Data is there and nothing crossed the rule. | A blue CpuState block: that minute's average CPU was **below 80%**. |
| **Orange** | Breach · Warning · Insufficient · Stale | A rule was crossed (Breach, Warning), or the data is incomplete (Insufficient) or old (Stale). | The 15 orange blocks: CPU average **80% or more** in each of those minutes. |
| **Dark orange** | Unknown | **No data for that minute.** Never means "healthy". | A machine that is switched off or still starting. |
| **Red** | Critical · Missing | A critical rule was crossed, or a required stream is missing. | SQL pending grants above 0 for three minutes (not in this hour). |
| **Grey** | NotApplicable · NotCollected | The row does not apply to this machine, or the signal is not collected. | SqlGrantState for a machine that is not the SQL guest. |
| **Green** | FRESH | In the Cockpit freshness tables: the machine reported recently. | Six green FRESH cells. |

> **If something goes wrong:** Ignore the small legend under the strip ("< 20, 20+, 50+, 80+"). It is a Grafana default for numbers; it does **not** describe these states. Orange and dark orange look alike on a projector – **hover** to read the word. Example: hover over the block at 14:51 LT (07:51 UTC) and the box says `<INCIDENT_DATE> 14:51:00 · CpuState Breach · RamState Observed · SqlGrantState NotApplicable`.

### The rules behind the words

| **Word** | **Rule (demo advisory rules – not a business SLA and not an Azure alert)** |
|---|---|
| **Warning** | OS **CPU** average **80% or more**, or **RAM** average **85% or more**, in **three consecutive complete minutes**. |
| **Critical** | SQL **pending grants** above 0 in three consecutive complete minutes (SQL guest only). |
| **Adequate** | For every evaluated signal: at least 3 minutes in the window, **at least 90%** of the minutes have data, the **longest gap is 2 minutes or less**, and the last sample is **no older than 5 minutes** at the end of the window. |
| **Insufficient / Unknown** | At least one evaluated signal fails the Adequate rule. **Unknown** is shown when nothing was seen and the data is incomplete. |

### Four combinations

| **Attention** | **Confidence** | **What it means** | **What you can say** |
|---|---|---|---|
| **Warning** | **Adequate** | The rules saw a sustained problem and the data is complete. | "We saw it, and we can trust what we saw." (this demo hour) |
| **No observed breach** | **Adequate** | Nothing crossed the rules in the signals we evaluate (CPU, RAM and, for SQL, pending grants), and the data is complete. | "Nothing found in these signals." This is **not** a statement about everything. |
| **Warning** | **Insufficient** | Something was seen, but minutes are missing. | "Check the coverage before you conclude." |
| **Unknown** | **Insufficient** | Too many minutes are missing to say anything. | "We do not know." Zoom to a period with data. |

> **Beginner tip:** **When can "Insufficient" appear?** Only when minutes are **really missing** – for example when a lab machine was switched off or was still starting. It never means that Azure Monitor cannot collect data: while a machine runs, every minute arrives. Example from the recorded data: the lab was powered off overnight, so the hour 00:00–01:00 UTC (07:00–08:00 LT) on the day after `<INCIDENT_DATE>` has a 21-minute gap at the start and the dashboards show "Warning" with "Insufficient" (65%). The dashboard refuses to claim more than it knows. For the demo use the recorded incident hour 07:30–08:30 UTC (14:30–15:30 LT) on `<INCIDENT_DATE>` and set it by hand as described in 3.0.5.

## 3.10 Tables with coloured cells: freshness and hypotheses

The example is a Warning with Adequate confidence: the hypothesis table of Command Center V3 Core for `WIN2022-GUEST`, for the recorded window 07:30–08:30 UTC (14:30–15:30 LT). The parts are:

1. The **time range** and the machine (**WIN2022-GUEST**).
2. The two **tiles**: Attention **Warning**, Confidence **Adequate**, coverage **100%**.
3. The **hypothesis table**. Scroll it to the right to see the columns Missing and NextCheck. Scroll down to see all six rows.

### How to read the table, step by step

- **Read the two tiles first.** They are the summary (see 3.9).

- **Read the Hypothesis column.** Each row is a **possible explanation to check**. It is **not** a conclusion.

- **Read EvidenceState and Confidence** of the row: what does the data say, and how complete is it?

- **Read Supporting, Contradicting and Missing.** What fits? What does not fit? What do we still not know?

- **Scroll right to NextCheck.** It is a safe, read-only next step for a person.

| **Column** | **What it tells you** |
|---|---|
| **Hypothesis** | A possible explanation to check (for example "Guest CPU saturation"). It is **not** a conclusion. |
| **EvidenceState** | For example "Supporting sampled signal", "MISSING sufficient evidence" or "NotCollected" (the signal is not collected, such as application availability). |
| **Confidence** | "Adequate sampled metric ONLY" means the data is complete – **but** a sampled metric alone cannot prove a cause (the word ONLY is the reminder). "Insufficient" means gaps. "NotCollected" means there is nothing to judge. It is **per signal**, not for the whole system. |
| **Supporting / Contradicting / Missing** | What fits, what does not fit and what we would still need to know. "None: absence is not contradiction" means not seeing a signal is not proof that it is fine. |
| **NextCheck** (scroll to the right) | A safe, read-only next step for the engineer. |

### What the six rows say for this hour

| **Hypothesis** | **EvidenceState · Confidence** | **Plain meaning** |
|---|---|---|
| Application availability | NotCollected · NotCollected | We do not measure application response in this lab, so there is nothing to judge. |
| Guest CPU saturation | Supporting sampled signal · Adequate sampled metric ONLY | CPU stayed at or above 80% for **15 consecutive complete minutes** and the data is complete. A CPU number alone does not say why. |
| Nested-host contention | Supporting sampled signal · Adequate sampled metric ONLY | The host CPU was also high for **14 sampled minutes**: **pressure**, but "NOT proven contention". |
| OS memory pressure | No sustained aggregate signal with adequate coverage · Adequate sampled metric ONLY | RAM stayed below its rule and the data is complete. This does not rule out one process using a lot of memory. |
| SQL workspace pressure | NotApplicable · NotApplicable | `WIN2022-GUEST` is not the SQL guest. |
| Storage pressure | Unqualified health threshold – inspect measured context · Context only | We have no defined "good or bad" level for storage. Look at the latency and IOPS charts as **context**. |

**Freshness tables** (green cells) work the same way: **FRESH** is green; a stale or missing stream is **never** shown green. In the shift e-mail the same words appear: "FRESH", "insufficient evidence".

> **Beginner tip:** If a table shows **Insufficient** for a signal, read 3.9 ("When can Insufficient appear?"): it means minutes are missing, and the cure is to look at a period that has data.

## 3.11 The relationship graph and the alert table

The example is a native alert table, a relationship graph and the Arc inventory table. The parts are:

1. **Alert table:** Rule, Severity (Sev2 = warning; Sev1 = error, used here for the "critical" rules), Monitor condition (Fired or **Resolved**), Fired at, Resolved at, Computer. "Unattributed" means the alert does not name one exact machine.
2. **Relationship graph:** circles are machines. A line from the host to each guest means "**configured** to run on this host". It is **not** discovered live and not a history of moves.
3. **Inventory table:** current status. It is a snapshot of now, not of the incident time.

**Alert severities in Azure:** Sev0 critical, **Sev1 error**, **Sev2 warning**, Sev3 informational, Sev4 verbose. In this lab: "-high" rules are Sev2, "-critical" rules are Sev1.

## 3.12 Seven traps – check yourself before you speak

| **Trap** | **Correct habit** |
|---|---|
| A line stops or has a gap and you say "zero". | A gap means **no data**. Say "no data for this period". |
| You add up lines that overlap (storage layers, aliases, committed plus cache). | They count the same thing twice. Compare them. The **only** memory sum that is right is a **part added to its own whole**: Free + Cache + Other = Committed (3.5). |
| You say a recorded chart is happening now. | Always say **Recorded** and show the time range. |
| You treat "0 alerts returned" as "healthy". | Say: "no current alerts were returned". Check freshness and confidence. |
| You use a threshold from another platform on a Hyper-V number. | Different measures. Compare the **idea**, not the number. |
| You compare the **height** of two charts. | Every chart has its **own vertical scale**. Read the numbers on the axis. The same colour means a different thing in every chart. Read each legend. |
| You read a **dark orange** or **grey** block as "fine". | Dark orange is **no data**; grey is **not applicable**. Only **blue** is "data present, nothing found" (3.9). |

## 3.13 How to read an AI answer

In Act 8B an AI helper answers in plain English. An AI answer is a **first draft from a very fast assistant**. It is often right and sometimes wrong, and it sounds confident in both cases. Use this **six-question check** every time. It takes about one minute.

| **#** | **Question** | **Example from testing this demo** |
|---|---|---|
| 1 | **Did it answer what I asked – for the right place and the right time?** | We wrote "this resource group". Copilot **ignored it** and asked about the whole subscription. We named the resource group, and the query then had a `resourceGroup` filter. |
| 2 | **Can I see the query or the steps?** | Copilot printed the Resource Graph and KQL queries. The Observability Agent listed every tool call and query. If an answer has **no query and no steps**, treat it as an opinion. |
| 3 | **Does the table, counter or field it used really exist? Does it return data?** | Copilot chose the counter `Processor / % Processor Time`. The query ran **without error** and returned **no results**. A discovery query showed that the host's CPU counters are called **Hyper-V Hypervisor Logical Processor**. |
| 4 | **Do the numbers match an independent source?** | The corrected query gave 94.7, 97.7 and 88.0 percent – the same plateau as the Workbook. The agent's ingestion table matched our command-line check **exactly**. |
| 5 | **What did the AI say it could not do?** | "I couldn't break ingestion down to emitting resources." "The upstream initiator remains unknown." "These are the first 5 results." A good answer **admits its limits**. |
| 6 | **What happens if I follow its advice?** | Nothing changes by itself. Buttons such as **Create Issue** write to Azure and are **never clicked in a demo**. |

| **If you see this in an AI answer** | **Do this** |
|---|---|
| "No results found" with no error | It is **not zero**. Ask the AI to list what exists (a discovery query), then choose the right name. |
| "These are the first 5 results" | The chat shows a preview. Click **Run** to see all rows. |
| Chart axis shows 14:45, the text says 07:45 UTC | Same moment in **two time zones**. LT = UTC + 7. |
| A generic sentence that does not fit (for example "request failures" in a CPU alert) | It is a **stock phrase**. Read the rest critically. |
| A summary that says "no other alerts" but you know there were some | Ask a follow-up question. In testing, one follow-up question added seven missing alert rules. |
| A reply in an unexpected language | Add "**Answer in English.**" to the request. |
