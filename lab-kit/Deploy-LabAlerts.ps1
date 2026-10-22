param([switch]$InitialBuildApproved)
. "$PSScriptRoot\context.ps1"
$url = "https://management.azure.com$ResourcePrefix/providers/Microsoft.Insights/scheduledQueryRules?api-version=2023-12-01"
$inventory = (Invoke-LabAz rest --method get --url $url -o json | Out-String) | ConvertFrom-Json
if ($inventory.nextLink) { throw 'Paged rule inventory requires review; refusing incomplete inventory.' }
$existing = @($inventory.value | ForEach-Object { $_.id })
$files = @(Get-ChildItem "$PSScriptRoot\alerts\*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike 'put-*' })
if ($files.Count -eq 0) { throw 'Alert payloads not found.' }
foreach ($file in $files) {
    $body = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $id = $body.id
    if (-not $id) { $id = "$ResourcePrefix/providers/Microsoft.Insights/scheduledQueryRules/$($body.name)" }
    Assert-LabResourceId $id
    foreach ($scope in $body.properties.scopes) { Assert-LabResourceId $scope }
    if ($id -notmatch '/providers/Microsoft.Insights/scheduledQueryRules/') { throw 'Unexpected rule type.' }
    if ($existing -contains $id) {
        Write-Output "Preserved existing rule, current criteria/actions unchanged: $($body.name)"
        continue
    }
    if (-not $InitialBuildApproved) { throw 'A rule is missing; pass -InitialBuildApproved to create it.' }
    if (@($body.properties.actions.actionGroups).Count -gt 0) { throw 'Fresh rule receiver activation requires separately reviewed email source.' }
    $payload = @{ location = $body.location; properties = $body.properties }
    $out = Join-Path $PSScriptRoot ('alerts\put-' + $file.Name)
    [IO.File]::WriteAllText($out, (ConvertTo-Json $payload -Depth 100), (New-Object Text.UTF8Encoding($false)))
    Invoke-LabAz rest --method put --url "https://management.azure.com$id`?api-version=2023-12-01" --body "@$out" -o none
}
Write-Output 'Existing rules preserved. Email attachment is a separate reviewed actions-only change.'
