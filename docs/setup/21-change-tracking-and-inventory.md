# 21. Change Tracking and Inventory - separate secondary-region collection

This document explains how Change Tracking and Inventory is enabled and verified for the SQL Arc machine, and how to observe a deliberate, benign change. The feature uses its own Log Analytics workspace (`law-arc-ct-sea`), its own data collection rule (DCR) and its own extension in a secondary region (Southeast Asia, `southeastasia`, in this lab), because some management features are not available in every region. Use it when you set up Change Tracking, check that it is collecting, or rehearse a change demonstration.

Commands in this document are written to run from the `lab-kit` folder (`cd lab-kit`) in a PowerShell session where the lab context has been loaded with `. .\context.ps1`. The context provides variables such as `$RG` and `$ArcPrefix` and helpers such as `Invoke-LabArcScript` and `Invoke-LabQuery`.

## 21.1 Workspace, DCR and extension

**What you are doing:** In this section, you enable or inspect **Change Tracking and Inventory** for the SQL Arc machine. **Change Tracking and Inventory** is the Azure feature that records operating-system configuration inventory and detects certain file, service, registry and software changes over time. It is separate from performance monitoring and separate from SQL row-level Change Tracking.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, and on the operator PC in Windows PowerShell with Azure CLI for the association and extension checks.

Portal clicks:

1. Open **Arc**.
2. Click **Machines**.
3. Open **SQL2019-GUEST**.
4. Open **Change tracking** or **Change Tracking and Inventory**.
5. Enable the AMA-based feature using **law-arc-ct-sea**, Southeast Asia.
6. Create or select the dedicated CT DCR in this same supported region, not the OS/SQL Perf DCR.
7. Open **Extensions** under Arc for the machine.
8. Verify the Windows ChangeTracking extension.
9. Remember that the Azure Monitor Agent and CT extension are different.
10. In CT settings, verify Windows services/software inventory plus a deliberate test-file registry/files scope.
11. Do **not** collect an entire system drive or a secret-bearing settings file.
12. Wait for baseline inventory.
13. Open `law-arc-ct-sea > Logs`.
14. Inspect `ConfigurationData` and `ConfigurationChange` as appropriate.

This data is not in the primary monitoring workspace (`law-arc-monitor-lab`) by default.

CLI path: the supported-region setup is scripted in `lab-kit/management/provision-ct.ps1` (described below after the inspection commands). It builds the dedicated DCR body from `lab-kit/schema/CtDcrCreation.json` and saves it as `lab-kit/management/ct-dcr-request.json`. `lab-kit/Deploy-LabManagement.ps1 -ConfigurationOnly` is an alternative that only re-applies reviewed configuration files listed in a `management/deployment-index.json` (each entry names a `resourceId`, an `apiVersion` and a `file`). The repository carries a one-entry example (`management/deployment-index.json`, which re-applies `ct-dcr-request.json`). The script refuses every resource except a Log Analytics workspace, a DCR or a DCR association, so a fresh build uses `provision-ct.ps1`. Neither script executes guest changes. Inspect the existing associations:

> **Do this on:** your operator PC, in PowerShell with Azure CLI. Run these exact commands.

```powershell
az monitor data-collection rule association list `
  --resource "$ArcPrefix/SQL2019-GUEST" -o json
az connectedmachine extension list -g $RG --machine-name SQL2019-GUEST `
  --query "[].{Name:name,Type:type,State:provisioningState}" -o table
```

**What you should see:** the dedicated CT association (`assoc-SQL2019-GUEST-ct`) and the extension `ChangeTracking-Windows`, plus the existing Windows and SQL monitoring associations. Do not remove those base associations while enabling CT. Never deploy the legacy MMA/Automation-account design as if it were this AMA-based feature.

For a fresh build, `lab-kit/management/provision-ct.ps1` creates everything this section needs in one run:

- the workspace `law-arc-ct-sea` in Southeast Asia (`PerGB2018` price tier, 30-day retention) and the `ChangeTracking(law-arc-ct-sea)` solution;
- the DCR `dcr-sql2019-change-tracking` (kind Windows, built from `lab-kit/schema/CtDcrCreation.json`) with the three streams `Microsoft-ConfigurationChange`, `Microsoft-ConfigurationChangeV2` and `Microsoft-ConfigurationData`, all sent to `law-arc-ct-sea`;
- the association `assoc-SQL2019-GUEST-ct` between that DCR and `SQL2019-GUEST`;
- the extension `ChangeTracking-Windows` (publisher `Microsoft.Azure.ChangeTrackingAndInventory`, type handler version 2.20, automatic upgrade on).

The DCR tracks services, installed software and inventory, plus exactly one demo file and one demo registry value (see [section 21.2](#212-observe-an-intentional-benign-change)). Collection frequencies are: registry every 3,000 seconds, files every 1,800 seconds, software every 1,800 seconds, services every 600 seconds and inventory every 36,000 seconds.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder. This creates Azure resources in the lab resource group: run it only on a fresh build.

```powershell
.\management\provision-ct.ps1
```

**What you should see:** the script ends with `CT workspace, dedicated DCR, association, and extension provisioned.` It writes the Azure responses (`ct-workspace.json`, `ct-solution.json`, `ct-dcr.json`, `ct-association.json`, `ct-extension.json`) next to itself. These are run-time output and are git-ignored; `ct-dcr-request.json` and `CT-TABLE-SCHEMAS.json` are committed. `CT-TABLE-SCHEMAS.json` lists the 59 columns of `ConfigurationChange` and the 41 columns of `ConfigurationData`, which is useful when you write KQL against them.

In the reference run, a benign test-file change was ingested as a **Modified** event; the file and its hash, and a benign registry value, were then restored locally. A separate registry-change event was not claimed. A future repeat still needs its own baseline and its own observed event.

The CT deployment uses **Analytics** tables `ConfigurationData` and `ConfigurationChange` with **30-day** retention. Its three required streams include `Microsoft-ConfigurationChangeV2` even if a standalone V2 table is not immediately visible. CT here is operating-system configuration tracking, **not SQL row-level Change Tracking**. File content upload is **disabled**: file metadata and old/new SHA-256 hashes are tracked, and no Storage account or SAS is created. Do not enable content upload for SQL data/logs or credential files.

Update Manager history is separate: **Azure Resource Graph** `patchassessmentresources` retains assessment results for about **seven days**, and `patchinstallationresources` retains installation history for **30 days**. Export the results if you need longer reporting; these records are not stored in `law-arc-ct-sea` merely because CT uses that workspace.

## 21.2 Observe an intentional benign change

**What you are doing:** This is the safe, benign change demonstration. You create the demo fixture once, then modify only the demo file in the tracked path and look for that change in CT.

> **Do this on:** your operator PC in Windows PowerShell for the one-time fixture creation, the Azure portal in a web browser on the operator PC for the CT view, **SQL2019-GUEST** in an elevated PowerShell window for the benign file change, and `law-arc-ct-sea` **Logs** for the KQL query.

The tracked demo fixture is created once by the supplied baseline script `lab-kit/management/guest-ct-baseline.ps1`. It runs only on `SQL2019-GUEST` and needs the `MSSQLSERVER` service to be running with automatic startup. It creates the folder `C:\HV-Demo\ChangeTracking-v22` with the file `fixture-demo.txt` (the text `Safe change tracking baseline`) and the registry key `HKLM:\SOFTWARE\HV-Demo\ChangeTracking-v22` with the string value `DemoState` set to `Baseline`. If the folder or the key already exists it stops with the error `Dedicated fixture already exists; do not overwrite`, so it can never overwrite an existing fixture. Run it once, after the DCR and the extension from [section 21.1](#211-workspace-dcr-and-extension) exist:

```powershell
Invoke-LabArcScript -Machine SQL2019-GUEST -ScriptPath .\management\guest-ct-baseline.ps1
```

To run it inside the guest instead, open an elevated PowerShell window on `SQL2019-GUEST` (reach the guest as in [Chapter 7](07-build-the-guests.md)), change to `C:\lab-kit\management` (the copy made in [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)) and run `.\guest-ct-baseline.ps1`.

**What you should see:** a JSON summary with `Utc`, `Computer`, `SqlState`, `SqlStartMode`, `LastBoot`, `File`, `Hash` (the SHA-256 hash of the file), `Registry` and `DemoState`. Keep the `Hash` value; you compare against it when you restore the file below.

Portal clicks, after the benign change below has been made and ingested:

1. Open the CT view.
2. Open **Changes**.
3. Filter to **SQL2019-GUEST**.
4. Filter to the rehearsal UTC window.
5. Select a real test-file or service change item.
6. Inspect the previous state, current state and timestamp.

Inventory baselines take time; "extension succeeded" is not "change was detected."

> **Do this on:** **SQL2019-GUEST**, in elevated PowerShell, only for the benign demo file. Run the exact commands below. The baseline script above must have created the file first.

```powershell
$fixture = 'C:\HV-Demo\ChangeTracking-v22\fixture-demo.txt'
if (-not (Test-Path -LiteralPath $fixture)) { throw 'Fixture missing: run guest-ct-baseline.ps1 first.' }
$stamp = [datetime]::UtcNow.ToString('o')
Set-Content -LiteralPath $fixture -Value "Benign change marker $stamp" -Encoding UTF8
Get-FileHash -LiteralPath $fixture -Algorithm SHA256
```

The file must already be in the configured tracked path before changes can be observed, so these commands modify the existing file and never create it. The path above must match the file path configured in the CT data collection rule (`lab-kit/management/ct-dcr-request.json`); if you use a different folder, change both together. Do not alter SQL startup type, stop a service, patch the OS or change a registry security policy just to create a CT event.

**What you should see:** `Get-FileHash` prints a SHA-256 hash that differs from the `Hash` value reported by the baseline script. The DCR collects files every 1,800 seconds, so allow about 30 minutes plus ingestion delay before you conclude that nothing was detected.

Paste this exact KQL into the `law-arc-ct-sea` **Logs** window:

```kql
ConfigurationChange
| where TimeGenerated > ago(24h)
| where Computer =~ "SQL2019-GUEST"
| order by TimeGenerated desc
| take 50
```

**What you should see:** a real change record with its schema-specific item fields, or **pending ingestion** with a local marker timestamp and no claim of completed detection. CT frequency depends on change type and source; do not promise 15-second CT detection merely because SQL memory samples use 15 seconds.

When the demonstration is finished, restore the demo file to its baseline text. The restore is itself a change, so CT may record a second change item for it.

> **Do this on:** **SQL2019-GUEST**, in elevated PowerShell. Run the exact commands below.

```powershell
$fixture = 'C:\HV-Demo\ChangeTracking-v22\fixture-demo.txt'
[IO.File]::WriteAllText($fixture, "Safe change tracking baseline`r`n", (New-Object Text.UTF8Encoding($false)))
Get-FileHash -LiteralPath $fixture -Algorithm SHA256
```

**What you should see:** a SHA-256 hash equal to the `Hash` value that the baseline script printed.

CLI path: the kit has two ready-made queries for the CT workspace. `lab-kit/queries/ct-file-changes.kql` lists file changes from the last 30 minutes whose path contains `ChangeTracking-v22`, with the previous and the current content checksum. `lab-kit/queries/ct-sql-services.kql` shows the latest state, start type and account of the `MSSQLSERVER`, `SQLSERVERAGENT` and `SqlServerExtension` services. The workbook ([Chapter 18](18-workbook.md)) uses both. `lab-kit/management/query-ct.ps1` counts the CT rows that arrived for `SQL2019-GUEST` in the last two hours by table and data type; pass `-Query` to run your own KQL against the CT workspace instead.

> **Do this on:** your operator PC, in PowerShell with Azure CLI, in the `lab-kit` folder with the lab context loaded. Run these exact commands.

```powershell
Invoke-LabQuery -QueryFile .\queries\ct-file-changes.kql -OutputPath .\exports\ct-file-changes.json -Workspace law-arc-ct-sea
Invoke-LabQuery -QueryFile .\queries\ct-sql-services.kql -OutputPath .\exports\ct-sql-services.json -Workspace law-arc-ct-sea
.\management\query-ct.ps1
```

**What you should see:** `Query saved: .\exports\ct-file-changes.json` and `Query saved: .\exports\ct-sql-services.json`, followed by the JSON result of `query-ct.ps1` with one row count per table and data type. The script also saves that result as `ct-ingestion-counts.json` next to itself (git-ignored). It reads the workspace ID from `ct-workspace.json`, which `provision-ct.ps1` writes, so on a lab that you built through the portal use the **Logs** window instead.
