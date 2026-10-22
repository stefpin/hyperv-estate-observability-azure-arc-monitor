# Reading the dashboards: page anatomy and the five-step method

Charts are only useful if the audience (and you) read them correctly. This chapter is a reading guide: read it once before the demo, then use it as a reference. It has four parts, spread over files `02` to `05` of this folder, as the table below shows. This file starts the guide with the parts of a Workbook page and of a Grafana page, the controls that are safe to touch, the five-step method you apply to every chart and the units cheat sheet. Times are written in UTC first; local time (LT, UTC+7) is what the Workbook and Grafana axes show on a computer set to UTC+7, which is how the lab was run.

| **Section** | **What you learn** | **File** |
|---|---|---|
| **3.0** Anatomy of a page | The parts of a **Workbook** page and of a **Grafana** page: time range, selector, tiles, legend, tooltip, the (i) icon – and which controls are safe to touch. | `02` |
| **3.1 – 3.11** Chart by chart | The five-step method and the units cheat sheet, then how to read each kind of chart and table, with a real example for each: one line, several lines, a ceiling, two lines with a gap, latency with IOPS, bars, coloured blocks, tables, graphs. | `02` (3.1–3.2), `03` (3.3–3.8), `04` (3.9–3.11) |
| **3.12 – 3.13** Traps and AI answers | Seven traps to avoid and a six-question check for an AI answer. | `04` |
| **3.14 – 3.17** Dashboard by dashboard | A **reading card** for every dashboard (which panel first, what is normal, what needs attention), a **worked incident**, a **cheat sheet** and **practice questions with answers**. | `05` |

> **Beginner tip:** **Short on time?** Read **3.0** (the page anatomy), **3.1** (the five-step method), **3.9** (tiles and colours) and the **reading card** of every dashboard you will show. That takes about 25 minutes.

## 3.0 Anatomy of a dashboard page – read this first

Before you read any chart, learn the **parts of the page**. This demo has only **two kinds of pages**: the **Azure Workbook** (opened inside the Azure Portal) and the **Grafana dashboards** (opened in their own browser tab). They look different, but both are built from the same few parts: a **time range**, a **selector**, **tiles**, **charts**, **tables** and a **legend**. Learn them once and every dashboard in this guide becomes easier.

### 3.0.1 The Azure Workbook page

> **Where to run it:** **Azure Portal** → resource group `rg-hyperv-arc-monitor-demo` → the Workbook (Act 2 shows how to open it).

A Workbook page is built from the eight parts below, listed from the top of the page downwards. The example is the host CPU chart of the recorded CPU scene, shown for the recorded window 04:15–04:50 UTC (11:15–11:50 LT).

1. **Toolbar.** **Refresh** (the circular arrow) loads the charts again – safe. **Edit** opens the editor – **do not click**. The other icons (save, pin, feedback and similar) are not needed in a demo – leave them alone. "Auto refresh: Off" means the page never updates by itself.
2. **Introduction text.** Says what the page is and repeats the lab warning (a demonstration lab, not a production design). Read it once.
3. **Time range.** The most important control. "Last 4 hours" shows live data; **Custom** shows a recorded period. Every chart below follows this one setting.
4. **Chart title.** Says what is measured. The **unit is in brackets**: (%), (MiB), (ms) ...
5. **Vertical axis (Y).** The scale. **Every chart chooses its own scale**, so read the numbers on the left before you decide whether a line is "high".
6. **Horizontal axis (X).** Time, shown in local time (LT) in this lab. The distance between two labels is always the same.
7. **Legend.** Colour → name. **Colours are used again in every chart**: blue is "CPU" here, but "MaxMemoryMB" in one SQL chart and "FreeMB" in the next. Always read the legend of the chart in front of you.
8. **The line.** Every corner is one **measurement bucket** (an average of the samples inside it). Straight segments join neighbouring buckets. A **gap** means there was **no data**.

**How to set a Custom time range** (this is how every recorded scene in the storyline starts):

- Click the **Time range** box (item 3 in the list above).

- In the small list click **Custom**. The list has five choices: Last hour, Last 4 hours, Last 24 hours, Last 7 days and Custom.

- A window "Enter a custom time range" opens. Fill **Start Time** (a date box and a time box) and **End Time** (a date box and a time box). Example for the recorded SQL memory scene: start date `<INCIDENT_DATE>` and time `11:08:00 AM`, end date `<INCIDENT_DATE>` and time `11:26:00 AM`. Type the date in the format the box shows (the lab PC shows month/day/year). The times are in your computer's time zone – on the operator PC used for this lab this is local time (LT, UTC+7), so 11:08 AM is 04:08 UTC.

- After you type **each** box, press the **Tab** key once. This confirms the box.

- Click **OK** and wait about 15 seconds. The Time range box now shows your range, for example the date followed by "11:08 AM - 11:26 AM".

> **If something goes wrong:** If the Time range box becomes **empty with a small red mark** and the charts say "This query could not run because some parameters are not set. Please set: Time range", the range was **not accepted**. Open the box again, choose **Custom** again and press **Tab** after every box before you click **OK**.

### 3.0.2 The Grafana page

> **Where to run it:** **Grafana** (browser). Example page: "Command Center V3 Core - 03 / Incident replay & handoff" (Command Center V3 Core, page 03). All Grafana dashboards share the layout below; the [dashboard list](../../monitoring/README.md) names every dashboard and its address (uid).

A Grafana page is built from the eight parts below, listed from the top of the page downwards. The example is Command Center V3 Core, page 03, for the recorded window 07:30–08:30 UTC (14:30–15:30 LT).

1. **Selector** (here "Workload"). Choose the machine. Most panels follow it. The word "FIXED" in the selector label and in panel titles such as "CPU vs FIXED HOST" reminds you that the host panels always stay on `HV-HOST-01`.
2. **Time range.** Shows the start, the end and the time zone (LT when the browser is set to UTC+7). The arrows **«** and **»** move the window earlier or later by its own length. The magnifier zooms out. Click the text to type a new range (see 3.0.5).
3. **Refresh.** Loads the data again. The Command Center pages never refresh by themselves; the Operations Cockpit refreshes every 2 minutes.
4. **Navigation buttons.** Jump between related pages (01 Estate, 02 Workload, 03 Incident). The machine and the time range are carried over. **RETURN TO LIVE** goes back to the last hour.
5. **Tiles.** One big word or number each. Read the **small title** above it first (for example "WINDOW ATTENTION" and "SIGNAL CONFIDENCE").
6. **Panel title row.** The **(i)** icon shows what the panel measures and its limits (see 3.0.4). The box-with-arrow icon opens the panel full size.
7. **Table header.** A **funnel** icon filters the column; clicking the name sorts it. A wide table scrolls **to the right**.
8. **Make editable · Export · Share.** **Do not click.** They change the dashboard or export it. You never need them.

### 3.0.3 Hover: read the exact value of every line at one moment

A chart shows the **shape**; the **tooltip** shows the **numbers**. Move the mouse over a chart – **do not click**. A thin vertical line follows the mouse, and a small box lists the **time** and **one row per line** with its value at that moment.

The example is the tooltip of the CPU panel ("CPU vs FIXED HOST" in V3 Core, "OS vs FIXED HOST hypervisor" in V2) at 07:53 UTC (14:53 LT), with the mouse over the CPU plateau of the recorded incident. The tooltip has four parts:

1. **The time** of the point under the mouse (local time, as on the axis).
2. **One row per line:** colour, name, value. Here: the guest's own CPU 100.0%, host hypervisor total 97.8%, guest run time 94.4%, hypervisor run time 3.4%, host root OS 1.0%.
3. **The shape under the mouse** – the plateau.
4. **The legend table** under the chart. **Last** is the latest value in the time range; **Max** is the highest value in the time range.

**Reading this example.** At 07:53 UTC (14:53 LT) the guest reports that its CPU is 100%. The host's processors are 97.8% busy – and that value is exactly **94.4% (running guests) + 3.4% (the hypervisor itself)**. The host's own Windows ("root OS") sees only 1.0%. Three numbers that are all called "CPU" tell three different stories. This is why the V2 chart title says **"NOT the same CPU"** and the V3 Core title says "distinct CPU accounting".

> **Beginner tip:** Hover once on a **calm** minute before the event and once on a **busy** minute during it, and compare the two boxes. Beginners learn more from two tooltips than from ten minutes of looking at the line.

### 3.0.4 The (i) icon: the panel's own explanation

Hover the mouse over the **(i)** icon in the panel title row. A box opens with the panel's **description**. In the CPU panel of 3.0.3 the description says that the selected OS, the host's root OS and the hypervisor total are explicitly different, and that the nested logical-processor total is not the underlying physical cores. The V2 description adds that **missing, NotCollected and NotApplicable are not healthy zeros**.

The text in square brackets at the start of a description (for example "[query:compute-trends]") is only the internal name of the query that feeds the panel. Ignore it. Read the rest **whenever a number surprises you** – the dashboard tells you its own limits.

### 3.0.5 The Grafana time picker

Click the time range at the top of the page to open the time picker. It has five parts:

1. The **time range text** at the top. Click it to open the picker.
2. The **From** and **To** boxes. Type year-month-day and hours:minutes:seconds, for example `<INCIDENT_DATE> 14:30:00`, where `<INCIDENT_DATE>` stands for the date of the recorded incident in the form `YYYY-MM-DD`.
3. **Apply time range** – click it after typing.
4. **Quick ranges** on the right (Last 5 minutes … Last 24 hours). They are **live** ranges that end "now".
5. The **time zone**: the time zone of the browser, UTC+07:00 on the presenter computer. What you type is local time (LT), so `14:30:00` means 07:30 UTC.

> **Do this:** Click the time range at the top. In **From** type `<INCIDENT_DATE> 14:30:00`. In **To** type `<INCIDENT_DATE> 15:30:00`. Click **Apply time range**. Wait about 10 seconds.

> **If something goes wrong:** The Command Center pages accept **1 minute to 4 hours** only. A longer range shows "NoEvaluableWindow" or "no evidence". That is the **guard**, not an error. To avoid typing the range, build a link that already contains it, as shown in [Act 11, Step 3](22-act-11-command-center-v1-v2-v3-core.md).

### 3.0.6 What is safe to touch

| **Control** | **Safe?** | **What it does** |
|---|---|---|
| Move the mouse over a chart or the (i) icon | **Safe** | Shows a tooltip or an explanation. |
| Change the **selector**, the **time range**, press **Refresh** | **Safe** | Reads data again. Nothing is stored. |
| Click a **navigation button** or **RETURN TO LIVE** | **Safe** | Opens another page with the same machine and time range. |
| Click a **table header**, the **funnel** icon, the page numbers | **Safe** | Sorts, filters or pages the table on your screen only. |
| Click a **name in a chart legend** | **Safe** | Shows only that line. Click again to show all lines. |
| Click **Zoom episode** or "View query in Azure Portal" | **Safe** | Opens a closer view, or the query behind the table. |
| Workbook: **Edit**, **Save**, pin, clone | **Do not click** | Changes or copies the Workbook. |
| Grafana: **Make editable**, **Export**, **Share**, star | **Do not click** | Changes the dashboard or creates exports and share links. |
| Any button that **creates, saves, starts, stops, deletes, applies or deploys** something (section 1.2 of [About this guide](00-about-this-guide.md) lists them; the AI scenes add **Create Issue**) | **Do not click** | Changes Azure. The **Run** button of the Logs query editor is fine: it only reads. |

## 3.1 The five-step method – use it for every chart

1. **Read the title and the unit.** The title says what is measured (CPU %, wait in nanoseconds, MiB of memory). The unit tells you if a number is big or small.

2. **Read the time range.** Is it Last hour (live) or a Custom interval (recorded replay)? Times in the Workbook and Grafana are local time (LT, UTC+7) in this lab.

3. **Read the legend.** Each coloured line is one machine or one counter. In Grafana the legend table also shows **Last** (latest value) and **Max** (highest value in the range).

4. **Read the shape.** Look for three things: the **normal level (baseline)**, the **change** (a plateau, a spike, a step) and the **recovery** (does it return to normal?).

5. **Check the context.** Ask: what else must I look at with this chart? (Latency needs IOPS. CPU needs the host wait. A line that ends needs "was there data?")

## 3.2 Units cheat sheet

| **You see** | **It means** | **Quick conversion / hint** |
|---|---|---|
| **%** | Percent of capacity, for example CPU busy time. | 0–100. A flat 100% line means "at the limit". |
| **ns, µs, ms, s** | Nanoseconds, microseconds, milliseconds, seconds. | 1,000 ns = 1 µs. 1,000 µs = 1 ms. **800,000 ns = 0.8 ms.** |
| **ns/dispatch** | Time a virtual processor waited **each time** it was scheduled. | Not a percentage. Do not compare it with a ready-time percentage from another platform: it is a different measure. |
| **K, M** on an axis | Thousand, million. | "800K" = 800,000. "9.6K" = 9,600. |
| **MiB, GiB** | Mebibytes and gibibytes of memory or disk. | 1 GiB = 1,024 MiB. SQL ceiling 9,829 MiB ≈ 9.6 GiB. |
| **IOPS, io/s** | Input/output operations per second. | How **busy** a disk is. Not how fast. |
| **MiB/s** | Data moved per second. | Throughput. Different from IOPS. |
| **ms (disk)** | Latency: how long one disk operation takes. | Compare only when IOPS are meaningful. |
| **threads** | Processor queue length. | How many tasks wait for a processor right now. |
