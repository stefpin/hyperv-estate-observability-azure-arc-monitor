param([switch]$ApprovedSampleTest)
$ErrorActionPreference='Stop'
if(-not $ApprovedSampleTest){throw 'Sample notification sends real email; pass -ApprovedSampleTest after you have reviewed the recipient.'}
. "$PSScriptRoot\..\context.ps1"
& "$PSScriptRoot\activate-email.ps1" | Out-Null
$raw=Invoke-LabAz monitor action-group test-notifications create `
 -g rg-hyperv-arc-monitor-demo --action-group ag-hv-demo-email --alert-type logalertv2 `
 --add-action email HvDemoRecipient operator@example.com usecommonalertschema -o json --only-show-errors
if($LASTEXITCODE -ne 0){throw 'Azure action-group sample test failed'}
[IO.File]::WriteAllText("$PSScriptRoot\sample-test-response.json",($raw|Out-String),(New-Object Text.UTF8Encoding($false)))
'Approved Azure logalertv2 sample test requested; inbox receipt must be verified separately.'
$raw
