. "$PSScriptRoot\common.ps1"
$account = "$HvRoot/providers/Microsoft.Automation/automationAccounts/aa-hv-sql-maintenance"
$result = Invoke-HvRest PUT "$account`?api-version=2024-10-23" @{
    location = 'southeastasia'; identity = @{ type = 'SystemAssigned' }
    properties = @{ sku = @{ name = 'Basic' }; publicNetworkAccess = $true; disableLocalAuth = $false }
    tags = @{ purpose = 'HV-safe-pre-post-checks' }
} 'automation-account.json'
$principal = $result.identity.principalId
if (-not $principal) { throw 'Automation managed identity absent' }
$roleGuid = '00000000-0000-0000-0000-000000000013'
$role = "$HvRoot/providers/Microsoft.Authorization/roleDefinitions/$roleGuid"
Invoke-HvRest PUT "$role`?api-version=2022-04-01" @{
    properties = @{
        roleName = 'SQL Maintenance Availability Checker'
        description = 'Read Arc machine and execute/delete guest Run Commands for safe pre/post checks. Assigned only to SQL2019-GUEST.'
        type = 'CustomRole'; assignableScopes = @($HvRoot)
        permissions = @(@{ actions = @(
            'Microsoft.HybridCompute/machines/read'
            'Microsoft.HybridCompute/machines/runCommands/read'
            'Microsoft.HybridCompute/machines/runCommands/write'
            'Microsoft.HybridCompute/machines/runCommands/delete'
        ); notActions = @(); dataActions = @(); notDataActions = @() })
    }
} 'automation-role.json' | Out-Null
Invoke-HvRest PUT "$HvMachine/providers/Microsoft.Authorization/roleAssignments/00000000-0000-0000-0000-000000000012`?api-version=2022-04-01" @{
    properties = @{ principalId = $principal; principalType = 'ServicePrincipal'; roleDefinitionId = $role }
} 'automation-role-assignment.json' | Out-Null
Invoke-HvRest PUT "$account/runtimeEnvironments/ps74-safe-checks`?api-version=2024-10-23" @{
    name = 'ps74-safe-checks'
    properties = @{ runtime = @{ language = 'PowerShell'; version = '7.4' }; defaultPackages = @{ Az = '12.3.0' } }
} 'automation-runtime.json' | Out-Null
$runbook = "$account/runbooks/Test-HvSqlMaintenanceAvailability"
Invoke-HvRest PUT "$runbook`?api-version=2024-10-23" @{
    location = 'southeastasia'
    properties = @{ runbookType = 'PowerShell'; runtimeEnvironment = 'ps74-safe-checks'; logProgress = $false; logVerbose = $false; description = 'SQL read-only pre/post availability checks. Never stops SQL, installs patches, reboots or sends email.' }
} 'automation-runbook-draft.json' | Out-Null
$token = & az account get-access-token --subscription $HvSub --resource https://management.azure.com/ --query accessToken -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'ARM token unavailable' }
$headers = @{ Authorization = "Bearer $token" }
$null = Invoke-RestMethod -Method PUT -Uri "https://management.azure.com$runbook/draft/content?api-version=2024-10-23" `
    -Headers $headers -ContentType 'text/plain' -Body ([IO.File]::ReadAllText("$PSScriptRoot\runbook-safe-check.ps1"))
$token = $null; $headers = $null
Invoke-HvRest POST "$runbook/publish`?api-version=2024-10-23" @{} '' | Out-Null
Invoke-HvRest GET "$runbook`?api-version=2024-10-23" $null 'automation-runbook.json' | Out-Null
Write-Output "Published safe pre/post runbook; managed identity $principal scoped only to SQL2019-GUEST."
