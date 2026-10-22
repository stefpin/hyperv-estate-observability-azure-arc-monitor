# Act 0. Before the audience arrives

Act 0 is the preparation you finish before the audience arrives. It takes about 10 minutes. Its goal is to make sure the lab is healthy and every browser tab is ready, so that you never have to search for something while people are watching. Before you start, the lab host `HV-HOST-01` and its five guests must be running, you must be signed in to the Azure Portal with the lab account, and – for the optional checks in section 0.3 – Windows PowerShell and Azure CLI (`az`) must be available on the Operator PC.

## 0.1 Open these browser tabs in this order

- **Tab 1 – Azure Portal**, Azure Arc → Machines, filtered to the lab resource group `rg-hyperv-arc-monitor-demo` (Act 1).

- **Tab 2 – Azure Portal**, the Workbook `Hyper-V and SQL Estate Report` in **Read** mode (Act 2).

- **Tab 3 – Azure Portal**, SQL Server instance `SQL2019-GUEST` (Act 5).

- **Tab 4 – Azure Portal**, Monitor → Alerts → Alert rules (Act 6).

- **Tab 5 – Grafana Operations Cockpit** (Act 9).

- **Tab 6 – Grafana Command Center V3 Core** (Act 11). You can open V1 and V2 later.

> **Beginner tip:** Right-click a tab → **Pin** so tabs stay small and in order. Give each tab a short name by using different resources. Close every other tab, especially mail and chat.

## 0.2 Quick health check in the Portal (2 minutes)

- In Tab 1, check that you see **6 machines** and every **Arc agent status** is **Connected** (see Act 1).

- In Tab 5 (Grafana Operations Cockpit), check the tiles **Fresh 6 · Stale 0 · Missing 0 · Expected 6**.

- If both are true, the telemetry is fresh. Continue.

> **If something goes wrong:** If a machine is **Offline** or **Stale**, do **not** repair it. Tell the audience that you will use **recorded evidence** for the affected scene. The lab keeps SQL Server running at all times; never restart anything.

## 0.3 Optional health check from PowerShell

> **Where to run it:** **Operator PC** → Start → type `PowerShell` → open **Windows PowerShell** (not Cloud Shell, not "Run as administrator"). The commands below are **read-only**.

**Step 1 – confirm you are signed in to the right subscription**

```powershell
$ErrorActionPreference = 'Stop'
$SUB = '<SUBSCRIPTION_ID>'
$RG  = 'rg-hyperv-arc-monitor-demo'
az account show --subscription $SUB --query "{Subscription:id,Tenant:tenantId,State:state}" -o table
```

Replace `<SUBSCRIPTION_ID>` with the ID of your lab subscription before you run the block.

> **What you should see:** A small table with your lab subscription ID, your tenant ID and State `Enabled`.

> **If something goes wrong:** If it says you are not signed in, run `az login`. A browser window opens for a normal sign-in. It changes nothing in Azure. Never type a password into PowerShell.

**Step 2 – list the six Arc machines**

```powershell
$ArcPrefix = "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.HybridCompute/machines"
az rest --subscription $SUB --method get --url "https://management.azure.com$ArcPrefix?api-version=2024-07-10" `
  --query "value[].{Name:name,Region:location,Status:properties.status,Cluster:tags.cluster}" -o table
```

> **What you should see:** Six rows. Five in the primary region and one (`SQL2019-GUEST`) in `southeastasia`. Status `Connected` for all. Cluster `WIN-CLUSTER-01` for the three Windows noisy neighbours.

> **Beginner tip:** A **backtick** at the end of a line (the key just below **Esc**, top-left of the keyboard) means "the command continues on the next line". Copy all lines together.

> **Beginner tip:** Folder paths in this guide, such as `<REPO_ROOT>\lab-kit`, are folders of this repository on the Operator PC (`<REPO_ROOT>` is the folder where you cloned or unpacked it; it contains `docs`, `lab-kit`, `monitoring`, `shift-report` and `tools`). If you present from another computer, clone or copy the repository there and change the path in the `Set-Location` lines of the later acts. The setup chapters are in [docs/setup](../setup/) and the scripts in [lab-kit](../../lab-kit/).
