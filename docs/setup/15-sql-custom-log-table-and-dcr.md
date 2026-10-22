# 15. Precise SQL custom-log table and SQL Perf DCR

This chapter creates the custom Log Analytics table `HvSqlMemory_CL`, which holds the SQL memory samples written by the collector from [chapter 14](14-sql-memory-ceiling-and-what-it-means.md). It then verifies or deploys the Data Collection Rule (DCR) `dcr-sql-servers`, so that both the SQL performance counters and the collector's JSON log file reach the correct workspace and table, and finally proves ingestion with queries. Use it after the Azure Monitor Agent and the other DCRs are in place ([chapter 11](11-azure-monitor-agent-and-dcrs.md)). The **Logs** page of the Log Analytics workspace is where you type and run the KQL queries in this chapter.

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables (such as `$RG` and `$ArcPrefix`) and the `Invoke-Lab*` helpers that it provides. The table schema is `lab-kit/schema/memory-table.json` and the rule payload is `lab-kit/dcr/dcr-sql-servers.json`.

## 15.1 Create the custom table before its DCR

**What you are doing:** you create the custom Log Analytics table first. This order matters. A DCR is a Data Collection Rule, which tells Azure Monitor what to collect and where to send it.

In the Azure Portal, the inspection route is **law-arc-monitor-lab > Tables**.

Use this sequence:

1. Open the Log Analytics workspace **law-arc-monitor-lab**.
2. Click **Tables**.
3. Do not use the generic Portal custom-text wizard as a substitute for the required JSON-schema creation path.
4. From the operator PC, run the command below to create `HvSqlMemory_CL`.
5. Return to **Tables**.
6. Inspect the new table's schema and retention settings.

Keep these facts exact:

- `TimeGenerated` is datetime.
- Memory and count fields use the types defined in `lab-kit/schema/memory-table.json`.
- Do not let a text-log wizard silently replace fields used by the workbook.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
$lawId = az monitor log-analytics workspace show -g $RG `
  -n law-arc-monitor-lab --query id -o tsv
Invoke-LabAz rest --method put `
  --url "https://management.azure.com$lawId/tables/HvSqlMemory_CL?api-version=2022-10-01" `
  --body '@schema\memory-table.json' -o none
```

**What you should see:** the table is provisioned with the schema, not just a custom string column containing the entire JSON. This changes only the lab workspace in the lab resource group.

## 15.2 SQL Perf and file source

**What you are doing:** you verify or deploy the DCR so that SQL performance counters and the JSON log file both flow into the correct workspace and table.

In the Azure Portal, go step by step:

1. Open **Data collection rules**.
2. Open `dcr-sql-servers`.
3. Confirm the region is the primary region (the region of the lab resource group).
4. Open **Data sources**.
5. Check the Windows SQL performance counters. The interval must be **15 seconds**.
6. Use the exact existing instance prefix `SQLServer` for the default instance.
7. Do not use `MSSQL$...` unless a named instance actually exists.
8. Verify Memory Manager counters for Total/Target/Free/Database Cache/Stolen Server Memory and Memory Grants Pending.
9. Verify SQL CPU/throughput/storage counters only where present.
10. Verify the JSON file pattern `C:\HV-Demo\logs\sql-memory-*.json`.
11. Verify stream `Custom-HvSqlMemory`.
12. Verify destination output table `Custom-HvSqlMemory_CL`.
13. Verify source values are converted to the expected types.
14. Verify destination `law-arc-monitor-lab`.
15. Verify the associated resource is the **SQL2019-GUEST Arc machine**.
16. Do not associate this rule with the Windows noisy neighbours.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
Invoke-LabAz monitor data-collection rule create -g $RG `
  --name dcr-sql-servers --rule-file .\dcr\dcr-sql-servers.json -o none
$ruleId = az monitor data-collection rule show -g $RG -n dcr-sql-servers --query id -o tsv
Invoke-LabAz monitor data-collection rule association create `
  --name assoc-SQL2019-GUEST-sql --rule-id $ruleId `
  --resource "$ArcPrefix/SQL2019-GUEST" -o none
```

**What you should see:** source names, schema and output stream all agree, and the association exists. The DCR payloads in the lab kit contain no machine IDs, secrets or tokens and are not token-bearing environment files. The only identifiers in `dcr-sql-servers.json` are the destination workspace resource ID (`/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-hyperv-arc-monitor-demo/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab`) and the location `<PRIMARY_REGION>`. If you have not replaced the placeholders with your own values (`tools/Set-RepoContext.ps1 -Apply`, [section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), do it before you deploy; `Deploy-LabMonitoring.ps1` also refuses a workspace ID that is outside the lab resource group. The machine is attached only by the association created above, never inside the rule file.

You do not have to run these two sections by hand if you already ran `Deploy-LabMonitoring.ps1` in [chapter 11](11-azure-monitor-agent-and-dcrs.md): it creates both custom tables from `lab-kit/schema/*-table.json` and all four rules, and it skips an association that already attaches the same rule to the machine. `lab-kit/sources/demo-v22/deploy-memory.ps1` is the single-purpose alternative: it creates `HvSqlMemory_CL`, `dcr-sql-servers` and the association `assoc-SQL2019-GUEST-sql` in one run (and writes `memory-table.json` and `dcr-sql-servers.json` next to itself as run-time files), ending with `SQL memory table and DCR created and associated.`

## 15.3 Prove ingestion before the demo

**What you are doing:** you confirm that the SQL memory custom table and the SQL Perf counters are actually ingesting data before you rely on them.

In the Azure Portal, follow these steps:

1. Open the workspace.
2. Click **Logs**.
3. Set the time range to **Last 30 minutes**.
4. Run the custom table query.
5. Run the SQL Perf query.
6. Confirm both show the SQL guest and real recent timestamps.

> **RUN ON - your own computer, PowerShell with Azure CLI**

```powershell
Invoke-LabQuery -QueryFile .\queries\sql-memory.kql `
  -OutputPath .\exports\sql-memory.json
Invoke-LabQuery -QueryFile .\queries\counter-inventory.kql `
  -OutputPath .\exports\counter-inventory.json
```

> **PASTE INTO - law-arc-monitor-lab, Logs, KQL**

```kql
HvSqlMemory_CL
| where TimeGenerated > ago(30m)
| where Computer =~ "SQL2019-GUEST"
| extend NonFreeCommittedMB=TotalMemoryMB-FreeMemoryMB
| project TimeGenerated,Stage,MaxMemoryMB,TotalMemoryMB,FreeMemoryMB,
    NonFreeCommittedMB,CacheMemoryMB,GrantAllocatedMB,GrantUsedMB,
    PendingGrants,ProcessMB,OsAvailableMB
| order by TimeGenerated asc
```

**What you should see:** values that match locally sampled DMVs within the normal sampling and ingestion delay, not exactly the current SSMS millisecond. If a stage file changes from idle to load, its label identifies the test phase, not proof of query activity. Use the real grant fields and the workload result together. The `exports` folder is created by `Invoke-LabQuery` inside `lab-kit`; it holds query results from your own workspace, so do not commit it.
