# 27. Official references

This document lists the first-party Microsoft Learn and documentation pages that back the behavior described in the guides: Azure Arc, Azure Monitor data collection rules and agents, SQL Server memory and Arc integration, Update Manager and its pre/post events, Change Tracking, nested Hyper-V, action-group e-mail, workbooks, Azure Managed Grafana and the Azure Functions application behind the shift report. Use it to confirm feature behavior before you change settings, and to check syntax against the current documentation. The documents of this repository are listed in [section 27.3](#273-documents-in-this-repository).

## 27.1 Microsoft references

**What you are doing:** Use these first-party references to confirm feature behavior before changing production settings. This keeps the guides grounded in Microsoft documentation.

> **Do this on:** a web browser for the documentation pages, and in the installed CLI for `--help` when you need command syntax confirmation. CLI extensions and API versions can evolve.

The link text is the page title or a short description. Microsoft moves documentation pages from time to time; if a link no longer opens, search Microsoft Learn for the page title.

### Azure Arc, the Azure VM and the lab network

- [Evaluate Azure Arc-enabled servers with an Azure virtual machine](https://learn.microsoft.com/azure/azure-arc/servers/plan-evaluate-on-azure-virtual-machine) - the evaluation procedure behind [Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md): the machine variable `MSFT_ARC_TEST` and the firewall rule that blocks the Azure metadata endpoint
- [Azure Arc-enabled servers overview](https://learn.microsoft.com/azure/azure-arc/servers/overview)
- [Azure Connected Machine agent overview](https://learn.microsoft.com/azure/azure-arc/servers/agent-overview)
- [Azure Arc agent connect/authentication](https://learn.microsoft.com/azure/azure-arc/servers/azcmagent-connect)
- [Azure Arc Run Command](https://learn.microsoft.com/azure/azure-arc/servers/run-command)
- [Azure Instance Metadata Service](https://learn.microsoft.com/azure/virtual-machines/instance-metadata-service)
- [Azure NAT Gateway](https://learn.microsoft.com/azure/nat-gateway/nat-overview)
- [Azure Bastion](https://learn.microsoft.com/azure/bastion/bastion-overview)
- [Nested Hyper-V](https://learn.microsoft.com/windows-server/virtualization/hyper-v/nested-virtualization)
- [PowerShell Direct](https://learn.microsoft.com/windows-server/virtualization/hyper-v/powershell-direct)
- [SetComputerNameExW (Windows computer-name API)](https://learn.microsoft.com/windows/win32/api/sysinfoapi/nf-sysinfoapi-setcomputernameexw)

### Azure Monitor: agent, data collection, alerts and workbooks

- [Log Analytics workspace overview](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-overview)
- [Azure Monitor Agent overview](https://learn.microsoft.com/azure/azure-monitor/agents/azure-monitor-agent-overview)
- [Azure Monitor data collection rules](https://learn.microsoft.com/azure/azure-monitor/data-collection/data-collection-rule-overview)
- [Collect performance counters with Azure Monitor Agent](https://learn.microsoft.com/azure/azure-monitor/vm/data-collection-performance)
- [AMA custom JSON logs](https://learn.microsoft.com/azure/azure-monitor/vm/data-collection-log-json)
- [Azure Monitor action groups, e-mail OTP verification, Portal test and rate limits](https://learn.microsoft.com/azure/azure-monitor/alerts/action-groups)
- [Action-group CLI and test-notifications commands](https://learn.microsoft.com/cli/azure/monitor/action-group)
- [Common alert schema](https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-common-schema)
- [Log-alert query evaluation and automatic resolution](https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-create-log-alert-rule)
- [Azure Monitor service limits](https://learn.microsoft.com/azure/azure-monitor/fundamentals/service-limits)
- [Azure Workbooks overview](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [Azure Resource Graph overview](https://learn.microsoft.com/azure/governance/resource-graph/overview)

### SQL Server

- [SQL server memory configuration](https://learn.microsoft.com/sql/database-engine/configure-windows/server-memory-server-configuration-options)
- [SQL query grants DMV](https://learn.microsoft.com/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-memory-grants-transact-sql)
- [SQL on Arc overview](https://learn.microsoft.com/sql/sql-server/azure-arc/overview)
- [SQL Arc supported regions](https://learn.microsoft.com/sql/sql-server/azure-arc/overview#supported-azure-regions)
- [SQL 2019 build/update history](https://support.microsoft.com/en-us/servicing/sql/sql-server-2019/kb4518398-build-versions)

### Update Manager, Automation, Event Grid and Change Tracking

- [Azure Update Manager overview](https://learn.microsoft.com/azure/update-manager/overview)
- [Update Manager Arc periodic assessment](https://learn.microsoft.com/azure/update-manager/assessment-options)
- [Update Manager scheduled patching](https://learn.microsoft.com/azure/update-manager/scheduled-patching)
- [Update Manager dynamic scoping](https://learn.microsoft.com/azure/update-manager/dynamic-scope-overview)
- [Update Manager pre and post events](https://learn.microsoft.com/azure/update-manager/pre-post-scripts-overview)
- [Manage pre and post events in Update Manager](https://learn.microsoft.com/azure/update-manager/manage-pre-post-events)
- [Runtime environments in Azure Automation](https://learn.microsoft.com/azure/automation/runtime-environment-overview)
- [System topics in Azure Event Grid](https://learn.microsoft.com/azure/event-grid/system-topics)
- [Change Tracking and Inventory AMA](https://learn.microsoft.com/azure/azure-change-tracking-inventory/overview-monitoring-agent)

### Grafana dashboards and the shift report

- [Azure Managed Grafana overview](https://learn.microsoft.com/azure/managed-grafana/overview) - the service that hosts the dashboards described in [monitoring/README.md](../../monitoring/README.md)
- [Azure Functions overview](https://learn.microsoft.com/azure/azure-functions/functions-overview) - the runtime of the shift-report application ([shift-report/README.md](../../shift-report/README.md))
- [Azure Communication Services e-mail overview](https://learn.microsoft.com/azure/communication-services/concepts/email/email-overview) - the service that sends the shift-report e-mail

## 27.2 Scope and limitations

This material is a reference implementation and demonstration guide for a lab. It is not a supported production pattern for converting Azure VMs into Azure Arc-enabled servers (the Hyper-V host is an Azure VM that simulates on-premises), not a guaranteed consolidation ratio, and not a security or compliance review. Treat the thresholds, schedules and sizes as lab values to be reviewed against your own requirements.

## 27.3 Documents in this repository

**What you are doing:** Use this table to find the other documents and tools of the repository. All links are relative, so they work on GitHub and in a local clone.

| Document | What it covers |
|---|---|
| [README](../../README.md) | What the repository contains, the quick start, the stated limitations and how to adapt it |
| [docs/README.md](../README.md) | Index of the operator guide and the demonstration storyline |
| [docs/architecture.md](../architecture.md) | How the pieces fit together, with the diagram [architecture-overview.png](../../diagrams/architecture-overview.png) |
| [lab-kit/README.md](../../lab-kit/README.md) | How the lab kit is organised and what protects a live lab from the kit; [Chapter 26](26-lab-kit-reference.md) is the file-by-file reference |
| [monitoring/README.md](../../monitoring/README.md) | The eleven Azure Managed Grafana dashboards, their data sources and how to import them |
| [shift-report/README.md](../../shift-report/README.md) | The Azure Functions application that sends the automated shift-report e-mail with three attachments ([section 23.4](23-reports-and-export.md#234-automated-shift-report-by-e-mail-optional)) |
| [shift-report/app/CONTRACT.txt](../../shift-report/app/CONTRACT.txt) | The runtime contract of that application: report set, e-mail envelope, scheduled-send policy and the constants you edit before deploying |
| [ENVIRONMENT.example.txt](../../ENVIRONMENT.example.txt) | The key list of the private `ENVIRONMENT.txt` that `lab-kit\Initialize-LabSecrets.ps1` creates ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) |
| [tools/Set-RepoContext.ps1](../../tools/Set-RepoContext.ps1) | Replaces the placeholders with your own subscription, tenant and region ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) |
| [tools/validate_repo.py](../../tools/validate_repo.py) | Repository self-checks: JSON and Python syntax, relative Markdown links and private files that must never be committed |
| [Presenter storyline](../demo/00-about-this-guide.md) | The scene-by-scene demonstration of the finished lab and how to read every chart |
| [NOTICE.md](../../NOTICE.md) | Not an official product, trademarks, third-party software of the shift-report application and media you must obtain yourself |
| [SANITIZATION.md](../../SANITIZATION.md) | Which values are placeholders, what was left out of this repository, and what you must supply yourself |
| [LICENSE](../../LICENSE) | The MIT license of the repository |
