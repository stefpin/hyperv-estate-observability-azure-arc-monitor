# Lab kit

Scripts, payloads and queries that build, monitor and exercise the lab described in [`docs/setup`](../docs/setup/). The
guides tell you which file to run where and in which order; [chapter 26](../docs/setup/26-lab-kit-reference.md) is the
file-by-file reference. This page explains how the kit is organised and what protects a live lab from the kit.

## Layout

| Path | What it is |
|---|---|
| `context.ps1` | Scope guard and helpers loaded by almost every operator-PC script (`. .\context.ps1`) |
| `Initialize-LabSecrets.ps1` | Creates the private `ENVIRONMENT.txt` at the repository root (prompts for secrets, never overwrites) |
| `New-LabHost.ps1`, `host-*.ps1`, `Build-LabWindowsGuest.ps1`, `build-guest.ps1`, `add-sql-disks.ps1`, `verify-guest.ps1` | Azure host VM, Hyper-V, guests and SQL disks |
| `Install-Lab*.ps1`, `Enable-LabSqlArc.ps1`, `Deploy-Lab*.ps1` | Extensions, SQL, collectors, monitoring, workbook, alerts and management deployment |
| `Start-LabCpuScene.ps1`, `cpu-burn.ps1`, `demo/` | Bounded, self-cleaning synthetic workloads for the rehearsal scenes |
| `dcr/`, `schema/` | Four data collection rule definitions and the custom table and SQL extension schemas |
| `alerts/` | One JSON payload per alert rule (17 rules) |
| `queries/` | 47 KQL and Resource Graph queries plus two helper scripts |
| `storage/`, `install-rhel-observers.sh`, `http-latency-*.sh` | RHEL disk observer and bounded local HTTP latency helpers |
| `email/` | Action group, attachment and end-to-end alert test helpers |
| `management/` | Update Manager, Change Tracking, Automation, Event Grid wiring; `guard/` holds the maintenance guard runbook and its offline tests; `operations/` holds the guard publication and validation helpers |
| `sources/` | Build sources for the workbook, collector setup and report export |
| `workbook-*.json` | The saved workbook definition (v2.2), its query set and its resource settings |

## How the kit protects a live lab

* **One resource group.** `context.ps1` checks that the signed-in Azure CLI session is the expected subscription and
  tenant, refuses a `-g`/`--resource-group` other than the lab group, and refuses REST URLs and resource IDs outside it.
* **Excluded operations.** The helper rejects provider registration, Azure Policy, VM Run Command, security pricing and
  group deletion. Arc Run Command is used only through helper functions (`Invoke-LabArcScript` and its equivalents in `management`,
  `management/operations`, `sources/sql-install` and `storage`), which create a uniquely named run command, pass secrets as
  protected parameters and always remove the run command.
* **Explicit switches.** Anything that can restart a machine, send e-mail or create a notification receiver needs a
  deliberate switch (for example `-ApprovedReceiverCreation`, `-ConfigureAndTest yes`, `-InitialBuildApproved`).
* **No secrets in the kit.** Passwords live only in `ENVIRONMENT.txt`, which is created outside this folder and ignored by
  Git. Evidence and query scripts are read-only.
* **Run-time output is not committed.** Scripts write Azure responses and evidence (for example `management/*.json`
  responses, `management/evidence/`, `reports-output/`) next to themselves; `.gitignore` excludes them.

## Before you run anything

1. Replace the placeholders with `..\tools\Set-RepoContext.ps1` (or by hand): `<SUBSCRIPTION_ID>`, `<TENANT_ID>` and
   `<PRIMARY_REGION>` appear in `context.ps1`, `Initialize-LabSecrets.ps1` and many scripts. Scripts that still contain a
   placeholder fail at the scope check on purpose.
2. Read the script you are about to run. They are written to be inspected: each states where it runs (operator PC, host,
   SQL guest, RHEL) and what it changes.
3. Use Windows PowerShell 5.1 or PowerShell 7 on a Windows operator PC with Azure CLI (the kit uses `icacls`, Windows
   paths and the Azure CLI Python path). Guest scripts run inside the guests through Arc Run Command or PowerShell
   Direct.

## Examples of values that are examples

* The Update Manager window is computed by `management/provision-maintenance.ps1` (next Monday 19:00 SE Asia Standard
  Time, 90 minutes, weekly, expiring about six weeks later) and the webhook expiry by `management/provision-events.ps1`;
  request files such as `management/maintenance-config-request.json` show one example payload.
* `management/guest-final-safety.ps1` needs `$ExpectedBootUtc` (the SQL guest's last boot time in UTC, recorded before the
  maintenance test); it fails closed until you set it.
* `192.168.100.0/24`, the machine names, the 9,829 MiB SQL ceiling and the VM sizes are the lab's fixed facts; change them
  consistently in the scripts, queries, dashboards and documentation if you build a different lab.
