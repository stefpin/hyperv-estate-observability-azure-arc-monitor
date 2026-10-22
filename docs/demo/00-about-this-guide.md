# About this guide

This guide is the demo storyline and chart-reading guide for a reference implementation of host-to-SQL observability for a Hyper-V estate: one Azure VM (`HV-HOST-01`) running nested Hyper-V with five guests, monitored with Azure Arc, Azure Monitor, Log Analytics, an Azure Workbook and Azure Managed Grafana. This first file explains what the guide is, the safety rules that keep a demonstration harmless, the callout boxes used throughout, the four places where you work, how to handle UTC and local time (UTC+7), and the placeholders in angle brackets. Read it once before you present, and keep section 1.5 at hand whenever you quote a time.

## 1.1 What this document is

This is a **demo storyline**. It tells you what to show, in which order, what to say, and exactly where to click or type. It is written for a beginner. If you have never used Azure, Grafana, SQL Server or PowerShell, you can still follow it.

The goal is simple: **earn the audience's trust**. You do this by telling one clear story, using real evidence from the lab, and being honest about what the evidence proves and what it does not prove.

This guide is about **the story, not the setup**. Everything you will show is already built in the resource group `rg-hyperv-arc-monitor-demo`. You do not need to install or configure anything while you present. For build and setup details, use the setup guides in [`docs/setup/`](../setup/) and the build kit in [`lab-kit/`](../../lab-kit/).

**How to find your way.** The guide is split into several files in `docs/demo/`. The number at the start of each file name gives the reading order. Files `00` to `05` hold this introduction, the story and the chart-reading guide; the remaining files of the folder continue with the demo acts and the reference material.

## 1.2 The five safety rules (read them twice)

- **Everything in this storyline is read-only.** You look, you scroll, you change the time range, you click links. You do **not** create, save, delete, install, assess, schedule or restart anything. Keep SQL Server running: do not stop, restart or reconfigure the SQL Server service, `SQL2019-GUEST` or any other guest during a session.

- **Never click these buttons:** `Edit` then `Save` in the Workbook, `Run assessment` or `Schedule assessment` on the SQL page, `Check for updates`, `One-time update`, `Schedule updates`, `Update settings`, `Start`, `Stop`, `Restart`, `Delete`, `Enable`, `Reconfigure`, `Create`. Do not add e-mail recipients, action-group receivers or other notification channels during a demonstration. Treat such a change like any other production change and take it through your normal change process.

- **Always say which kind of evidence you are showing:** Live (happening now), Recorded (a real past event, replayed), Configuration (a setting, not an event) or Not shown. A replay is always labelled as a replay and shown with its time range. Never present a recorded chart as if it is live.

- **Never show secrets.** Do not open files that contain environment details, passwords, keys or links with tokens. If a sign-in box appears, type the password only in the box and never display it where the audience can read it.

- **Stay inside the lab resource group.** An Azure subscription can contain resources that have nothing to do with the demonstration. Always filter by `rg-hyperv-arc-monitor-demo` (the steps in the acts show how) so that unrelated resources never appear on the screen.

> **Say this:** "This is a read-only demonstration. Everything you will see comes from monitoring data that is already collected. We will tell you clearly when something is live, when it is a recorded real event, and when it is only a configuration."

## 1.3 The callout boxes used in this document

Callouts are block quotes that start with a bold label. The label tells you what kind of help the box gives.

| **Box** | **What it means** |
|---|---|
| **Say this** | Words you can read aloud to the audience. Change them to your own style, but keep the facts. |
| **Do this** | Actions you perform: click, type, scroll. |
| **Where to run it** | Tells you which window to use: Azure Portal, Grafana, or PowerShell on your own computer. |
| **What you should see** | The result that tells you the step worked. |
| **If something goes wrong** | A safe fallback. Never try to "fix" the lab during a demo. |
| **Be honest** | Exact words to use when a limit applies. This protects your credibility. |
| **Beginner tip** | Small helpers: shortcuts, explanations of terms. |
| **Numbered parts (1, 2, 3 ...)** | The parts of a page or a chart, listed in the order you read them. The text describes what you see for each number and refers to it later as "item 1", "item 2" and so on. |

Some files also use **Warning** (a risk to the lab or to the demonstration) and **Why** (the reason behind a step).

## 1.4 Four places where you work

Beginners often type the right thing in the wrong window. Use this table before every step.

| **Place** | **How to open it** | **What you do there** |
|---|---|---|
| **Azure Portal** | Open a web browser (Microsoft Edge). Go to `https://portal.azure.com`. Sign in with your lab account. | Resource pages, the Workbook, alerts, SQL, updates, Change Tracking, Logs (KQL queries). |
| **Grafana** | Open the dashboards listed in the [dashboard list](../../monitoring/README.md), by title in Grafana or at `https://<GRAFANA_ENDPOINT>/d/<DASHBOARD_UID>`. Sign in with the **same** account. Each Grafana instance can ask for its own sign-in. | Infrastructure & SQL Operations Cockpit ("Operations Cockpit"), PDF & Excel Evidence Report ("Evidence Report"), Command Center V1, V2 and V3 Core, and the Frozen shift health report ("Shift Report"). The Shift Report dashboard is generated for each report by the [shift-report app](../../shift-report/README.md) at run time, so it is not one of the shipped dashboards. |
| **PowerShell on your own computer** (Operator PC) | Click **Start**, type `PowerShell`, open **Windows PowerShell**. Azure CLI (`az`) must already be installed. | Optional repeatable checks with `az` commands. Read-only. |
| **Inside the lab (Bastion)** | Azure Portal → Virtual machines → `HV-HOST-01` → **Connect** → **Bastion**. | Only for generating live workloads. **Not used** in this storyline because it replays recorded events. |

> **Where to run it:** Do **not** use Azure Cloud Shell for the commands in this guide. Cloud Shell is a different computer. It does not have your files or the lab variables. Always use **Windows PowerShell on your own PC**.

## 1.5 Time zones – this avoids 80% of confusion

Azure stores most times in **UTC**. Local time (**LT**) in this lab is **UTC + 7 hours**. The Workbook and the Grafana dashboards show times in the time zone of the browser, so on a presenter computer that is set to UTC+7 the axes on the screen are in LT. The setup guides quote UTC. In this guide every clock time is written in UTC first, with LT in brackets where it helps. Use this table; it lists the recorded lab results (real events that the acts replay) and the fixed schedule of the shift report.

| **Event** | **UTC** | **Local time (LT, UTC+7)** |
|---|---|---|
| Recorded CPU scene (three Windows guests busy) | 04:22–04:42 | **11:22–11:42** |
| Recorded storage scene (SQL data volume busy) | 04:44–04:51 | **11:44–11:51** |
| Recorded SQL memory-grant scene | 04:13–04:22 | **11:13–11:22** |
| Real alert: Fired | 07:46:00 | **14:46:00** |
| Same alert: automatically Resolved | 08:16:58 | **15:16:58** |
| Real CPU episode on WIN2022-GUEST (Command Center replay – **recommended**) | 07:45–08:00 | **14:45–15:00** |
| Real CPU episode on WIN2022-GUEST (alternative replay, on the following day) | 00:38–00:41 | **07:38–07:41** |
| Automatic shift-report e-mails (when automatic dispatch is enabled) | 23:00, 07:00, 15:00 | **06:00, 14:00, 22:00** every day |

The recorded CPU scene, the storage scene, the first SQL memory-grant run and the real alert all fall on the same day, written `<INCIDENT_DATE>` in this guide (the second SQL memory run was recorded on another day; see [reading the charts](03-reading-charts-cpu-memory-storage.md)). The alternative replay is on the following day (in UTC and in LT).

> **Beginner tip:** Add "UTC" or "local time" every time you say a time. Say "eleven twenty-two local time", not just "eleven twenty-two".

> **If something goes wrong:** Avoid starting **new** heavy queries during the report windows 22:50–23:10 UTC, 06:50–07:10 UTC and 14:50–15:10 UTC (05:50–06:10, 13:50–14:10 and 21:50–22:10 LT). The automatic shift report is being produced then. Scrolling pages that are already open is fine. The shift report is described in [Act 10](21-act-10-reports-that-arrive-by-themselves.md).

## 1.6 Placeholders

Text in angle brackets, such as `<INCIDENT_DATE>`, stands for a value that you replace with your own before you run a command or type a prompt. Every placeholder used in this guide is explained once, in the table below. None of them is a secret.

| **Placeholder** | **What to put there** | **Used in** |
|---|---|---|
| `<REPO_ROOT>` | The folder on the Operator PC that holds the repository: the folder that contains `docs`, `lab-kit`, `monitoring`, `shift-report` and `tools`. | Acts 0, 3, 6, 7 and 10, Appendix A |
| `<SUBSCRIPTION_ID>` | The ID of the Azure subscription that holds the lab. The code folders of the repository use the same placeholder; [`tools/Set-RepoContext.ps1`](../../tools/Set-RepoContext.ps1) writes your value into them. | Act 0 |
| `<GRAFANA_ENDPOINT>` | The endpoint of your Azure Managed Grafana instance, shown on the **Overview** page of the instance in the Azure Portal. A dashboard address has the form `https://<GRAFANA_ENDPOINT>/d/<DASHBOARD_UID>`. | Section 1.4, reading guide 5, Acts 9, 10 and 11 |
| `<DASHBOARD_UID>` | The unique ID of a dashboard: the last part of its address, for example `hv-operations-cockpit`. The IDs of the shipped dashboards are in the [dashboard list](../../monitoring/README.md). | Section 1.4, Act 11 |
| `<INCIDENT_DATE>` | The recording day: the day of the recorded CPU, storage and SQL-memory scenes and of the real alert. In KQL and PowerShell write it as `YYYY-MM-DD`. All these events fall on the same date in UTC and in LT. | Section 1.5, reading guides 2 to 5, Acts 3 to 7 and Act 8B |
| `<INCIDENT_START>`, `<INCIDENT_END>` | Start and end of the recorded incident hour in UTC, in ISO 8601 form with a trailing Z (`YYYY-MM-DDTHH:MM:SSZ`): 07:30:00 and 08:30:00 UTC on `<INCIDENT_DATE>` (14:30 to 15:30 LT). The hour contains the CPU episode (07:45 to 08:00 UTC) behind the alert of Act 6. | Act 11, capability checklist, Appendix D |
| `<FROM_MS>`, `<TO_MS>` | Start and end of a time window as epoch milliseconds (milliseconds since 1 January 1970, 00:00 UTC), the form that Grafana links use. Act 11, Step 3 shows how to compute them from `<INCIDENT_START>` and `<INCIDENT_END>`. | Act 11 |
| `<CPU_TEST_START>`, `<CPU_TEST_END>`, `<STORAGE_TEST_START>`, `<STORAGE_TEST_END>`, `<SQL_TEST_START>`, `<SQL_TEST_END>` | Start and end of the recorded CPU, storage and SQL-memory scenes, in UTC and in LT, as written on the checklist card. The values of the reference recording are in the table of section 1.5. | Appendix D |
| `<TEST_DATE>`, `<TEST_START_LT>`, `<TEST_END_LT>`, `<TEST_START_UTC>`, `<TEST_END_UTC>`, `<ALERT_FIRED_UTC>`, `<SLOW_START_LT>`, `<SLOW_END_LT>` | The date and times of the recorded tests and of the alert, as typed into the prompt cards of Act 8B. Each one is explained, with the values of the reference recording, in the table of [section 8B.1](19-act-8b-copilot-and-observability-agent.md). | Act 8B, Appendix F |
| `<DD Mon YYYY>`, `<HH:mm>` | The local date of a shift report (two-digit day, English month abbreviation, year) and its cut-off time (05:55, 13:55 or 21:55 LT), as they appear in the subject of the shift e-mail. | Reading guide 5, Act 10 |
| `<REPORT_ID>` | The identifier of one shift report. For a scheduled report it is `shift-` followed by the UTC send time (`shift-YYYYMMDDTHHMMSSZ`); a rehearsal uses `dryrun-` followed by a random identifier. It is part of the names of the three attachments (`HV-<REPORT_ID>.pdf`, `HV-<REPORT_ID>.xlsx` and `HV-<REPORT_ID>-workbook.pdf`). | Act 10 |
