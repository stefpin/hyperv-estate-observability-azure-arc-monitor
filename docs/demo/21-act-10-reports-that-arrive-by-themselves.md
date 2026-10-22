# Act 10. Reports that arrive by themselves (minutes 101–105)

This is the presenter's script for Act 10 of the demo storyline. Use it to show the "PDF & Excel Evidence Report" page, the "Frozen shift health report" dashboard and the automatic shift-report e-mail, which the Azure Functions app in [`shift-report/`](../../shift-report/README.md) sends three times a day with **three attachments**. **Goal:** show that evidence is **packaged for people who do not open dashboards**: a PDF, an Excel file, and an automatic e-mail three times a day. The Evidence Report is one of the dashboards shipped in [`monitoring/grafana/operations`](../../monitoring/README.md). The "Frozen shift health report" is **not** shipped: the shift-report app creates it **at run time** for every report it prepares (section 10.2).

## 10.1 The PDF & Excel Evidence Report page

> **Do this:** On the cockpit, click the button **PDF & Excel evidence**. (Or open `https://<GRAFANA_ENDPOINT>/d/hv-operations-report`.) Look at the page. Scroll one screen.

**What you should see (top of the page):**

1. The **Download native PDF** button in the link bar at the top of the dashboard (the other links are **Operations cockpit**, **Original Azure workbook** and **Existing alert rules - unchanged**).
2. A text block "Fixed-window evidence report": read-only, no automatic refresh, and the interval is captured for the PDF and Excel.
3. The same freshness tiles as on the cockpit ("ALL SIX EXPECTED - Reporting counts at interval end"): Fresh 6, Missing 0 when all six machines report.

**What you should see (after scrolling):**

1. "CPU - Selected OS metrics plus fixed host hypervisor": CPU of the selected machines together with the host hypervisor.
2. "HOST-SIDE - All five guests - P95 sampled dispatch wait": the host-side P95 dispatch wait for all five guests.
3. "SELECTED MACHINES - Physical RAM use - Windows / RHEL": physical memory use for Windows and RHEL.

| **Delivered file** | **What it is** |
|---|---|
| **PDF** | A native Grafana export of this page (the **Download native PDF** button: landscape, simple layout): real charts and tables, one visual panel per page, about 17–18 pages for the 18 panels of this page. Not a screenshot pasted into a PDF. |
| **Excel (.xlsx)** | Not produced by this page. The workbook is attachment 2 of the shift e-mail (section 10.3): 20 sheets with the shift summary, 16 evidence sheets with every exported row, the alert health, the query provenance (exact KQL, units and scope from `query-manifest.json`) and the plotted chart data. Not a renamed CSV. |

> **Do this:** To show finished files without running anything, open a PDF and an Excel workbook that you saved beforehand from a shift e-mail (section 10.3) or from a rehearsal report of the shift-report app (for example from File Explorer). The repository does not contain sample report files: you create them in your own lab.

> **If something goes wrong:** Those files are samples from an earlier report, not a current one. Say "this is a sample report produced in the shift-report format". Do not present them as a current production report.

> **Where to run it:** **Optional – download a fresh PDF of this page** only if the audience asks. **Grafana in the browser.** It reads data and writes one local file; it does not change Azure, save dashboards or send e-mail.

> **Do this:** Set the **time range** (top right) to a fixed window, for example the last hour, wait until every panel has loaded, then click **Download native PDF**. Grafana creates the PDF and your browser saves it in the Downloads folder.

> **If something goes wrong:** Check the interval printed on the PDF. Do not accept a PDF labelled **1970** or with an unexpected interval: the generic Grafana Export menu can pass dates incorrectly; the **Download native PDF** button uses the correct format.

> **Where to run it:** **Optional – CSV exports of the key tables** only if the audience asks. **Operator PC → Windows PowerShell.** The script runs read-only Log Analytics queries over the last four hours and one read-only Azure Resource Manager request, and writes **five new local CSV files**; it does not change Azure, save dashboards or send e-mail. It needs Azure CLI signed in, and the default `-WorkspaceId` of `query-la.ps1` must hold your workspace ID ([setup chapter 2](../setup/02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt); the script is described in [section 23.2 of the operator guide](../setup/23-reports-and-export.md#232-portal-csv--excel-export)). Open a CSV file in Excel if the audience wants to see a spreadsheet; the PDF and Excel pair of the shift report comes from the e-mail in section 10.3.

```powershell
Set-Location '<REPO_ROOT>\lab-kit\sources\demo-v22'
.\export-report.ps1
```

> **What you should see:** One line per CSV file with its name and its size in bytes. The five files `HV-SQL-Memory-Stages.csv`, `HV-SQL-Granted-Versus-Used.csv`, `HV-Guest-Contention.csv`, `HV-RHEL-Storage.csv` and `HV-SQL-Database-Inventory.csv` are written to the folder `reports-output` in the repository root, which the repository's `.gitignore` excludes.

## 10.2 The frozen shift report dashboard

> **Do this:** Open `https://<GRAFANA_ENDPOINT>/d/hv-shift-health-report`. Note the **time range** at the top. Scroll one screen.

> **Good to know:** This dashboard is **not** one of the files in `monitoring/grafana`. The shift-report app creates it at run time, in the Grafana folder with the uid `hv-shift-health`, every time it prepares a report: each report is saved as a new version of the same dashboard (version message "Immutable shift snapshot" plus the report ID). The address therefore always shows the **latest** report; earlier reports stay in the version history of the dashboard and in the attachments of their e-mails. If your lab has not prepared a report yet, the page does not exist: skip this section.

**What you should see:**

1. A **fixed** time range, for example 06:00 to 13:55 local time (UTC+7), which is 23:00 to 06:55 UTC: it starts eight hours before the send time and ends at the 5-minute cutoff before it. The report never moves: it is a **frozen** shift.
2. "CPU utilization (percent; processor queue excluded)": the CPU of every machine for the shift.
3. "Physical memory used (percent)". Then, further down, the other six charts: SQL memory, SQL query grants, Windows logical group IOPS, guest scheduling wait, storage rates and SQL activity. These eight charts are also the eight chart pages of the PDF attachment in section 10.3.

> **Say this:** "Every shift report freezes its numbers: the charts are drawn from the stored points of that shift, so the evidence does not change after the event. This page shows the newest shift; the PDF and Excel attachments of each e-mail keep the earlier ones."

## 10.3 The automatic shift-report e-mail

| **Item** | **Value** |
|---|---|
| When | Every day at **06:00, 14:00 and 22:00 local time (UTC+7, "LT")**, which is **23:00, 07:00 and 15:00 UTC**. The data stops 5 minutes earlier (05:55, 13:55 and 21:55 LT = 22:55, 06:55 and 14:55 UTC) and starts 8 hours before the send time. |
| Sent by | The shift-report app (Azure Functions, [`shift-report/`](../../shift-report/README.md)), on its own schedule. |
| Recipient | One configured recipient (for example `operator@example.com`), no copies. |
| Subject | `Hyper-V Estate - Shift Report - <DD Mon YYYY> - Cutoff <HH:mm> LT`. A rehearsal send adds ` [TEST]` at the end. |
| Content | An e-mail body with tables and two inline brand images, plus **three attachments** (see below). The combined size of the documents and the images is limited to 5 MiB. |
| Manual step | None per scheduled run once the gates below are open. Nobody has to press anything for the e-mail to be produced and sent. |
| Safety gates | Sending is **fail-closed**: the switches `SEND_ENABLED`, `SCHEDULE_ENABLED` and `AUTO_SEND_ENABLED` are off by default, the scheduled-send policy is pinned by a hash and only the one configured recipient is accepted. Nothing is sent until an operator has opened the gates ([Safety properties](../../shift-report/README.md#safety-properties)). |
| Failure behaviour | A missed or failed run is **not** made up later and is not replaced by an older report (no backfill). Missing or stale data is shown as "INSUFFICIENT EVIDENCE", never as healthy. |

The schedule in one table:

| **Send time (LT = UTC+7)** | **Send time (UTC)** | **Data cut-off (LT)** | **Data cut-off (UTC)** |
|---|---|---|---|
| 06:00 | 23:00 (previous day) | 05:55 | 22:55 (previous day) |
| 14:00 | 07:00 | 13:55 | 06:55 |
| 22:00 | 15:00 | 21:55 | 14:55 |

Every shift e-mail carries **three attachments**. The two brand images at the top of the message are inline images, not attachments. `<REPORT_ID>` is the identifier that the app gives to each report ([About this guide](00-about-this-guide.md)).

| **#** | **Attachment** | **What it is** |
|---|---|---|
| 1 | Grafana chart PDF (`HV-<REPORT_ID>.pdf`) | The shift's Grafana charts as a PDF: a summary page followed by exactly eight native Grafana chart pages (CPU, memory, SQL memory, SQL grants, Windows group IOPS, scheduling wait, storage rates, SQL activity). |
| 2 | Excel workbook (`HV-<REPORT_ID>.xlsx`) | All the evidence of the shift in one workbook: 20 sheets with the shift summary, every evidence dataset in full, the alert health, the query provenance and the plotted chart data. |
| 3 | PDF of the workbook content (`HV-<REPORT_ID>-workbook.pdf`) | A PDF that contains the same content as the Excel workbook, so the evidence can be read without Excel (formula results are shown as stored values; typically hundreds of pages). |

**What the e-mail body shows:**

- The overall status: MONITORED SIGNALS NORMAL, ATTENTION REQUIRED, CRITICAL CONDITION OBSERVED or INSUFFICIENT EVIDENCE.
- Fresh signals ("Required signals: N/14 fresh; expected machines: M/6 fresh").
- SQL memory.
- The top three CPU waits ("CPU contention - highest sampled P95").
- Storage highlights.
- The Windows logical group (not a failover cluster).
- The open items and actions.

A test or rehearsal send carries the line "TEST / REHEARSAL - not a scheduled shift" in the body and ` [TEST]` at the end of the subject; the real scheduled e-mails carry neither.

> **Say this:** "Nobody has to open a dashboard. Three times a day an e-mail arrives with the estate health in tables and three attachments: the chart PDF, the Excel workbook with all the evidence, and a PDF with the same content as the workbook. Fresh signals, SQL memory, the top three CPU waits, storage highlights and the open items."

> **Be honest - say exactly this:** "The service sends on its schedule and its format is fixed. 'Accepted for sending' is not the same as 'received in the inbox', and we do not promise that every future e-mail will be delivered."

> **Beginner tip:** You do **not** need to trigger or test anything. Never press any "send", "status" or "dispatch" link. If asked for proof, show an e-mail that has already arrived in the recipient mailbox, with the mailbox owner's permission.

How the app works, its safety properties, and how to deploy and rehearse it: [shift-report/README.md](../../shift-report/README.md) (see "The e-mail" and "Deploy") and the contract in [`shift-report/app/CONTRACT.txt`](../../shift-report/app/CONTRACT.txt). The operator guide gives a short summary in [section 23.4](../setup/23-reports-and-export.md#234-automated-shift-report-by-e-mail-optional).
