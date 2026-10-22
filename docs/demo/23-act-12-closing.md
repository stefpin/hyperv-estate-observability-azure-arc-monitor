# Act 12. Closing – summary, limits, cost and access (minutes 116–125)

This is the presenter's script for the closing act of the demo storyline. Use it to summarise what the lab showed, to state its limits before the audience asks, and to answer the first questions on cost and access. The longer list of expected questions is in [Questions and answers](25-questions-and-answers.md); the full list of what is built is in the [capability checklist](24-capability-checklist.md).

## 12.1 The closing story

> **Say this:** "Let us summarise in five sentences. **One**: Azure Arc gives one inventory for Windows, Linux and SQL Server. **Two**: we showed a hidden problem – a guest waiting for the host – and a SQL memory number that is easy to misread, both with real recorded evidence. **Three**: alerts, patch governance, change tracking and shift reports happen automatically. **Four**: our dashboards tell you not just what they see but how much to trust it. **Five**: when your people ask in plain English, the AI shows its query, we check it against evidence, and nothing changes without a person. That is the approach this lab demonstrates for monitoring a Hyper-V estate."

## 12.2 What we did not show – say it before they ask

- SQL **waits, blocking chains and query text** are not collected in this version of the lab.
- **Application** availability, response times and traces are not part of this lab.
- **Capacity forecasting, right-sizing and automatic workload balancing** are not built.
- **No automatic root cause** and **no automatic remediation**.
- The host is a **nested lab host** in Azure. Do not quote the lab's CPU or storage numbers as physical-hardware capacity.
- **Patch installation** and reboots were not run during the demo; the schedule is a configuration.
- **AI answers can be wrong or incomplete.** In the reference run Copilot ignored "this resource group" and chose a wrong counter, and the Observability Agent missed seven alert rules until a follow-up question. That is why we check every answer. Its **autonomous operations** are a preview and were not shown.

## 12.3 Cost and access – say only what you can defend

- Azure Monitor, Log Analytics, Azure Arc and Azure Managed Grafana are **pay-as-you-go**. Cost depends on data volume, retention and the number of dashboard users. The setup chapter [Cost, continuous-operation safety and eventual teardown](../setup/25-cost-and-operations.md) shows how to view the cost of the lab resource group.
- At the time of writing, each Azure Managed Grafana instance is billed separately: an hourly charge per instance plus a monthly charge for each additional active user. Prices differ by region and change over time, so **check the current price for your region before quoting any number** – use the Azure Pricing Calculator (`https://azure.microsoft.com/pricing/calculator`) during the conversation.
- In this lab, access to every dashboard needs a **Microsoft Entra** sign-in. There are no anonymous links, no API keys and no e-mail from Grafana.
- The reference lab ran its four dashboard families (operations, Command Center V1, V2 and V3 Core) in four Grafana instances so that older generations stayed untouched as **fallbacks**; a production deployment would normally use one instance with several data sources (see the [dashboard list](../../monitoring/README.md)).
- **AI:** when the lab was built, Azure Copilot and the Troubleshooting Agent were included, and the **Observability Agent** was billed by use (Azure Agent Credits). The documentation gave two different caps per deep investigation, so check the current documentation for the figure before you quote it.
