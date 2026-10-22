# Questions and answers

These are the technical questions a presenter is most likely to be asked after the demo, each with a short, honest answer. Use the list as a reference after the closing act. Where an answer points to an Act or a section, the details are in the script for that Act.

## Lab design and scope

| **Question** | **Short, honest answer** |
|---|---|
| Is this running on-premises? | No. It is an Azure-hosted nested lab that simulates an on-premises estate. Arc manages the machines; it does not make them physical. |
| Is WIN-CLUSTER-01 a real cluster? | No. It is a tag that groups three Windows guests for monitoring. It is not failover clustering or high availability (see [setup chapter 1](../setup/01-scope-architecture-and-success-criteria.md)). |
| Is 2.5 : 1 CPU over-commitment safe? | There is no universal safe ratio. We showed what happens with 12 busy vCPUs on 8 processors and how to see the waiting. |
| Why are there two regions? | Some Azure Arc management features are not available in every region. The lab therefore registers the SQL guest, and uses a separate Change Tracking workspace, in a secondary region (Southeast Asia in this lab). This is a lab choice, not a design recommendation (see [setup chapter 1, section 1.3](../setup/01-scope-architecture-and-success-criteria.md)). |

## SQL memory

| **Question** | **Short, honest answer** |
|---|---|
| Is 9,829 MiB what SQL uses? | No. It is the ceiling (80% of detected RAM). SQL used about 1.1 GiB. Query grants and cache are different things. See [Act 5, section 5.5](15-act-5-sql-server.md). |
| Do the SQL memory numbers add up? | Yes – **if you add the parts to their own whole**: Free + Cache + OtherInternal = Committed (checked within 0.01 MiB in the recorded test). Do not add different wholes together (Committed + Cache, or Granted + Used). See [section 3.5 of the chart-reading guide](03-reading-charts-cpu-memory-storage.md#35-a-ceiling-and-what-is-really-used-sql-memory). |
| Why did committed memory stay flat in one run and rise in another? | Same query, different starting point. In the first recorded run SQL had about 331 MiB of empty space and used it; in the second run it had about 15 MiB and had to ask Windows for about 289 MiB more. Both are normal. See [section 3.5 of the chart-reading guide](03-reading-charts-cpu-memory-storage.md#35-a-ceiling-and-what-is-really-used-sql-memory). |

## CPU contention, evidence and dashboards

| **Question** | **Short, honest answer** |
|---|---|
| Why does a dashboard sometimes say "Insufficient"? | Because minutes are missing – for example a lab machine was switched off or still starting. The dashboard does not guess; it shows what is missing. While a machine runs, every minute arrives. See [section 3.9 of the block-and-tile guide](04-reading-charts-blocks-tables-graphs.md#39-coloured-blocks-and-tiles). |
| Is wait time the same as the "CPU ready" percentage that other virtualisation platforms report? | No. Different measure of the same problem. Do not compare the numbers. |
| Is the web response time in Azure Monitor or on the dashboards? | No. In this lab Azure Monitor measures hosts, guests, disks and SQL – not how fast a web page answers. The dashboard says so itself: Application availability – NotCollected. The web numbers (1.6 → 2.9 → 1.4 ms) were recorded by a small logger **inside** the Linux guest during the recorded CPU test and are shown as **recorded evidence of direction**. A response-time view needs an application probe or application telemetry – a possible extension. See [Act 3, section 3.5](13-act-3-the-cpu-story.md). |
| A slowdown of 1.2 milliseconds – does that matter? | Not to a person, and we do not claim it does. It shows the **mechanism**: when the host makes a guest wait, the guest's work gets slower, and the guest's own CPU chart cannot show why. It is one test on one day – not an outage and not a service-level result. See [Act 3, section 3.5](13-act-3-the-cpu-story.md). |
| Does it find the root cause automatically? | No. It gives evidence, supporting and missing facts, confidence and a next check. A person decides. See [Act 11](22-act-11-command-center-v1-v2-v3-core.md). |
| Can it do capacity forecasting or automatic workload balancing? | Not in this build. They are possible extensions. |

## Alerts, patching and reports

| **Question** | **Short, honest answer** |
|---|---|
| Did the alert and e-mail really work? | Yes, for one real recorded incident: the alert fired, resolved about 30 minutes later, and the e-mails were received. We do not claim every rule fired. See [Act 6](16-act-6-alerts.md). |
| Did the patch window run? | The schedule is configured and verified; we do not claim a past run in this demo. Installing patches and rebooting is disruptive and was not run. See [Act 7](17-act-7-safe-management.md) and [setup chapter 20](../setup/20-update-manager.md). |
| Can we get the reports? | Yes. Native PDF from the dashboards, CSV from tables, and an automatic shift e-mail three times a day (06:00, 14:00 and 22:00 local time, UTC+7). Each shift e-mail carries three attachments: the Grafana chart PDF (a summary page and eight chart pages), the Excel workbook of all evidence (20 sheets) and a PDF with the same content as the workbook. See [Act 10](21-act-10-reports-that-arrive-by-themselves.md) and the [shift-report README](../../shift-report/README.md). |

## Access, change and cost

| **Question** | **Short, honest answer** |
|---|---|
| Who can see the dashboards? | Only users who are granted access and sign in with Microsoft Entra. No anonymous links. |
| Does it change the monitored servers? | The dashboards only read. The monitoring agent and extensions collect data; they were installed during the lab build. |
| What does it cost? | Pay-as-you-go. Use the Azure Pricing Calculator with your data volume, retention and number of users. See [setup chapter 25](../setup/25-cost-and-operations.md) for cost visibility in the lab. |

## AI-assisted operations

| **Question** | **Short, honest answer** |
|---|---|
| Is the AI always right? | No. In the reference run Copilot ignored "this resource group" once and chose a wrong counter once, and the Observability Agent first missed seven alert rules. Its numbers were exact and one follow-up question fixed the gap. That is why we **check every answer** and the AI **shows its query**. See [Act 8B](19-act-8b-copilot-and-observability-agent.md). |
| Can the AI change the monitored servers? | Not in what we showed. The helpers read and advise, and they ask for consent. Saving an investigation (**Create Issue**) writes a record to Azure Monitor and is a separate, deliberate choice. The autonomous mode of the Observability Agent creates **issues**, not fixes. |
| Where does the data go? | The agents use **your** permissions and the telemetry already stored in your Azure Monitor workspace. At the time of writing, Microsoft documents that prompts and answers are **not used to train** the models and are kept up to 30 days; check the current documentation. The Observability Agent is a global service, so check the current documentation for where the processing happens if data residency matters. See [Act 8B, section 8B.8](19-act-8b-copilot-and-observability-agent.md). |
| What does the AI cost? | When the lab was built, Azure Copilot and the Troubleshooting Agent were included and the Observability Agent was billed by use (Azure Agent Credits). One deep investigation has a documented upper limit; check the current documentation for the figure before you quote it. See [Act 8B, section 8B.8](19-act-8b-copilot-and-observability-agent.md). |
| Does it work in languages other than English? | Azure Copilot is available in many languages; check the current documentation for the list. A reply can occasionally come in a language other than the one you used. The Observability Agent supports English best. Add "Answer in English." to a prompt to get English. |
| Will AI replace engineers? | No. It writes the first draft in seconds. An engineer who understands the data decides whether the draft is right. The example of the two CPU counters shows why. |
| Can it be switched off? | Yes. At the time of writing, a tenant administrator can allow or block Azure Copilot and each agent separately in the **Azure Copilot admin center** (Settings → Access management). |
| How do I judge an AI assistant? | Ask four questions of any AI assistant ([Act 8B, section 8B.6](19-act-8b-copilot-and-observability-agent.md), Scene 4): does it show the steps and queries it ran, does it say what it could not check, can it change things without my approval, and can I rerun what it did with my own tools (KQL, the CLI)? In this lab the answers were yes, yes, no and yes. |
