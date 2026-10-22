. "$PSScriptRoot\common.ps1"
$config = "$HvRoot/providers/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated"
# Weekly Monday window at 19:00 SE Asia Standard Time (UTC+7): the first window is the next Monday and the
# schedule expires about six weeks later.
$first = (Get-Date).Date.AddDays(1)
while ($first.DayOfWeek -ne 'Monday') { $first = $first.AddDays(1) }
$invariant = [Globalization.CultureInfo]::InvariantCulture
$windowStart = $first.AddHours(19).ToString('yyyy-MM-dd HH:mm', $invariant)
$windowExpiry = $first.AddDays(39).ToString('yyyy-MM-dd', $invariant) + ' 23:59'
$body = @{
    location = 'southeastasia'
    tags = @{ purpose = 'HV-demo' }
    properties = @{
        maintenanceScope = 'InGuestPatch'; visibility = 'Custom'
        extensionProperties = @{ InGuestPatchMode = 'User' }
        maintenanceWindow = @{
            startDateTime = $windowStart; expirationDateTime = $windowExpiry
            duration = '01:30'; timeZone = 'SE Asia Standard Time'; recurEvery = 'Week Monday'
        }
        installPatches = @{
            rebootSetting = 'Never'
            windowsParameters = @{
                classificationsToInclude = @()
                kbNumbersToInclude = @('2267602')
                kbNumbersToExclude = @()
                excludeKbsRequiringReboot = $true
            }
        }
    }
}
Save-HvJson 'maintenance-config-request.json' $body
Invoke-HvRest PUT "$config`?api-version=2023-04-01" $body 'maintenance-config.json' | Out-Null
& az tag update --resource-id $HvMachine --operation Merge --tags HvUmTarget=SQL2019-GUEST HvUmApproval=Pending --only-show-errors -o none
if ($LASTEXITCODE -ne 0) { throw 'Could not merge maintenance gating tags' }
$dynamic = @{
    location = '<PRIMARY_REGION>'
    properties = @{
        maintenanceConfigurationId = $config
        filter = @{
            locations = @('southeastasia'); osTypes = @('Windows')
            resourceGroups = @(); resourceTypes = @('Microsoft.HybridCompute/machines')
            tagSettings = @{ filterOperator = 'All'; tags = @{ HvUmTarget = @('SQL2019-GUEST'); HvUmApproval = @('Approved') } }
        }
    }
}
Save-HvJson 'maintenance-dynamic-scope-request.json' $dynamic
Invoke-HvRest PUT "$HvRoot/providers/Microsoft.Maintenance/configurationAssignments/ca-hv-sql2019-approved`?api-version=2023-04-01" $dynamic 'maintenance-dynamic-scope.json' | Out-Null
Save-HvJson 'maintenance-static-assignment-NOT-APPLIED.json' @{
    location = 'southeastasia'
    properties = @{ maintenanceConfigurationId = $config; resourceId = $HvMachine }
}
Invoke-HvRest GET "$HvMachine/providers/Microsoft.Maintenance/configurationAssignments`?api-version=2023-04-01" $null 'maintenance-machine-assignments.json' | Out-Null
Write-Output 'Recurring schedule created; static assignment NOT applied; dynamic approval filter matches zero machines.'
