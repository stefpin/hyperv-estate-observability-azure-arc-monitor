# Documentation

Two complementary bodies of documentation sit next to the code. They are written for people who will build, operate
or present the lab, so they explain *where* every step runs, give the exact commands, say what you should see and what to
do when you do not.

* **[Operator guide](setup/)** - build the lab and its monitoring from an empty subscription, verify each stage and keep
  it healthy. Chapters build on each other; start at the first incomplete chapter, not at the top.
* **[Presenter storyline](demo/)** - how to read every dashboard and chart, a scene-by-scene demonstration (Acts 0 to 12,
  plus Act 8B on Azure Copilot and the Observability Agent), a capability checklist, questions and answers and
  appendices.

Related pages: [architecture notes](architecture.md), [lab kit](../lab-kit/README.md),
[dashboards](../monitoring/README.md) and the [shift-report application](../shift-report/README.md).

Conventions used throughout: commands that run on your own computer are PowerShell unless stated; `<SUBSCRIPTION_ID>`,
`<TENANT_ID>`, `<PRIMARY_REGION>` and `<SUFFIX>` are placeholders (see [chapter 2](setup/02-tools-secrets-and-conventions.md)
and `tools/Set-RepoContext.ps1`); times are given in UTC with local time (UTC+7, "LT") alongside.

## Operator guide

| Guide | What it covers |
|---|---|
| [1. Scope, architecture and success criteria](setup/01-scope-architecture-and-success-criteria.md) | What the lab is and how to tell that it is complete: machines and sizing, network and storage layers, the region and identity map, and the completion checks. |
| [2. Tools, command locations and secret handling](setup/02-tools-secrets-and-conventions.md) | Where each command runs, how to replace the repository placeholders, open the lab kit on the operator PC, handle passwords and installation media, and copy the kit to the host. |
| [3. Build order and change gates](setup/03-build-order-and-change-gates.md) | The order of work and the change gates that keep a running lab safe; read it before you create, delete, restart or reinstall anything. |
| [4. Azure foundation: resource group, network, NAT, Bastion and workspaces](setup/04-azure-foundation.md) | Resource provider check, resource group, virtual network, explicit outbound NAT, Azure Bastion and the Log Analytics workspaces. |
| [5. Create and access the Azure Hyper-V host](setup/05-create-the-hyper-v-host.md) | Create the Azure VM HV-HOST-01 that acts as the outer Hyper-V host, and reach it and its nested guests. |
| [6. Host operating system, Hyper-V and guest network](setup/06-host-os-hyper-v-and-guest-network.md) | Prepare the host operating system: initialize the data disk as F:, install the Hyper-V role and build the internal switch and NAT for the nested guests. |
| [7. Build all five guests and verify identities](setup/07-build-the-guests.md) | Build the three noisy-neighbour Windows guests and the dedicated SQL guest, and verify their identities. |
| [8. RHEL 9.4: registration, nginx victim and latency logger](setup/08-rhel-guest-and-linux-collectors.md) | Build the RHEL guest, register it, and install the nginx victim, the response-time logger and the storage observer. |
| [9. Lab-only Azure-VM disguise and IMDS protection](setup/09-lab-only-azure-vm-disguise-and-imds-protection.md) | The lab-only measures that let the Azure VM stand in for an on-premises server, and how to prove that the Azure metadata endpoint is unreachable. |
| [10. Azure Arc onboarding, resource tags and Arc Run Command](setup/10-azure-arc-onboarding.md) | Connect the lab machines to Azure Arc, apply the resource tags and verify Arc Run Command. |
| [11. Azure Monitor Agent and base collection rules](setup/11-azure-monitor-agent-and-dcrs.md) | Install Azure Monitor Agent on the Arc machines and confirm that the data collection rules have the right scope, sources and destination. |
| [12. SQL data/log disks and SQL Server 2019 installation](setup/12-sql-server-installation.md) | Prepare the SQL data and log disks, mount the installation media, install SQL Server 2019 and apply the patches. |
| [13. SQL Server enabled by Azure Arc - licence, dashboard and DB inventory](setup/13-sql-server-enabled-by-azure-arc.md) | Verify the SQL Server extension for Azure Arc, the licence type and what the built-in SQL Arc screens show. |
| [14. SQL memory ceiling - what allocated versus active means](setup/14-sql-memory-ceiling-and-what-it-means.md) | Define the SQL memory ceiling, configure it safely, explain every memory line without double counting, and create the demo databases and the least-privilege collector. |
| [15. Precise SQL custom-log table and SQL Perf DCR](setup/15-sql-custom-log-table-and-dcr.md) | Create the custom table HvSqlMemory_CL and the data collection rule for the SQL memory samples. |
| [16. Storage telemetry - host, per-VHDX and per-volume views](setup/16-storage-telemetry.md) | Verify the three storage views (host disks, per-VHDX and per-volume) and the RHEL disk observer, and show them separately and correctly. |
| [17. CPU contention, response time and the tagged Windows group](setup/17-cpu-contention-and-response-time.md) | The host-side CPU contention that a guest cannot see, the bounded CPU scene on the noisy neighbours and the response-time logger. |
| [18. Workbook - deployment, navigation and accurate time windows](setup/18-workbook.md) | Deploy the Azure Monitor workbook, read it section by section and set accurate time windows. |
| [19. Alerts - meaningful thresholds and Azure-native e-mail](setup/19-alerts.md) | Review, wire up and prove the alert rules and the Azure-native e-mail notification. |
| [20. Azure Update Manager - assessment, periodic checks and maintenance](setup/20-update-manager.md) | Azure Update Manager: assessment, periodic checks, the maintenance configuration and dynamic scope, and the pre/post guard runbook. |
| [21. Change Tracking and Inventory - separate secondary-region collection](setup/21-change-tracking-and-inventory.md) | Enable and verify Change Tracking and Inventory for the SQL Arc machine, and observe a deliberate, benign change. |
| [22. Rehearsal - four separate scenes, real exports and recovery](setup/22-rehearsal-scenes.md) | Rehearsal guide: read-only starting checks, separate CPU, storage and SQL memory scenes, and a closing pass over the management, alert and report results. |
| [23. Reports, export and sharing the lab kit](setup/23-reports-and-export.md) | Build reproducible reports, export tabular data as CSV or Excel, and share the non-secret lab kit. |
| [24. Troubleshooting - diagnose before changing](setup/24-troubleshooting.md) | Troubleshooting recipes: diagnose before you change anything. |
| [25. Cost, continuous-operation safety and eventual teardown](setup/25-cost-and-operations.md) | What the lab costs, the daily non-disruptive health checks for a continuously running lab, and how teardown works. |
| [26. Lab kit reference](setup/26-lab-kit-reference.md) | Reference for the lab kit: its layout, what each script or file family is for, and where it runs. |
| [27. Official references](setup/27-references.md) | The first-party Microsoft documentation that backs the behaviour described in the guides. |

## Presenter storyline

| Guide | What it covers |
|---|---|
| [About this guide](demo/00-about-this-guide.md) | Orientation for the storyline and chart-reading guide: the estate, the conventions, the placeholders and how to use the guide. |
| [The story, the cast and the tools](demo/01-story-cast-and-tools.md) | The one-page version: the story, the promises the demonstration proves, the machines, the tools and the storyline at a glance. |
| [Reading the dashboards: page anatomy and the five-step method](demo/02-reading-dashboards-anatomy-and-method.md) | How to read a dashboard: page anatomy, the Grafana time picker and the five-step reading method. |
| [Reading the charts: CPU, memory and storage](demo/03-reading-charts-cpu-memory-storage.md) | How to read the charts that carry the technical story: host CPU, scheduling wait, SQL memory with its ledger, granted versus used, storage latency and IOPS. |
| [Reading the charts: coloured blocks, tables, graphs, traps and AI answers](demo/04-reading-charts-blocks-tables-graphs.md) | The dashboard elements that carry a verdict: tiles, status strips, hypotheses, freshness, tables, graphs, common traps and AI answers. |
| [Reading cards, a worked incident and practice](demo/05-reading-cards-and-worked-examples.md) | Whole dashboards read end to end, a worked incident and practice questions. |
| [Act 0. Before the audience arrives](demo/10-act-0-before-the-audience.md) | Act 0: the preparation you finish before a demonstration. |
| [Act 1. Meet the estate](demo/11-act-1-meet-the-estate.md) | Act 1 (minutes 0-10): meet the estate. |
| [Act 2. One report to see it all – the Azure Workbook](demo/12-act-2-the-workbook.md) | Act 2 (minutes 10-18): one report to see it all, the Azure Workbook. |
| [Act 3. The CPU story – what a guest cannot see](demo/13-act-3-the-cpu-story.md) | Act 3 (minutes 18-32): the CPU story, what a guest cannot see. |
| [Act 4. The storage story – read the layers together](demo/14-act-4-the-storage-story.md) | Act 4 (minutes 32-42): the storage story, reading the layers together. |
| [Act 5. SQL Server – the data tier](demo/15-act-5-sql-server.md) | Act 5 (minutes 42-57): SQL Server, the data tier. |
| [Act 6. Alerts – warn before the phone rings](demo/16-act-6-alerts.md) | Act 6 (minutes 57-65): alerts that warn before the phone rings. |
| [Act 7. Safe management – patching and change history](demo/17-act-7-safe-management.md) | Act 7 (minutes 65-73): safe management, patching and change history. |
| [Act 8. Ask your own question – Logs and KQL](demo/18-act-8-logs-and-kql.md) | Act 8 (minutes 73-78): ask your own question with Logs and KQL. |
| [Act 8B. Ask in your own words – Azure Copilot and the Observability Agent](demo/19-act-8b-copilot-and-observability-agent.md) | Act 8B (minutes 78-93): ask in your own words with Azure Copilot and the Observability Agent. |
| [Act 9. The Grafana Operations Cockpit (minutes 93–101)](demo/20-act-9-grafana-operations-cockpit.md) | Act 9 (minutes 93-101): the Grafana Operations Cockpit. |
| [Act 10. Reports that arrive by themselves (minutes 101–105)](demo/21-act-10-reports-that-arrive-by-themselves.md) | Act 10 (minutes 101-105): reports that arrive by themselves. |
| [Act 11. Command Center V1, V2 and V3 Core – from dashboards to investigations (minutes 105–116)](demo/22-act-11-command-center-v1-v2-v3-core.md) | Act 11 (minutes 105-116): Command Center V1, V2 and V3 Core, from dashboards to investigations. |
| [Act 12. Closing – summary, limits, cost and access (minutes 116–125)](demo/23-act-12-closing.md) | Act 12 (minutes 116-125): closing with the summary, the limits, the cost and questions. |
| [Capability checklist – everything that is built](demo/24-capability-checklist.md) | Every capability in the environment, where to see it and how it is shown. |
| [Questions and answers](demo/25-questions-and-answers.md) | Technical questions you are likely to be asked, each with a short, honest answer. |
| [Appendices: command index, glossary, checklists and Act 8B prompt cards](demo/26-appendices.md) | Reference material: command index, glossary, before/during/after checklists and the Act 8B prompt cards. |
