# Act 3. The CPU story – what a guest cannot see

Act 3 covers minutes 18–32 of the storyline (about 14 minutes). Its goal is to show the most important idea of the whole demo: a guest can be slowed by the **host** without knowing it. You replay a real recorded test and say "Recorded" out loud each time. Before you start, the Workbook from Act 2 must be open in Read mode. For section 3.5 the Grafana Command Center V3 Core tab (Tab 6 of Act 0) must be open and the rehearsal file `cpu-storage-rehearsal.json` (written by `lab-kit\sources\demo-v22\run-cpu-storage-rehearsal.ps1`, see section 3.5, part 2) must be on the Operator PC. For section 3.6 the PowerShell variables `$SUB` and `$RG` from Act 0 must still be defined. The recording stays in the workspace for 30 days; its date is written `<INCIDENT_DATE>` in this guide (see "Time zones" and "Placeholders" in [About this guide](00-about-this-guide.md)).

## 3.1 The background story (tell this first)

> **Say this:** "On the day of the recording we ran a controlled test. Three Windows guests – the noisy neighbours – were each told to use all four virtual processors for fifteen minutes. That is **twelve busy virtual processors** on a host that has **eight real processors**. In total the guests are **assigned 20 virtual processors**. Meanwhile the Linux guest and the SQL server stayed quiet. We were not loading SQL at all."

| **Fact** | **Value** |
|---|---|
| Host | 8 logical processors, 64 GB |
| Assigned guest vCPUs (all five guests) | 20 → ratio 2.5 : 1 |
| Busy vCPUs during the test | 12 (three guests x four workers) |
| Duration | 900 seconds, then the workers stop by themselves |
| Time | The recorded window: 04:22–04:42 UTC (11:22–11:42 LT, UTC+7) |

## 3.2 Show the host CPU

> **Where to run it:** **Azure Portal → Workbook** (Act 2).

> **Do this:** Click the **Time range** pill → **Custom**. Start: the date of the recording (`<INCIDENT_DATE>`, typed in the format the box shows – month/day/year on the lab PC) and `11:15:00 AM`. End: the same date and `11:50:00 AM`. Click **OK**. Wait 10–15 seconds. Look at the first chart **Host hypervisor processor utilization (%)**. The Portal uses the time zone of the browser, UTC+7 (LT) on the presenter PC, so the times you type are local time: 11:15–11:50 LT is 04:15–04:50 UTC.

The first chart, with the recorded window selected, shows these parts in reading order:

- **(1)** The time range shows the recorded window (11:15–11:50 LT). **Say "Recorded" out loud.**

- **(2)** The **plateau**: host CPU is about 95–98% while the three guests are busy (average about 94%).

- **(3)** The **recovery**: after the workers stop, the host drops back to a low value (average about 17%).

> **Say this:** "Before the test the host was around a quarter busy. During the test it was almost full. After the test it recovered by itself. That part is familiar to anyone who runs virtualisation hosts."

## 3.3 Show the hidden part – scheduling wait

> **Do this:** Scroll down to **Per-guest scheduling wait (nanoseconds per dispatch, not CPU-ready %)**. Read the colours in the legend at the right. Compare the high lines with the low lines. Scroll slightly to the table **Per-guest contention evidence**.

The scheduling-wait chart and the table below it show these parts in reading order:

- **(1)** **Legend**: each guest has a colour.

- **(2)** The two busiest Windows guests (blue and pink) climb to about **800,000 nanoseconds** per dispatch while the test runs.

- **(3)** The **Linux** (green) and **SQL** (purple) guests stay **far lower**. They were not busy. (Section 3.5 looks closely at the Linux guest: its wait still rises from about 20,000 to about 110,000 nanoseconds – small on this scale, but real.)

- **(4)** The table gives numbers: **Mean**, **P95** (95% of samples were below this) and **Peak** for every guest.

> **Say this:** "This is the hidden part. A guest cannot see this. Its own CPU chart only says it is busy. This chart says: the host made it wait – in this test up to eight hundred thousand nanoseconds, about 0.8 millisecond, **per scheduling turn**. The Linux and SQL guests, which were not busy, waited far less."

> **Beginner tip:** Convert quickly: **1,000 ns = 1 microsecond (µs)**. **1,000,000 ns = 1 millisecond (ms)**. So 800,000 ns = 0.8 ms. The chart axis shows "800K", which means 800 thousand.

## 3.4 The logical Windows group

> **Do this:** Scroll to the chart **WIN-CLUSTER-01 - three equal 4-vCPU Windows members (%)**.

The group chart and the memory chart below it show these parts in reading order:

- **(1)** Legend: **ClusterCPU** (average of the three members) and **BusiestMemberCPU**.

- **(2)** During the test the busiest member reaches 100% a little before the group average.

- **(3)** The next chart shows group memory. Memory use stays low and is **not** the same as committed memory.

> **Be honest:** "`WIN-CLUSTER-01` is a **tag** that groups three machines for monitoring. It is **not Windows failover clustering**, not high availability, and not a failover demonstration."

> **If something goes wrong:** If the Workbook shows no data for the custom window, check that you typed the date of the recording and local time (11:15–11:50 LT). If the Workbook still fails, use the recorded numbers of the evidence card in section 3.5 and say "Recorded evidence from the test day".

## 3.5 Tie it to the user experience – the recorded evidence card

**Goal (about 3 minutes):** connect the hidden host wait to something a user can feel – how fast a web page answers. The **evidence card** has three parts: the **cause** (a dashboard), the **effect** (a recorded file) and the **limit** (what Azure Monitor does not measure). Say "Recorded" each time.

| **Part** | **What it shows** | **Where you see it** | **In Azure Monitor?** |
|---|---|---|---|
| **1 · Cause** | The host was almost full, and the quiet Linux guest had to wait for a processor. | Grafana, Command Center V3 Core | **Yes.** Azure Monitor measured it. |
| **2 · Effect** | How fast the Linux guest's own web server answered. | A recorded file on the operator PC, read with PowerShell | **No.** A small logger **inside** the guest wrote it. |
| **3 · Limit** | The dashboard's own word for application response: **NotCollected**. | Grafana, the same page as part 1 | It is the dashboard's honest statement. |

### Part 1 – The cause: the quiet Linux guest had to wait

> **Where to run it:** **Grafana** (browser) → **Command Center V3 Core** (Tab 6) → view **02 / Guided workload evidence**. If a Microsoft sign-in window appears, click **your own lab account**.

> **Do this:** Open the V3 Core workload view. Choose **RHEL94-GUEST** in the selector, click the time range at the top, type `<INCIDENT_DATE> 11:15:00` in **From** and `<INCIDENT_DATE> 11:50:00` in **To**, and click **Apply time range** (local time, UTC+7; see section [3.0.5, "The Grafana time picker"](02-reading-dashboards-anatomy-and-method.md#305-the-grafana-time-picker) of the chart-reading guide). Wait about 10 seconds. Scroll down one screen to the four chart panels.

The workload view for RHEL94-GUEST during the recorded CPU test (11:15–11:50 LT) shows these parts in reading order:

- **(1)** **CPU chart.** The lines that rise to about **90–98%** belong to the **host** (their legend names start with "FIXED HOST"). The Linux guest's own line ("Selected OS CPU", green) stays at the very bottom.

- **(2)** **Legend of the CPU chart.** "Selected OS CPU" is the Linux guest itself: last **2.2%**, highest **3.9%**. The host's processors reach **97.8%** (third row, partly hidden).

- **(3)** **Processor queue:** "N/A - unavailable evidence". For Linux this counter is **not collected**, and the dashboard says so instead of drawing a zero.

- **(4)** **Per-vCPU matrix.** One row for each of the four virtual processors of the Linux guest. All blocks stay in the **lowest band ("< 20%", dark blue)** the whole time: the guest is not busy.

- **(5)** **Dispatch-wait chart** (nanoseconds per dispatch – **not** CPU-ready %). The waits rise from about **20,000 ns** to about **110,000 ns** while the host is full, then fall back.

- **(6)** **Legend of the wait chart.** "Max" of the first two virtual processors: **94,983.6** and **110,712.4** ns.

> **Say this:** "Look at the Linux guest. It is the quiet one: its own CPU never went above four percent and all four of its virtual processors stayed in the lowest band. But look at the host – almost full – and at the wait chart. Every time the Linux guest wanted a processor it had to wait: about twenty microseconds at rest, up to about one hundred and ten during the test. The guest's own CPU chart cannot show you that."

### Part 2 – The effect: how fast did its web server answer?

Azure Monitor does not hold this number. It was measured by a small logger **inside** the Linux guest during the rehearsal of the recorded test. The rehearsal script `run-cpu-storage-rehearsal.ps1` read the logger's last 300 response times after each phase and saved the result in `cpu-storage-rehearsal.json`, next to the script, on the operator PC (the script is described in [setup chapter 22, section 22.2](../setup/22-rehearsal-scenes.md#222-cpu-scene-then-stop-and-prove-recovery)). Your own rehearsal creates this file; the repository does not contain a recorded copy. You read it with five read-only lines of PowerShell. Short on time (about 2 minutes for all of 3.5)? Skip the PowerShell lines and go straight to the evidence-card table below.

> **Where to run it:** **Operator PC → Windows PowerShell.** Read-only: the lines only **read** a local file. Do not use Azure Cloud Shell – it cannot see this file.

> **Do this:** Click **Start**, type `PowerShell` and open **Windows PowerShell** (not as administrator). Copy the five lines of the code box below, paste them into the window and press **Enter**.

**Read the recorded CPU scene from the rehearsal file (read-only)**

```powershell
Set-Location '<REPO_ROOT>\lab-kit\sources\demo-v22'
$f = '.\cpu-storage-rehearsal.json'
$cpu = (Get-Content -LiteralPath $f -Raw | ConvertFrom-Json) | Where-Object Scenario -eq 'CPU'
"CPU scene: $($cpu.StartUtc) -> $($cpu.EndUtc)"
$cpu.Output -split "\r?\n" | Select-String 'HostCPU|localhost HTTP'
```

> **What you should see:** A line with the scene time and then **six result lines**: for each phase (**baseline, loaded, recovery**) one line about the host and one line about the Linux web server.

The PowerShell window shows these parts in reading order:

- **(1)** **The commands.** They open the rehearsal file and keep only the entry called "CPU". They read; they never write.

- **(2)** **The scene time:** 04:22:38 to 04:42:26 **UTC** – in local time (LT, UTC+7) 11:22 to 11:42.

- **(3)** **Baseline** – before the load: host CPU **25.82%**; the Linux guest's mean wait **48,408.94 ns**; local web response mean **1.623 ms** and 95th percentile (**p95**) **4.357 ms**.

- **(4)** **Loaded** – while the three Windows guests are busy: **94.44%**, **85,539.54 ns**, mean **2.857 ms**, p95 **7.843 ms**.

- **(5)** **Recovery** – after the workers stop: **17.03%**, **19,161.43 ns**, mean **1.353 ms**, p95 **1.928 ms**.

**What the words mean.** `HostCPU average` is how busy the host's processors were. `RHEL mean scheduling wait` is the Linux guest's wait per dispatch in nanoseconds – the same measure as the wait chart. `localhost HTTP latency last300` is the time in **milliseconds** that the Linux guest's own web server needed to answer a request sent to itself: the **mean** and the **95th percentile (p95)** of the **last 300 requests** the logger had recorded when the reading was taken. "localhost" means the guest talks to itself – **no network is involved**. `samples` is how many readings were averaged for the wait value.

> **Beginner tip:** **Notepad instead?** You can also open the file in Notepad (File Explorer → the folder of the first code line → right-click `cpu-storage-rehearsal.json` → **Open with** → Notepad). The "Output" is then **one very long line** with `\n` signs between the results. PowerShell shows the same text line by line, so use PowerShell.

### The evidence card – one source, one table

> **Recorded evidence card**
>
> - **Source:** the rehearsal file `cpu-storage-rehearsal.json`, entry "CPU" – a local file on the operator PC.
> - **Time:** the recorded window, 04:22:38–04:42:26 UTC (11:22–11:42 LT, UTC+7).
> - **What was done:** three Windows guests ran twelve busy workers for 900 seconds. The Linux guest and SQL stayed quiet.
> - **What it is:** recorded evidence from **one** test.
> - **What it is not:** not an Azure Monitor chart, not a real user's network path and not a service-level measurement.

Everything in the table comes from **the same file** – the six lines above. That is on purpose: numbers from one source do not contradict each other.

| **Phase (recorded window)** | **Host CPU (mean)** | **Linux guest: mean scheduling wait** | **Local web response: mean** | **Local web response: p95** |
|---|---|---|---|---|
| **Baseline** (before the load) | 25.82% | 48,408.94 ns | 1.623 ms | 4.357 ms |
| **Loaded** (the 900-second test) | **94.44%** | **85,539.54 ns** | **2.857 ms** | **7.843 ms** |
| **Recovery** (after the load) | 17.03% | 19,161.43 ns | 1.353 ms | 1.928 ms |
| Loaded compared with baseline | about 3.7 times | about 1.8 times | about 1.8 times | about 1.8 times |
| Difference (loaded − baseline) | +68.6 points | +37,130.6 ns | +1.23 ms | +3.49 ms |

**How to read the card.** **(1)** Read down the **host CPU** column: about a quarter busy, then almost full, then recovered. **(2)** Read across the **loaded** row: while the host is full, the Linux guest's **wait** is about 1.8 times longer **and** its web server answers about 1.8 times slower – on average and at the p95. **(3)** Read the **recovery** row: everything returns to normal by itself. **(4)** Look at the **size**: 1.2 milliseconds more on average, 3.5 milliseconds more at the p95. A person would **not notice** that. The card shows the **direction**, not a damage report.

> **Say this:** "Here is the same event seen from the user's side. On the Linux guest a small logger timed its own web server. At rest it answered in 1.6 milliseconds. While the host was full: 2.9 milliseconds, and the slow cases – the 95th percentile – went from 4.4 to 7.8 milliseconds, almost twice as long. After the test it was back to 1.4. Nothing inside the Linux guest changed. It simply had to **wait for a processor**, and its web server answered slower. A user would not notice one millisecond – but this is the **mechanism**: when a host makes a guest wait, the work of that guest gets slower. And the guest's own CPU chart cannot tell you why."

### Part 3 – The limit: what Azure Monitor does not measure

> **Do this:** Go back to the Grafana page of part 1. Scroll to the top. Look at the table **GUIDED HYPOTHESES** and read its **first row**, then the row **Nested-host contention**.

The top of the same page, with the recorded window selected, shows these parts in reading order:

- **(1)** The **machine** selector: RHEL94-GUEST. (Close the side menu to make room for the table.)

- **(2)** The **time range**: the recorded 35 minutes.

- **(3)** The two tiles: **Attention: No observed breach** and **Confidence: Adequate – 100%**. The Linux guest itself broke no rule in this window and its data is complete.

- **(4)** The **first row**: Application availability – **NotCollected** – **NotCollected**. The "Supporting" cell says "None: application availability not collected".

- **(5)** The **Missing** cell of that row: "**App probes, business SLO and request latency not collected**". This is the dashboard saying in its own words: we do not measure response time.

- **(6)** A row that **is** supported: Nested-host contention – "Supporting sampled signal" – "Nested host CPU high for 14 sampled minutes; pressure, **NOT proven contention**".

> **Say this:** "The first row of this table is the honest one: Application availability – NotCollected. In this lab Azure Monitor measures the hosts, the guests, the disks and SQL Server – it does **not** measure how fast a web page answers. The response numbers I showed come from a small logger **inside** the Linux guest, recorded on the day. I show them as **recorded evidence of direction**, not as a service-level measurement. If you want response time on the dashboard, that is a design item for your own implementation – an application probe or application telemetry."

> **Good to know:** Hyper-V reports **wait time per dispatch** in nanoseconds, not a "CPU ready" percentage of time. Both describe the same problem: a virtual machine wants to run but has to wait for a physical processor. Do **not** apply thresholds written for a different unit. A scheduling number tells you **why** something could be slow; only an application measurement tells you **how slow** it was.

> **Be honest:** "This wait is in nanoseconds per dispatch. It is not a CPU-ready percentage, and a sample percentile is not the percentile of every individual dispatch. The test also does not prove an outage – it proves the **mechanism**."

> **Be honest:** "The web response numbers were measured **inside** the Linux guest against its own web server. They are **not** a real user's network path, **not** an Azure Monitor measurement and **not** a service-level result. They come from **one** test on **one** day. The Windows guests waited **more** than the Linux guest (up to about 800,000 nanoseconds): the Linux guest is the **light** victim, not the worst-waiting guest."

> **Beginner tip:** **Why do the card and the charts show different numbers?** The card is a **summary of a few samples** written into the file during the test: the host CPU of **94.44%** is the average of 30 samples taken during the load, and the baseline wait of **48,408.94 ns** is the average of only 6. The Workbook and Grafana charts draw **every minute**: their host plateau reads about **95–98%** and the Linux guest's resting wait about **20,000 ns**. Same event, different sampling. Quote the **card's numbers as one set**; do not mix a card number and a chart reading in the same sentence.

> **If something goes wrong:** **Do not run a separate web-latency test, send web requests to the Linux guest or log in to it during the demo.** The file is enough; a live measurement is a separate test and is not part of this demonstration. If the file is not on the PC, say "recorded evidence from the test day" and show the table above – it is the same data. **When the recorded window is older than 30 days**, the Grafana parts (1 and 3) are empty because recorded data is deleted after 30 days; the file and the card stay valid.

## 3.6 The same facts from PowerShell (optional)

This block asks Azure Monitor for the **host CPU** of 3.2 as a query. It does **not** contain the web response – that exists only in the file of 3.5.

> **Where to run it:** **Optional PowerShell** (Operator PC, read-only): run a query for the same interval. First get the workspace ID, then run the query. Replace `<INCIDENT_DATE>` with the date of the recording in the form `YYYY-MM-DD` before you run the block.

**Host CPU every 5 minutes for the recorded test**

```powershell
$ws = az monitor log-analytics workspace show --subscription $SUB -g $RG -n law-arc-monitor-lab --query customerId -o tsv
$q = 'Perf | where TimeGenerated between (datetime(<INCIDENT_DATE>T04:22:00Z) .. datetime(<INCIDENT_DATE>T04:43:00Z))
| where Computer == "HV-HOST-01" and ObjectName == "Hyper-V Hypervisor Logical Processor" and CounterName == "% Total Run Time" and InstanceName == "_Total"
| summarize AvgCPU=avg(CounterValue) by bin(TimeGenerated,5m) | order by TimeGenerated asc'
az monitor log-analytics query --subscription $SUB --workspace $ws --analytics-query $q -o table
```

> **If something goes wrong:** If `az` says a Log Analytics extension is missing, skip this PowerShell step. The Portal chart already proves the point.
