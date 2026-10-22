param([Parameter(Mandatory=$true)][string]$GuardPath)
. "$PSScriptRoot\common.ps1"
Initialize-LabArm
$sourcePath = (Resolve-Path -LiteralPath $GuardPath).Path
$source = [IO.File]::ReadAllText($sourcePath).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
$tokens = $null
$parseErrors = $null
$null = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'The safeguard source does not parse.' }
$runbookId = "$Account/runbooks/Test-HvSqlMaintenanceAvailability"
$old = Invoke-LabArm GET "$runbookId`?api-version=2024-10-23"
if ($old.properties.runtimeEnvironment -ne 'ps74-safe-checks' -or $old.properties.state -notin @('Published','Edit')) {
    throw 'Unexpected runbook state or runtime; review instead of overwriting.'
}
$existing = ([string](Invoke-LabArm GET "$runbookId/content?api-version=2024-10-23")).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
$original = [IO.File]::ReadAllText((Join-Path $Evidence 'original-published-runbook.ps1')).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
if ($existing -cne $original -and $existing -cne $source) { throw 'Published source changed independently; do not overwrite it.' }
$target = Invoke-LabArm GET "$Machine`?api-version=2025-01-13"
if ($target.tags.HvUmApproval -ne 'Pending') { throw 'Set the target tag HvUmApproval to Pending before replacing the safeguard.' }
$description = 'Maintenance guard: scoped SQL query/availability checks, same-run continuity checkpoints and explicit cancellation on failed pre-check. Never installs patches, stops SQL, reboots or sends email.'
if ($old.properties.description -ne $description) {
    $null = Invoke-LabArm PUT "$runbookId`?api-version=2024-10-23" @{
        location = 'southeastasia'
        properties = @{
            runbookType = 'PowerShell'
            runtimeEnvironment = 'ps74-safe-checks'
            logProgress = $false
            logVerbose = $false
            description = $description
        }
    }
}
$draft = ([string](Invoke-LabArm GET "$runbookId/draft/content?api-version=2024-10-23")).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
if ($draft -cne $source) {
    & az automation runbook replace-content --resource-group $Group --automation-account-name aa-hv-sql-maintenance `
        --name Test-HvSqlMaintenanceAvailability --subscription $Subscription --content "@$sourcePath" --no-wait --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw 'Supported CLI draft import failed; target approval remains Pending.' }
}
$deadline = [datetime]::UtcNow.AddMinutes(5)
do {
    $draft = ([string](Invoke-LabArm GET "$runbookId/draft/content?api-version=2024-10-23")).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
    if ($draft -ceq $source) { break }
    Start-Sleep -Seconds 5
} while ([datetime]::UtcNow -lt $deadline)
if ($draft -cne $source) { throw 'Imported draft content does not match the validated source.' }
$null = Invoke-LabArm POST "$runbookId/publish?api-version=2024-10-23" @{}
$deadline = [datetime]::UtcNow.AddMinutes(5)
do {
    Start-Sleep -Seconds 5
    $metadata = Invoke-LabArm GET "$runbookId`?api-version=2024-10-23"
    $published = ([string](Invoke-LabArm GET "$runbookId/content?api-version=2024-10-23")).Replace("`r`n","`n").TrimStart([char]0xFEFF).TrimEnd([char]10)
    if ($metadata.properties.state -eq 'Published' -and $published -ceq $source) { break }
} while ([datetime]::UtcNow -lt $deadline)
if ($metadata.properties.state -ne 'Published' -or $published -cne $source) {
    throw 'The exact safeguard content is not yet published; target approval must remain pending.'
}
$sha = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($source))).Replace('-','')
$result = [pscustomobject]@{
    RunbookId = $runbookId
    State = $metadata.properties.state
    Runtime = $metadata.properties.runtimeEnvironment
    SourceSha256 = $sha
    HashNormalization = 'UTF8 source; CRLF normalized to LF; BOM and final LF removed by CLI import'
    SourceFileSha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    PublishedUtc = [datetime]::UtcNow.ToString('o')
    RunbookParameters = $metadata.properties.parameters
}
Save-LabEvidence 'published-guard.json' $result
$result | ConvertTo-Json -Depth 6
