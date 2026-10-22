. "$PSScriptRoot\common.ps1"
Initialize-LabArm
$automationResource = Invoke-LabArm GET "$Account`?api-version=2024-10-23"
$principal = $automationResource.identity.principalId
if ($principal -ne '00000000-0000-0000-0000-000000000010') { throw 'Automation identity does not match the principal ID in this script: set it first (tools\Set-RepoContext.ps1 -AutomationPrincipalId) or review the change before granting permissions.' }
$planPath = Join-Path $Evidence 'guard-role-plan.json'
if (Test-Path -LiteralPath $planPath) {
    $storedPlan = [IO.File]::ReadAllText($planPath) | ConvertFrom-Json
    $plan = if ($storedPlan.PSObject.Properties['value']) {
        @($storedPlan.value | ForEach-Object { $_ })
    } else { @($storedPlan | ForEach-Object { $_ }) }
} else {
    $plan = @(
        [pscustomobject]@{
            Name = 'SQL Scheduled Maintenance Cancellation'
            DefinitionId = "$Root/providers/Microsoft.Authorization/roleDefinitions/$([guid]::NewGuid())"
            AssignmentId = "$Configuration/providers/Microsoft.Authorization/roleAssignments/$([guid]::NewGuid())"
            Scope = $Configuration
            Actions = @('Microsoft.Maintenance/maintenanceConfigurations/read','Microsoft.Maintenance/applyUpdates/read','Microsoft.Maintenance/applyUpdates/write')
        },
        [pscustomobject]@{
            Name = 'SQL Maintenance Run Checkpoints'
            DefinitionId = "$Root/providers/Microsoft.Authorization/roleDefinitions/$([guid]::NewGuid())"
            AssignmentId = "$Account/providers/Microsoft.Authorization/roleAssignments/$([guid]::NewGuid())"
            Scope = $Account
            Actions = @('Microsoft.Automation/automationAccounts/variables/read','Microsoft.Automation/automationAccounts/variables/write')
        }
    )
    Save-LabEvidence 'guard-role-plan.json' $plan
}
$results = foreach ($role in $plan) {
    Assert-LabPath $role.DefinitionId
    Assert-LabPath $role.AssignmentId
    if ($role.Scope -notin @($Configuration,$Account) -or @($role.Actions | Where-Object { $_ -like '*`**' }).Count) {
        throw 'Unexpected role scope or wildcard action.'
    }
    $definition = Invoke-LabArm PUT "$($role.DefinitionId)?api-version=2022-04-01" @{
        properties = @{
            roleName = $role.Name
            description = 'Maintenance-guard safeguard; assignable only within the lab resource group.'
            type = 'CustomRole'
            assignableScopes = @($Root)
            permissions = @(@{
                actions = @($role.Actions)
                notActions = @()
                dataActions = @()
                notDataActions = @()
            })
        }
    }
    $assignment = Invoke-LabArm PUT "$($role.AssignmentId)?api-version=2022-04-01" @{
        properties = @{
            principalId = $principal
            principalType = 'ServicePrincipal'
            roleDefinitionId = $definition.id
        }
    }
    $readDefinition = Invoke-LabArm GET "$($role.DefinitionId)?api-version=2022-04-01"
    $readAssignment = Invoke-LabArm GET "$($role.AssignmentId)?api-version=2022-04-01"
    if (@($readDefinition.properties.assignableScopes).Count -ne 1 -or
        $readDefinition.properties.assignableScopes[0] -ne $Root -or
        $readAssignment.properties.scope -ne $role.Scope -or
        $readAssignment.properties.principalId -ne $principal) { throw 'Role readback does not match the authorized scope.' }
    [pscustomobject]@{ Definition = $readDefinition; Assignment = $readAssignment }
}
Save-LabEvidence 'guard-roles.json' @($results)
$results | ForEach-Object {
    [pscustomobject]@{
        Role = $_.Definition.properties.roleName
        AssignableScopes = $_.Definition.properties.assignableScopes
        AssignedScope = $_.Assignment.properties.scope
        Actions = $_.Definition.properties.permissions[0].actions
    }
} | ConvertTo-Json -Depth 6
