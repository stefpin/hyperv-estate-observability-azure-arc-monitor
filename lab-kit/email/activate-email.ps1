param([switch]$ApprovedReceiverCreation)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\context.ps1"
$subscription='<SUBSCRIPTION_ID>'
$group='rg-hyperv-arc-monitor-demo'
$name='ag-hv-demo-email'
$recipient='operator@example.com'
$createdUtc=(Get-Date).ToUniversalTime().ToString('o')
$existing=Invoke-LabAz monitor action-group list -g $group --query '[].name' -o json
$names=@(foreach($entry in (($existing|Out-String)|ConvertFrom-Json)){$entry})
if($names -notcontains $name){
    if(-not $ApprovedReceiverCreation){throw 'Creating a receiver can send email; pass -ApprovedReceiverCreation after you have reviewed the recipient.'}
    Invoke-LabAz monitor action-group create -g $group -n $name --short-name HVDEMO `
        --location global --action email HvDemoRecipient $recipient usecommonalertschema `
        --tags 'Demo=hyperv-observability' "CreatedUtc=$createdUtc" --only-show-errors -o none
    if($LASTEXITCODE -ne 0){throw 'Action-group creation failed'}
}
$raw=Invoke-LabAz monitor action-group show -g $group -n $name -o json
$object=($raw|Out-String)|ConvertFrom-Json
if($object.emailReceivers.Count -ne 1 -or $object.emailReceivers[0].emailAddress -ne $recipient){throw 'Unexpected action-group recipient list; do not attach it'}
Assert-LabResourceId $object.id
if(-not $object.enabled -or -not $object.emailReceivers[0].useCommonAlertSchema){throw 'Receiver/group must be enabled with common schema.'}
if($object.emailReceivers[0].name -ne 'HvDemoRecipient' -or $object.emailReceivers[0].status -ne 'Enabled'){
    throw 'Unexpected receiver name/status; inspect any required verification before testing.'
}
foreach($type in 'armRoleReceivers','smsReceivers','voiceReceivers','webhookReceivers','automationRunbookReceivers','azureAppPushReceivers','azureFunctionReceivers','eventHubReceivers','itsmReceivers','logicAppReceivers'){
    if(@($object.$type).Count -gt 0){throw 'Unexpected extra notification/action type; do not attach it.'}
}
[IO.File]::WriteAllText("$PSScriptRoot\action-group-initial.json",(ConvertTo-Json $object -Depth 25),(New-Object Text.UTF8Encoding($false)))
"Action group=$($object.id); enabled=$($object.enabled); recipient=$recipient; commonSchema=$($object.emailReceivers[0].useCommonAlertSchema); status=$($object.emailReceivers[0].status)."
'Receiver creation may send the approved Azure-generated verification/membership message; alert rules are not attached yet.'
