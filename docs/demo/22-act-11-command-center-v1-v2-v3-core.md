# Act 11. Command Center V1, V2 and V3 Core – from dashboards to investigations (minutes 105–116)

This is the presenter's script for Act 11 of the demo storyline. Use it to walk through the three generations of the Command Center dashboards in Azure Managed Grafana (V1, V2 and V3 Core) and to replay a recorded incident in V3 Core. **Goal:** show how the dashboards grow from "charts" to **investigations**: first what is wrong, then how sure we are, then replay, explain and hand over. The dashboard definitions are in [`monitoring/grafana`](../../monitoring/grafana/); the [dashboard list](../../monitoring/README.md) names every dashboard, its folder and its data source.

| **Generation** | **New idea** | **Dashboard folder** |
|---|---|---|
| **V1** | Three linked views: Estate → Workload → Incident. Existing data only. | [`monitoring/grafana/command-center-v1`](../../monitoring/grafana/command-center-v1/) |
| **V2** | Separates **attention** from **confidence** and **native alerts**. Adds vCPU view, storage layers, SQL trends, episodes, replay and zoom. | [`monitoring/grafana/command-center-v2`](../../monitoring/grafana/command-center-v2/) |
| **V3 Core** | Adds **verified alert attribution**, **six guided hypotheses** (supporting, contradicting, missing evidence) and **replay with hand-over links**. | [`monitoring/grafana/command-center-v3-core`](../../monitoring/grafana/command-center-v3-core/) |

Every dashboard address has the form `https://<GRAFANA_ENDPOINT>/d/<DASHBOARD_UID>`. `<GRAFANA_ENDPOINT>` is the endpoint of the Azure Managed Grafana instance that hosts the dashboard (see the **Overview** page of that instance in the Azure portal). The reference lab ran each dashboard family in its own instance, so the endpoint can differ per generation; when you import all three into one instance it is the same.

| **Generation** | **Dashboard UIDs (estate · workload · incident)** |
|---|---|
| V1 | `hv-cc-estate` · `hv-cc-workload` · `hv-cc-incident` |
| V2 | `hv-cc-v2-estate` · `hv-cc-v2-workload` · `hv-cc-v2-incident` |
| V3 Core | `hv-cc-v3-core-estate` · `hv-cc-v3-core-workload` · `hv-cc-v3-core-incident` |

> **Beginner tip:** Each generation is a **separate** set of three dashboards. Older ones stay unchanged as fallbacks. In a short demo, use **V3 Core** for the main story and mention V1 and V2 as the earlier, simpler generations. If a newer dashboard is slow or fails, switch the browser address to the next one in the fallback order: V3 Core → V2 → V1 → Operations Cockpit → Azure Workbook (the Workbook is always independent of Grafana). Nothing has to be repaired first. Close the tab you are leaving.

## 11.1 The common rules of all three

- **Manual refresh.** Press **Refresh** yourself. This keeps load on shared data services low.
- **Default: last 1 hour. Allowed range: 1 minute to 4 hours.** An invalid range shows **"no evidence"**, never "healthy".
- Three **linked views** (top row 01, 02, 03). The machine and time range are **carried over** when you jump between them.
- **RETURN TO LIVE** resets a view to the last hour.
- Every **unknown is shown as unknown**. Missing data is never green.
- **Panel titles.** In V2 and V3 Core the panel titles are written in capitals and followed, after a slash, by short qualifiers that say what the panel shows and what it does not claim (for example "SEQUENCE / first qualifying symptom + CT offsets / correlation - cause"). This script names a panel by its first words.

## 11.2 Command Center V1 – three linked views

> **Where to run it:** **Grafana V1** (browser). Open `https://<GRAFANA_ENDPOINT>/d/hv-cc-estate`; the dashboard is titled "Infrastructure & SQL Command Center - Estate Overview".

**V1 · Estate Overview – what you should see:**

1. Navigation links at the top: **01 - Estate Overview**, **02 - Selected Workload Deep Dive**, **03 - Incident Investigation**, **Read-only resource context** and **Existing Workbook - independent fallback** (the original Azure Workbook).
2. Tiles **Fresh required streams / 14**, **Stale required streams / 14** and **Missing required streams / 14**: in the recorded lab result **14** are fresh, 0 stale and 0 missing. The tile **CONFIGURED - machines / guests / nested host** shows **6** expected machines, **5** guests and **1** nested host.
3. In row **01 - EXPECTED ESTATE**, the table **Six expected machines - row actions retain machine + interval** with the actions **Deep dive** and **Investigate**, heartbeat and latest metrics.

> **Do this:** In the table click **Deep dive** on the row **SQL2019-GUEST**. The Workload view opens for that machine and the same time range.

**V1 · Selected Workload Deep Dive for SQL2019-GUEST – what you should see:**

1. The **machine selector** (default SQL2019-GUEST). Its label says that the FIXED HOST panels always stay on HV-HOST-01.
2. In row **01 - COMPUTE + MEMORY**: the charts **OS CPU vs FIXED HOST - 1m mean %** and **per-vCPU run time - not VM average** (each title starts with the selected machine).
3. The next panels are the **dispatch wait**, the processor queue and RAM, then, in row **02 - STORAGE + NETWORK** ("compare layers, NEVER add them"), storage, capacity and network, and in row **03 - SQL LENS** the SQL panels (SQL2019-GUEST only, otherwise N/A).

**V1 · Incident Investigation – what you should see:**

1. The same machine selector.
2. Row **01 - FORM A HYPOTHESIS** with the table **SQL2019-GUEST candidate signals - observed rules, NOT automated RCA** (the title starts with the selected machine): for each lens (OS CPU, RAM use, dispatch wait) it shows value, samples, last sample, evidence, a **Next check** and the limit. It is guidance, **not an automatic root cause**.

## 11.3 Command Center V2 – attention, confidence and native alerts

> **Where to run it:** **Grafana V2** (browser). Open `https://<GRAFANA_ENDPOINT>/d/hv-cc-v2-estate`; the dashboard is titled "Command Center V2 - 01 / Estate attention".

**V2 · Estate attention – what you should see:**

1. The text **MODE / live versus fixed history** and the tile **WINDOW GUARD / no evidence - healthy**. The page tells you whether you are looking at live data or a fixed/delayed history and whether the time window is valid.
2. Three separate questions: **ATTENTION / sampled advisory - native alert** (is something sampled as a problem?), **CONFIDENCE / fresh streams out of 14** (is the evidence complete? In the recorded lab result all 14 are fresh) and **NATIVE ALERTS / CURRENT fired by severity, RG-wide** (real Azure alert counts by severity).
3. The table **OPERATIONAL ATTENTION / all six expected machines**: the actions **OpenWorkload** and **OpenIncident**, attention, confidence and coverage. The table **EVIDENCE CONFIDENCE / 14 expected streams** lists the streams behind the confidence tile.
4. **RETURN TO LIVE - last 1h** (a link in the top row and in the MODE text).

**V2 · Native alerts, configured relationships and Arc inventory – what you should see:**

1. **ACTUAL NATIVE INSTANCES / current snapshot, not complete history**: rule, severity, **Resolved**, fired and resolved times (from Azure's own alert records).
2. **CONFIGURED RELATIONSHIPS / baseline, NOT discovery:** a graph of the host and its five guests plus the SQL instance. The title says what it is: a configured baseline, **not discovery**.
3. **ARC INVENTORY / current index, not selected-time health:** current status and OS of each machine.

**V2 · Workload evidence for SQL2019-GUEST – what you should see:**

1. **per-vCPU HOTSPOT MATRIX / 1m sample CPU % intensity** (coloured blocks, one row for each virtual processor) and the **dispatch wait** trend.
2. **STORAGE / qualified ms by device + layer**, **IOPS / layers and aliases NEVER additive** and **queue + MiB/s / separate axes**: latency, IOPS, queue and throughput by device and layer.
3. **SQL ONLY** panels: ceiling, manager and process, peak grants with paired use (from the same row), OS headroom and pending grants.

> **Say this:** "V2 teaches the three-question habit: Is something wrong? How sure are we? What does Azure itself say? They are shown side by side and **never mixed** into one green or red light."

## 11.4 Command Center V3 Core – the investigation

> **Where to run it:** **Grafana V3 Core** (browser). Open `https://<GRAFANA_ENDPOINT>/d/hv-cc-v3-core-estate`; the dashboard is titled "Command Center V3 Core - 01 / Estate attention".

### Step 1 – Estate attention

**V3 Core · Estate attention – what you should see:**

1. Links in the top row: the three views, **RETURN TO LIVE - last 1h**, the pre-set **HISTORICAL REPLAY** link (do not use it – see Step 3) and **Read-only handoff bookmark - same context**.
2. Tiles: **ATTENTION / distinct machines / DEMO only** (sampled episode machines, insufficient signal evidence), **CONFIDENCE / freshness is NOT availability** (**Fresh streams** out of the 14 expected) and **NATIVE / never added to advisory machine counts** (native alert counts: "0 returned · not health"). The tile that starts with **SELECTION** is the window guard: it asks you to select a range of 1 minute to 4 hours when the range is outside that limit.
3. **WINDOW ATTENTION / all SIX expected machines:** attention, confidence and what signals were evaluated.
4. **COVERAGE / 14 expected streams / at selected END:** the coverage of the 14 expected data streams at the selected end time.

> **Say this:** "'0 returned' means Azure returned no current fired alerts – it does **not** say 'healthy'. V3 never turns an empty answer into a green light."

**V3 Core · Native alerts with verified attribution – what you should see:**

1. **NATIVE INSTANCES / CURRENT snapshot + original time context.** Look at the **Computer** and **Attribution** columns: an alert that does not name exactly one machine shows **Unattributed** in the **Computer** column, and the **Attribution** column gives the reason, for example "No exact target or supported instance dimension in ARG".
2. **CONFIGURED RELATIONSHIPS / NOT discovery or historical placement** (still a baseline, not discovery).
3. **ARC / CURRENT index / not selected-time availability** (current snapshot, not history).

> **Be honest - say exactly this:** "Most of our alert rules watch a **workspace**, not one machine. So an alert record often does not say which machine had the problem. V3 only assigns an alert to a machine when the alert itself names exactly one machine; otherwise it says **Unattributed**. We prefer 'we do not know' over a wrong guess."

### Step 2 – Guided workload evidence

> **Do this:** Go to view **02 / Guided workload evidence**. Choose the machine **SQL2019-GUEST** in the selector.

**V3 Core · Guided hypotheses for SQL2019-GUEST – what you should see:**

1. The **machine selector.**
2. Tiles **SQL2019-GUEST / WINDOW ATTENTION** and **SQL2019-GUEST / SIGNAL CONFIDENCE** (their titles start with the selected machine): window attention, **signal confidence "Adequate"** (recorded lab result) and minimum coverage 100%.
3. **GUIDED HYPOTHESES / support - contradiction - MISSING / never automatic cause**: six candidates – Application availability, Guest CPU saturation, Nested-host contention, OS memory pressure, SQL workspace pressure and Storage pressure. For each candidate a column shows the **evidence state**, the **confidence**, and the **supporting**, **contradicting** and **missing** evidence.

**V3 Core · Workload charts – what you should see:**

1. **CPU vs FIXED HOST / distinct CPU accounting:** SQL guest CPU versus the **fixed host** (separate CPU accounting).
2. **RAM + queue / RHEL queue NotCollected:** SQL guest RAM and the queue. For Linux the queue is **not collected** and shown as such.
3. **per-vCPU RUN / observed sample-minute matrix:** the **per-vCPU run matrix**.
4. **DISPATCH WAIT / sample P95 ns/dispatch / NOT Ready%:** **dispatch wait** (nanoseconds per dispatch, not a percentage).

### Step 3 – Replay a real incident

Replay needs a recorded incident whose data is still inside the Log Analytics retention period (30 days in the lab). In this guide the recorded incident hour is written as `<INCIDENT_START>`–`<INCIDENT_END>` (UTC): one hour that contains the CPU-contention episode behind the alert shown in Act 6. The episode starts 15 minutes after `<INCIDENT_START>` and lasts 15 minutes. The values quoted in this step are recorded lab results; a replay of your own recording shows your own values. The meaning of `<INCIDENT_START>`, `<INCIDENT_END>`, `<FROM_MS>` and `<TO_MS>` is explained under "Placeholders" in [About this guide](00-about-this-guide.md).

> **Do this:** Open the replay of the recorded incident hour for **WIN2022-GUEST** with a replay link (see "Build a replay link" below). Or do it by hand: open **03 / Incident replay & handoff**, choose **WIN2022-GUEST** in the selector, click the time range at the top, type the start of the window in **From** and the end in **To**, and click **Apply time range** (see section [3.0.5, "The Grafana time picker"](02-reading-dashboards-anatomy-and-method.md#305-the-grafana-time-picker) of the chart-reading guide). The picker reads what you type in the time zone of the browser (UTC+7 on the presenter PC), so add 7 hours to `<INCIDENT_START>` and `<INCIDENT_END>` before you type them. Wait about 10 seconds.

**Build a replay link.** Grafana replay links carry the window as **epoch milliseconds** in the `from` and `to` parameters, on purpose. Convert the UTC window once on the operator PC and paste the result into the browser:

```powershell
# <INCIDENT_START> and <INCIDENT_END> are ISO 8601 UTC timestamps that end with Z
$from = [DateTimeOffset]::Parse('<INCIDENT_START>').ToUnixTimeMilliseconds()
$to   = [DateTimeOffset]::Parse('<INCIDENT_END>').ToUnixTimeMilliseconds()
"https://<GRAFANA_ENDPOINT>/d/hv-cc-v3-core-incident?var-machine=WIN2022-GUEST&from=$from&to=$to"
```

The V2 replay of the same hour uses the same parameters on `https://<GRAFANA_ENDPOINT>/d/hv-cc-v2-incident`. The same pattern works for any dashboard: the view that [Act 3, section 3.5](13-act-3-the-cpu-story.md) opens by hand for the recorded CPU-test window can also be opened with `https://<GRAFANA_ENDPOINT>/d/hv-cc-v3-core-workload?var-machine=RHEL94-GUEST&from=<FROM_MS>&to=<TO_MS>`, where `<FROM_MS>` and `<TO_MS>` are the window converted to epoch milliseconds as shown above.

> **If something goes wrong:** Do **not** click the pre-set top-row button **HISTORICAL REPLAY**, and do not rely on the "Recorded ..." links in the **READ-ONLY HANDOFF** text at the bottom of the incident page. They are fixed links saved in the dashboard definition: they open an hour recorded in the reference lab, in which the lab was still starting, so they show "Insufficient" or no data in your own lab (see the notes on recorded windows in the [dashboard list](../../monitoring/README.md#things-to-know) and the tip in [section 3.9 of the chart-reading guide](04-reading-charts-blocks-tables-graphs.md#39-coloured-blocks-and-tiles)). Do not type ISO dates (like `YYYY-MM-DDTHH:MM:SSZ`) into the replay link: in this Grafana build they can be misread. Use the epoch numbers, click the links inside the dashboards, or type the range in the time picker. If the recorded hour has expired, replay another recorded hour that has complete data (every minute present) or record a new episode.

**V3 Core · Replay of the recorded hour for WIN2022-GUEST – what you should see:**

1. The **time range** is fixed to the recorded hour.
2. The two tiles **WIN2022-GUEST / WINDOW ATTENTION** and **WIN2022-GUEST / SIGNAL CONFIDENCE** show attention **Warning**, signal confidence **Adequate** and a minimum signal coverage of 100% (recorded lab result).
3. **GUIDED HYPOTHESES.** "Guest CPU saturation" and "Nested-host contention": Supporting sampled signal with Adequate sampled metric ONLY. "OS memory pressure": no sustained signal. "SQL workspace pressure": **NotApplicable** (this is not the SQL guest). Scroll the table to see the last two rows.

> **Say this:** "Here is a **real** past event – the hour of the alert you saw in Act 6. WIN2022-GUEST had a sustained CPU episode. V3 says: Warning – and confidence is **Adequate**: every minute of the hour has data, so we can trust what it says. Look at the table: CPU saturation is supported, the host was under pressure too, memory is not the story – and every row tells us what it can and cannot prove."

> **Do this:** Scroll down to the tables **SEQUENCE** and **LONGEST REAL EPISODE**, and the **SAMPLED STATES** strip.

**V3 Core · Episode sequence and sampled states – what you should see:**

1. **Sequence:** the first qualifying symptom 15 minutes after `<INCIDENT_START>` (the start of the episode), with the link **Zoom episode**.
2. **Longest real episode:** before, during and after values of OS CPU and RAM. Scroll the table to the right for the **Mean** and **Peak** columns (recorded lab result for OS CPU: about 1.2% → 99.4% → 0.6%).
3. **Sampled states:** each block is one minute; **orange = the CPU rule was crossed** (**15 blocks**, the 15 minutes of the episode); **blue = below the rule**; grey = not applicable (see the colour dictionary in [section 3.9 of the chart-reading guide](04-reading-charts-blocks-tables-graphs.md#39-coloured-blocks-and-tiles)).

> **Be honest - say exactly this:** If anyone asks about an "Insufficient" they have seen elsewhere, say: "Insufficient means that some minutes have no data – for example a lab machine that was switched off. The dashboard does not guess; it tells us what is missing. This hour has every minute."

### Step 4 – Zoom and read the evidence

> **Do this:** In the **SEQUENCE** table click **Zoom episode**. The view re-opens for the episode plus five minutes on each side: 25 minutes, from `<INCIDENT_START>` + 10 minutes to `<INCIDENT_START>` + 35 minutes. Scroll to the **SEQUENCE** table and the strip, then further down to the charts.

**V3 Core · Zoom, the sequence row and the sampled states – what you should see:**

1. The new, shorter **time range**.
2. The **SEQUENCE** row of the episode.
3. **Sampled states:** 25 one-minute blocks – **5 blue, 15 orange, 5 blue**: calm, busy, calm.

**V3 Core · Zoomed charts of the same 25 minutes (scroll down) – what you should see:**

1. **CPU of the guest** next to the **fixed host** (distinct CPU accounting): the guest at 100%, the host's hypervisor total close to it.
2. **RAM and the processor queue:** RAM flat, the queue rising during the episode.
3. The **per-vCPU run matrix** (one row per virtual processor).
4. **Dispatch wait** (nanoseconds per dispatch, not a percentage).

> **Say this:** "When we zoom into the 25 minutes around the episode, the picture is simple: five calm minutes, **fifteen** busy minutes, five calm minutes. OS CPU averaged about 1% before, 99% during and 1% after. At the same time the host's processors were almost fully used and the guests waited for them, while RAM stayed flat. The dashboard gives us the **evidence** and the **next check**. It does not claim a cause."

### Step 5 – Hand over and return

> **Do this:** In the top row click **Read-only handoff bookmark - same context**. The page reloads with the same machine and time range; copy the address from the browser address bar and paste it in a chat or e-mail. Click **RETURN TO LIVE - last 1h** to go back.

> **Beginner tip:** A bookmark stores **only** the machine and the time range, not any incident data. It lets a colleague open the same evidence. It does not freeze data and does not extend how long data is kept.

> **Good to know:** What matters when evidence is passed to someone else is **how it is presented**: each hypothesis lists supporting, contradicting and missing evidence with a stated confidence, and the replay refuses to over-claim.

> **Be honest - say exactly this:** "A sampled episode, a time-aligned change or an alert does **not prove** the root cause. V3 gives you the evidence and the next check, not an automatic diagnosis."
