# 18. Workbook - deployment, navigation and accurate time windows

This chapter deploys the Azure Monitor workbook **Hyper-V and SQL Estate Report** (definition version 2.2) from `lab-kit/workbook-hyperv-estate-v2.2.json`, explains how to read it section by section, and shows how to use its time range correctly, including how to label a historical replay honestly. A workbook is an Azure Monitor dashboard/report made from queries and visuals. When it works, the workbook opens in the Azure Portal and shows a live host CPU chart and the other sections listed in section 18.2. Use it after the data sources it reads are flowing ([chapter 11](11-azure-monitor-agent-and-dcrs.md), [chapter 15](15-sql-custom-log-table-and-dcr.md) and [chapter 16](16-storage-telemetry.md)).

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables (such as `$RG`) and the `Invoke-Lab*` helpers that it provides.

## 18.1 Deploy the workbook

**What you are doing:** you deploy the workbook definition from `lab-kit/workbook-hyperv-estate-v2.2.json`. Paste the serialized workbook content, not an ARM resource envelope (the JSON wrapper that describes an Azure resource). You can do this in the Portal (the clicks below) or with `lab-kit/Deploy-LabWorkbook.ps1`, which uploads the same definition through the REST API.

In the Azure Portal, follow these exact clicks:

1. Search **Monitor > Workbooks**, or open the `law-arc-monitor-lab` workspace and then open **Workbooks**.
2. Click **New**.
3. Click **Edit**.
4. Click **Advanced Editor** using the `</>` control.
5. Choose Gallery/Workbook JSON as appropriate.
6. Open `lab-kit/workbook-hyperv-estate-v2.2.json` in a text editor.
7. Paste **the serialized workbook content**, not an ARM resource envelope.
8. The file you paste is already the serialized definition. The ARM envelope is the separate file `lab-kit/workbook-resource.json`; its `properties.serializedData` holds the same definition as a string, and only `Deploy-LabWorkbook.ps1` uses it.
9. Click **Apply**.
10. Verify every section, parameter and workspace target.
11. Click **Save**.
12. Set the display name to `Hyper-V and SQL Estate Report`.
13. Save it in this lab resource group.
14. Use the region of the lab resource group (`<PRIMARY_REGION>`), the same value as `location` in `lab-kit/workbook-resource.json`.
15. When updating, leave the already published workbook ID intact.
16. Do not create anonymous duplicates without recording the chosen ID.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
.\Deploy-LabWorkbook.ps1
az resource list -g $RG --resource-type Microsoft.Insights/workbooks `
  --query "[].{Name:name,Id:id,Region:location}" -o table
```

**What you should see:** a saved workbook (definition version 2.2) with actual data. `Deploy-LabWorkbook.ps1` reads `lab-kit/workbook-resource.json`. The file has no `id`, so the script uses the fixed workbook ID `/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-hyperv-arc-monitor-demo/providers/Microsoft.Insights/workbooks/00000000-0000-0000-0000-000000000005` (the Grafana dashboards of `monitoring/` link to this ID). It checks that the ID is inside the lab resource group and ends in a GUID, writes the request body to `workbook-put.json` beside itself, PUTs it with API version 2022-04-01 (the first run creates the workbook, later runs update it in place) and ends with `Saved workbook: <id>. Open Portal and validate every tab.` The script saves the workbook under the display name `Hyper-V and SQL Estate Report` from `workbook-resource.json`, the same name that the Portal route above uses. A Portal chart and a REST resource upload are not identical validation paths; perform both.

## 18.2 Reader navigation

**What you are doing:** you walk a reader through the workbook and explain what each area is for.

In the Azure Portal, open **Hyper-V and SQL Estate Report** in **Read mode**.

Follow this reading flow:

1. Confirm that it has **31 validated query panels** (27 Log Analytics queries, three Azure Resource Graph queries and the one Azure Resource Manager database inventory panel).
2. For live checks, set the time range to **Last hour** (the shortest preset; the presets are 1 hour, 4 hours, 24 hours and 7 days, and the default is 4 hours) or choose a custom window.
3. The workbook has one parameter, **Time range**. The workspace and the machines are fixed inside the panel queries, so there is no machine or group selector.
4. Navigate through estate/heartbeats (the Arc inventory and reporting-health panels sit after the storage panels in the workbook).
5. Navigate through host CPU.
6. Navigate through per-guest wait.
7. Navigate through the three-member group.
8. Navigate through Windows and Hyper-V storage.
9. Navigate through Windows and RHEL memory.
10. Navigate through Linux device IOPS, latency and detail.
11. Navigate through SQL ceiling, committed, cache, grants and headroom.
12. Navigate through the native SQL database inventory.
13. Navigate through CT (Change Tracking) file changes and SQL services.
14. Navigate through Update Manager assessment/history.
15. Remember that CT panels target `law-arc-ct-sea` (the Change Tracking workspace in the secondary region), not the monitor workspace.
16. Keep the full management and Alert blades in separate tabs for actions/details.
17. Refresh after ingestion.

Keep these implementation details exact when explaining the workbook:

- The SQL database inventory uses an **ARM GET panel, queryType 12, JSONPath `$.value[*]`**, and returns **seven databases**: the four system databases plus `OrdersDemo`, `BillingDemo` and `ReportingDemo`.
- Resource Graph exposed zero SQL child database rows in this lab, so a Resource Graph database-child query is not a valid substitute.
- Memory charts use **showLegend=true, showMetrics=false**: a time-series SUM of MB samples is not meaningful allocated memory.

Azure CLI can retrieve workbook JSON and run the underlying KQL, but it cannot reproduce the interactive visual workbook renderer. Use `lab-kit/Get-LabEvidence.ps1` for numeric equivalence; use the Portal to validate layout, legends and time filtering.

**What you should see:** all query fields match the current schema. If a tile is blank, add an explicit troubleshooting note explaining why (for example no data in the selected time range or workspace). Do not manually insert an invented value.

To re-run the 31 panel queries from the command line, use `lab-kit/sources/demo-v22/validate-workbook.ps1`. It reads the queries in `lab-kit/sources/demo-v22/workbook-queries.json`, replaces the workbook time range with the last 6 hours, runs the Log Analytics, Resource Graph (needs the Azure CLI `resource-graph` extension, `az extension add --name resource-graph`) and ARM panels, and writes `workbook-validation.json` beside itself. It calls `query-la.ps1`, whose `-WorkspaceId` default is a sentinel GUID in the published copy. If you have not yet given the workspace ID of `law-arc-monitor-lab` to `tools\Set-RepoContext.ps1` as `-WorkspaceId` ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), replace that default in `lab-kit/sources/demo-v22/query-la.ps1` with the workspace ID first.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
az monitor log-analytics workspace show -g $RG -n law-arc-monitor-lab --query customerId -o tsv
.\sources\demo-v22\validate-workbook.ps1
```

**What you should see:** the first command prints the workspace ID (its `customerId`), the value for `Set-RepoContext.ps1 -WorkspaceId` or for the default in `query-la.ps1`. The script then prints one line `Validated <panel name>: <n> rows.` per panel, 31 in all. A panel that shows 0 rows had no data in the last 6 hours, for example the Change Tracking panels before the first change in [chapter 21](21-change-tracking-and-inventory.md).

## 18.3 Historical replay is allowed only when labelled

**What you are doing:** you explain how to use a recorded rehearsal window honestly. Historical replay is allowed only if you label it clearly as historical.

In the Azure Portal:

1. Select the recorded UTC custom window.
2. Label it **Recorded rehearsal `<START_UTC>`-`<END_UTC>` UTC**.
3. Explain clearly that it is not live.
4. For live mode, show recent timestamps.
5. Do not use a historical success window while saying "this is firing now."

For the query route, export the underlying KQL for that same window, along with the resource scope, units and stage timestamps. Replaying data is valid reporting; altering thresholds or counters to fabricate a result is not.
