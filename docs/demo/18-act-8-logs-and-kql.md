# Act 8. Ask your own question – Logs and KQL

Act 8 covers minutes 73–78 of the storyline (about 5 minutes). Its goal is to prove that the data is **open**: anyone with access can ask any question in a simple query language (KQL) and export the answer. Before you start, you need the Azure Portal and access to the Log Analytics workspace `law-arc-monitor-lab`. Everything in this act only reads data.

## 8.1 Open Logs

> **Where to run it:** **Azure Portal**.

> **Do this:** Top search box → type `law-arc-monitor-lab` → open the **Log Analytics workspace**. In the left menu click **Logs**. A welcome window and then the **Queries hub** appear. Close them with their **X** button (or press **Esc**). They are only tips.

The Logs page, when it first opens, shows these parts in reading order:

- **(1)** The Queries hub window. It lists sample queries. Close it.

- **(2)** The close **X**.

- **(3)** "Always show Queries hub" – switch it off if you do not want it every time.

## 8.2 Run a query

> **Do this:** At the top right of the query area, change **Simple mode** to **KQL mode**. Click inside the big empty query editor. Paste the query below. Click **Run**. Wait for the result.

> **Where to run it:** Paste this into the **Logs query editor** in the Portal. **Not** into PowerShell.

**KQL – which machines reported in the last 30 minutes?**

```kql
Heartbeat
| where TimeGenerated > ago(30m)
| where _ResourceId contains "/resourceGroups/rg-hyperv-arc-monitor-demo/"
| summarize LastSeen=max(TimeGenerated), Environment=any(ComputerEnvironment) by Computer, _ResourceId
| extend AgeMinutes = datetime_diff("minute", now(), LastSeen)
| order by Computer asc
```

This query is stored in [lab-kit/queries/heartbeat.kql](../../lab-kit/queries/heartbeat.kql); the [queries folder](../../lab-kit/queries/) holds the other ready-made queries of the lab, and [setup chapter 11](../setup/11-azure-monitor-agent-and-dcrs.md) explains the heartbeat check.

The result of the heartbeat query (six machines) shows these parts in reading order:

- **(1)** The query ran in **law-arc-monitor-lab** (see the header) with the time range set inside the query.

- **(2)** Six rows: every machine with its **LastSeen** time.

- **(3)** **Environment:** the host shows **Azure** (because it really is an Azure VM), the guests show **Non-Azure**.

- **(4)** **AgeMinutes** 0 or 1: all machines reported in the last minute or two.

> **Say this:** "This is the raw data under every chart you saw. Your own analysts can ask new questions – this query asks who reported in the last half hour. The answer: all six, within a minute or two."

> **Be honest:** "Notice the host says 'Azure': this lab host **is** an Azure virtual machine that simulates an on-premises estate. Arc does not make it physical, and we never pretend it does."

## 8.3 One more query and the export

> **Where to run it:** Paste into the **Logs query editor**.

**KQL – the SQL memory samples behind Act 5**

```kql
HvSqlMemory_CL
| where TimeGenerated > ago(30m)
| where Computer =~ "SQL2019-GUEST"
| project TimeGenerated, MaxMemoryMB, TotalMemoryMB, FreeMemoryMB, CacheMemoryMB, GrantAllocatedMB, GrantUsedMB
| order by TimeGenerated desc
| take 20
```

> **Do this:** Above the results, click **Export** (or the **…** menu) and choose **CSV**. A file downloads to your Downloads folder. Open it in Excel to prove it works.

> **Beginner tip:** A KQL query reads like a sentence: **take this table** (`Heartbeat`), then `|` **keep rows where** … `|` **summarize** … `|` **order by** … Each `|` passes the result to the next step.

> **Beginner tip:** **Next, in Act 8B:** not everybody writes KQL. We will ask **Azure Copilot** to write these queries from plain English – and we will check its homework.
