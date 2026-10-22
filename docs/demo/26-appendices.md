# Appendices: command index, glossary, checklists and Act 8B prompt cards

This document collects the reference material of the demo storyline: the PowerShell and CLI command index (A), the glossary for beginners (C), the before, during and after checklists (D), and the prompt cards, saved queries and answer key for the AI-assisted scenes of Act 8B (F). The appendix letters are kept stable so that references in the Acts (for example "Appendix F") still work (there is no Appendix B or E). Use it while you prepare, while you present and when you clean up.

## A. PowerShell and CLI command index

> **Where to run it:** All commands run on the **Operator PC → Windows PowerShell** (not Cloud Shell). Start with the variables in Act 0. Every command is **read-only** or only writes local files.

| **Act** | **What it shows** | **Command (short)** | **Note** |
|---|---|---|---|
| 0 | Signed in to the right subscription | `az account show --subscription $SUB ...` | Sign in with `az login` if needed. |
| 0, 1 | Six Arc machines | `az rest ... machines?api-version=2024-07-10` | No extension needed. |
| 3.5 | Recorded CPU scene and web response (rehearsal file) | `$cpu = (Get-Content -LiteralPath $f -Raw \| ConvertFrom-Json) \| Where-Object Scenario -eq 'CPU'` | Reads a local file; prints six result lines. The five PowerShell lines are in Act 3, section 3.5. |
| 3.6 | Host CPU every 5 minutes (recorded test) | `az monitor log-analytics query ...` | Needs the Log Analytics CLI extension; skip if missing. |
| 5 | Databases known to Azure Arc | `az rest ... /databases?api-version=2026-01-01` | Read-only. |
| 6 | Recorded e-mail receipts | `Get-Content ... mail-receipt-evidence.json \| ConvertFrom-Json` | Reads a local file. |
| 7 | Missing updates | `az graph query ...` | Needs the Resource Graph extension; skip if missing. |
| 10 | A new CSV export of the report evidence (optional) | `.\export-report.ps1` in `lab-kit\sources\demo-v22` | Reads the last four hours from Log Analytics and the database inventory, and writes five CSV files to `<REPO_ROOT>\reports-output`. Needs a signed-in `az`. The PDF comes from the **Download native PDF** button. |
| 8B | Verify Copilot's Arc inventory query | `az graph query -q $q --subscriptions $SUB --query "data" -o table` | Read-only. |
| 8B | Verify an AI-written KQL query | `az monitor log-analytics query --workspace $WS --analytics-query $KQL ...` | Use single quotes inside the query. |
| 8B | Verify the recorded alert list | `az rest --method get --url .../providers/Microsoft.AlertsManagement/alerts --uri-parameters ...` | Read-only. |
| 8B | Verify the disk metrics | `az monitor metrics list --resource $VM --metric 'Data Disk IOPS Consumed Percentage' ...` | Read-only. |

## C. Glossary for beginners

| **Term** | **Simple meaning** |
|---|---|
| Azure Arc | Azure's way to manage machines and SQL Server that are not "native" Azure virtual machines. |
| Hyper-V | Microsoft's technology to run virtual machines on a Windows host. |
| Nested | A virtual machine running inside another virtual machine. Our five guests run inside an Azure VM. |
| Guest / host | The guest is the virtual machine; the host is the machine that runs the guests. |
| vCPU / logical processor | A virtual processor given to a guest / a processor thread of the host. |
| Workbook | An Azure Monitor report page with charts and tables. |
| Log Analytics workspace | The database where Azure Monitor keeps measurements and logs. |
| KQL | Kusto Query Language: a read-only language to ask questions to the workspace. |
| Heartbeat | A small "I am alive" message every agent sends every minute. |
| Scheduling wait / dispatch | How long a virtual processor waits for a real processor each time it is scheduled. |
| P95 | The value that 95 out of 100 samples are below. A good "bad but not extreme" number. |
| IOPS / latency | Operations per second / time per operation for a disk. |
| VHDX | The file on the host that holds a guest's virtual disk. |
| Query grant | Memory SQL reserves for a query to sort or join data before it runs. |
| Ceiling (max server memory) | The maximum memory SQL is allowed to use for its memory manager. |
| Best Practices Assessment | An automatic checklist of SQL Server settings and health. |
| Update Manager | Azure service that checks for missing updates and schedules installs. |
| Maintenance configuration | A saved schedule and rules for patching. |
| Change Tracking | Records changes to services, files and software. |
| Alert rule / action group | A saved check that raises an alert / the list of people notified. |
| Fired / Resolved | Alert started / alert closed by Azure itself. |
| Grafana | A dashboard tool. Azure Managed Grafana is the Azure-hosted version. |
| Attention / confidence | "Did we see a problem?" / "Is the evidence complete enough to trust?" |
| Replay | Showing a real past period exactly as recorded. |
| Epoch milliseconds | The number of milliseconds since 1 January 1970, 00:00 UTC. Grafana replay links carry the start and end of the window in this form. |
| Bastion | Secure remote access to a machine through the Azure Portal. |
| LT / UTC | Local time (UTC+7 in the lab) / world reference time. LT = UTC + 7. |
| Azure Copilot | An AI helper in the Azure Portal header. You ask in plain English; it answers, writes queries and explains. |
| Agent (AI agent) | An AI helper that can take **several steps** by itself – for example collect data, compare it and write a report – and shows those steps. |
| Observability Agent | The AI agent inside Azure Monitor. It chats with your logs and investigates alerts. |
| Prompt | The sentence you type to an AI helper. |
| Azure Resource Graph | The Azure inventory database. Copilot writes queries for it. Query language is KQL-like. |
| Counter (ObjectName / CounterName) | One kind of measurement in the Perf table, named by an object and a counter, for example "Hyper-V Hypervisor Logical Processor" and "% Total Run Time". |
| Discovery query | A query that lists what exists (tables, counters) instead of asking for values. The way to fix an "empty" AI answer. |
| Temporary chat | An AI conversation that is not saved. Leaving it asks you to confirm that it will be deleted. |
| Azure Monitor issue | A saved record of an incident with its investigation. Created by choosing **Create Issue** (we never do in a demo) or by autonomous operations. |
| Azure Agent Credit (AAC) | The unit in which the Observability Agent usage is billed. |
| Hallucination | When an AI states something that is not true or not in the data. The reason we check every answer. |
| Committed memory | The memory SQL's memory manager currently holds. It equals Free + Cache + OtherInternal (the memory ledger, [section 3.5 of the chart-reading guide](03-reading-charts-cpu-memory-storage.md#35-a-ceiling-and-what-is-really-used-sql-memory)). |
| Coverage (%) | The share of minutes in the chosen time range that have data. Below 90% the evidence is not "Adequate" and the dashboard says "Insufficient" (see [section 3.9](04-reading-charts-blocks-tables-graphs.md#39-coloured-blocks-and-tiles)). |
| Status strip | A row of small blocks, one per minute. The colour is the state: blue observed, orange breach, dark orange unknown (no data), grey not applicable. |
| Legend | The key next to a chart: colour → name. Colours are used again in every chart, so read each legend. |
| Tooltip | The small box that appears when you hover over a chart: the time and the value of every line at that moment. |
| Time picker | The control that sets the period you look at: Workbook "Time range" box, Grafana time range at the top. |
| Plateau | A line that rises and stays high for a while, then falls: a sustained event. |
| localhost | "This computer itself". A request to localhost goes from a machine to its own web server and never crosses a network. |
| NotCollected | The dashboard's word for "this signal is not measured in this lab". It is not a zero and not an error – it is an honest gap. |
| Evidence card | One small table with numbers from **one** recorded source, together with its time, its source and what it is **not**. Used in [Act 3, section 3.5](13-act-3-the-cpu-story.md). |

## D. Checklists

### D.1 Before the demo

- Browser tabs prepared ([Act 0.1](10-act-0-before-the-audience.md)). Other tabs closed. Notifications off.
- Six machines Connected; cockpit shows Fresh 6.
- No local file that holds passwords or environment notes is open. No passwords visible.
- Not inside the shift-report windows: 05:50–06:10, 13:50–14:10 and 21:50–22:10 LT (22:50–23:10, 06:50–07:10 and 14:50–15:10 UTC); see [section 1.5 of About this guide](00-about-this-guide.md).
- Zoom the browser to 100–110%. Test the projector with the Workbook and one Grafana page.
- Recorded intervals written on a card, in UTC and local time (UTC+7): the CPU test (`<CPU_TEST_START>`–`<CPU_TEST_END>`), the storage test (`<STORAGE_TEST_START>`–`<STORAGE_TEST_END>`), the SQL test (`<SQL_TEST_START>`–`<SQL_TEST_END>`) and the **Command Center replay** (`<INCIDENT_START>`–`<INCIDENT_END>`).
- **For Act 8B:** Copilot opens and answers a test question; the network allows WebSocket to `directline.botframework.com`; Appendix F printed; PowerShell variables `$SUB`, `$RG`, `$WS` set; the **Alert details** link of the recorded alert tested; the recorded data has not expired (it is kept for 30 days, see F.5).
- **For Act 3 (section 3.5):** the rehearsal file `cpu-storage-rehearsal.json` is in `lab-kit\sources\demo-v22` on the operator PC (your own run of `run-cpu-storage-rehearsal.ps1` creates it; see [setup chapter 22](../setup/22-rehearsal-scenes.md)) and the five PowerShell lines of [section 3.5](13-act-3-the-cpu-story.md) print **six** result lines; the Command Center V3 Core replay link for RHEL94-GUEST over the recorded CPU-test window (see [Act 11](22-act-11-command-center-v1-v2-v3-core.md) for how a replay link is built) opens while the recorded data is still inside the 30-day retention. Do not run a separate web-latency test.

### D.2 During the demo

- Say **Live / Recorded / Configuration** at each change of scene.
- Never click the buttons in the safety list ([About this guide](00-about-this-guide.md), section 1.2).
- If a page is slow, wait 15 seconds; do not click repeatedly.
- If something fails, use the fallback (the **If something goes wrong** callouts). Do not repair the lab.
- If the portal says a resource is not found, you are probably signed in to the wrong directory: click your account at the top right → **Switch directory** and choose the lab directory.
- For the alert **rules** list, use Monitor → Alerts → Alert rules and search `hv-`; do not open the subscription-wide list on screen, because it also shows other resources.
- **AI scenes:** name the resource group or workspace in every request; read the query before you run it; never press **Create Issue**, **Apply** or **Deploy**; never use Copilot full-screen.

### D.3 After the demo

- Leave the Workbook without saving. Close Logs tabs (answer "discard" if asked about unsaved edits).
- Close all Grafana tabs.
- Do not stop, restart or change any machine.
- Write down open questions and follow them up after the session.
- **AI scenes:** close temporary chats and click **OK** on the "permanently deleted" message. Optionally delete your Copilot chats from the chat list. The next day, look at Cost Management for the Observability Agent usage.

## F. Act 8B – prompt cards, saved queries and answer key

Print this appendix. **AI answers differ from run to run**, so the words you get will not be identical to the figures. What must stay the same is the **answer key** (F.3). If the AI's query or numbers disagree with the key, paste the **saved query** of F.2 instead.

The times and values in this appendix are recorded lab results from the reference recording of the lab. Replace the placeholders with the intervals of your own recording; if your lab holds a different recording, check your own values once with the saved queries and the CLI commands in Appendix A before you use the answer key.

The placeholders of the cards are explained in "Placeholders" in [About this guide](00-about-this-guide.md) and repeated here, so that this appendix can be printed on its own.

| **Placeholder** | **Meaning** |
|---|---|
| `<TEST_DATE>` | The date of the recorded CPU test, written as day, month name and year. |
| `<TEST_START_LT>`, `<TEST_END_LT>` | Start and end of the recorded CPU test in local time (UTC+7), written as `HH:MM`. |
| `<TEST_START_UTC>`, `<TEST_END_UTC>` | The same window in UTC (local time minus 7 hours). In KQL use the ISO 8601 form `YYYY-MM-DDTHH:MM:SSZ`. |
| `<ALERT_FIRED_UTC>` | The time and date at which the recorded alert fired, in UTC, written as in the prompt (for example `HH:MM UTC on D Month YYYY`). |
| `<SLOW_START_LT>`, `<SLOW_END_LT>` | Approximate start and end of the recorded storage slowdown in local time (UTC+7). |

### F.1 Prompt cards (copy exactly)

| **Card** | **Where to type it** | **Prompt** | **A good answer looks like** |
|---|---|---|---|
| **1B** | Portal → **Copilot** (resource group page) | `List the Azure Arc-enabled servers in resource group rg-hyperv-arc-monitor-demo only, with name, location and connection status.` | The query contains `resourceGroup =~ 'rg-hyperv-arc-monitor-demo'`. **Run** shows **6 of 6** rows, all Connected. |
| **2a** | Logs (KQL mode) + **Copilot** | `Write a KQL query for the Log Analytics workspace law-arc-monitor-lab that shows which computers sent a heartbeat in the last 30 minutes and how many minutes ago their last heartbeat was.` | Table `Heartbeat`, `summarize max(TimeGenerated) by Computer`, `datetime_diff`. Six computers, `MinutesAgo` 0 or 1. |
| **2b** | same | `In the Log Analytics workspace law-arc-monitor-lab, write a KQL query that shows the Hyper-V host CPU usage of HV-HOST-01 every 5 minutes on <TEST_DATE> between <TEST_START_LT> and <TEST_END_LT> local time (UTC+7).` | Time converted to **UTC** (`<TEST_START_UTC>`–`<TEST_END_UTC>`). The **counter may be wrong** (we got `Processor`) and the query returns **"No results"**. That is the point of the scene. |
| **2c** | same chat | `That query returned no results. Write a KQL query that lists the distinct ObjectName and CounterName values in the Perf table for computer HV-HOST-01 in the last 7 days, with the number of samples. Answer in English.` | About **75 rows** in the reference recording (about 30 with only the shipped host rule). Many start with **Hyper-V**. |
| **2d** | same chat | `Rewrite the host CPU query for HV-HOST-01 using ObjectName "Hyper-V Hypervisor Logical Processor", CounterName "% Total Run Time" and InstanceName "_Total". Average every 5 minutes for <TEST_DATE> between <TEST_START_LT> and <TEST_END_LT> local time (UTC+7). Answer in English.` | Seven rows: **13.4, 24.6, 94.7, 97.7, 88.0, 12.5, 9.0** percent. |
| **2e** | new Copilot chat | `Explain this KQL query to a beginner in simple English, line by line, in at most 6 short bullet points:` then paste the query of F.2 item 5 | Six correct bullets (table, time filter, resource-group filter, last seen, age in minutes, order). |
| **2f** | Logs + Copilot (**always works**) | `Write a KQL query for the Log Analytics workspace law-arc-monitor-lab that shows the Hyper-V host CPU usage of HV-HOST-01 every 5 minutes in the last 24 hours. Use ObjectName "Hyper-V Hypervisor Logical Processor", CounterName "% Total Run Time" and InstanceName "_Total". Answer in English.` | A quiet host: averages of about **6–9 percent** (value seen in the reference lab). |
| **3a** | Logs → **Observability agent** | Click the button **Ingestion volume**, then **Send** (text: `Which tables and resources used the most ingestion volume in the last 24 hours?`) | **Perf** by far (about 96 percent). It says it cannot attribute volume to resources. |
| **3b** | same chat | Click the button **Break down Perf by Computer**, then **Send** | HV-HOST-01 about **37 %**, SQL2019-GUEST **22 %**, RHEL94-GUEST **12 %**, three Windows guests **9.7 %** each. |
| **4a** | **Investigate** page, after the report | `Were other alert rules in this workspace fired in the 20 minutes after <ALERT_FIRED_UTC>? Please list them with their fired times.` | **Seven other rules** (list in F.3). |
| **5a** | VM page → **Copilot → Troubleshooting** | `Why is the data disk of this VM slow? The slowness started on <TEST_DATE> at about <SLOW_START_LT> local time (UTC+7) and lasted until about <SLOW_END_LT>.` | Guided steps (select **HV-HOST-01-data** and the half hour that contains the slowdown). A **general** answer is expected. |

### F.2 Saved queries (paste into the Logs editor in KQL mode)

These are verified. In **PowerShell** replace every double quote `"` by a single quote `'` (see the tip in Act 8B, scene 2).

**Saved query 1**

```kql
// 1. Heartbeat - who reported in the last 30 minutes
Heartbeat
| where TimeGenerated > ago(30m)
| summarize LastHeartbeat = max(TimeGenerated) by Computer
| extend MinutesAgo = datetime_diff('minute', now(), LastHeartbeat)
| project Computer, MinutesAgo
```

**Saved query 2** (recorded; it stops returning rows when the recorded data leaves the 30-day retention). Replace `<TEST_START_UTC>` and `<TEST_END_UTC>` with the ISO 8601 UTC timestamps of your recorded CPU test.

```kql
// 2. Host CPU during the recorded CPU test (<TEST_START_UTC> to <TEST_END_UTC>)
Perf
| where Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Logical Processor" and CounterName == "% Total Run Time" and InstanceName == "_Total"
| where TimeGenerated between (datetime(<TEST_START_UTC>) .. datetime(<TEST_END_UTC>))
| summarize avg_CounterValue = avg(CounterValue) by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```

**Saved query 3**

```kql
// 3. Host CPU, last 24 hours (always works)
Perf
| where Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Logical Processor" and CounterName == "% Total Run Time" and InstanceName == "_Total"
| where TimeGenerated > ago(24h)
| summarize avg_CounterValue = avg(CounterValue) by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```

**Saved query 4**

```kql
// 4. Discovery - which counters exist for the host
Perf
| where Computer == "HV-HOST-01"
| where TimeGenerated > ago(7d)
| summarize SampleCount = count() by ObjectName, CounterName
| order by SampleCount desc
```

**Saved query 5**

```kql
// 5. The Act 8 heartbeat query (the one to ask Copilot to explain; also stored as lab-kit/queries/heartbeat.kql)
Heartbeat
| where TimeGenerated > ago(30m)
| where _ResourceId contains "/resourceGroups/rg-hyperv-arc-monitor-demo/"
| summarize LastSeen=max(TimeGenerated), Environment=any(ComputerEnvironment) by Computer, _ResourceId
| extend AgeMinutes=datetime_diff("minute",now(),LastSeen)
| order by Computer asc
```

**Saved query 6**

```kql
// 6. Data volume by table, last 24 hours
Usage
| where TimeGenerated > ago(24h)
| summarize MB = round(sum(Quantity), 2) by DataType
| order by MB desc
```

### F.3 Answer key

All clock times in this table are UTC; the values are recorded lab results from the reference recording.

| **Scene** | **Check** | **Correct answer** |
|---|---|---|
| 1 | Arc servers in the resource group | **6**: HV-HOST-01, RHEL94-GUEST, SQL2019-GUEST, WIN2019-GUEST, WIN2022-GUEST, WIN2025-GUEST-01. All Connected. SQL2019-GUEST in `southeastasia`, the others in the primary region. |
| 2a | Heartbeat query | 6 computers, `MinutesAgo` 0 or 1 |
| 2d | Host CPU, 5-minute averages, seven UTC bins from the start of the test (04:15 / 04:20 / 04:25 / 04:30 / 04:35 / 04:40 / 04:45) | **13.4 / 24.6 / 94.7 / 97.7 / 88.0 / 12.5 / 9.0** percent (local time = UTC + 7) |
| 2b trap | Same bins, counter "Processor Information" | 2.0 / 5.2 / 7.2 / 1.1 / 1.3 / 0.7 / 0.8 percent – **wrong story** |
| 3 | Ingestion, 24 hours | Perf **227.0 MB**, Heartbeat 5.3, Event 3.0, `HvSqlMemory_CL` 0.7, `HvLinuxDisk_CL` 0.3. Per computer (Perf rows): HV-HOST-01 444,651 (36.7 %); SQL2019-GUEST 267,806 (22.1 %); RHEL94-GUEST 146,610 (12.1 %); each Windows guest 118,080 (9.7 %). Numbers shift slightly each day. |
| 4 | The alert | `hv-cluster-contention-high`, **Sev2**, fired **07:46:00 UTC** (the `<ALERT_FIRED_UTC>` of card 4a), resolved 08:16:58 UTC (about 30 minutes later). Value 463,277 against threshold 110,000. |
| 4 | Wait per dispatch, per guest | Baseline 16,857–34,426 ns. Peaks: WIN2019-GUEST **898,238**, WIN2022-GUEST **893,908**, WIN2025-GUEST-01 **555,356**, SQL2019-GUEST 120,509, RHEL94-GUEST 76,813. First minute above 100,000 ns: **07:45 UTC** (the minute before the alert fired). |
| 4 | Other alert rules in the next 20 minutes | `hv-guest-contention-high` 07:50:03 (×4) · `hv-cluster-cpu-high` 07:55:27 · `hv-host-cpu-high` 07:56:16 · `hv-host-cpu-critical` 07:57:25 · `hv-cluster-cpu-critical` 07:59:13 · `hv-guest-cpu-high` 08:00:34 (×3) · `hv-guest-cpu-critical` 08:01:40 (×3) |
| 4 | Activity Log, 07:00–08:30 UTC | **Nothing before 08:18 UTC.** Later: Arc run-command read/write/delete (08:25–08:29), policy audit actions, a few network and VM writes (08:18–08:22). All after the spike. |
| 5 | HV-HOST-01-data, 04:30–05:00 UTC | Data-disk IOPS consumed **35 %** at most (limit 2,300 IOPS, P20 512 GB); bandwidth 10 %; VM uncached IOPS 6 %, bandwidth 5 %; cached IOPS 2 %. **No throttling.** |

### F.4 What the AI got wrong or left incomplete in the reference run

Tell this list yourself, before the audience finds it. It shows that you check, and it makes the things the AI got right more credible.

- Copilot **ignored "this resource group"** and asked about the whole subscription (more machines than the lab's six). Fix: name the resource group.
- The chat showed **5 of 6** machines ("first 5 results"). Fix: click Run.
- Copilot chose the **wrong counter** for the host CPU. The query returned "No results". Fix: a discovery query.
- Copilot replied in a **language other than English** (it can happen with long requests). Fix: "Answer in English."
- The investigation's first checks used the **wrong dates** (a period before the incident). It corrected itself.
- The report said **no aligned alerts**, but seven other alert rules had fired. Fix: one follow-up question.
- The plan used a stock phrase ("request failures") that does not fit a CPU wait alert.
- The Troubleshooting Agent gave **general advice**, not the verdict ("no limit reached"). Fix: check the metrics yourself.

**What it got right:** the time conversion from local time (UTC+7) to UTC; the heartbeat query; the explanation of a query; every number in the ingestion table; the per-computer ranking; the cause of the alert (host CPU contention); the baseline and peak wait values; the heartbeat and "not an outage" statement; the full list of other alerts after one follow-up.

### F.5 Shelf life of the recorded scenes

Logs and alerts are kept **30 days**. About 30 days after the recording, the recorded data is gone: scenes 2b–2d, 4 and 5 will return "no results". Until then they work. After that use cards **2a, 2e, 2f, 3a, 3b** (last 24 hours). To repeat scene 4 you need a **new** alert; that means running the CPU load again (on the host, with `lab-kit\Start-LabCpuScene.ps1`, see [setup chapter 17](../setup/17-cpu-contention-and-response-time.md)), which changes the lab. Another option is to set a longer retention for the Perf table. Both options change the lab, so decide on them deliberately and outside the demo.
