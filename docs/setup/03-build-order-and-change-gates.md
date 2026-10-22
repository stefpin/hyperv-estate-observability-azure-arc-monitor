# 3. Build order and change gates

This chapter gives the order of work for the lab and the change gates that keep a running lab safe. Use it before you create, delete, restart or reinstall anything. Before you start you should have read [Chapter 1](01-scope-architecture-and-success-criteria.md) (what the lab is) and [Chapter 2](02-tools-secrets-and-conventions.md) (where commands run and how secrets are handled), and your operator PC session should be loaded with `context.ps1`.

## 3.1 Do not rebuild a healthy live lab

This section is a safety stop. Before you create, delete, restart, or reinstall anything, first check whether the live lab is already in the required state.

**Azure Portal check.** Follow these exact clicks:

1. Open `https://portal.azure.com`.
2. Sign in with an account that has access to the lab subscription.
3. In the top search box, type `rg-hyperv-arc-monitor-demo` and press Enter.
4. Click the resource group named `rg-hyperv-arc-monitor-demo`.
5. On the resource group's page, click `Overview`.
6. If resources already exist, verify the names and properties.
7. Continue at the first incomplete chapter instead of rebuilding from the top.
8. Avoid **Delete**, **Recreate**, **Restart** and **Install updates** merely because this is a build guide.

**CLI path:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in the same Windows PowerShell window used for the earlier Azure CLI steps.

```powershell
az resource list -g $RG --query "sort_by([], &type)[].{Name:name,Type:type,Region:location}" -o table
az connectedmachine list -g $RG --query "[].{Name:name,Status:status,Region:location}" -o table
```

**What you should see:** the host and four guests in the primary region and the SQL guest in Southeast Asia. The resource count grows when rules, extensions, databases and maintenance configuration are added; a fixed resource count is not a success criterion.

## 3.2 Build and operations stages

This table is the timing plan. Treat it as the sequence of work and the list of gates that must be met before the next stage starts.

| Timing | Work | Gate before proceeding |
|---|---|---|
| Before a demonstration | Confirm the e-mail notification set-up is in place and leave it unchanged; publish and validate the maintenance guard, then arm the recurring schedule with a merge-only tag change (`HvUmApproval` from `Pending` to `Approved`; configuration only, see [Chapter 20](20-update-manager.md)) | Read back the actual Azure configuration and verify it; arming only after the guard is validated and you have decided to arm it; no patch installation; evidence collected |
| The day before | Full timed dry run; preserve exports; resolve evidence gaps | Stop all temporary load; SQL stays running |
| One hour before | Read-only pre-flight | No restarting or patching |
| During a demonstration | CPU scene, recovery, separate storage scene, SQL memory, management, report | Note that the regional layout is a lab choice and name the limits set by the change gates in section 3.3 |
| While the lab is in use | Keep the lab available continuously; monitor cost and health | SQL stays running |
| Optional, once the data flows | Grafana dashboards ([monitoring/README.md](../../monitoring/README.md)) and the automated shift report ([shift-report/README.md](../../shift-report/README.md), [Chapter 23](23-reports-and-export.md)) | The shift report sends nothing until its fail-closed gates (`SEND_ENABLED`, `SCHEDULE_ENABLED`, `AUTO_SEND_ENABLED`, all `false` by default) are opened on purpose; opening them is a gated change |
| End of life | Controlled teardown | A deliberate decision by the operator; back up and export first |

## 3.3 Change gates and prohibited shortcuts

This section tells you which actions are allowed and which are still gated. Read it before you click any save or run button that can change the environment.

For Azure Portal changes, use this rule every time:

1. Open the relevant resource and blade.
2. Review the intended change carefully.
3. Before selecting **Save**, **Install** or **Create**, confirm that the change is actually permitted at the current stage of the build (see the table in section 3.2).

Keep the following rules exact:

> **Warning:** Actual operating-system or SQL patch installation, and any workflow that can restart services, remains gated: do not run it until you have deliberately decided to make that change. Enabling e-mail notifications is gated too: preview the change first, confirm the recipient list and the notification mechanism, and enable it only after that review. Publishing and validating the maintenance guard, and arming the recurring schedule, are configuration changes; they are not an execution of that schedule. Arming is a merge-only tag change on the SQL machine (`HvUmApproval` from `Pending` to `Approved`, see [Chapter 20](20-update-manager.md)) and is itself the confirmation step: make it only after the guard is published and validated and you have decided to arm it. Verify what is configured by reading back the Azure configuration. The real scheduled installation and event chain, and any other disruptive work, remain gated until you deliberately enable them. Using this design in a production region or subscription needs its own design and security review.

**CLI path:** run read-only checks first. The lab kit's mutation helpers enforce the single resource group, but they cannot tell whether a change is intended. Add a confirmation switch or value to a command only when you intend that specific change: `-InitialBuildApproved` (`Deploy-LabAlerts.ps1`), `-ApprovedReceiverCreation` (`email\activate-email.ps1`), `-ApprovedSampleTest` (`email\test-channel.ps1`), `-ApprovedAttachment` (`email\attach-email.ps1`), `-ApprovedCpuTest` (`email\real-alert-test.ps1`), `-ConfigurationOnly` (`Deploy-LabManagement.ps1`), `-ConfigureAndTest yes` (`management\provision-events.ps1`) and `-InitialBuildMaintenanceApproved yes` (`host-patch.ps1 -Stage Apply`). Looking at management features in the Portal needs none of them. Never claim a configuration-only schedule or workflow was executed.
