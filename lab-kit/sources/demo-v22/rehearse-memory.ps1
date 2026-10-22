param([ValidateSet('Prepare','Baseline','WarmCache','GrantLoad','Recovery')][string]$StartAt = 'Prepare')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\sql-install\arc-run.ps1"
$evidence = @()
if($StartAt -ne 'Prepare' -and (Test-Path "$PSScriptRoot\memory-rehearsal.json")){
    foreach($entry in (Get-Content "$PSScriptRoot\memory-rehearsal.json" -Raw|ConvertFrom-Json)){$evidence+=$entry}
}
$stages=@('Prepare','Baseline','WarmCache','GrantLoad','Recovery')
$index=[array]::IndexOf($stages,$StartAt)
foreach ($stage in $stages[$index..($stages.Count-1)]) {
    $start = [datetime]::UtcNow
    $result = Invoke-HvArc -Machine SQL2019-GUEST -Name ('memory-' + $stage.ToLowerInvariant()) `
        -ScriptPath "$PSScriptRoot\guest-workload.ps1" -Parameters @{Stage=$stage;Seconds=180} -Timeout 1200
    $result.Output
    $evidence += @{Stage=$stage;StartUtc=$start.ToString('o');EndUtc=[datetime]::UtcNow.ToString('o');Output=$result.Output}
    [IO.File]::WriteAllText("$PSScriptRoot\memory-rehearsal.json", (ConvertTo-Json -InputObject $evidence -Depth 8), (New-Object Text.UTF8Encoding($false)))
    & az connectedmachine run-command delete --subscription '<SUBSCRIPTION_ID>' `
        -g rg-hyperv-arc-monitor-demo --machine-name $result.Machine --name $result.Name --yes --no-wait --only-show-errors -o none
    if($LASTEXITCODE -ne 0){throw "Removing completed memory command $($result.Name) failed"}
}
