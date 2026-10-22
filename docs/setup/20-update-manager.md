# 20. Azure Update Manager - assessment, periodic checks and maintenance

This document covers how Azure Update Manager is used in the lab: running an assessment, turning on periodic assessment, defining the maintenance configuration and its dynamic scope, understanding why a definition-only update differs from a real OS or SQL patch, how the pre/post maintenance events and the scoped guard work, how to inspect the safe chain and its permission scopes, and how to prove after a maintenance test that the guest did not restart. Use it when you review or enable patch assessment and scheduled maintenance for the SQL guest.

Only the SQL guest (`SQL2019-GUEST`) is used for Update Manager. It is registered as an Azure Arc machine in a secondary region (Southeast Asia, `southeastasia`, in this lab kit) because some management features are not available in every region. The other lab machines stay in the primary region and are outside the demonstrated management support; do not move them.

Commands in this document are written to run from the `lab-kit` folder (`cd lab-kit`) in a PowerShell session where the lab context has been loaded with `. .\context.ps1`. The context provides `Invoke-LabAz` and variables such as `$RG`, `$ResourcePrefix` and `$ArcPrefix`.

The scripts for this chapter are in `lab-kit\management` and its `guard` and `operations` subfolders; [Chapter 26](26-lab-kit-reference.md) describes every file. They run on the operator PC, each folder has its own `common.ps1` with the scope checks, and they write the Azure responses they receive next to themselves (the `operations` scripts write to `management\evidence`). Those response files are git-ignored, while the `*-request.json` payloads are committed. In build order the steps are:

| Step | What you run (from the `lab-kit` folder) | What it does | Section |
|---|---|---|---|
| 1 | `.\management\enable-assess.ps1` | Turns on periodic assessment and submits one assessment | 20.1, 20.2 |
| 2 | `.\management\provision-maintenance.ps1` | Creates the maintenance configuration and the dynamic scope, and sets the gating tags (`HvUmApproval=Pending`) | 20.3 |
| 3 | `.\management\provision-automation.ps1` | Creates the Automation account, its managed identity, the runtime environment and the first, read-only runbook | 20.5 |
| 4 | `.\management\provision-events.ps1` | Creates the Event Grid topic, the two webhooks and the two event subscriptions | 20.5, 20.6 |
| 5 | `.\management\operations\capture-baseline.ps1` | Saves the before-state and runs a read-only SQL baseline check | 20.5 |
| 6 | `.\management\operations\grant-guard-roles.ps1` | Creates two narrow custom roles and assigns them to the Automation identity | 20.5, 20.6 |
| 7 | `.\management\guard\test-maintenance-guard.ps1` | Runs the offline tests of the guard (no Azure or guest access) | 20.5 |
| 8 | `.\management\operations\publish-guard.ps1` | Publishes the guard in place of the first runbook | 20.5 |
| 9 | `.\management\operations\test-cloud-guard.ps1` | Runs independent, read-only Pre and Post jobs against the published guard | 20.5 |
| 10 | Tag change `HvUmApproval=Approved` | Arms the maintenance target | 20.3 |
| 11 | `.\management\guest-final-safety.ps1` | Checks on the SQL guest that SQL Server is running and that the guest did not restart | 20.7 |

Steps 1 to 4, 6, 8 and 10 create or change Azure resources: read the change gates in [Chapter 3](03-build-order-and-change-gates.md) first. Steps 5, 7, 9 and 11 are read-only checks.

## 20.1 SQL guest only; do not move the original Arc estate

**What you are doing:** In this step, you run or review an **assessment** in Azure Update Manager. **Update Manager** is Azure's patch assessment and scheduling service. An assessment checks what updates are available. It is not the same as installing updates.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, or on the operator PC in Windows PowerShell with Azure CLI for the REST call.

Portal clicks:

1. In the Azure portal, search for **Azure Update Manager**.
2. Open **Azure Update Manager**.
3. Click **Machines**.
4. Filter to this RG if needed.
5. Find **SQL2019-GUEST**.
6. Open the Arc machine in Southeast Asia.
7. Click **Check for updates** or **Assess now**.
8. Wait for the result.
9. Inspect the last-assessed time, classifications, pending reboot and result details.

**Check for updates / Assess now** is an assessment, not an install. The other lab machines are registered in the primary region and remain outside the demonstrated management support.

> **Do this on:** your operator PC, in PowerShell with Azure CLI. Run the exact request below.

```powershell
$sqlMachine = "$ArcPrefix/SQL2019-GUEST"
Invoke-LabAz rest --method post `
  --url "https://management.azure.com$sqlMachine/assessPatches?api-version=2025-01-13" `
  --body '{}' -o json
```

Assessment may take several minutes and requires outbound Windows Update reachability. An accepted operation response is not a final assessment: wait for the operation to finish and then read the machine's assessment result in Update Manager. `management\enable-assess.ps1` (section 20.2) sends this same request after it has turned on periodic assessment, so you can run the script instead of the request above.

## 20.2 Periodic assessment

**What you are doing:** This step turns on automatic periodic assessment only. It does not turn on automatic installation.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, or on the operator PC in Windows PowerShell with Azure CLI for the patch-settings update.

Portal clicks:

1. Open **Azure Update Manager**.
2. Click **Machines**.
3. Open **SQL2019-GUEST**.
4. Open **Update settings** or **Change update settings**.
5. Turn **Periodic assessment** on.
6. Confirm the mode is AutomaticByPlatform.
7. Save the change.
8. After the schedule runs, refresh the machine view and inspect the updated last-assessed information.

This doesn't install patches automatically.

> **Do this on:** your operator PC, in PowerShell with Azure CLI. Run the exact commands below.

```powershell
Invoke-LabAz rest --method patch `
  --url "https://management.azure.com$ArcPrefix/SQL2019-GUEST?api-version=2025-01-13" `
  --body '@management\periodic-assessment-request.json' -o none
az connectedmachine show -g $RG -n SQL2019-GUEST `
  --query "osProfile.windowsConfiguration.patchSettings" -o json
```

The request body is `lab-kit/management/periodic-assessment-request.json`. `management\enable-assess.ps1` does the same work in one run: it sends this PATCH, submits one assessment as in section 20.1 and writes the responses to `periodic-assessment-result.json` and `assessment-submit.json` next to itself.

**What you should see:** `assessmentMode` should be `AutomaticByPlatform`. The payload updates only the supported patch-settings field, not the machine's region or identity. Do not set unsupported Azure VM patch fields on an Arc server by copying a VM command.

## 20.3 Maintenance configuration and dynamic scope

**What you are doing:** This section is about the maintenance schedule definition and the dynamic scope that decides which machine the schedule targets. A **maintenance configuration** is the reusable update window definition. A **dynamic scope** is the filter that maps the configuration to the intended resource.

The lab's schedule is a weekly window on Monday at 19:00 local time (UTC+7, called LT in this guide; the Windows time zone is `SE Asia Standard Time`), which is 12:00 UTC, with a duration of 90 minutes: Monday 19:00-20:30 LT, which is 12:00-13:30 UTC. `provision-maintenance.ps1` computes the dates when it runs. The first window is the first Monday after the day you run it, and the schedule ends 39 days after that Monday at 23:59, which covers six weekly windows, so that the schedule does not run indefinitely. If the configuration `mc-hv-sql2019-definitions-gated` already exists, inspect it and change it in place; do not create a second schedule.

> **Do this on:** the Azure portal in a web browser on the operator PC.

1. Search for **Maintenance configurations**.
2. Open the existing **mc-hv-sql2019-definitions-gated**.
3. Edit the existing schedule or open **Add-Modify schedule**, as applicable in the current blade.
4. Save a weekly schedule: repeat every week on Monday, start 19:00 in the time zone `SE Asia Standard Time` (UTC+07:00), duration 90 minutes, and set an end date about six weeks after the first window.
5. For updates, include only KB2267602.
6. Leave broad classifications empty.
7. Exclude reboot-requiring packages.
8. Use **Never** for the reboot setting.

The configuration stores a start time and a time zone. `SE Asia Standard Time` has no daylight saving time, so 19:00 there is always 12:00 UTC. If you enter the window in another time zone, convert it so that it still equals Monday 19:00-20:30 LT (12:00-13:30 UTC).

CLI equivalent: `lab-kit/management/provision-maintenance.ps1` creates the same configuration and the dynamic scope. It builds the request itself (the weekly Monday window above, `InGuestPatch` with `InGuestPatchMode` `User`, reboot setting `Never`, only KB2267602), writes the payloads it sends to `lab-kit/management/maintenance-config-request.json` and `lab-kit/management/maintenance-dynamic-scope-request.json` (the committed copies are examples; the script overwrites them with the dates it computes), and merges the tags `HvUmTarget=SQL2019-GUEST` and `HvUmApproval=Pending` onto the Arc machine. It also saves `maintenance-static-assignment-NOT-APPLIED.json` and `maintenance-machine-assignments.json` next to itself; the static assignment is deliberately not applied. Run it once for a new build. Running it again recomputes the window and sets `HvUmApproval` back to `Pending`, which pauses maintenance (see "Arming" below). To change an existing configuration from the CLI instead, update the same resource in place with a GET, preserve its fields, send the change with a PUT, then GET it again to read it back.

> **Do this on:** the operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder. Run the script for a new build, then read the configuration back with the second command (this is also the read-back for an in-place change).

```powershell
.\management\provision-maintenance.ps1
Invoke-LabAz rest --method get `
  --url "https://management.azure.com$ResourcePrefix/providers/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated?api-version=2023-04-01" `
  -o json
```

**What you should see:** the script ends with `Recurring schedule created; static assignment NOT applied; dynamic approval filter matches zero machines.`

**Expected:** maintenance location `southeastasia`, `InGuestPatch`/`User`, the Monday window, the exact KB2267602 whitelist, `excludeKbsRequiringReboot` true, and the reboot setting normalized to `NeverReboot`. Do not call `installPatches` or `applyUpdates` as part of this check.

**Failure:** on any mismatch, leave the SQL machine's `HvUmApproval` tag at `Pending` (see below) and fix the configuration before enabling the scope.

Dynamic scope review:

> **Do this on:** the Azure portal in a web browser on the operator PC for the dynamic scope review.

1. Open the existing RG-scoped **ca-hv-sql2019-approved**.
2. Verify that the assignment resource location is the primary region.
3. Verify that the filter's Arc machine location is `southeastasia`.
4. Verify that the operating system filter is Windows.
5. Verify that the resource type filter is `Microsoft.HybridCompute/machines`.
6. Verify that the tag filter uses AND with `HvUmTarget=SQL2019-GUEST` and `HvUmApproval=Approved`.
7. Do not recreate or relocate it.

Arming: until the guard is ready, the SQL machine's `HvUmApproval` tag is `Pending` (`provision-maintenance.ps1` sets it), so the dynamic scope selects nothing. Changing the tag to `Approved` arms the schedule, so make this change only after the guard runbook is published and its readiness checks pass (see 20.5), and only when you have decided to arm it ([Chapter 3](03-build-order-and-change-gates.md)). Arming is a merge-only tag change that preserves every other tag; nothing else changes.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, or on the operator PC in Windows PowerShell with Azure CLI.

Portal clicks:

1. Open the Arc machine **SQL2019-GUEST**.
2. Click **Tags**.
3. Change `HvUmApproval` from `Pending` to `Approved`. Leave `HvUmTarget` and all other tags unchanged.
4. Click **Apply**.

CLI route:

```powershell
$sqlMachine = "$ArcPrefix/SQL2019-GUEST"
Invoke-LabAz tag update --resource-id $sqlMachine --operation Merge --tags HvUmApproval=Approved -o none
az connectedmachine show -g $RG -n SQL2019-GUEST --query tags -o json
```

**Expected:** after the tag change, the tags show `HvUmTarget=SQL2019-GUEST` and `HvUmApproval=Approved` next to all earlier tags, and the dynamic scope preview lists exactly `SQL2019-GUEST`.

To pause maintenance, set the tag back to `Pending` with the same command (`--tags HvUmApproval=Pending`); do not delete the lab.

## 20.4 Definition-only update versus real OS/SQL patch

**What you are doing:** This section keeps a critical difference clear. Changing the future schedule definition is not the same thing as running a patch install now.

The lab schedule selects only KB2267602 (Microsoft Defender definition updates) for future scheduled runs. Do not substitute OS, SQL or driver updates when no applicable definition exists. A run with no candidate updates is reported accurately as having no candidates, not as an installation success. Do not start a one-time installation as part of this check.

> **Do this on:** the Azure portal in a web browser on the operator PC.

1. Open Update Manager for **SQL2019-GUEST**.
2. Inspect the assessment and history.
3. Inspect the current update selection.
4. Do **not** click **Install one-time updates**.

> **Do this on:** the operator PC CLI route. GET the current maintenance configuration, and read the assessment and installation history with the Azure Resource Graph queries `lab-kit/queries/update-assessment.arg.kql` and `lab-kit/queries/update-history.arg.kql`.

**Expected:** only the selected KB is in scope and no new install has started. SQL Server and SQL Agent remain Running/Automatic, the edition remains SQL Server 2019 Enterprise Core, and max server memory stays at 9,829 MB.

**Failure:** do not broaden classifications or reboot to make a green result. `NeverReboot` does not override independent OS policies; expected non-disruptive definition maintenance is not an absolute uptime guarantee. A Windows Server 2022 Standard Arc guest cannot use the Windows Server 2025 Arc Hotpatch benefit.

## 20.5 Pre/post maintenance workflows - scoped guard

**What you are doing:** This section is about the guard workflow around the maintenance window. The **pre** stage checks whether the machine is safe for maintenance. The **post** stage checks whether it is healthy after maintenance.

The Automation account, the first runbook and the Event Grid routes are created by two scripts. Check in the Portal first whether they exist; if they do, reuse them and do not run the scripts again. The guard source is `lab-kit/management/guard/runbook-maintenance-guard.ps1`.

> **Do this on:** the operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder. Creating the webhooks is a gated change ([Chapter 3](03-build-order-and-change-gates.md)): `-ConfigureAndTest yes` is the explicit confirmation switch that the second script requires, and `-EnvironmentPath` must be the full path of your `ENVIRONMENT.txt` (see [Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

```powershell
.\management\provision-automation.ps1
.\management\provision-events.ps1 -EnvironmentPath (Resolve-Path ..\ENVIRONMENT.txt).Path -ConfigureAndTest yes
```

**What you should see:** `Published safe pre/post runbook; managed identity <principal id> scoped only to SQL2019-GUEST.` and then, once for Pre and once for Post, `<Pre or Post> webhook and Event Grid subscription configured; independent check submitted.`

`provision-automation.ps1` creates the Automation account `aa-hv-sql-maintenance` in `southeastasia` (Basic SKU, system-assigned managed identity), the custom role "SQL Maintenance Availability Checker" (read the Arc machine; read, write and delete its Run Commands) assigned only at the SQL2019-GUEST machine scope, the runtime environment `ps74-safe-checks` (PowerShell 7.4, Az 12.3.0) and the runbook `Test-HvSqlMaintenanceAvailability`, which it publishes with the read-only check `runbook-safe-check.ps1` as its first content. `provision-events.ps1` creates the Event Grid system topic `eg-hv-sql-maintenance` on the maintenance configuration, the webhooks `wh-hv-sql-pre` and `wh-hv-sql-post` and the event subscriptions `es-hv-sql-pre` and `es-hv-sql-post` (see 20.6). Each webhook expires 45 days after its creation, and an expired webhook delivers nothing, so check the expiry before every window. The webhook addresses are secrets: the script appends them to `ENVIRONMENT.txt` as `HV_UM_Pre_WEBHOOK_URI` and `HV_UM_Post_WEBHOOK_URI`, never prints them, and sends one independent test event to each webhook.

The startup contract uses schema version 2: the original Kernel-General event 12 `StartTime` is `BootUtc`, `WmiBootUtc` is diagnostic only, and independent SQL and kernel monotonic counters corroborate startup. Do not require the SQL start time to be later than or equal to the WMI-derived boot time.

The published guard infers Pre or Post from `eventType` and has no default phase, so a Post event is never handled as Pre; an explicit `Phase` parameter that conflicts with the event type is rejected. The webhooks that `provision-events.ps1` creates also pass `Phase` and `DemoOnly=false`, but the guard does not depend on them. The guard checks a REAL SQL query, the SQL Agent and SQL services Running/Automatic, guest boot, the SQL start/process baseline and database ONLINE. It keeps the original baseline across duplicate Pre events and compares it in Post. `DemoOnly` independent checks never cancel a maintenance run or write checkpoints. The baseline is stored as non-secret, append-only checkpoint variables in the Automation account, one per delivery; the earliest healthy Pre is the baseline.

A real Pre also needs the two Arc tags `HvUmApproval=Approved` and `HvUmTarget=SQL2019-GUEST`, and the guest's Windows Update policy must prevent automatic installation or be notify-only (registry policy `NoAutoUpdate=1`, or `AUOptions=2` with `NoAutoUpdate` absent or 0). The Windows guests are built with the notify-only policy (`AUOptions=2`, see [Chapter 7](07-build-the-guests.md)), so no change is needed on the guest. None of the lab runbooks installs updates, changes SQL Server, changes services or reboots the guest.

> **Do this on:** the Azure portal in a web browser on the operator PC.

1. Open the Automation account **aa-hv-sql-maintenance**.
2. Open **Runtime environments**.
3. Open **ps74-safe-checks**.
4. Confirm PowerShell 7.4/Az 12.3.
5. Open **Test-HvSqlMaintenanceAvailability**.
6. Use **Edit**, **Test**, **Publish**, and **Jobs** only as your reviewed process allows.
7. Inspect the exact maintenance source and the event filters (see 20.6).

> **Do this on:** the operator PC CLI route, in the `lab-kit` folder. Save the before-state, grant the guard's roles, run the offline tests, import and publish the reviewed guard, then run the independent cloud checks. Replace the sentinel principal ID in `grant-guard-roles.ps1` first, as described in section 20.6.

```powershell
# Step 5: save the before-state and run the read-only SQL baseline (writes to management\evidence)
.\management\operations\capture-baseline.ps1
# Step 6: create and assign the two narrow guard roles (what they allow: section 20.6)
.\management\operations\grant-guard-roles.ps1
# Step 7: offline tests of the guard; no Azure or guest access
.\management\guard\test-maintenance-guard.ps1
# Step 8: publish the guard (the SQL machine must still carry HvUmApproval=Pending)
.\management\operations\publish-guard.ps1 -GuardPath .\management\guard\runbook-maintenance-guard.ps1
# Step 9: independent, read-only Pre and Post jobs against the published guard
.\management\operations\test-cloud-guard.ps1
```

What the five scripts do and what you should see:

- `capture-baseline.ps1` saves `baseline-resources.json` (the maintenance configuration, the dynamic scope, the Arc machines and their assignments, the resource inventory, the role assignments, the Automation account and the runbook as they are now), `original-published-runbook.ps1` (the runbook that is published now; `publish-guard.ps1` needs it) and `baseline-sql-health.json` (a read-only SQL and OS check that it runs through a short-lived Run Command and deletes afterwards; it includes the guest's last boot time as `LastBootUtc`) in `management\evidence`. It prints `ExistingMatches`, the number of machines that already carry `HvUmApproval=Approved` and `HvUmTarget=SQL2019-GUEST`, and `StaticAssignments`, the number of static maintenance assignments of the SQL machine; both are expected to be 0 while the tag is `Pending`.
- `grant-guard-roles.ps1` reads every role definition and assignment back and saves the plan and the read-back in `guard-role-plan.json` and `guard-roles.json`.
- `test-maintenance-guard.ps1` prints one `PASS` or `FAIL` line per test and ends with `OFFLINE ONLY: <n> passed; <m> failed. No Azure or guest execution occurred.` It stops with an error if any test failed.
- `publish-guard.ps1` stops with `Set the target tag HvUmApproval to Pending before replacing the safeguard.` unless `HvUmApproval` is `Pending`, and with `Published source changed independently; do not overwrite it.` if the published runbook is neither the one that `capture-baseline.ps1` saved nor your file. It imports the guard as the draft (this uses the `automation` Azure CLI extension from [Chapter 2](02-tools-secrets-and-conventions.md)), publishes it, reads the published content back, requires it to equal your file exactly and writes `published-guard.json`.
- `test-cloud-guard.ps1` starts independent Pre and Post jobs with `Phase` and `DemoOnly=true` (each may take up to 12 minutes) and requires `HandlerHealth` Healthy, `DemoOnly` true, a successful SQL query, a healthy guest and no patch installation, cancellation or checkpoint write. It saves `guard-independent-jobs.json`, `guard-independent-Pre-output.txt`, `guard-independent-Post-output.txt` and `guard-cloud-validation.json`, which states that no real scheduled installation and no real cancellation was exercised.

Afterwards GET the runbook state, the runtime environment and the actual job results in the Portal (or with `az rest`) to confirm what is really published.

**Expected readiness:** real, independent SQL checks pass, and the offline tests of scoped cancellation, timeout, idempotency and phase handling pass. Keep these test results explicitly separate from any scheduled run.

**Failure:** leave the `HvUmApproval` tag at `Pending`. Never reboot the guest or stop a service to exercise a test.

Only a REAL Pre failure or timeout, occurring before the earlier of the `eventCancellationCutOffDateTime` and the window start minus 10 minutes, may cancel the ONE actual occurrence identified by its CorrelationId, using a PUT with `properties.status=Cancel`. Never send an empty body. Azure Update Manager does not automatically wait for, or cancel on, a failed pre-check. The guard adds no automated backup, index rebuild, cache clearing or load test.

## 20.6 Inspect the actual safe chain and its permission scopes

**What you are doing:** This section is a permissions and evidence review. The goal is to prove that the scope stays narrow and that the safe chain is understood before anyone relies on it.

> **Do this on:** the Azure portal in a web browser on the operator PC.

1. Open **SQL2019-GUEST** **IAM**.
2. Open the exact **mc-hv-sql2019-definitions-gated** **IAM**.
3. Open the exact **aa-hv-sql-maintenance** **IAM**.

The role that grants Arc read and `runCommands` read/write/delete (the custom role "SQL Maintenance Availability Checker", created by `provision-automation.ps1`) stays machine-only. The role that grants maintenance configuration read plus `Microsoft.Maintenance/applyUpdates/read/write` (the custom role "SQL Scheduled Maintenance Cancellation") stays exact-configuration-only. The role that grants Automation variables read/write (the custom role "SQL Maintenance Run Checkpoints") stays exact-account-only. A custom role's `assignableScopes` is the lab RG only; that is not an assignment at the RG. Protect runbook edit rights, because Run Command write can execute an arbitrary guest script.

> **Do this on:** the operator PC CLI route. The last two roles are created and assigned by `management\operations\grant-guard-roles.ps1` (step 6 in section 20.5). Read back the role assignments at each exact scope and the custom role definitions. Creating or changing roles is administrator-only.

Before the first run, set the principal ID of the Automation account's managed identity in the script. The ID is printed by `provision-automation.ps1` (`managed identity <principal id>`) and is shown in the Portal under the Automation account, **Identity**. The script compares the identity it finds with the ID written in the test near the top of the file and stops with `Automation identity does not match the principal ID in this script: set it first (tools\Set-RepoContext.ps1 -AutomationPrincipalId) or review the change before granting permissions.` if they differ. The file ships with the sentinel `00000000-0000-0000-0000-000000000010` in that test (see [Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), so pass your own principal ID to `tools\Set-RepoContext.ps1` as `-AutomationPrincipalId` (or replace it by hand) before you run the script. The script also refuses wildcard actions and any scope other than the exact maintenance configuration and the exact Automation account, and it stops if a read-back differs from what it intended to create.

| Role | Allowed actions | Assigned at |
|---|---|---|
| SQL Maintenance Availability Checker | `Microsoft.HybridCompute/machines/read`, `Microsoft.HybridCompute/machines/runCommands/read`, `.../write`, `.../delete` | The SQL2019-GUEST Arc machine only |
| SQL Scheduled Maintenance Cancellation | `Microsoft.Maintenance/maintenanceConfigurations/read`, `Microsoft.Maintenance/applyUpdates/read`, `Microsoft.Maintenance/applyUpdates/write` | The exact configuration `mc-hv-sql2019-definitions-gated` |
| SQL Maintenance Run Checkpoints | `Microsoft.Automation/automationAccounts/variables/read`, `.../write` | The exact Automation account `aa-hv-sql-maintenance` |

The two guard roles are also stored in Azure CLI role-definition format in `management\operations\cancellation-role-cli.json` and `management\operations\checkpoint-role-cli.json`.

**Expected:** no Contributor or Owner assignment, no wildcards and no broader machine access.

**Failure:** keep the `HvUmApproval` tag at `Pending` while you resolve role-propagation delays or 403 errors; never expand the scope to make a check pass.

> **Do this on:** the Portal or CLI route for the eventing chain inspection.

1. Inspect **eg-hv-sql-maintenance**.
2. Confirm that the source is exactly the maintenance configuration.
3. Inspect **es-hv-sql-pre** and **es-hv-sql-post**.
4. Confirm their respective filters and EventGridSchema.
5. Confirm that the **wh-hv-sql-pre/post** webhooks of the Automation account exist, stay unchanged and have not expired (they were created with an expiry 45 days after creation; see 20.5).
6. Do **not** print URLs.

**Expected:** the published runbook dispatches on `eventType`, and independent safe tests are identified as tests. A direct or webhook test job is NOT evidence of the real scheduled Pre/install/Post chain or of a production cancellation.

Timeline for a maintenance window that starts at T:

| When | What |
|---|---|
| Before T-40 minutes | Finalize any schedule or guard change; later edits need at least 40 minutes lead time |
| T-40 to T-30 minutes | Pre events run |
| By the earlier of the cut-off and T-10 minutes | A cancellation, if any, must be confirmed |
| T to T+90 minutes | Install window |
| After the window | Post may run after the window ends |

For the lab window, which starts at 19:00 LT (12:00 UTC), this is: finalize before 18:20 LT (11:20 UTC), Pre 18:20-18:30 LT (11:20-11:30 UTC), cancellation confirmed by 18:50 LT (11:50 UTC), install window 19:00-20:30 LT (12:00-13:30 UTC), Post possibly after 20:30 LT (13:30 UTC). Do not forcibly kill an in-progress installation.

## 20.7 Final safety check after a maintenance test

**What you are doing:** After a maintenance test, you prove from inside the guest that SQL Server is still running and that the guest did not restart. This check is read-only: it only reads the guest's state.

`management\guest-final-safety.ps1` runs on `SQL2019-GUEST` only; on any other machine it stops with `Wrong machine`. It compares the guest's last boot time with the value in `$ExpectedBootUtc`, which you must set yourself: the file contains the placeholder `<BOOT_TIME_UTC>` there, and the check fails until you replace it with the guest's last boot time in UTC, recorded BEFORE the maintenance test and copied exactly in round-trip format (the `o` format that the command below prints). You get the value from `LastBootUtc` in `management\evidence\baseline-sql-health.json` (written by `capture-baseline.ps1` in section 20.5) or by running this on the guest:

```powershell
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
```

The script also reads the file `C:\HV-Demo\ChangeTracking-v22\fixture-demo.txt` and the registry value `DemoState` that `guest-ct-baseline.ps1` creates ([Chapter 21](21-change-tracking-and-inventory.md)), so run that baseline script first.

> **Do this on:** the operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder, after you have edited `$ExpectedBootUtc` in `management\guest-final-safety.ps1`. The command runs the script on `SQL2019-GUEST` through Azure Arc.

```powershell
Invoke-LabArcScript -Machine SQL2019-GUEST -ScriptPath .\management\guest-final-safety.ps1
```

**What you should see:** a JSON document with the UTC time of the check, the state and start mode of SQL Server and SQL Agent, `LastBootUtc`, `ExpectedBootUnchanged` (`true`), the operating system, the Windows Update policy values, the Defender signature version, the reboot flags, the Windows Update history entries for KB2267602, and the hash and registry value of the change-tracking fixture.

**Failure:** the script throws `Final SQL or no-reboot safety check failed` after it has printed the JSON if the SQL Server service is not Running/Automatic or if the boot time differs from `$ExpectedBootUtc`. Through Azure Arc you only see `Arc script failed: state=Failed ...`; to read the JSON, run the script directly in an elevated PowerShell window on the guest (the lab kit is in `C:\lab-kit` after `Copy-LabPublicSources.ps1 -Target SqlGuest`; see [Chapter 2](02-tools-secrets-and-conventions.md)). Treat a failure as a finding: do not restart the guest or any service to make the check pass; read the output, then follow [Chapter 24](24-troubleshooting.md).
