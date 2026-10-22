. "$PSScriptRoot\context.ps1"
$file=Join-Path $PSScriptRoot 'workbook-resource.json'
if(-not(Test-Path $file)){throw 'Workbook resource source missing.'}
$body=Get-Content $file -Raw | ConvertFrom-Json
$id=$body.id
if(-not $id){$id="$ResourcePrefix/providers/Microsoft.Insights/workbooks/00000000-0000-0000-0000-000000000005"}
Assert-LabResourceId $id
if($id -notmatch '/providers/Microsoft.Insights/workbooks/[0-9a-f-]{36}$'){throw 'Workbook GUID/ID missing or invalid.'}
$payload=@{location=$body.location;kind=$body.kind;properties=$body.properties}
$out=Join-Path $PSScriptRoot 'workbook-put.json'
[IO.File]::WriteAllText($out,(ConvertTo-Json $payload -Depth 100),(New-Object Text.UTF8Encoding($false)))
Invoke-LabAz rest --method put --url "https://management.azure.com$id`?api-version=2022-04-01" --body "@$out" -o none
Write-Output "Saved workbook: $id. Open Portal and validate every tab."
