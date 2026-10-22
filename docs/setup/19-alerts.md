# 19. Alerts - meaningful thresholds and Azure-native e-mail

This document explains how to review, wire up and prove the lab's alert setup in a careful, beginner-friendly way. It covers the alert thresholds and the reasoning behind them, how to inspect the exact condition of a rule, the difference between a configured rule and a fired alert, how to create one Azure-native e-mail action group (only if none exists) and attach it to the existing rules without changing their conditions, how receiver verification, the sample test and a genuine Fired/Resolved incident differ, a genuine end-to-end CPU rehearsal with automatic recovery, and e-mail troubleshooting. Use it when you review the alert rules, enable notifications, or rehearse a real alert.

An **action group** is Azure Monitor's notification target. In this lab it is an Azure-native e-mail destination. A **scheduled query rule** is an alert rule that runs a KQL query on a schedule and fires when the rule condition becomes true.

> **Warning:** Notification settings send real e-mail. Only enable notifications in an environment you own or are authorised to change, use a single named recipient (this guide uses `operator@example.com`), and never print tokens, one-time passcodes, private mailbox content, `ENVIRONMENT.txt` or webhook URLs.

Commands in this document are written to run from the `lab-kit` folder (`cd lab-kit`) in a PowerShell session where the lab context has been loaded with `. .\context.ps1`. The context provides helpers such as `Invoke-LabAz` and variables such as `$RG` and `$ResourcePrefix`. The rule payloads are in `lab-kit/alerts/`, the deployer is `lab-kit/Deploy-LabAlerts.ps1` and the e-mail helpers are in `lab-kit/email/`.

## 19.1 Example operational thresholds (lab values, not production standards)

These values are example thresholds for the lab demonstration. They are a starting point that you adapt to your environment, not a production standard. Read the table exactly as written.

| Signal | Warning | Critical / additional requirement |
|---|---|---|
| CPU utilization | >80% sustained 10 minutes | >90% sustained 10 minutes |
| Physical memory used | >85% sustained | >90% sustained; verify denominator/available-memory counter |
| Disk latency | >20 ms for 5 minutes | >50 ms; meaningful concurrent I/O required |
| Hyper-V wait | >3 times the calibrated quiet baseline | Calibrate actual time units per guest; do not call it % |
| Heartbeat | Missing >10 minutes | Machine had a known recent baseline; avoid "never seen" false conclusions |
| SQL memory grants pending | Nonzero for 5 minutes | Query workspace pressure, not generic OS memory alert |

The thresholds configured in the deployed rules (listed next) override the example values above. They are example values for the lab, not a production policy. A five-minute CPU scene may not fire a ten-minute sustained alert; that is correct.

The deployed inventory contains **17 enabled rules**:

- warning CPU >80% and critical >90% for host, guest and group over 10-minute lookbacks;
- warning physical memory >85% and critical >90% for Windows machines and the group over 10-minute lookbacks (the rule queries compare the available bytes with the machine size built into the query: 64 GiB for `HV-HOST-01`, 12 GiB for `SQL2019-GUEST`, 8 GiB for each of the three Windows guests; change the query if you change a machine size);
- missing heartbeat >10 minutes for any of the six lab machines (a machine that has never sent a heartbeat counts as 1,440 minutes);
- guest and group wait >110,000 **nanoseconds per dispatch** over five minutes;
- SQL pending grants >0 over five minutes;
- SQL OS available memory <1,024 MB over ten minutes;
- disk transfer latency warning >20 ms and critical >50 ms over five minutes **with IOPS >1**.

Warning rules are severity 2; the six critical counterparts are severity 1. These criteria and settings must be preserved when you attach e-mail: attaching an action group changes only the rule's `actions`. Inspect each exact payload's aggregation rather than assuming every signal uses the same calculation: the CPU and memory rules average, the wait rules use the 95th percentile, and the pending-grants rule takes the **minimum** over its lookback, so it fires only when every sample in the window shows pending grants. The cluster rules name the three Windows guests `WIN2019-GUEST`, `WIN2022-GUEST` and `WIN2025-GUEST-01` explicitly.

These log alerts evaluate the query and aggregation over their lookback. They are not a promise that every individual sample exceeded the threshold continuously.

The wait threshold is calibrated to this lab: during a quiet 15-minute baseline window the maximum per-guest P95 wait was **35,732 ns**; three times that is **107,196 ns**, rounded up to **110,000 ns**. Guest and group rules evaluate P95 wait over five minutes. This is an explicit measured calibration for this lab, not a hidden alert-fabrication trick and not a universal production limit. The deployed rule payloads are authoritative; check them rather than an older inventory export.

## 19.2 Create/query the rule and inspect its exact condition

**What you are doing:** In this step, you review exactly how a rule is defined. The goal is to confirm the real condition, scope, threshold, and actions, not to make casual changes.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, or on the operator PC in a Windows PowerShell window with Azure CLI for the CLI route.

Portal clicks for a fresh build only:

1. In the Azure portal, open **Monitor**.
2. In **Monitor**, click **Alerts**.
3. In **Alerts**, click **Alert rules**.
4. Click **Create**.
5. Click **Alert rule**.
6. In the new rule flow, scope the proper lab workspace or supported machine signal.
7. In **Condition**, choose **Custom log search**.
8. Paste the supplied rule KQL.
9. Inspect the dimensions and the machine/cluster filtering.
10. Set the aggregation, comparison, threshold, evaluation frequency, and lookback exactly as in the deployed payload.
11. In **Details**, use the lab RG, a meaningful rule name, the correct severity, and the correct enabled state.
12. In **Actions**, select only the existing e-mail action group after completing the checks in [section 19.4](#194-preview-what-azure-will-send-and-keep-the-notification-boundary-narrow) and [section 19.5](#195-inventory-first-create-exactly-one-correct-receiver-only-if-absent); preserve any existing groups.

For an existing lab, do not recreate rules.

For existing rules:

1. Open the rule.
2. Click **Edit**.
3. Inspect the configuration.
4. Do **not** lower the threshold.
5. Review CPU, memory, wait, storage, heartbeat and SQL grants coverage.
6. Confirm that the cluster rules list only the three Windows guests `WIN2019-GUEST`, `WIN2022-GUEST` and `WIN2025-GUEST-01`.
7. Confirm that SQL/storage rules use their own valid conditions.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI. Run the exact commands below unchanged.

```powershell
az monitor scheduled-query list -g $RG `
  --query "[].{Name:name,Enabled:enabled,Severity:severity,Scopes:scopes}" -o json
.\Deploy-LabAlerts.ps1
```

**What you should see:** the rule detail page shows the rule's scope, its action group and its condition; the command lists the lab's rules with their enabled state, severity and scopes. On a lab that already has the 17 rules, `Deploy-LabAlerts.ps1` prints `Preserved existing rule, current criteria/actions unchanged: <rule name>` for each rule and ends with `Existing rules preserved. Email attachment is a separate reviewed actions-only change.` On a fresh build, without the switch described next, it stops with `A rule is missing; pass -InitialBuildApproved to create it.`

For a fresh build only, create the 17 rules from the payloads in `lab-kit/alerts/`. The payloads carry no action group, so nothing is sent.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI, in the `lab-kit` folder. Run it once on a new build, after the data sources of [chapter 11](11-azure-monitor-agent-and-dcrs.md) and [chapter 15](15-sql-custom-log-table-and-dcr.md) exist.

```powershell
.\Deploy-LabAlerts.ps1 -InitialBuildApproved
Remove-Item .\alerts\put-*.json -ErrorAction SilentlyContinue
```

The deployer writes each request body it sends as `alerts\put-<rule name>.json` next to the payloads, and both `Deploy-LabAlerts.ps1` and `email\attach-email.ps1` ([section 19.7](#197-attach-to-all-17-existing-rules-without-changing-their-conditions)) ignore these `put-*.json` files. The second command removes them so that only the 17 payload files stay.

The deployer is an **initial-build** helper, not an e-mail reset. It skips a rule that already exists instead of replacing its current actions or criteria; it creates a missing rule only with `-InitialBuildApproved`. It does not create receivers and it does not detach an action group. For a live lab, use the read-only inventory and the attachment procedure in [section 19.7](#197-attach-to-all-17-existing-rules-without-changing-their-conditions). The operational wait threshold remains **110,000 ns**; no temporary lowered threshold is used to claim a real end-to-end pass.

## 19.3 Fired alert versus rule configuration

**What you are doing:** Here you separate two different things that beginners often mix up. A configured rule means the alert can run. A fired alert means Azure actually detected a matching condition and created an alert instance.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, or on the operator PC with the reviewed read-only scripts for the CLI route.

Portal clicks:

1. Open **Monitor**.
2. Click **Alerts**.
3. Filter to this RG.
4. Filter to the UTC rehearsal window you need to show.
5. Open the alert instance.
6. Inspect the alert condition, fired time, severity, and affected resource.

If no alert fired, show the rule or query and say **configured, not demonstrated fired**. Alert-history absence is not proof of no workload.

CLI path: use the Monitor alert-management REST API scoped to this resource group, as in `lab-kit/queries/alert-history.ps1`, or query the actual result windows. Rule existence is not a fired alert. If you use a temporary test threshold, record the original, test and restored values and times, and verify the restoration. Never present a temporary threshold as production and never silently create a fake alert record.

A fired instance of one rule shows that telemetry and alert history work for that rule. It does not prove that every CPU, memory or critical rule would fire, and it does not prove e-mail delivery; delivery is proven separately (see [section 19.6](#196-receiver-verification-and-sample-test-are-separate-checks) and [section 19.8](#198-genuine-end-to-end-cpu-rehearsal-then-automatic-recovery)).

## 19.4 Preview what Azure will send, and keep the notification boundary narrow

**What you are doing:** Before any notification write action, you check exactly what kind of e-mail Azure may send. This keeps the notification boundary narrow and clear. Only enable notifications in an environment you own or are authorised to change.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal preview, and on the operator PC with the reviewed lab kit for the CLI preparation.

Portal review steps:

1. Confirm the intended subscription and resource group.
2. Review the **Email** receiver (`operator@example.com` in this guide).
3. Confirm that the common alert schema is enabled.
4. Review the notification types that may appear during setup and testing.

Expect these notification types: a possible verification/one-time-passcode message, a membership/welcome notice, a synthetic **LogAlertV2** sample, then genuine **Fired** and **Resolved** lab notices.

Preview the native subject/body fields:

1. Alert rule and state.
2. Severity.
3. UTC time.
4. Affected resource/resource ID.
5. Subscription/RG.
6. Condition/query information.
7. Portal links.

Exact native wording and future dynamic values are Azure-controlled, not custom text. **Creating the receiver itself can send a verification or membership e-mail**; plan for it rather than treating it as a silent preparatory step.

CLI path: load the lab context, then read the safe preview and the reviewed helper sources in `lab-kit/email/` before running anything that writes. If you repeat the setup for another recipient, tenant, group or delivery mechanism, review the preview again first. Do not print tokens, OTPs, private mailbox bodies, `ENVIRONMENT.txt` or webhook URLs.

## 19.5 Inventory first; create exactly one correct receiver only if absent

**What you are doing:** First you inventory what already exists. Only if the e-mail action group is truly absent do you create it. This avoids duplicates and unnecessary notification e-mails.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, then on the operator PC in Windows PowerShell with Azure CLI for the read-only inventory route.

Portal clicks:

1. Verify that the Portal directory and subscription match the lab subscription you selected.
2. Open **Monitor**.
3. Click **Alerts**.
4. Click **Alert rules**.
5. Filter to **rg-hyperv-arc-monitor-demo**.
6. Inspect the 17 existing enabled rules, thresholds, frequencies, lookbacks and current action groups.
7. Go back to **Monitor > Alerts** and click **Action groups**.
8. Filter to this RG.
9. Inspect the existing groups before clicking **Create**.
10. If `ag-hv-demo-email` already exists, open it and validate it. Do not create a second group or send another membership notice just for rehearsal.
11. For a fresh receiver only, click **Create action group**.
12. In **Basics**, use the lab subscription, this RG, region **Global**, action group `ag-hv-demo-email`, and short display name **HVDEMO**.
13. Go to **Notifications**.
14. For **Notification type**, choose **Email/SMS message/Push/Voice**.
15. Choose **Email**.
16. Enter **only** `operator@example.com` (replace it with your own operator address).
17. Enter receiver name **HvDemoRecipient**.
18. Set **Enable the common alert schema** to **Yes**.
19. Do not choose **Email Azure Resource Manager Role**: that can notify other role members.
20. Add no SMS, webhook, runbook, ARM-role e-mail or additional recipient.
21. In **Actions**, add nothing.
22. Review the recipient, type/schema and RG.
23. Re-check the recipient, the notification types you reviewed in [section 19.4](#194-preview-what-azure-will-send-and-keep-the-notification-boundary-narrow) before you click **Create**.
24. If Azure asks for verification, follow [section 19.6](#196-receiver-verification-and-sample-test-are-separate-checks).

Creating a group is not proof that its e-mail receiver is Verified.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI. Run this read-only inventory exactly as shown.

```powershell
. .\context.ps1
Invoke-LabAz monitor action-group list -g $RG -o json
$RulesUrl = "https://management.azure.com$ResourcePrefix" +
  '/providers/Microsoft.Insights/scheduledQueryRules?api-version=2023-12-01'
$Rules = (Invoke-LabAz rest --method get --url $RulesUrl -o json |
  Out-String) | ConvertFrom-Json
$Rules.value | Select-Object name,
  @{n='Enabled';e={$_.properties.enabled}},
  @{n='Groups';e={$_.properties.actions.actionGroups -join ';'}}
```

**What you should see:** the 17 existing lab rules and whether the e-mail action group already exists. A failed lookup is not "absent"; resolve permissions or context first. If the group already exists, validate and reuse it; do not recreate it. Azure REST bodies use **`--body "@<local JSON path>"`**, not shell-inline JSON with escaped quotes or ampersands. Do not redeploy the original rule payloads (which carry no action group) over live rules. Rule descriptions are free text and can be out of date: check the real `actionGroups` and receiver state in a GET, not the description.

> **Do this on:** your operator PC, in PowerShell. Run it only when you are authorised to notify this recipient.

```powershell
# Existing group: inspect and reuse; no create if already present.
.\email\activate-email.ps1 -ApprovedReceiverCreation
```

The `-Approved...` switches on the e-mail helpers are explicit confirmation switches: a helper refuses to write anything unless you pass its switch, so a script is never run by accident. `activate-email.ps1` needs its switch only when it has to create the group; for a group that already exists it only validates it.

If the group is missing, the helper's create command is `az monitor action-group create`, equivalent to:

```powershell
az monitor action-group create -g $RG -n ag-hv-demo-email `
  --short-name HVDEMO --location global `
  --action email HvDemoRecipient operator@example.com usecommonalertschema
```

The helper checks the configured tenant and subscription first and refuses any extra receiver or notification type. Read its source (`lab-kit/email/activate-email.ps1`) for the exact tag and argument sequence. Reading this document sends no e-mail.

**What you should see:** `Action group=<resource ID>; enabled=True; recipient=operator@example.com; commonSchema=True; status=Enabled.` followed by a reminder that creating a receiver may send an Azure-generated verification or membership message and that the alert rules are not attached yet. The helper stops with `Unexpected action-group recipient list; do not attach it` if the group holds any other recipient or notification type. It saves the group definition as `lab-kit/email/action-group-initial.json`; the e-mail helpers write their response files next to themselves, and `lab-kit/email/*.json` is git-ignored. The address is built into `activate-email.ps1` and `test-channel.ps1`: to use another address, run `tools/Set-RepoContext.ps1 -Recipient <address>` first ([chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

## 19.6 Receiver verification and sample test are separate checks

**What you are doing:** In this section, you verify the receiver state first and test the notification channel second. These are related, but they are not the same check.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal steps, and on the operator PC in Windows PowerShell with Azure CLI for the GET check and sample test helper.

Portal clicks to inspect verification:

1. Open **Monitor**.
2. Click **Alerts**.
3. Click **Action groups**.
4. Open the action group.
5. Open **Notifications**.
6. Inspect the saved e-mail receiver.
7. Inspect whether Azure shows a verification prompt.

Azure documentation says a new address must complete one-time-passcode (OTP) verification within **30 minutes**; verification persists for that address across action groups in the same tenant. When Azure requests it, find the Azure verification message in your mailbox privately and enter the code in the Portal verification flow. If the code has expired or is missing, open the group and use **Resend** for the same address. Never publish a code, verification link or raw message.

In the reference lab, **no OTP was requested** for the receiver and the API receiver status was **Enabled**; the sample and genuine notices that followed proved delivery. Do not invent a verification step, and do not claim that all tenants or addresses are exempt. Check the saved receiver again after any requested verification.

> **Do this on:** your operator PC, in Windows PowerShell with Azure CLI. Run this exact receiver GET.

```powershell
$GroupId = "$ResourcePrefix/providers/Microsoft.Insights/" +
  'actionGroups/ag-hv-demo-email'
Assert-LabResourceId $GroupId
$GroupUrl = "https://management.azure.com$GroupId" +
  '?api-version=2023-01-01'
$Group = (Invoke-LabAz rest --method get --url $GroupUrl -o json |
  Out-String) | ConvertFrom-Json
$Group.properties.emailReceivers |
  Select-Object name,emailAddress,useCommonAlertSchema,status
```

**What you should see:** the sole e-mail recipient, `useCommonAlertSchema` true and receiver **status `Enabled`**. Report that literal value; "Verified" is not what the API returns. Successful creation alone is not delivery evidence or proof that no OTP flow is needed. Complete any verification Azure requests before testing. Mailbox sign-in and Azure CLI sign-in are separate identities: one successful login does not guarantee the other.

After verification, test the channel in the Portal:

1. Open the action group.
2. Click **Test**.
3. Choose sample type **Log alert V2 / LogAlertV2**.
4. Select only the e-mail receiver.
5. Click **Test**.
6. Inspect the Azure service result.
7. Independently verify that the sample message arrived in the recipient mailbox.

The sample uses Azure's reference alert content; it **does not prove the lab query evaluated true**, and its sample resource ID and Alert ID are not a genuine lab incident. Record service completion and mailbox received time separately.

CLI equivalent: in the Azure CLI used for the lab, `test-notifications create` is the only test-notification subcommand; neither **`show` nor `get-status`** is available. The create command waits and returns **state Complete / actionDetails Status Succeeded**; use that returned result, not an invented follow-up subcommand. This command sends a real sample e-mail; service completion remains distinct from mailbox receipt.

> **Do this on:** your operator PC, in PowerShell. This sends one real synthetic sample e-mail to the receiver.

```powershell
.\email\test-channel.ps1 -ApprovedSampleTest
# Exact CLI operation inside the guarded helper:
# az monitor action-group test-notifications create -g $RG `
#   --action-group ag-hv-demo-email --alert-type logalertv2 `
#   --add-action email HvDemoRecipient operator@example.com `
#   usecommonalertschema --output json
```

The helper first validates the group with `activate-email.ps1` (so the group must already exist), saves Azure's answer as `lab-kit/email/sample-test-response.json` and prints `Approved Azure logalertv2 sample test requested; inbox receipt must be verified separately.` followed by the JSON result. No REST fallback is documented. The sample e-mail can arrive before the command reports completion, which is valid: delivery and long-running operation completion are separate timestamps.

## 19.7 Attach to all 17 existing rules without changing their conditions

**What you are doing:** In this step, you attach the e-mail action group to the existing rules. You are not rebuilding rules and you are not changing thresholds or KQL.

> **Do this on:** the Azure portal in a web browser on the operator PC for the Portal route, and on the operator PC in PowerShell for the reviewed helper route.

Portal clicks:

1. Open **Monitor**.
2. Click **Alerts**.
3. Click **Alert rules**.
4. Filter to this RG.
5. For each of the 17 rules, open the rule.
6. Click **Edit**.
7. Click **Actions**.
8. Click **Select action groups**.
9. Add the e-mail action group.
10. Retain any existing groups/receivers.
11. Save the rule.

Do not change scope, KQL, dimension splitting, aggregation, threshold, failing periods, severity, enabled state, the five-minute evaluation frequency, lookback or automatic mitigation. Keep a before/after inventory and verify **17 of 17** attachments from an actual resource GET.

CLI path: the reviewed helper GETs the current rule first, validates each rule, scope and group ID against the lab RG, merges the e-mail action group into `properties.actions.actionGroups`, preserves the other `actions` fields and sends an **actions-only PATCH** with a local JSON `@file`. It must not PUT an old full payload or wipe another group. It preserves the current criteria and settings and validates the before/after definition comparison. An attachment count is evidence of configuration, not of query firing or received mail.

> **Do this on:** your operator PC, in PowerShell. Run it only when you are authorised to notify this recipient from the existing 17 rules.

```powershell
.\email\attach-email.ps1 -ApprovedAttachment
```

Rules that are already attached are preserved without another PATCH. The helper validates all 17 source names and compares criteria, scopes, enabled state, severity, evaluation frequency, lookback and `autoMitigate` before and after. It retains existing groups and other action properties. It requires exactly 17 payload files in `lab-kit/alerts/` (the generated `put-*.json` files are ignored; see the note in [section 19.2](#192-createquery-the-rule-and-inspect-its-exact-condition)), calls `activate-email.ps1` first (so the action group must already exist), prints `Attached approved email group to <rule name>; conditions unchanged.` for each rule, and writes one `attach-<rule name>.json` PATCH body per rule and the summary `rule-attachments.json` into `lab-kit/email/`.

## 19.8 Genuine end-to-end CPU rehearsal, then automatic recovery

**What you are doing:** This is the real rehearsal path for a genuine Fired and Resolved alert flow. The aim is to show a real lab condition, real alert processing, real e-mail, and automatic recovery, without lowering thresholds or faking state.

> **Do this on:** the Azure portal in a web browser on the operator PC for monitoring and evidence review, and on the host or operator PC as explicitly stated for the workload launch route you choose.

Portal steps:

1. Open **Monitor > Alerts**.
2. Filter to this RG.
3. Show the current Monitor condition and UTC time.
4. If an instance already **Fired before attachment**, allow that instance to become **Resolved** first. Do not manually mark its alert state Closed to pretend the Monitor condition resolved.
5. Record the quiet baseline, the receiver status and the 17 confirmed attachments.
6. Complete any verification Azure requests.
7. Keep SQL Server/Agent **Running/Automatic**.
8. Do **not** load SQL, restart the host or guests, lower thresholds or fake an alert.
9. Open **Virtual machines**.
10. Open **HV-HOST-01**.
11. Click **Connect**.
12. Click **Bastion**.
13. In the host elevated PowerShell session, start the bounded **900-second** CPU scene on **WIN2019-GUEST, WIN2022-GUEST and WIN2025-GUEST-01 only**, four workers each.
14. Remember what this means: it is 12 busy Windows vCPUs; RHEL remains the light observer and SQL remains idle-but-running.
15. Watch the workbook and genuine alert history.
16. Allow for query lookback (five/ten minutes), ingestion delay and five-minute evaluation cycles.
17. Do not treat a sample-Test Success or a CPU spike by itself as a pass.
18. Open each actual Fired incident and compare the lab resource, rule, dimensions and Alert ID with the received Azure-native notice.
19. Wait for self-termination and PID-specific cleanup.
20. Wait for quiet telemetry and **automatic** Resolved events.
21. Record actual alert-state times and separate mailbox receipt times.
22. Do **not** reboot for recovery.
23. Show only the Azure lab metadata needed for the demo.
24. Never project a private Inbox list, unrelated messages, a raw e-mail body, an OTP or an authentication session.

> **Do this on:** **HV-HOST-01**, in an elevated Windows PowerShell window; bounded 900-second scene.

```powershell
Set-Location F:\Build\lab-kit
.\Start-LabCpuScene.ps1 -Seconds 900
```

This helper prompts privately for the three Windows guest credentials, checks the host and cleans up only its own recorded, bounded worker PIDs. SQL is excluded. On the operator PC, use the read-only `lab-kit/queries/alert-history.ps1` and the CPU/wait KQL exports with exact UTC bounds. Repeat the same 900-second scene and recovery for each rehearsal, and do not assume that a repeat run produces the same Alert ID or the same send delay.

Alternative CLI route from the **operator PC**: run an equivalent bounded 900-second scene (four workers on each of the three Windows guests) through the guarded Arc helper instead of launching the wrapper on the host. `lab-kit/email/real-alert-test.ps1` runs `lab-kit/sources/demo-v22/host-cpu-rehearsal.ps1` on the host through an Arc Run Command, so the host needs the one-time SSH key preparation described in [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene). **Choose one route, not both.** Private credentials are read only from the existing `ENVIRONMENT.txt` at the repository root ([chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)), in memory; `lab-kit/context.ps1` stages the protected parameters in a permission-restricted `HV-Private` folder in your user profile, outside the repository, and deletes them and the unique Arc Run Command afterwards.

> **Do this on:** your operator PC, in PowerShell; genuine scene plus read-only recovery proof.

```powershell
$RehearsalUtc = [datetime]::UtcNow
.\email\real-alert-test.ps1 -ApprovedCpuTest
.\email\read-alert-evidence.ps1 -Phase Firing -SinceUtc $RehearsalUtc
$Observed = Get-Content .\email\alerts-firing.json -Raw |
  ConvertFrom-Json
$Selected = @($Observed.Alerts | Where-Object {
  $_.Name -eq 'hv-cluster-contention-high'
} | Sort-Object StartUtc -Descending | Select-Object -First 1)
if ($Selected.Count -ne 1) {
  throw 'No genuine new cluster incident yet; inspect ingestion/evaluation.'
}
$NewAlertGuid = ($Selected[0].AlertId -split '/')[-1]
.\email\wait-real-recovery.ps1 -AlertGuid $NewAlertGuid
.\email\verify-sql-continuity.ps1
```

The recovery helper reads only this new Alert ID; it never closes an alert, lowers a threshold or reuses an earlier run's ID as proof of a new run. At a five-minute evaluation frequency, this stateful rule must be clear for **three evaluation periods**, in addition to lookback and ingestion delay. Verify the matching new Fired and Resolved e-mails privately in your mailbox; the CLI cannot infer mailbox delivery.

What each helper prints and writes (all files go next to the scripts in `lab-kit/email/`, which is git-ignored for `*.json`):

- `real-alert-test.ps1` prints the scene output (see [section 17.2](17-cpu-contention-and-response-time.md#172-run-a-bounded-three-guest-cpu-scene)) and writes `real-workload-evidence.json`.
- `read-alert-evidence.ps1` prints one line per alert (`<rule name>: <monitor condition>; start=<UTC>; updated=<UTC>`) and writes `alerts-firing.json`; with `-Phase Recovery` or `-Phase Final` it writes `alerts-recovery.json` or `alerts-final.json`. `-SinceUtc` defaults to one hour ago.
- `wait-real-recovery.ps1` polls the one alert every two minutes for up to 60 minutes, writes `selected-alert-resolved.json` and ends with `Selected genuine alert resolved naturally; now verify its recovery email in Outlook.` If the alert does not resolve in time it stops with an error and changes nothing.
- `verify-sql-continuity.ps1` runs `lab-kit/sources/demo-v22/guest-final-health.ps1` on `SQL2019-GUEST` through Arc, writes `sql-continuity.json` and ends with `FINAL-DEMO-HEALTH-OK`. The health check is strict. It expects the state that [chapter 14](14-sql-memory-ceiling-and-what-it-means.md) and [chapter 22](22-rehearsal-scenes.md) leave behind: `MSSQLSERVER`, `SQLSERVERAGENT` and `SqlServerExtension` Running/Automatic, the `HV-SQL-Memory-Collector` task running, `C:\HV-Demo\stage.txt` containing `idle`, max server memory of exactly 9,829 MB, no offline database, the `HvSqlCollector` login not a sysadmin, the `OrdersDemo` order-lines table present, no leftover rehearsal SQL session, no pending memory grants and no test files in `E:\HV-IO-Demo`. If your SQL guest has another memory size, change the expected value 9829 in that script to your own ceiling from [section 14.2](14-sql-memory-ceiling-and-what-it-means.md#142-configure-a-ceiling-safely) first.

**Pass criteria:**

- a genuine lab query incident with unchanged operational lab thresholds;
- the matching Fired e-mail;
- workload cleanup;
- an automatically Resolved incident and the matching Resolved e-mail;
- the receiver enabled, with any requested verification completed;
- all 17 attachments and settings preserved;
- unchanged SQL process and boot continuity, with SQL Running/Automatic.

The selected cluster contention incident passes on its own; do not generalize it to every incident or e-mail, and other incidents may remain Fired while you test. Failed or missing signals or mail remain missing; do not call a sample or a configuration-only result an end-to-end success. Multiple warning/critical rules and per-machine/group dimensions can send multiple notices. Azure e-mail rate limits apply across subscriptions.

## 19.9 E-mail troubleshooting without broadening the notification scope

Use this table when e-mail behavior is not what you expected. Stay inside the notification scope you set up (one named recipient, e-mail only) while troubleshooting.

| Symptom | Portal path | CLI/evidence path and interpretation |
|---|---|---|
| Receiver requests verification / no OTP | Action group > Notifications > follow any verification prompt; same-address Resend; privately check Junk/Quarantine | In the reference lab the GET said Enabled and no OTP was requested. For a new-address flow, the OTP is valid 30 minutes; do not publish it or assume exemptions |
| Test says Success, no Inbox message | Check mailbox delivery time, Junk and your organisation's mail quarantine with the mailbox administrator | Service result is not receipt evidence; compare separate receivedDateTime metadata |
| No genuine notification after attachment | Inspect Monitor condition; an old Fired instance may need to be Resolved before a new test | Compare attachment UTC, alert start UTC and current Monitor condition; do not assume retroactive delivery |
| Query did not fire | Inspect current condition, dimension and workload evidence; wait for ingestion/evaluation | Preserve the 110,000-ns wait threshold; five/ten-minute lookback plus ingestion and five-minute frequency are not instantaneous |
| Load stopped, still Fired | Confirm quiet telemetry and autoMitigate; wait further evaluation cycles | Keep workload cleanup and Resolved timestamps distinct; Closed alert-state is not automatically Resolved Monitor condition |
| Too many or delayed messages | Review warning/critical and per-machine/group instances; action-group rate-limit notice | Do not infer one signal from e-mail count; deduplicate by actual alert IDs and state; service limits apply |
| Wrong account / access denied | The Azure directory and the mailbox are different identities | Check the tenant and subscription through the lab context; mailbox sign-in cannot replace Azure CLI authorization |

Azure notices come from Azure-owned sender addresses, for example the `azure-noreply` and `azureemail-noreply` senders at `microsoft.com` and the `alerts-noreply` sender at `mail.windowsazure.com`. Treat these as troubleshooting clues, not as permission to trust arbitrary links or to change your mail policy. Verify the actual sender and the lab metadata, and ask your mailbox administrator about quarantine without pasting raw private mail into documentation or tickets.
