# 23. Reports, export and sharing the lab kit

This document explains how to build a report that someone else can reproduce later, how to export real tabular data from the Portal or from the lab kit scripts as CSV or Excel, what to include (and never include) when you share the lab, and where to find the optional automated shift report by e-mail. Use it after a rehearsal or a demonstration, when you need evidence with exact time boundaries rather than screenshots.

Commands in this document are written to run from the `lab-kit` folder (`cd lab-kit`) in a PowerShell session where the lab context has been loaded with `. .\context.ps1`.

## 23.1 Build a report with reproducible boundaries

**What you are doing:** In this step, you build a report that another person can reproduce later. The report must show the exact time range, scope, query outputs and limits. A screenshot alone is not enough.

> **Do this on:** the Azure portal in a web browser on the operator PC for the workbook route, and on the operator PC in PowerShell for the export script route.

Portal clicks:

1. Open the saved workbook.
2. Select the exact custom UTC interval.
3. Select the machine or cluster scope.
4. Click **Apply**.
5. Click **Refresh**.
6. Include host CPU, guest wait, group/per-guest memory, per-volume/VHDX storage, SQL ceiling/committed/non-free/cache/grants and real management/alert results.
7. Record the lab kit build or commit, the time zone, the scope, the sampling, the units and the limitations.

CLI path: `Get-LabEvidence.ps1 -OutputDirectory .\exports\report` (`lab-kit/Get-LabEvidence.ps1`) exports the non-secret cloud configuration (`arc-machines.json`, `resources.json` and `alert-rules.json`), the output of five queries (`heartbeat`, `counter-inventory`, `sql-memory`, `storage-windows` and `cpu-wait`; their sources are the files of the same names in `lab-kit/queries/`) and `snapshot-time.txt`, which holds the UTC time of the export. The queries keep the time window that is written inside their `.kql` files, so copy and edit a query when you need an exact window (the `between` filter in [section 17.3](17-cpu-contention-and-response-time.md#173-baseline-load-and-recovery-are-separate-windows) shows how). Record the UTC start and end of each rehearsal scene next to the export; do not merge the CPU, storage and SQL scenes into one ambiguous workload interval.

> **Do this on:** your operator PC, in PowerShell with Azure CLI, in the `lab-kit` folder with the lab context loaded. Run the exact command below; it is read-only.

```powershell
.\Get-LabEvidence.ps1 -OutputDirectory .\exports\report
```

**What you should see:** the script ends with `Read-only public evidence export completed; no guest commands or Azure writes.` A report reader can reproduce each observation from the workspace, the KQL and the timestamps. A written guide is not itself the telemetry report or evidence of an exported workbook.

## 23.2 Portal CSV / Excel export

**What you are doing:** This step exports real tabular data from the workbook or from Logs. The result must be an actual CSV or Excel file that opens and contains rows.

> **Do this on:** the Azure portal in a web browser on the operator PC for the export clicks, then on the operator PC for the CLI conversion route.

Portal clicks:

1. In the workbook, go to the tabular query results.
2. If you see **Export to Excel** or **Download as CSV**, click that control.
3. If a chart does not show an export control, click **Edit**.
4. Open the **underlying query** or **Logs** route.
5. Run the same query with the same time range.
6. Click **Export**.
7. Choose **CSV**.
8. Download to the non-secret exports directory.
9. Open the CSV in Excel.
10. Inspect the headers, UTC timestamps, numeric units and machine rows.

Export success means a real readable file, not a screenshot of an export menu.

> **Do this on:** your operator PC, in PowerShell with Azure CLI, in the `lab-kit` folder with the lab context loaded. Run the exact commands below.

```powershell
Invoke-LabQuery -QueryFile .\queries\sql-memory.kql `
  -OutputPath .\exports\sql-memory.json
.\Convert-LabQueryToCsv.ps1 -JsonPath .\exports\sql-memory.json `
  -CsvPath .\exports\sql-memory.csv
```

**What you should see:** the query JSON contains real tabular rows, either as raw tables/columns/rows or in Azure CLI's flattened row-array form; the converter handles both. The CSV contains the corresponding headers and data. Verify at least one actual row, not just a header. `Convert-LabQueryToCsv.ps1` prints `CSV written with <n> real rows.` and refuses to write a file when the query returned no rows (`No query rows: refusing an apparently successful empty report.`). Do not export `ENVIRONMENT.txt` or include credentials as report columns.

For the five tables that the estate demonstration uses, `lab-kit/sources/demo-v22/export-report.ps1` takes no parameters and writes five CSV files that cover the last four hours:

- `HV-SQL-Memory-Stages.csv`: committed memory, cache, peak granted and used workspace memory and pending grants per memory stage;
- `HV-SQL-Granted-Versus-Used.csv`: the largest unused workspace grant of the `query-grants` stage;
- `HV-Guest-Contention.csv`: mean, P95 and peak CPU wait per dispatch for each guest;
- `HV-RHEL-Storage.csv`: the RHEL disk samples;
- `HV-SQL-Database-Inventory.csv`: the databases of the SQL Arc instance, with state, size and compatibility level.

The files go to the `reports-output` folder in the repository root, which is git-ignored. The script reads Log Analytics through `lab-kit/sources/demo-v22/query-la.ps1`, whose default `-WorkspaceId` is a sentinel GUID; if you have not yet given the workspace ID of `law-arc-monitor-lab` to `tools\Set-RepoContext.ps1` as `-WorkspaceId`, do that first ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)). Run the memory scene ([section 22.4](22-rehearsal-scenes.md#224-sql-memory-scene-then-retained-cache)) shortly before, so that the stage and grant tables have rows.

> **Do this on:** your operator PC, in PowerShell with Azure CLI, in the `lab-kit` folder. Run the exact command below.

```powershell
.\sources\demo-v22\export-report.ps1
```

**What you should see:** one line `Report <file name>: <n> bytes.` for each CSV file in the folder. A file of only a few bytes has no rows, which is accurate when the scene was not run in the last four hours but is not a report: open each file and verify at least one data row.

## 23.3 Sharing the lab kit

**What you are doing:** This is the set of files to share with anyone else who will build or run the lab. It should give them the non-secret documents and public helpers they need, without sharing private secrets.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visual walkthrough, and on the operator PC for the lab kit inspection.

Portal steps:

1. Show the saved workbook.
2. Show the Arc SQL instance link.
3. Show the supported management links.
4. Show the actual alert rules.
5. Explain that anyone reusing the lab deploys it in their own subscription and under their own governance.

Share the documentation plus the **public scripts, schema and queries** in `lab-kit/` and the non-secret evidence exports. Never share lab passwords, a SQL product key, personal Red Hat account credentials, an onboarding token or `ENVIRONMENT.txt`.

CLI path: inspect the repository [README](../../README.md), the [lab kit README](../../lab-kit/README.md), the public resource settings and the exported reports. Source and helper paths are documented, and the scripts do not assume that any folder from the machine where the lab was built exists on yours.

## 23.4 Automated shift report by e-mail (optional)

**What you are doing:** The reports of sections 23.1 and 23.2 are built by hand. The repository also contains an optional, separately deployed service that builds a shift-end report from the same telemetry and e-mails it automatically: the Azure Functions application in [`shift-report/`](../../shift-report/README.md). Nothing else in the lab depends on it, and it sends nothing until you deploy it in your own subscription, review it and open its gates deliberately.

> **Do this on:** your operator PC, to read the two documents below. Building, deploying and enabling the application is a separate decision for your own environment; it is not a step of the lab build.

Read these two files first:

- [`shift-report/README.md`](../../shift-report/README.md): what the application does, what to edit (the environment constants at the top of `shift-report/app/domain.py` and `shift-report/app/automation.py`, and the brand images), how to run its 173 offline tests, how to re-pin the send policy with `shift-report/tools/pin_policy.py`, the reference ARM templates in `shift-report/infra/` and the rehearsal to run before any gate is opened.
- [`shift-report/app/CONTRACT.txt`](../../shift-report/app/CONTRACT.txt): the operator-facing contract with the routes, the ledger states, the approval schema, the budgets and the activation checklist.

In short:

- The e-mail is sent three times a day, at 06:00, 14:00 and 22:00 local time (UTC+7, no daylight saving), which is 23:00, 07:00 and 15:00 UTC. The source cutoff is five minutes before each boundary and the source window is the eight hours before it.
- It has **three attachments**:

| Attachment | Content |
|---|---|
| `HV-<reportId>.pdf` | A summary page and exactly eight native Grafana chart pages |
| `HV-<reportId>.xlsx` | Every evidence dataset in full, the query provenance and the plotted chart data (20 sheets) |
| `HV-<reportId>-workbook.pdf` | Every cell of the Excel file rendered as PDF pages |

- Two small inline images in the HTML body are not attachments. The subject has the form `Hyper-V Estate - Shift Report - <date> - Cutoff <time> LT` (the cutoff is 05:55, 13:55 or 21:55 LT; a `[TEST]` suffix marks rehearsals), and the documents and images together may not exceed 5 MiB.
- Missing or stale telemetry produces the status *INSUFFICIENT EVIDENCE*, never a healthy one.
- The application is safe by default: `SEND_ENABLED`, `SCHEDULE_ENABLED` and `AUTO_SEND_ENABLED` are `false` until you set them, scheduled sending also needs `AUTO_SEND_POLICY_SHA256` to equal the hash of the pinned policy file, and a manual send needs a per-report approval that names the report ID and the hash of the exact e-mail envelope. Missed timers are never back-filled, and an interrupted submission is never resent automatically.

The chart pages come from a Grafana report dashboard that the application generates at run time. The eleven Grafana dashboards that you import yourself, including the Operations report page `hv-operations-report` (**PDF & Excel Evidence Report**), are described in [`monitoring/README.md`](../../monitoring/README.md). The application depends on PyMuPDF, which is licensed AGPL-3.0 or commercially: read [`NOTICE.md`](../../NOTICE.md) before you deploy or redistribute it.

**What you should see:** you can name the three attachments, the three daily dispatch times and the gates that keep the application silent until you open them. Nothing in this chapter sends an e-mail.
