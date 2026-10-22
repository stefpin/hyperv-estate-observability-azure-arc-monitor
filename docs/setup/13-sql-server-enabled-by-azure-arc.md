# 13. SQL Server enabled by Azure Arc - licence, dashboard and DB inventory

This chapter verifies that the SQL Server extension for Azure Arc is installed, that the SQL Arc resource uses the intended licence type, and what the built-in SQL Arc screens (Overview, Performance dashboard and Databases) do and do not prove. Use it after SQL Server is installed ([chapter 12](12-sql-server-installation.md)) and `SQL2019-GUEST` is connected to Azure Arc. When it works, the Overview page of the `SQL2019-GUEST` Arc machine shows it **Connected** in Southeast Asia, the secondary region used for the SQL machine.

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables (such as `$RG`, `$ResourcePrefix`) and the `Invoke-Lab*` helpers that it provides.

## 13.1 SQL extension and pay-as-you-go licence type

**What you are doing:** you verify that the Azure Arc SQL extension is installed and that the SQL Arc resource uses the intended licence type. Pay-as-you-go (PAYG) here is a management and licensing setting in Azure Arc. It is not the SQL edition installed by SQL Setup.

In the Azure Portal, follow these steps carefully:

1. Open **Arc**.
2. Click **Machines**.
3. Click **SQL2019-GUEST**.
4. Click **Extensions**.
5. Verify **WindowsAgent.SqlServer**.
6. Verify publisher **Microsoft.AzureData**.
7. Verify automatic upgrade is on.
8. Open **Azure Arc > SQL Server instances**. If needed, search for **SQL Server - Azure Arc**.
9. Open the instance for **SQL2019-GUEST**.
10. Under **Configuration**, confirm licence type **Pay-as-you-go**.
11. Confirm management/monitoring is enabled.
12. Confirm there is no excluded default instance.
13. Review the licence type before saving.

> **Note:** The licence type is a billing and licensing setting of the Arc resource, separate from the edition that SQL Setup installed. With **Pay-as-you-go**, SQL Server usage is billed through Azure; with **License with Software Assurance**, you apply a licence entitlement you already own instead. Choose the option that matches your own licensing position. The lab uses Pay-as-you-go.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**

```powershell
az connectedmachine extension list -g $RG --machine-name SQL2019-GUEST `
  --query "[?publisher=='Microsoft.AzureData'].{Name:name,Type:type,Version:typeHandlerVersion,Settings:settings,State:provisioningState}" -o json
$SqlArcId = "$ResourcePrefix/providers/Microsoft.AzureArcData/SqlServerInstances/SQL2019-GUEST"
az resource show --ids $SqlArcId --api-version 2026-01-01 -o json
```

**What you should see:** edition Enterprise, licence type PAYG, status Connected, four vCores, Southeast Asia, patchLevel 15.0.4490.9, and monitoring enabled. The installed extension reported version **1.1.3547.472** during onboarding; automatic upgrade can change it later. The extension service account `NT SERVICE\SqlServerExtension` uses the supported least-privilege path. Do not grant sysadmin to the custom collector or invent a SQL password.

For a fresh deployment, use `lab-kit/Enable-LabSqlArc.ps1`. It resolves the SQL machine's region and stops with `SQL Arc requires the selected Southeast Asia machine.` unless `SQL2019-GUEST` is the Southeast Asia Arc machine. It then creates the extension `WindowsAgent.SqlServer` (publisher `Microsoft.AzureData`) with automatic upgrade on and the settings from `lab-kit/schema/sql-extension-settings.json`: `LicenseType=PAYG`, `SqlManagement.IsEnabled=true` and `ExcludedSqlInstances=[]`. The script reads that settings file by a relative path, so run it from the `lab-kit` folder.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder with the lab context loaded. Run it once, after SQL Server is installed and `SQL2019-GUEST` is Connected in Azure Arc.

```powershell
.\Enable-LabSqlArc.ps1
```

**What you should see:** the script prints nothing when it succeeds. Check the extension and the SQL Arc resource with the two commands above; the SQL Arc instance can take several minutes to appear.

> **Warning:** Do not change Defender subscription policy or plans as part of this setup. The status of an existing Defender extension is shown for information only; it is not a reason to enable paid Defender plans.

## 13.2 Dashboard interpretation and DB list

**What you are doing:** you walk through the built-in SQL Arc screens and explain what they do and do not prove.

In the Azure Portal, follow this order:

1. Open the SQL Arc instance.
2. Click **Overview**. Confirm the connected status and the edition/licence details.
3. Click **Performance dashboard**. Choose a post-restart time window. Check for real CPU, memory, storage allocation/used, throughput and IOPS points.
4. Click **Databases**. At first, expect `master`, `model`, `msdb` and `tempdb`. After [chapter 14](14-sql-memory-ceiling-and-what-it-means.md), expect `OrdersDemo`, `BillingDemo` and `ReportingDemo` when the inventory refreshes.
5. Explain clearly that the built-in SQL dashboard is separate from the precise max/committed/non-free/cache/grant comparison in the custom workbook.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**

```powershell
az resource list -g $RG --resource-type Microsoft.AzureArcData/sqlServerInstances `
  --query "[].{Name:name,Region:location,Id:id}" -o table
az resource list -g $RG --resource-type Microsoft.AzureArcData/sqlServerInstances/databases `
  --query "[].{Name:name,Id:id}" -o table
```

If the resource list omits nested database children, use the SQL instance's REST collection instead.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**

```powershell
Invoke-LabAz rest --method get `
  --url "https://management.azure.com$SqlArcId/databases?api-version=2026-01-01" -o json
```

**What you should see:** the Azure resource list or the REST result shows the SQL Arc instance and its database inventory. `lab-kit/queries/sql-databases.ps1` makes the same REST call from the `lab-kit` folder. In the guest, `SELECT name,state_desc FROM sys.databases ORDER BY name;` verifies the actual SQL database state immediately; the Arc inventory can lag.

> **Warning:** Do not interpret a briefly negative rate across a service restart as negative physical I/O: cumulative counter resets invalidate that interval. Always select a stable post-restart window.
