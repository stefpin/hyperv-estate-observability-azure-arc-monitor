# 4. Azure foundation: resource group, network, NAT, Bastion and workspaces

This chapter builds the Azure foundation for the lab: the resource provider check, the resource group, the virtual network, the explicit outbound path (NAT gateway), Azure Bastion and the Log Analytics workspaces. When it is complete, the Overview page of `rg-hyperv-arc-monitor-demo` lists the virtual network, the NAT gateway, the public IP addresses, Bastion and the workspaces. Before you start, your operator PC session must be loaded and signed in to the lab subscription ([Chapter 2](02-tools-secrets-and-conventions.md)), and you must have checked with [Chapter 3](03-build-order-and-change-gates.md) that the resources do not already exist; on an existing, healthy lab these sections are verification only. Commands write the primary region as `<PRIMARY_REGION>`; replace it with the region code you chose (see [Placeholders and ENVIRONMENT.txt](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)).

## 4.1 Read-only provider prerequisite

Here you are checking whether the required Azure resource providers are already registered. This is a read-only check; this guide does not register providers for you.

**Azure Portal check.** Follow these exact clicks:

1. Open `https://portal.azure.com`.
2. In the top search box, type `Subscriptions` and press Enter.
3. Click `Subscriptions`.
4. Click the lab subscription, the one whose ID is `<SUBSCRIPTION_ID>`.
5. In the left-hand menu, click `Resource providers`.
6. Check the registration state for `Microsoft.Compute`, `Microsoft.Network`, `Microsoft.HybridCompute`, `Microsoft.Insights`, `Microsoft.OperationalInsights`, `Microsoft.Maintenance`, `Microsoft.AzureArcData`, `Microsoft.GuestConfiguration`, `Microsoft.Automation`, `Microsoft.EventGrid` and `Microsoft.OperationsManagement`.
7. Do not click **Register**: this guide changes only resources inside the lab resource group, and registering a provider is a subscription-level change.

**CLI path:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI, after the [Chapter 2](02-tools-secrets-and-conventions.md) setup has been completed in this same window.

```powershell
$providers = 'Microsoft.Compute','Microsoft.Network','Microsoft.HybridCompute',
  'Microsoft.Insights','Microsoft.OperationalInsights','Microsoft.Maintenance',
  'Microsoft.AzureArcData','Microsoft.GuestConfiguration','Microsoft.Automation',
  'Microsoft.EventGrid','Microsoft.OperationsManagement'
foreach ($p in $providers) {
  az provider show --namespace $p --query "{Provider:namespace,State:registrationState}" -o table
}
```

**What you should see:** required providers read `Registered`. If not, stop the dependent build and report the missing prerequisite; do not silently broaden scope.

## 4.2 Resource group and virtual network

This section creates the main Azure container and the virtual network for the lab, but only if you are doing a fresh build. If the resources already exist and are correct, do not recreate them.

**Portal path, fresh build only:**

1. Open `https://portal.azure.com`.
2. In the top search box, type `Resource groups` and press Enter.
3. Click `Resource groups`.
4. Click `Create`.
5. Select the lab subscription.
6. In the `Resource group name` box, type `rg-hyperv-arc-monitor-demo`.
7. In the `Region` box, choose your primary region (the region you use for `<PRIMARY_REGION>`).
8. Go to `Tags`.
9. Add `purpose=hv-hyperv-arc-demo`. Tag the resource group in this way so that the cost of the lab can be attributed to it.
10. Optional: add any further tags that your own conventions require. The lab scripts do not need them.
11. Click **Review + create**.
12. Click **Create**.
13. After the resource group exists, use the top search box again and type `Virtual networks`.
14. Click `Virtual networks`.
15. Click `Create`.
16. Choose the resource group `rg-hyperv-arc-monitor-demo`.
17. In the `Name` box, type `vnet-arc-lab`.
18. In the `Region` box, choose your primary region.
19. Go to `IP addresses`.
20. Use address space `10.50.0.0/16`.
21. Remove the proposed default subnet if necessary.
22. Add a subnet named `snet-lab` with `10.50.1.0/24`, private subnet enabled.
23. Add subnet purpose `Azure Bastion`, exact name `AzureBastionSubnet`, address `10.50.250.0/26`.
24. Review and create the virtual network.
25. After deployment finishes, open the VNet's `Subnets` page and verify both prefixes.
26. Do not attach any resource from another group.

When the deployment is correct, the `Subnets` page of `vnet-arc-lab` lists `snet-lab` (`10.50.1.0/24`) and `AzureBastionSubnet` (`10.50.250.0/26`).

**CLI path, equivalent fresh creation:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI. Use the same operator-PC window where `context.ps1` is already loaded.

```powershell
Invoke-LabAz group create -n $RG -l <PRIMARY_REGION> `
  --tags purpose=hv-hyperv-arc-demo -o none
Invoke-LabAz network vnet create -g $RG -n vnet-arc-lab -l <PRIMARY_REGION> `
  --address-prefixes 10.50.0.0/16 --subnet-name snet-lab `
  --subnet-prefixes 10.50.1.0/24 -o none
Invoke-LabAz network vnet subnet create -g $RG --vnet-name vnet-arc-lab `
  -n AzureBastionSubnet --address-prefixes 10.50.250.0/26 -o none
```

**What you should see:** provisioning succeeds; both subnets are in the lab resource group. Add any further tags that your own conventions require to `--tags` as further `key=value` pairs. `Invoke-LabAz` checks native command exit codes; `$ErrorActionPreference='Stop'` alone does not make every failed `az` command throw in PowerShell 5.1.

## 4.3 Explicit outbound route

Here you are creating the outbound internet path for the private lab subnet. Bastion is for inbound administration only. It is not the outbound path for downloads or agents.

**Azure Portal steps.** Follow this exact click path:

1. Open `https://portal.azure.com`.
2. In the top search box, type `NAT gateways` and press Enter.
3. Click `NAT gateways`.
4. Click `Create`.
5. Select the resource group `rg-hyperv-arc-monitor-demo`.
6. In the `Name` box, type `natgw-arc-lab`.
7. In the `Region` box, choose your primary region.
8. Confirm the SKU is `Standard`.
9. Set the timeout to `10 minutes`.
10. Go to `Outbound IP`.
11. Create a new Standard/static public IP named `pip-natgw-arc-lab`.
12. Go to `Networking`.
13. Select `vnet-arc-lab`.
14. Tick only `snet-lab`.
15. Review and create the NAT gateway.
16. After deployment finishes, open `vnet-arc-lab`.
17. In the left-hand menu, click `Subnets`.
18. Confirm the NAT gateway column shows `natgw-arc-lab` on `snet-lab`.

**CLI path:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in the same Windows PowerShell window used for the other Azure CLI steps.

```powershell
Invoke-LabAz network public-ip create -g $RG -n pip-natgw-arc-lab `
  -l <PRIMARY_REGION> --sku Standard --allocation-method Static -o none
Invoke-LabAz network nat gateway create -g $RG -n natgw-arc-lab `
  -l <PRIMARY_REGION> --public-ip-addresses pip-natgw-arc-lab --idle-timeout 10 -o none
Invoke-LabAz network vnet subnet update -g $RG --vnet-name vnet-arc-lab `
  -n snet-lab --nat-gateway natgw-arc-lab --default-outbound false -o none
```

**What you should see:** NAT attachment succeeds. Bastion is inbound administrative access and is **not** outbound internet access. Private subnets need the explicit outbound path for downloads, activation, Arc and AMA.

## 4.4 Bastion

Here you are creating Azure Bastion so you can open a browser-based remote session to the host VM without exposing RDP on the internet.

**Azure Portal steps.** Follow this exact click path:

1. Open `https://portal.azure.com`.
2. In the top search box, type `Bastions` and press Enter.
3. Click `Bastions`.
4. Click `Create`.
5. Choose the resource group `rg-hyperv-arc-monitor-demo`.
6. In the `Name` box, type `bas-arc-lab`.
7. In the `Region` box, choose your primary region.
8. Set the tier to `Basic`.
9. Select the virtual network `vnet-arc-lab`.
10. Select the subnet `AzureBastionSubnet`.
11. Create a new Standard/static public IP named `pip-bastion`.
12. Review and create.
13. Allow `10-20 minutes` for deployment.
14. When deployment is complete, open the Bastion resource.
15. On the `Overview` page, wait until the status shows `Succeeded`.

**CLI path:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI.

```powershell
Invoke-LabAz network public-ip create -g $RG -n pip-bastion `
  -l <PRIMARY_REGION> --sku Standard --allocation-method Static -o none
Invoke-LabAz network bastion create -g $RG -n bas-arc-lab -l <PRIMARY_REGION> `
  --vnet-name vnet-arc-lab --public-ip-address pip-bastion --sku Basic -o none
```

**What you should see:** `Succeeded`. Basic supports browser connection to the host, not every native tunnelling feature available in higher tiers. Do not upgrade the Bastion SKU just to avoid using the browser route.

## 4.5 Monitoring workspaces and optional endpoint

Here you are creating the Log Analytics workspaces that store monitoring data. A Log Analytics workspace is where Azure Monitor keeps the collected logs and metrics for later queries and views. After `law-arc-monitor-lab` is created, its Overview page shows the workspace in the lab resource group and the primary region.

**Azure Portal steps.** Follow this exact click path:

1. Open `https://portal.azure.com`.
2. In the top search box, type `Log Analytics workspaces` and press Enter.
3. Click `Log Analytics workspaces`.
4. Click `Create`.
5. Choose the resource group `rg-hyperv-arc-monitor-demo`.
6. In the `Name` box, type `law-arc-monitor-lab`.
7. In the `Region` box, choose your primary region.
8. Review and create.
9. After the workspace is created, open `law-arc-monitor-lab`.
10. In the left-hand menu, click `Usage and estimated costs`.
11. Click `Data retention`.
12. Set the intended lab retention, minimum `30 days` for the standard table plan.
13. For SQL management, repeat the same process with `law-arc-ct-sea`, region `Southeast Asia`, only if it is not already present.

**CLI path:**

> **RUN ON - Operator PC, PowerShell + Azure CLI**
>
> Do this on: your own computer, in Windows PowerShell with Azure CLI.

```powershell
Invoke-LabAz monitor log-analytics workspace create -g $RG `
  --workspace-name law-arc-monitor-lab -l <PRIMARY_REGION> --retention-time 30 -o none
Invoke-LabAz monitor log-analytics workspace create -g $RG `
  --workspace-name law-arc-ct-sea -l southeastasia --retention-time 30 -o none
```

**What you should see:** workspace locations differ as planned. Public-network AMA file/performance collection does not automatically require a data collection endpoint (DCE). If your environment already has a data collection endpoint you may keep it; create or use an endpoint only if the source or Private Link design requires it. The data collection rules in `lab-kit/dcr` name none.

Write the IDs of the two workspaces (the `customerId` property) into the repository now: the command block in [Placeholders and ENVIRONMENT.txt](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt) reads them with `az monitor log-analytics workspace show` and passes them to `tools\Set-RepoContext.ps1` as `-WorkspaceId` and `-CtWorkspaceId`. Do this before you use the storage and query helpers in the later chapters, which need the workspace ID.
