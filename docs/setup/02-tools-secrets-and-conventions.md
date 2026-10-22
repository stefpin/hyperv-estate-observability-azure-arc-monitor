# 2. Tools, command locations and secret handling

This chapter explains where each command runs, how to replace the placeholders in the repository, open the lab kit on the operator PC and sign in, how passwords and installation media are handled (including the private `ENVIRONMENT.txt`), and how the lab kit reaches the host and the SQL guest. Before you start you need a Windows operator PC with Windows PowerShell 5.1 and Azure CLI, a local copy of this repository (the folder that contains `lab-kit/`), and an Azure account that can reach the lab subscription.

## 2.1 Five windows you must distinguish

This chapter is about using the correct window every time. Beginners often make mistakes by typing the right command into the wrong machine.

Use the table below as your "where am I?" guide before every step.

| Label in this guide | How to open it | What runs there |
|---|---|---|
| Operator PC, PowerShell + Azure CLI | Start > Windows PowerShell | `az`, the lab kit's orchestrator scripts, cloud queries |
| Hyper-V host, elevated PowerShell | Portal VM > Connect > Bastion; Start > PowerShell > Run as administrator | Hyper-V, VMConnect, PowerShell Direct |
| Windows guest, elevated PowerShell | Host VMConnect or `Enter-PSSession -VMName` | SQL setup, service settings, guest disks |
| SQL query on SQL2019-GUEST | Windows-authenticated SSMS or the lab kit's `Invoke-LabSql` helper | T-SQL / DMVs |
| RHEL guest, Bash | Host `ssh -l labadmin 192.168.100.14` | `sudo`, `dnf`, `systemctl`, `iostat` |

Read these rules before you copy any command:

- PowerShell blocks use Windows PowerShell 5.1 syntax.
- A backtick at the end of a line continues the command; do not add spaces after it.
- `$RG` is a PowerShell variable, not Bash `RG=...`.
- Bash blocks run only after entering RHEL by SSH.
- Windows file paths use backslashes. Linux paths and URLs naturally use slashes; they are not Windows filesystem paths.
- Values in angle brackets, such as `<PRIMARY_REGION>`, `<SUBSCRIPTION_ID>`, `<TENANT_ID>`, `<START_UTC>` or `<END_UTC>` (the start and end of an interval you recorded, in ISO 8601 form with a trailing Z), are placeholders. Replace them with your own values before you run the command. The first three also appear in the repository's scripts and payloads, where `tools\Set-RepoContext.ps1` replaces them once for you (see [Placeholders and ENVIRONMENT.txt](#placeholders-and-environmenttxt) in section 2.2).
- Azure Portal's Cloud Shell is not used as the default here: automatic storage creation could fall outside the lab resource group.

**SQL Setup does not install SQL Server Management Studio (SSMS).** SSMS is optional in this guide. If its icon is absent, use the guest's elevated PowerShell plus `lab-kit/guest-sql.ps1` / `Invoke-LabSql`; this works with Windows' built-in .NET SQL client and the same Windows authentication. No additional module or SQL password is needed. SSMS menu instructions describe the equivalent GUI if it is already installed; they are not an undisclosed prerequisite.

## 2.2 Open the lab kit on the operator PC

Here you are preparing the repository and opening the local folder that contains the helper scripts for this guide, the **lab kit** (`lab-kit/`). You must do this on your own computer, not inside Azure Portal. On a fresh clone, do the one-time setup in the first subsection before you load `context.ps1`: the scope check in `context.ps1` stops with `Wrong subscription or tenant` while the file still contains `<SUBSCRIPTION_ID>` and `<TENANT_ID>`.

### Placeholders and ENVIRONMENT.txt

The scripts and payloads in this repository carry neutral placeholders instead of real identifiers:

| Placeholder | Replace with |
|---|---|
| `<SUBSCRIPTION_ID>` | The ID of the Azure subscription that holds the lab |
| `<TENANT_ID>` | The ID of the Microsoft Entra tenant of that subscription |
| `<PRIMARY_REGION>` | The region code of the primary region (see [section 1.1](01-scope-architecture-and-success-criteria.md)) |
| `00000000-0000-0000-0000-000000000009` and `00000000-0000-0000-0000-000000000018` (sentinel GUIDs) | The workspace IDs (the `customerId` property) of the Log Analytics workspaces `law-arc-monitor-lab` and `law-arc-ct-sea`; you know them only after [Chapter 4](04-azure-foundation.md#45-monitoring-workspaces-and-optional-endpoint) has created the workspaces (see below) |
| `00000000-0000-0000-0000-000000000010` (sentinel GUID) | The principal ID of the Automation account's managed identity; you know it only after the account exists ([Chapter 20](20-update-manager.md)) |

`tools\Set-RepoContext.ps1` replaces the first three placeholders in the `lab-kit`, `monitoring` and `shift-report` folders. `-SubscriptionId`, `-TenantId` and `-PrimaryRegion` are required. The script is a dry run by default and only reports how many replacements it would make; add `-Apply` to write the files. Run it twice, first without and then with `-Apply`, and then create the private settings file:

> **RUN ON - Operator PC, Windows PowerShell**
>
> Do this on: your own computer, in a Windows PowerShell window opened in the repository root (the folder that contains `lab-kit`, `tools` and `docs`). Run the last command once, for a completely new build only.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\tools\Set-RepoContext.ps1 -SubscriptionId <your-subscription-id> -TenantId <your-tenant-id> -PrimaryRegion <your-region>
.\tools\Set-RepoContext.ps1 -SubscriptionId <your-subscription-id> -TenantId <your-tenant-id> -PrimaryRegion <your-region> -Apply
.\lab-kit\Initialize-LabSecrets.ps1
```

**What you should see:** the first run prints a table with the number of files and occurrences per placeholder and ends with `Dry run: <n> file(s) would change. Re-run with -Apply to write them.` The second run prints the same table, then `Updated <n> file(s).`, a line that tells you to re-pin the shift-report policy (only when files under `shift-report` changed) and a reminder to pass the workspace IDs, the Automation principal ID and the Grafana host name if you have not set them yet. The last command asks for seven private values and ends with `Private initial-build settings created; do not display/share/screenshot this file.`

Optional parameters of `Set-RepoContext.ps1`: `-ResourceGroup` renames the default resource group `rg-hyperv-arc-monitor-demo`, `-Recipient` replaces `operator@example.com`, `-WorkspaceId` and `-CtWorkspaceId` replace the two workspace sentinels, `-AutomationPrincipalId` the principal-ID sentinel (see below) and `-GrafanaEndpoint` the Grafana host name of the shift-report application, and `-IncludeDocs` also edits the Markdown files in `docs`, so that the commands in this guide show your own values. `-AcsSender` and `-Suffix` are used only by the shift-report application (see [shift-report/README.md](../../shift-report/README.md)); when a run changes files under `shift-report`, the script reminds you to re-pin that application's policy with `python shift-report/tools/pin_policy.py`.

**Sentinel GUIDs.** A value such as `00000000-0000-0000-0000-0000000000NN` stands for an ID that cannot be known before your resources exist. Two groups need your own values:

- The workspace IDs (the `customerId` property) of the Log Analytics workspaces `law-arc-monitor-lab` (sentinel `00000000-0000-0000-0000-000000000009`) and `law-arc-ct-sea` (sentinel `00000000-0000-0000-0000-000000000018`). They occur in `shift-report\app\domain.py` (`WORKSPACES`) and in the query manifest and the dashboard builder under `shift-report\app\config`. The first one also occurs in `lab-kit\storage\storage-local.ps1` and as the default `-WorkspaceId` of `lab-kit\sources\demo-v22\query-la.ps1`. `Set-RepoContext.ps1` replaces them when you pass `-WorkspaceId` and `-CtWorkspaceId`.
- The principal ID of the Automation account's managed identity in `lab-kit\management\operations\grant-guard-roles.ps1` (sentinel `00000000-0000-0000-0000-000000000010`; see [Chapter 20](20-update-manager.md)). Pass it to `tools\Set-RepoContext.ps1` as `-AutomationPrincipalId` once `provision-automation.ps1` has created the account. If you use the shift-report application, also set the constants described in [shift-report/README.md](../../shift-report/README.md) by hand; the script can only fill in the values you pass to it, such as the Grafana host name (`-GrafanaEndpoint`).

The workspace IDs exist only after [Chapter 4](04-azure-foundation.md#45-monitoring-workspaces-and-optional-endpoint) has created the workspaces, so you run the script a second time at that point (the three required parameters have to be given again; nothing is left to replace for them). Do this once, in the `lab-kit` folder with the lab context loaded (see below):

> **RUN ON - Operator PC, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder with `context.ps1` loaded. Run it once, after both workspaces exist.

```powershell
$MonitorWorkspaceId = az monitor log-analytics workspace show -g $RG -n law-arc-monitor-lab --query customerId -o tsv
$CtWorkspaceId = az monitor log-analytics workspace show -g $RG -n law-arc-ct-sea --query customerId -o tsv
..\tools\Set-RepoContext.ps1 -SubscriptionId $SUB -TenantId $TENANT -PrimaryRegion <your-region> -WorkspaceId $MonitorWorkspaceId -CtWorkspaceId $CtWorkspaceId
..\tools\Set-RepoContext.ps1 -SubscriptionId $SUB -TenantId $TENANT -PrimaryRegion <your-region> -WorkspaceId $MonitorWorkspaceId -CtWorkspaceId $CtWorkspaceId -Apply
```

**What you should see:** the dry run lists the two workspace sentinels with their number of files and occurrences; the second run prints `Updated <n> file(s).` and, because files under `shift-report` change, the re-pin reminder. Afterwards neither sentinel is left in the list that the next command prints.

The other sentinel GUIDs in the kit, for example the fixed workbook ID `00000000-0000-0000-0000-000000000005` ([Chapter 18](18-workbook.md)), are identifiers that the scripts themselves create and refer to. Leave them as they are.

To list every sentinel GUID that is left, run this in the repository root:

```powershell
Get-ChildItem lab-kit, shift-report -Recurse -File |
  Select-String -Pattern '00000000-0000-0000-0000-0000000000[0-9a-f]{2}' |
  Select-Object Path, LineNumber
```

**ENVIRONMENT.txt.** The lab's passwords and other private settings live in `ENVIRONMENT.txt`, in the repository root (one folder above `lab-kit`). The file is not part of the repository: it is git-ignored, and `lab-kit\Initialize-LabSecrets.ps1` creates it on your PC. Run the script after `Set-RepoContext.ps1 -Apply`, because it writes the non-secret settings (subscription, tenant, resource group, region, host and SQL guest names and addresses) from the values stored in the script. It then prompts for seven passwords without displaying them: the host administrator, the three Windows guests, the RHEL guest, the SQL guest and the SQL memory-collector account. Each password needs at least 16 characters. The script never overwrites an existing file. It creates the file with permissions for your account, SYSTEM and Administrators only, and deletes it again if those permissions cannot be applied. `Get-LabSettings` refuses to read a file whose `SUBSCRIPTION_ID` or `RESOURCE_GROUP` differs from the values in `context.ps1`. [`ENVIRONMENT.example.txt`](../../ENVIRONMENT.example.txt) in the repository root lists every key. It is a reference, not a file to copy and fill in. Scripts read the file but do not print it; `management\provision-events.ps1` appends the two Update Manager webhook addresses to it (see [Chapter 20](20-update-manager.md)). Treat the file like a password vault (see section 2.3).

### Open the lab kit and sign in

For the file-opening steps, follow these exact clicks:

1. On your own computer, open `File Explorer`.
2. Browse to the folder where you cloned or extracted this repository (the repository root).
3. Open the folder named `lab-kit`.
4. Click once in an empty area inside that folder.
5. Hold `Shift` and right-click.
6. Click **Open PowerShell window here**.
7. If that menu item is not available, open Windows PowerShell normally and then paste the exact command block below.
8. Azure Portal does not upload this folder automatically.

**CLI path, exact local directory:**

> **RUN ON - Operator PC, Windows PowerShell**
>
> Do this on: your own computer, in a Windows PowerShell window. This is not the Hyper-V host and not a guest VM. Keep using this same window for later operator-PC commands so the loaded helper functions stay available.

```powershell
# Start in the repository root (the folder that contains lab-kit).
# If you opened PowerShell from inside lab-kit with Shift + right-click, skip the cd.
cd lab-kit
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\context.ps1
az account show --query "{Subscription:id,Tenant:tenantId,State:state}" -o table
```

**What you should see:** your `<SUBSCRIPTION_ID>` and `<TENANT_ID>` and the state `Enabled`. The dot then space before `.\context.ps1` is important: it loads helper functions into this window. Repeat in every new PowerShell window. Changing the working directory does not sign you in.

If Azure CLI is installed but signed out, use the sign-in commands below in a normal visible operator window. This is so you can complete the browser sign-in yourself if Azure opens a sign-in page.

Do not leave a hidden process waiting for an invisible authentication dialog.

> **RUN ON - Operator PC, Windows PowerShell**
>
> Do this on: your own computer, still in Windows PowerShell. Run this only if `az account show` showed that you are not already signed in to the correct tenant and subscription.

```powershell
az login --tenant <TENANT_ID>
az account set --subscription <SUBSCRIPTION_ID>
. .\context.ps1
```

**What you should see:** login completes and context validation passes. `context.ps1` fails closed if the tenant or subscription differs from the ones the lab is configured for. Installing missing Azure CLI command extensions changes the local PC, not the subscription:

> **RUN ON - Operator PC, Windows PowerShell**
>
> Do this on: your own computer, in the same PowerShell window, after you have signed in successfully.

```powershell
az extension add --name connectedmachine --upgrade --only-show-errors
az extension add --name monitor-control-service --upgrade --only-show-errors
az extension add --name log-analytics --upgrade --only-show-errors
az extension add --name scheduled-query --upgrade --only-show-errors
az extension add --name resource-graph --upgrade --only-show-errors
az extension add --name automation --upgrade --only-show-errors
```

**What you should see:** each command ends without an error. The first three extensions serve the Arc, data collection rule and Log Analytics commands. `scheduled-query` is used by `lab-kit\Get-LabEvidence.ps1`, `resource-graph` by `lab-kit\sources\demo-v22\validate-workbook.ps1` and `automation` by `lab-kit\management\operations\publish-guard.ps1`, so you can add those three later, when you reach the chapter that needs them.

## 2.3 Secrets and media prerequisites

This section is about handling passwords and install media safely. Read it before you open any credential prompt or mount any ISO.

**About `ENVIRONMENT.txt`.** `ENVIRONMENT.txt` is the lab's private settings file; [section 2.2](#placeholders-and-environmenttxt) explains how to create it. It lives one folder above `lab-kit/`, that is, in the repository root, and it is git-ignored so that it is never committed. The lab kit's helper functions `Get-LabSettings` and `Get-LabCredential` read it in memory. Treat it like a password vault: never display it, never copy it into a transcript, ticket or chat, and never upload it anywhere (to a guest, a Storage account or a file share).

For secret handling in the Portal or in a remote desktop session, follow these safety rules exactly:

1. Do not display the settings file.
2. Retrieve the appropriate password privately from your local `ENVIRONMENT.txt`.
3. Enter it only into the Bastion or guest sign-in dialog.
4. If taking a screenshot, close credential dialogs first.
5. Do not paste passwords into portal command previews or a SQL query.

For script-based secret handling, keep these rules exact:

**CLI path:** `Get-LabCredential -Machine SQL2019-GUEST` returns a PSCredential object without displaying the password. `Get-LabSettings` reads the existing settings in memory. Do not run `$E`, `Format-List *`, `Get-Content ENVIRONMENT.txt` or a transcript while handling them. For a completely new build, `lab-kit/Initialize-LabSecrets.ps1` prompts privately and creates the settings file only if one does not exist; it never replaces live settings (see [Placeholders and ENVIRONMENT.txt](#placeholders-and-environmenttxt)).

**Required media:**

- Windows Server 2019, 2022 and 2025 evaluation ISOs.
- RHEL 9.4 x86_64 Binary DVD, downloaded from your own authorized Red Hat account.
- SQL Server 2019 **Enterprise Core** installation media that you are entitled to use.

Evaluation or Developer SQL media is not a substitute for the edition/licensing dashboard shown in this guide. Setup uses the product key embedded in the entitled media and never prints it. No `sa` password or SQL service-account password is needed.

## 2.4 Copy the lab kit to the host and the SQL guest

Here you are copying only the lab kit scripts (never secrets) to the host and to the SQL guest. This avoids confusion about what Basic Bastion can and cannot do.

For the Bastion reminder, follow this logic:

1. Open Bastion if you want to look at the host or guest folders after the copy.
2. Remember that Basic Bastion is not a general local-file upload tool.
3. On the already Arc-connected lab, use the operator PC command below to send the lab kit through **Arc Run Command**.
4. After the copy finishes, go back to File Explorer in the Bastion session and inspect the destination folders.
5. This transport copies the lab kit sources only; it does not run their build or workload procedures.

**CLI route:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder of the Windows PowerShell window where the setup in section 2.2 has already been completed (`context.ps1` loaded). Do not run this on the host or inside a guest.

```powershell
.\Copy-LabPublicSources.ps1 -Target Host
.\Copy-LabPublicSources.ps1 -Target SqlGuest
```

**What you should see:** `Public bundle copied to host F:\Build\lab-kit. No guest script executed.` and `Public bundle copied to SQL2019-GUEST C:\lab-kit. No guest script executed.` The lab kit is now on the host at `F:\Build\lab-kit` and on the SQL guest at `C:\lab-kit`. `-Target Host` is the default. `-Target SqlGuest` puts the files on the host first and then copies them from there to the SQL guest through PowerShell Direct (user `labadmin`, password `SQL_GUEST_PASSWORD`, passed to the host only as a protected run-command parameter), so the SQL guest must be running. In an elevated PowerShell window on the SQL guest, first run `Set-Location C:\lab-kit`, then its labelled guest commands; on the host use `Set-Location F:\Build\lab-kit`. On a completely new host before Arc exists, use Bastion and create the small host and guest scripts in Notepad from the lab kit's source files; onboard Arc first (see [Chapter 10](10-azure-arc-onboarding.md)) before you use this transport. Do not expose a public share, do not create a Storage account outside the lab resource group, and do not upload `ENVIRONMENT.txt` to transfer sources.

The script checks every file under `lab-kit` before it sends anything. It stops with `Unexpected or potentially private file in public bundle; inspect before transfer.` if a file has an extension other than `.ps1`, `.py`, `.json`, `.kql`, `.sh`, `.txt`, `.service` or `.md`, or a name that contains `ENVIRONMENT` or `webhook` or starts with `protected-` or `parameter-`. This includes response files that scripts have written next to themselves ([Chapter 26](26-lab-kit-reference.md)): copy the lab kit before you run the Update Manager scripts in [Chapter 20](20-update-manager.md), whose webhook response files would stop the copy, or move such files out of the folder first.
