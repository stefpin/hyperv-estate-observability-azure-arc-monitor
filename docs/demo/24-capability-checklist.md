# Capability checklist – everything that is built

This checklist lists **every capability** in the demonstration environment, where to see it and how it is shown. Use it during rehearsal and tick each row. The section numbers 5.1 to 5.7 belong to this checklist only; the Act numbers are those of the storyline. **Mode:** **L** = live, **R** = recorded replay, **C** = configuration shown, **N** = exists but not demonstrated (say so).

## 5.1 Foundation – Azure Arc and the lab

| **#** | **Capability** | **Where to see it** | **Act** | **Mode** |
|---|---|---|---|---|
| 1 | Arc inventory of 6 machines, status Connected | Portal → Azure Arc → Machines (filter by resource group) | 1 | L |
| 2 | Two regions: the primary region and a secondary region (Southeast Asia in this lab) | Machine Overview → Location | 1 | C |
| 3 | Tags: logical group `cluster=WIN-CLUSTER-01`; patch tags `HvUmTarget`, `HvUmApproval` | Machine Overview → Tags | 1, 7 | C |
| 4 | Extensions: monitoring, change tracking, Defender, patching, SQL | Machine → Settings → Extensions | 1 | C |
| 5 | Secure access with Azure Bastion, no public IP | Virtual machine → Connect → Bastion | 1 | C |
| 6 | Heartbeat / reporting freshness of all machines | Workbook table; Logs query; cockpit tiles | 2, 8, 9 | L |

## 5.2 The Workbook – all 31 panels

The Workbook `Hyper-V and SQL Estate Report` (definition version 2.2, see [setup chapter 18](../setup/18-workbook.md)) has **31 chart and table panels** plus a header, an introduction and the time-range picker. The column **Panels** adds up to 31.

| **#** | **Workbook panel(s) – title keywords** | **Panels** | **Act** | **Mode** |
|---|---|---|---|---|
| 7 | Header, introduction and **Time range** picker (Custom = replay) | – | 2 | L/R |
| 8 | **Host hypervisor processor utilization (%)** | 1 | 3 | R |
| 9 | **Per-guest scheduling wait** (ns per dispatch) chart and **Per-guest contention evidence** table (mean, P95, peak) | 2 | 3 | R |
| 10 | **Guest-reported processor utilization (%)** | 1 | 3 | R |
| 11 | **WIN-CLUSTER-01** – CPU of three 4-vCPU members, physical RAM in use, scheduling wait per dispatch | 3 | 3 | R |
| 12 | **Windows physical memory in use per machine (%)** and **RHEL guest-reported used memory (%)** | 2 | 3 | L |
| 13 | **Configured ceiling, SQL-manager committed and process footprint (MiB)** | 1 | 5 | R |
| 14 | **SQL-manager free, database cache and other/internal memory (MiB)** | 1 | 5 | R |
| 15 | **Query workspace: peak granted and paired actual-use snapshot (MiB)** | 1 | 5 | R |
| 16 | **Memory stages and observed allocation/use** (table: idle, query-grants, recovery) | 1 | 5 | R |
| 17 | **SQL guest OS headroom (MiB) and grant-pressure count** | 1 | 5 | R |
| 18 | **SQL memory counters independently collected by AMA** (second source for the same memory) | 1 | 5 | L |
| 19 | **Host disks** read/write **IOPS** and **latency (ms)** | 2 | 4 | R |
| 20 | **Hyper-V virtual disk (VHDX)** read/write **latency** and **IOPS** | 2 | 4 | R |
| 21 | **Windows guest volume** **latency** and **IOPS** | 2 | 4 | R |
| 22 | **RHEL block-device** IOPS, operation-weighted latency and the **device to mounted-volume mapping** table | 3 | 4 | R |
| 23 | **Live SQL database inventory** (Arc ARM API) – seven databases | 1 | 5 | L |
| 24 | **Arc inventory and region/cluster membership** | 1 | 1 | L |
| 25 | **Reporting health - all six machines** (heartbeat table) | 1 | 1 | L |
| 26 | **Change Tracking** – real reversible file change; latest SQL service inventory | 2 | 7 | R |
| 27 | **Update Manager** – missing update inventory; actual installation history | 2 | 7 | L |
| 28 | Export hint and **Export to Excel** on every table (no extra panel) | – | 2 | L |
| | **Total query panels** | **31** | | |

## 5.3 SQL Server (Azure Arc), alerts, management and data

| **#** | **Capability** | **Where to see it** | **Act** | **Mode** |
|---|---|---|---|---|
| 29 | SQL instance overview: edition, version, pay-as-you-go licence | SQL Server instance → Overview | 5 | L |
| 30 | Native SQL Performance Dashboard | SQL instance → Monitoring → Performance Dashboard | 5 | L |
| 31 | Database list with status and last collected time | SQL instance → Data management → Databases | 5 | L |
| 32 | Best Practices Assessment and results (recorded lab result: 396 checks) | SQL instance → Settings → Best practices assessment | 5 | R |
| 33 | Backups, Availability Groups, SQL Server Connections menus | SQL instance menus | – | N |
| 34 | 17 alert rules with severities and thresholds | Monitor → Alerts → Alert rules → search `hv-` (definitions in [`lab-kit/alerts`](../../lab-kit/alerts/)) | 6 | C |
| 35 | A real Fired → Resolved incident | Alert instance page | 6 | R |
| 36 | Alert e-mail to the action group recipient, with receipts | Local receipt note `mail-receipt-evidence.json` (PowerShell, Act 6.3) | 6 | R |
| 37 | Periodic update assessment (recorded lab result: 4 updates) | Arc machine → Operations → Updates | 7 | L |
| 38 | Maintenance configuration: Monday window, Defender definitions only, never reboot | Maintenance configurations → `mc-hv-sql2019-definitions-gated` (setup chapter [20](../setup/20-update-manager.md)) | 7 | C |
| 39 | Safety guard (pre/post tasks) that can cancel a run | Same page; Automation account | 7 | C |
| 40 | Change Tracking (recorded lab result: 414 changes in 24 h) and Inventory | Arc machine → Operations → Change tracking / Inventory | 7 | L |
| 41 | Policies, Machine Configuration, Run command menus | Arc machine → Operations | 7 | N |
| 42 | Log Analytics workspace, Queries hub, KQL, CSV export | `law-arc-monitor-lab` → Logs | 8 | L |
| 43 | Separate Change Tracking workspace `law-arc-ct-sea` (Southeast Asia) | Workspace list | 7, 8 | C |

## 5.4 Grafana and reporting

| **#** | **Capability** | **Where to see it** | **Act** | **Mode** |
|---|---|---|---|---|
| 44 | Operations Cockpit with banner, freshness tiles, selectors | Grafana → `hv-operations-cockpit` ("Infrastructure & SQL Operations Cockpit") | 9 | L |
| 45 | Five sections: estate, CPU contention, SQL memory, storage layers, Arc/management | Cockpit → click the section titles | 9 | L |
| 46 | Native PDF download from a dashboard | Cockpit/report → Download native PDF | 9, 10 | L |
| 47 | PDF & Excel Evidence Report page | Grafana → `hv-operations-report` ("PDF & Excel Evidence Report") | 10 | L |
| 48 | The shift Excel workbook (20 sheets) and the native PDF of the Evidence Report page (about 17–18 pages) | The Excel attachment of a received shift e-mail and a PDF downloaded beforehand (File Explorer) | 10 | R |
| 49 | CSV export of the report evidence (last 4 hours, five files) | Operator PC PowerShell: `lab-kit\sources\demo-v22\export-report.ps1` (optional, see [Act 10](21-act-10-reports-that-arrive-by-themselves.md)) | 10 | N |
| 50 | Frozen shift health report dashboard (created at run time by the shift-report app; not shipped in `monitoring/grafana`) | Grafana → `hv-shift-health-report` | 10 | R |
| 51 | Automatic shift e-mail at 06:00, 14:00 and 22:00 LT (UTC+7) = 23:00, 07:00 and 15:00 UTC, with three attachments: the Grafana chart PDF, the Excel workbook of all evidence, and a PDF with the same content as the workbook (plus two inline brand images) | Recipient mailbox; design and safety gates in [`shift-report/README.md`](../../shift-report/README.md) | 10 | C |

## 5.5 Command Center V1, V2 and V3 Core

| **#** | **Capability** | **Where to see it** | **Act** | **Mode** |
|---|---|---|---|---|
| 52 | V1: Estate Overview, Workload Deep Dive, Incident Investigation, linked by machine and time | Grafana → Command Center V1 (`hv-cc-estate`, `hv-cc-workload`, `hv-cc-incident`) | 11 | L |
| 53 | V1: "form a hypothesis" table with next checks | V1 → 03 - Incident Investigation → row "01 - FORM A HYPOTHESIS" | 11 | L |
| 54 | V2: window guard, attention vs confidence vs native alerts | V2 → 01 / Estate attention | 11 | L |
| 55 | V2: native alert snapshot, configured relationship graph, Arc inventory | V2 → Estate (scroll) | 11 | L |
| 56 | V2: per-vCPU matrix, storage layers, SQL trends, peak grants with paired use | V2 → 02 / Workload evidence | 11 | L |
| 57 | V2: replay, episodes, zoom, before/during/after, CT chronology | V2 → 03 / Incident investigation (replay link) | 11 | R |
| 58 | V3: verified alert attribution and "Unattributed" honesty | V3 → Estate (scroll) | 11 | L |
| 59 | V3: current vs recovered vs historical alert lifecycle; group scope as context only | V3 → native alert tables | 11 | L |
| 60 | V3: six guided hypotheses with supporting, contradicting, missing evidence and confidence | V3 → 02 / Guided workload evidence and 03 / Incident replay & handoff | 11 | L/R |
| 61 | V3: replay of the recorded incident hour (`<INCIDENT_START>`–`<INCIDENT_END>` UTC) and one-click episode zoom | V3 → incident view → replay link or time range → Zoom episode ([Act 11, Step 3](22-act-11-command-center-v1-v2-v3-core.md)) | 11 | R |
| 62 | V3: read-only hand-over bookmark and RETURN TO LIVE | V3 → top row links | 11 | L |
| 63 | Fallback order: V3 → V2 → V1 → Operations Cockpit → Workbook | Act 11 (Beginner tip) | 0, 11 | C |

## 5.6 Governance, safety and cost

| **#** | **Capability** | **How it is shown** | **Act** | **Mode** |
|---|---|---|---|---|
| 64 | Read-only by design; no workloads, saves or sends in the demo | Safety rules at the start of the storyline | all | C |
| 65 | Microsoft Entra sign-in only; no anonymous access, no API keys | Closing | 12 | C |
| 66 | Pay-as-you-go cost model and cost boundaries | Closing | 12 | C |
| 67 | Honest limitations list | Act 12.2; "Be honest" callouts | 12 | C |

## 5.7 AI-assisted operations

| **#** | **Capability** | **Where to see it** | **Act** | **Mode** |
|---|---|---|---|---|
| 68 | Azure Copilot in the Portal and its helper menu | Portal header → Copilot | 8B | L |
| 69 | Plain-English Arc inventory (Copilot writes the Resource Graph query) | Copilot → Run in Resource Graph Explorer | 8B | L |
| 70 | Copilot writes KQL (heartbeat; host CPU with local-time-to-UTC conversion) | Logs (KQL mode) + Copilot | 8B | L/R |
| 71 | Find and fix an AI mistake (wrong counter → corrected query) | Logs + Copilot | 8B | R |
| 72 | "Explain this query" for beginners | Copilot | 8B | L |
| 73 | Observability Agent chat: ingestion and per-computer breakdown | Logs → Observability agent | 8B | L |
| 74 | Deep investigation of the recorded alert, graded against an answer key | Alert details → Investigate | 8B | R |
| 75 | Troubleshooting Agent: guided disk check (optional scene) | Virtual machine → Copilot | 8B | R |
| 76 | Autonomous operations, Azure Monitor issues, SRE Agent (preview) | Talk track only (Act 8B, section 8B.8) | 8B | N |
