# Act 1. Meet the estate

Act 1 covers the first ten minutes of the storyline (minutes 0–10). Its goal is to show that everything – Windows, Linux and SQL – appears in **one inventory**, and that the lab is secure by design. Before you start, the Portal tab on Azure Arc → Machines from Act 0 must be open, all six machines must show **Connected**, and – for the optional step in section 1.5 – the PowerShell variables `$SUB`, `$RG` and `$ArcPrefix` from Act 0 must still be defined in the same window.

> **Say this:** "We start with a simple question every operations team asks: what do we actually have? Here is the answer, in one list, coming straight from Azure."

## 1.1 Azure Arc inventory

> **Where to run it:** **Azure Portal** (browser).

> **Do this:** Click the top search box. Type `Azure Arc`. Click **Azure Arc** in the results. In the left menu, open **Infrastructure → Machines**. Click the box **Filter for any field…**. Type `rg-hyperv-arc-monitor-demo` and press **Enter**. Wait for the list to refresh. Look at the bottom: it must say **Showing 6 of 6**.

The Machines list, filtered to the lab resource group, shows these parts in reading order:

- **(1)** Filter box. This hides other projects' machines that share the subscription.

- **(2)** **Arc agent status = Connected** for all six machines. Connected means Azure can see and manage the machine.

- **(3)** **Monitoring extension = Installed.** The Azure Monitor Agent collects the measurements.

- **(4)** **Showing 6 of 6.** One host plus five guests.

> **Say this:** "Six machines: the Hyper-V host and five guests – three Windows, one Linux, one SQL Server. Windows and Linux in the same list. All are **Connected**, and all have the monitoring agent installed."

> **Good to know:** Azure Arc inventories Windows, Linux **and SQL Server** with the same method, and Azure policy, update and monitoring features attach to the same record.

## 1.2 One machine in detail – the SQL server

> **Do this:** In the list, click **SQL2019-GUEST**. On the **Overview** page, read **Status**, **Location**, **Tags** and the cards under **Capabilities**.

The Arc record of `SQL2019-GUEST` shows these parts in reading order:

- **(1)** **Status: Connected. Location: Southeast Asia.** The SQL management features are enabled in Southeast Asia.

- **(2)** **Tags** `HvUmTarget` and `HvUmApproval`. The patching schedule uses these two tags to choose its target (Act 7).

- **(3)** **Capabilities**: Updates, Logs, Monitoring insights, Policies, Change tracking and inventory, Security, Windows Admin Center, Site Recovery.

- **(4)** **4 pending updates** is the result of the latest update assessment (Act 7).

> **Be honest:** "Most machines are registered in the primary region. The SQL guest is registered in a secondary region, Southeast Asia, because some Arc management features are not available in every region. This is a lab layout chosen for feature availability, not a recommendation for where to place production data." (Background: [setup chapter 1](../setup/01-scope-architecture-and-success-criteria.md), section 1.3.)

## 1.3 Extensions – the agents that do the work

> **Do this:** On the `SQL2019-GUEST` page, in the left menu click **Settings → Extensions**.

The list shows the extensions installed on `SQL2019-GUEST`:

- **(1)** Azure Monitor Agent (measurements), Change Tracking, Microsoft Defender for Endpoint and Defender for SQL (security), Windows Patch Extension and Windows OS Update (patching), and the SQL Server extension (SQL inventory and monitoring).

> **Say this:** "No new agent per feature. A few Azure extensions on the same machine give monitoring, change tracking, patching and security."

## 1.4 The host and secure access

> **Do this:** In the top search box type `HV-HOST-01`. Click the result of type **Virtual machine**. On **Overview**, read **Status**, **Size** and **Private IP address**. Note that there is **no public IP**. In the left menu, click **Connect → Bastion**. Look at the page, but **do not click Connect**.

The **Overview** page of `HV-HOST-01` shows:

- **(1)** Status Running, Windows, size `Standard_E8s_v5` (8 logical processors, 64 GB). Only a private IP address is shown.

The **Connect → Bastion** page shows:

- **(1)** The menu path **Connect → Bastion**.

- **(2)** **Go to Bastion.** Azure Bastion gives secure remote access through the Portal. No public IP and no open remote-desktop port. We only point at it; we do not connect.

> **Say this:** "The host has no public IP address. Administrators reach it through Azure Bastion, so no remote-desktop port is open to the internet."

## 1.5 The same list from PowerShell (optional)

> **Where to run it:** **Operator PC → Windows PowerShell**. Use the variables from Act 0 step 1. Read-only.

```powershell
az rest --subscription $SUB --method get --url "https://management.azure.com$ArcPrefix?api-version=2024-07-10" `
  --query "value[].{Name:name,Region:location,Status:properties.status}" -o table
```

> **What you should see:** The same six machines with their regions and `Connected` status.
