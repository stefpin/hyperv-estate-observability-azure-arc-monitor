# 25. Cost, continuous-operation safety and eventual teardown

This document covers how to see what the lab costs without changing other resources, the daily non-disruptive checks that keep a continuously running lab healthy, and how teardown works. Teardown is a separate, deliberate task and is not part of routine preparation or an end-of-demo cleanup. Use it when you budget the lab, set up daily health checks, or decide to remove the lab.

Commands in this document run on your own operator PC, from the `lab-kit` folder ([section 2.2](02-tools-secrets-and-conventions.md#22-open-the-lab-kit-on-the-operator-pc)), in a PowerShell session where the lab context has been loaded with `. .\context.ps1`.

## 25.1 Cost visibility without changing other resources

**What you are doing:** This gives a cost view for the lab resource group only. It is for visibility, not for rewriting other subscription settings. Tag the resource group (for example with `purpose=hv-hyperv-arc-demo`, [section 4.2](04-azure-foundation.md#42-resource-group-and-virtual-network)) so that the cost of the lab can be attributed to it; the tags are visible on the resource group's **Tags** page.

> **Do this on:** the Azure portal in a web browser on the operator PC for Cost Analysis, and on the operator PC for the supporting inventory references.

Portal clicks:

1. Open **Cost Management**.
2. Click **Cost analysis**.
3. Scope to the lab resource group.
4. Use daily view.
5. Group by resource or service.

Charges include the Windows E8s_v5 host, Premium disks, Bastion, NAT/public IP, Log Analytics/custom logs, SQL Enterprise pay-as-you-go, and any applicable Defender/Update Manager benefits or charges. Do not enable or disable a subscription plan to make a demo cost chart cleaner.

CLI path: use the resource inventory (`az resource list -g $RG -o table`, or `resources.json` written by `lab-kit/Get-LabEvidence.ps1`, [section 23.1](23-reports-and-export.md#231-build-a-report-with-reproducible-boundaries)), the public Azure pricing pages and a Cost Management query at this resource group when your account has read permission. The public SQL Server Enterprise pay-as-you-go price observed on the Azure pricing page in October 2026 was **US$0.375 per vCore-hour**, with a four-core minimum, which is **about US$1.50 per hour** and about US$36 per day for a continuously running four-core SQL Server, before discounts, taxes and other services. This is a planning estimate in US dollars at list price, not an invoice or a perpetual fixed price; the price depends on the region and the agreement, so check the current Azure pricing pages before you budget.

> **Warning:** Keep SQL Server running. The lab runs SQL Server continuously, so stopping SQL is not a cost-control option in this lab.

## 25.2 Daily non-disruptive checks

**What you are doing:** These are the daily continuity checks. They keep the lab healthy without breaking the ongoing demo environment.

> **Do this on:** the Azure portal in a web browser on the operator PC for the visual checks, and on the operator PC for the scheduled read-only evidence collection.

Portal checks:

1. Verify Arc Connected.
2. Verify the latest workbook data.
3. Verify the SQL service/dashboard.
4. Verify disk free space.
5. Verify alert history.
6. Avoid unattended update installs or restarts during demonstrations.
7. Review log retention and collector growth.

CLI path: run the read-only `Get-LabEvidence.ps1` (`lab-kit/Get-LabEvidence.ps1`) each day, for example from a task that you schedule on your own PC while you are signed in to Azure CLI. It makes no guest command and no Azure write.

> **Do this on:** your own computer, in the `lab-kit` folder of a PowerShell window where `context.ps1` is loaded. Run the exact command below.

```powershell
.\Get-LabEvidence.ps1 -OutputDirectory .\exports\daily
```

**What you should see:** the Arc machine, resource and alert-rule inventories and the results of the five health queries as JSON files in `exports\daily`, and the final line `Read-only public evidence export completed; no guest commands or Azure writes.` ([section 23.1](23-reports-and-export.md#231-build-a-report-with-reproducible-boundaries)). Compare the heartbeat ages and the resource list with the day before.

Guest collector log growth is limited differently on each guest. On `RHEL94-GUEST`, `logrotate` keeps seven rotations of `/var/log/hv-demo/http-latency.json` (daily, or at 50 MB), and the storage observer deletes its own `/var/log/hv-storage/disk-<yyyymmdd>.log` files that are older than seven days. Nothing prunes `C:\HV-Demo\logs\sql-memory-<yyyymmdd>.json` on `SQL2019-GUEST`, which receives one file per UTC day. A reviewed retention task may delete **only aged observer JSON files** of that pattern after the required exports. Do not delete live-day logs, databases, VHDX files, update inventory or any secret source file as "cleanup." Preserve monitoring continuity and keep SQL Automatic/Running.

## 25.3 Teardown is a separate, deliberate task

**What you are doing:** This section is only for the teardown phase, when you have decided to remove the whole lab. It is not part of routine preparation or the live demo, and it is never an end-of-demo cleanup.

> **Do this on:** the Azure portal in a web browser on the operator PC, or on the operator PC in PowerShell with Azure CLI for the destructive route. Do it only when you intend to remove the whole lab and have exported what you need.

Portal clicks:

1. Export the report, the evidence and the public configuration first ([Chapter 23](23-reports-and-export.md)).
2. Confirm that no required DB data remains.
3. List this resource group's resources.
4. Open the resource group.
5. Click **Delete resource group**.
6. Type the exact RG name.
7. Confirm only after review.

This removes the lab, including the running SQL guest.

> **Do this on:** your operator PC, in PowerShell with Azure CLI, in the `lab-kit` folder, for teardown only. Run the exact commands below only when you are certain you want to remove the lab.

```powershell
. .\context.ps1
Assert-LabContext
az resource list -g $RG --subscription $SUB --query "[].{Name:name,Type:type}" -o table
# DESTRUCTIVE: removes the whole lab. Use only after you have exported what you need.
az group delete -n rg-hyperv-arc-monitor-demo --subscription $SUB --yes
```

These commands call `az` directly because `Invoke-LabAz` refuses teardown commands by design. `Assert-LabContext` stops with `Wrong subscription or tenant; no changes are permitted.` when the signed-in account is not the lab account, and `--subscription $SUB` pins both commands to the lab subscription.

**What you should see before deletion:** the resource list shows only lab resources. **What you should see after deletion:** this resource group is absent, and no other resource group, provider or policy was changed. Do not unregister subscription providers or remove shared subscriptions, workspaces, policy assignments or Defender plans. Disconnect the Red Hat registration and the Arc guest agents before deletion only if the guest disks will be retained or reused; if all disks are destroyed, document that removal path.
