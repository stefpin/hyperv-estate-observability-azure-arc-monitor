# The story, the cast and the tools

This file is the one-page version of the demo: the one-sentence story, the seven promises the demo proves, the machines in the lab, the tools and what each one shows, and the storyline at a glance with minute timings for the full session. Read it before you plan a session, and use the table in section 2.5 to choose between the full version, the short version and the AI-only version.

## 2.1 The one-sentence story

> **Say this:** "A list of virtual machines is only the start. We show you the **whole chain** – host, guests, disks, SQL Server – in one place, using **real recorded evidence**, and we tell you honestly **how much to trust each number**."

## 2.2 The seven promises we prove

| **Promise** | **How we prove it in the demo** | **Act** |
|---|---|---|
| **1. One view from host to SQL** | Azure Arc brings Windows, Linux and SQL Server into one inventory. One Workbook and the Grafana dashboards (Operations Cockpit, Evidence Report and three generations of Command Center) read the same data. | 1, 2, 9, 11 |
| **2. Hidden problems become visible** | A guest can look calm while the host makes it wait. We show host scheduling wait per guest next to guest CPU. | 3 |
| **3. Database insight, not just machine insight** | SQL memory ceiling versus real use, query memory grants, database inventory, best-practice assessment, patching. | 5, 7 |
| **4. It tells you before users call** | 17 alert rules, a real Fired → Resolved incident, and automatic shift reports by e-mail. | 6, 10 |
| **5. Honest evidence** | Every number shows its time, unit and confidence. Missing data is never painted green. | 11, 12 |
| **6. Open and under your control** | Your data stays in your own Log Analytics workspaces. You can query it (KQL), export it (CSV, Excel, PDF) and read-only access is built in. | 8, 10 |
| **7. AI that shows its work** | Anybody can ask in plain English. Azure Copilot writes the query, the Observability Agent investigates an alert, and **every answer can be checked against evidence**. Nothing changes without a person. | 8B |

## 2.3 The cast – what is in the lab

| **Machine** | **Role in the story** | **Details** |
|---|---|---|
| `HV-HOST-01` | The **host**. A Windows Server 2025 Hyper-V host. | 8 logical processors, 64 GB RAM. Deployed in the primary region. |
| `WIN2019-GUEST`, `WIN2022-GUEST`, `WIN2025-GUEST-01` | **Noisy neighbours.** Three Windows guests, 4 vCPU and 8 GB each. Tagged `cluster=WIN-CLUSTER-01`. | A **logical monitoring group**. Not Windows failover clustering. |
| `RHEL94-GUEST` | The **light victim.** A Red Hat Linux guest running a small web server (nginx). | 4 vCPU, 8 GB. |
| `SQL2019-GUEST` | The **database server.** SQL Server 2019 Enterprise, Arc licence type pay-as-you-go. Seven databases. | 4 vCPU, 12 GB. SQL memory ceiling 9,829 MiB. Arc region: a secondary region (Southeast Asia in this lab), because some management features are not available in every region. |

> **Be honest:** "This is a **demonstration lab**. The host is an Azure virtual machine running five nested guests. It simulates an on-premises estate. It is not a production design."

## 2.4 The tools – which one shows what

| **Tool** | **One-line description** | **Best used for** |
|---|---|---|
| **Azure Arc** (Portal) | The inventory and management layer for machines and SQL Server. | Who is in the estate? Connected? Which region? Tags? Extensions? |
| **Azure Workbook** `Hyper-V and SQL Estate Report` (definition version 2.2) | One long interactive report with 31 charts and tables. | Full technical walk-through, CPU, storage, SQL, history replay. |
| **SQL Server – Azure Arc** pages | Native SQL pages: performance, databases, best-practice assessment. | Database inventory and health checks. |
| **Azure Monitor alerts** | 17 alert rules (their names start with `hv-`), notifications by e-mail. | Proactive warning. |
| **Update Manager, Maintenance, Change Tracking** | Patching assessment, safe schedule, change history. | Governance and control. |
| **Log Analytics + KQL** | The place where all measurements are stored. | Ask your own question, export data. |
| **Azure Copilot** | An AI helper in the Portal header. Answers in plain English and writes Resource Graph and KQL queries. | Write and explain queries; understand Azure. |
| **Observability Agent** | An AI agent inside Azure Monitor: chat with your logs and investigate an alert. | First-pass investigation, always checked against evidence. |
| **Grafana – Infrastructure & SQL Operations Cockpit / PDF & Excel Evidence Report / Frozen shift health report** | Operations dashboard, printable report, and the frozen shift report dashboard. The shift report dashboard is generated for each report by the [shift-report app](../../shift-report/README.md) at run time, so it is not one of the shipped dashboards. | Daily operations and reporting. |
| **Grafana – Command Center V1, V2, V3 Core** | Three generations of investigation dashboards. | Find, explain and replay incidents with honest confidence. |

In the rest of this guide the Grafana dashboards are called by their short names: **Operations Cockpit**, **Evidence Report**, **Shift Report** and **Command Center V1**, **V2** and **V3 Core**.

## 2.5 Storyline at a glance (full version, about 125 minutes)

| **Act** | **Title** | **Minutes** | **Where** | **Key message** |
|---|---|---|---|---|
| 0 | Before the audience arrives | – | Portal, Grafana | Check the lab is healthy. |
| 1 | Meet the estate | 0–10 | Portal | Everything is in one inventory. |
| 2 | One report to see it all | 10–18 | Portal Workbook | 31 charts, one place. |
| 3 | The CPU story | 18–32 | Workbook | Guests can wait without knowing. |
| 4 | The storage story | 32–42 | Workbook | Storage has layers; read them together. |
| 5 | SQL Server – the data tier | 42–57 | Portal + Workbook | Ceiling is not usage. |
| 6 | Alerts | 57–65 | Portal | Warn before users call. |
| 7 | Safe management | 65–73 | Portal | Patching and change history under control. |
| 8 | Ask your own question | 73–78 | Portal Logs | Open data, KQL, export. |
| **8B** | **Ask in your own words – Copilot and the Observability Agent** | 78–93 | Portal | AI proposes, evidence disposes. |
| 9 | The Grafana operations cockpit | 93–101 | Grafana | Operations view and PDF/Excel. |
| 10 | Reports that arrive by themselves | 101–105 | Grafana + e-mail | Shift report e-mail three times a day. |
| 11 | Command Center V1, V2, V3 Core | 105–116 | Grafana | From dashboards to investigations. |
| 12 | Closing and Q&A | 116–125 | This guide | What the evidence proves – and what it does not. |

> **Beginner tip:** **Short version (about 45 minutes):** Act 1 (5 min), Act 3 (10 min), Act 5 (10 min), Act 6 (5 min), Act 11 (10 min), Act 12 (5 min). Skip the others but say what exists.

> **Beginner tip:** **AI mini-session (about 25 minutes):** Act 8 (5 min, the KQL basics) + **Act 8B** (15 min, scenes 1–4) + the AI part of Act 12 (5 min). Use it for an audience that already knows the rest of the demo, or as a follow-up session. Remember that the recorded scenes are only available for a limited time: check that they are still there before you rehearse (the guide for Act 8B describes the scenes).
