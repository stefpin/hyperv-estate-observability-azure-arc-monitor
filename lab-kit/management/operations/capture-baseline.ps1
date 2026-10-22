. "$PSScriptRoot\common.ps1"
Initialize-LabArm
$start = [datetime]::UtcNow.ToString('o')
$before = [ordered]@{
    CapturedUtc = $start
    Maintenance = Invoke-LabArm GET "$Configuration`?api-version=2023-04-01"
    DynamicScope = Invoke-LabArm GET "$Scope`?api-version=2023-04-01"
    Machines = Invoke-LabArm GET "$Root/providers/Microsoft.HybridCompute/machines?api-version=2025-01-13"
    MachineAssignments = Invoke-LabArm GET "$Machine/providers/Microsoft.Maintenance/configurationAssignments?api-version=2023-04-01"
    GroupResourceInventory = Invoke-LabArm GET "$Root/resources?api-version=2021-04-01"
    Roles = Invoke-LabArm GET "$Root/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"
    Automation = Invoke-LabArm GET "$Account`?api-version=2024-10-23"
    Runbook = Invoke-LabArm GET "$Account/runbooks/Test-HvSqlMaintenanceAvailability?api-version=2024-10-23"
}
Save-LabEvidence 'baseline-resources.json' $before
$published = Invoke-LabArm GET "$Account/runbooks/Test-HvSqlMaintenanceAvailability/content?api-version=2024-10-23"
[IO.File]::WriteAllText((Join-Path $Evidence 'original-published-runbook.ps1'), [string]$published, (New-Object Text.UTF8Encoding($false)))
$source = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'guest-baseline.ps1'))
$health = Invoke-OwnedSqlCheck $source
Save-LabEvidence 'baseline-sql-health.json' $health
[pscustomobject]@{
    CapturedUtc = $start
    ExistingMatches = @($before.Machines.value | Where-Object { $_.tags.HvUmTarget -eq 'SQL2019-GUEST' -and $_.tags.HvUmApproval -eq 'Approved' }).Count
    StaticAssignments = @($before.MachineAssignments.value).Count
    Guest = $health
} | ConvertTo-Json -Depth 8
