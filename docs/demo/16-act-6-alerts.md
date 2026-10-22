# Act 6. Alerts – warn before the phone rings

Act 6 covers minutes 57–65 of the storyline (about 8 minutes). Its goal is to show that proactive alerts exist, that a **real** incident fired and recovered by itself, and that rules, incidents and e-mails are **three different things**. Before you start, the Azure Portal tab Monitor → Alerts → Alert rules (Tab 4 of Act 0) must be open. For section 6.3 your local receipt note `mail-receipt-evidence.json` (explained in 6.3) must be on the Operator PC and PowerShell must be ready. Times are written in UTC with local time (LT, UTC+7) alongside; the real alert, its e-mails and the recorded CPU scenes all fall on the same recording day, written `<INCIDENT_DATE>` in this guide.

## 6.1 The rules

> **Where to run it:** **Azure Portal**.

> **Do this:** In the top search box type `Monitor` and open **Monitor**. In the left menu click **Alerts**. On the toolbar click **Alert rules**. Click the **Search** box (top left of the table) and type `hv-`. Wait a few seconds until the list shortens. Read the **Name**, **Severity**, **Target scope** and **Status** columns.

The Alert rules list, filtered on `hv-`, shows these parts in reading order:

- **(1)** The **Search** box with `hv-`. Without it the list also shows rules that do not belong to the lab.

- **(2)** **Rule names** such as `hv-host-cpu-high`, `hv-guest-contention-high`, `hv-sql-grants-pending`.

- **(3)** **Severity:** "2 – Warning" for the -high rules and "1 – Error" (critical) for the -critical rules.

- **(4)** **Status: Enabled** for every rule.

- **(5)** **Showing 1 – 17 of 17** `hv-` rules.

| **Rule family** | **Warning** | **Critical** | **Looks back** |
|---|---|---|---|
| CPU (host, guest, group) | > 80% | > 90% | 10 minutes |
| Physical memory (Windows, group) | > 85% | > 90% | 10 minutes |
| Disk latency (with real I/O, IOPS > 1) | > 20 ms | > 50 ms | 5 minutes |
| Hyper-V scheduling wait (guest, group) | P95 > 110,000 ns | – | 5 minutes |
| Heartbeat missing | > 10 minutes | – | – |
| SQL memory grants pending | > 0 | – | 5 minutes |
| SQL guest OS available memory low | < 1,024 MB | – | 10 minutes |

The rule payloads are in [lab-kit/alerts](../../lab-kit/alerts/) and the reasoning behind the thresholds is in [setup chapter 19](../setup/19-alerts.md).

> **Be honest:** "These thresholds are **demonstration values** calibrated in the lab. The wait threshold, for example, is three times the quiet-time measurement, rounded up. They are not a production policy."

## 6.2 A real incident that fired and recovered by itself

On the afternoon of the recording day (about 14:40–15:00 LT, 07:40–08:00 UTC) we ran the CPU load a **second time**, as a rehearsal for the alert and e-mail flow. The group-contention rule **fired for real** at 14:46 LT (07:46 UTC) and **resolved automatically** at 15:16 LT (08:16 UTC), after the load had ended. (In Act 8B an AI agent investigates this same alert.)

> **Do this:** Open Monitor → Alerts, set **Time range** to Custom for the recorded window (the date of the recording, 14:00–16:00 LT, which is 07:00–09:00 UTC), and open the alert named `hv-cluster-contention-high`. On the page, read **Severity**, **Monitor condition**, **Alert rule** and **Start date time**. If you saved the link of this alert instance before the session, you can open it directly instead.

The alert instance page shows these parts in reading order:

- **(1)** **Severity Sev2** (warning).

- **(2)** **Monitor condition: Resolved.** Azure closed it by itself when the condition cleared.

- **(3)** **Alert rule:** `hv-cluster-contention-high`, in this resource group.

- **(4)** **Start date time: 2:46:00 PM** on the recording day (local time, LT). The fired time was 07:46:00 UTC.

> **Say this:** "A configured rule is a promise. This page is the proof: on the recording day at 14:46 local time the rule fired because the three Windows guests were waiting too long for the processor. At 15:16 it resolved **by itself** when the test ended. Nobody pressed a button."

> **If something goes wrong:** Do **not** change the **Alert state** (New / Acknowledged / Closed) and do not edit the rule. "New" is the user-response state; "Resolved" is Azure's own monitor condition. They are different.

> **Beginner tip:** **One incident, three views.** The alert fired at 14:46 LT (this act). The e-mail proves the delivery (6.3). **Act 11** replays the same hour, 14:30–15:30 LT, in the Command Center: the CPU episode starts at **14:45** and lasts **15 minutes**. Tell it as one story.

## 6.3 The e-mail proof

The alert's action group sends an e-mail to a **single recipient** (for example `operator@example.com`). Azure's service result does not prove that a message arrived, and the command line cannot see the mailbox ([setup chapter 19](../setup/19-alerts.md), sections 19.6 and 19.8). So the delivery proof for the recorded incident is a **local note** that you keep yourself after checking the mailbox privately: a JSON list of the e-mails you received. No script of the lab kit creates this note; the alert side of the same incident is written by the kit's evidence scripts as `alerts-firing.json`, `alerts-recovery.json` and `selected-alert-resolved.json` in `lab-kit\email` when you run them; these files are not part of the repository. Show the note on your own PC, not in the mailbox.

> **Where to run it:** **Operator PC → Windows PowerShell.** Read-only (reads a local file).

**Show the recorded e-mail receipts**

```powershell
Set-Location '<REPO_ROOT>\lab-kit\email'
$mail = Get-Content -LiteralPath '.\mail-receipt-evidence.json' -Raw | ConvertFrom-Json
$mail | Select-Object Kind,ReceivedUtc,Rule,AlertId,FiredUtc,ResolvedUtc | Format-List
```

Keep the note next to the other e-mail evidence in `lab-kit\email` (any local folder works; change the path in the first line). Its fields are `Kind`, `ReceivedUtc`, `Rule`, `AlertId`, `FiredUtc` and `ResolvedUtc`.

> **What you should see:** Several records: an enrolment mail (Azure's notice that the address was added to the action group), a **sample test** mail (07:39:18 UTC), the **Fired** mail (07:46:14 UTC) and the **Resolved** mail (08:17:12 UTC) for the same alert ID.

> **Be honest:** "The sample test e-mail is the sample message Azure Monitor generates when you test the action group, **not** a real incident. The Fired and Resolved e-mails belong to the same real incident. This proves delivery for **this** incident and **this** recipient only – not every rule and not every future event."

> **Good to know:** The alert is based on **a KQL query that you can read and edit**, so the logic is transparent. The query of every rule is in the payloads under [lab-kit/alerts](../../lab-kit/alerts/).
