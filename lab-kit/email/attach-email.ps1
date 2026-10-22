param([switch]$ApprovedAttachment)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\context.ps1"
if(-not $ApprovedAttachment){throw 'Pass -ApprovedAttachment after you have reviewed the single recipient.'}
$sub='<SUBSCRIPTION_ID>';$rg='rg-hyperv-arc-monitor-demo'
$groupId="/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/actionGroups/ag-hv-demo-email"
$source=@(Get-ChildItem "$PSScriptRoot\..\alerts\*.json" | Where-Object { $_.Name -notlike 'put-*' } | ForEach-Object {@{Name=$_.BaseName}})
if($source.Count -ne 17){throw 'Expected the 17 alert-rule payload files.'}
& "$PSScriptRoot\activate-email.ps1" | Out-Null
$evidence=@()
foreach($rule in $source){
 $id="/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/scheduledQueryRules/$($rule.Name)"
 Assert-LabResourceId $id
 $raw=Invoke-LabAz resource show --ids $id --api-version 2023-12-01 -o json
 $before=($raw|Out-String)|ConvertFrom-Json
 $actions=@{}
 if($before.properties.actions){foreach($p in $before.properties.actions.PSObject.Properties){$actions[$p.Name]=$p.Value}}
 $groups=@($actions.actionGroups|Where-Object{$_})
 foreach($scope in $before.properties.scopes){Assert-LabResourceId $scope}
 $needsAttachment=$groups -notcontains $groupId
 if($needsAttachment){$groups+=$groupId}
 $actions.actionGroups=$groups
 $body=@{properties=@{actions=$actions}}
 $file="$PSScriptRoot\attach-$($rule.Name).json"
 [IO.File]::WriteAllText($file,(ConvertTo-Json $body -Depth 20),(New-Object Text.UTF8Encoding($false)))
 if($needsAttachment){Invoke-LabAz rest --method patch --url "https://management.azure.com$id`?api-version=2023-12-01" --body "@$file" -o none}
 $raw=Invoke-LabAz resource show --ids $id --api-version 2023-12-01 -o json
 $after=($raw|Out-String)|ConvertFrom-Json
 if(@($after.properties.actions.actionGroups) -notcontains $groupId){throw 'Notification group did not persist'}
 foreach($property in 'criteria','windowSize','evaluationFrequency','autoMitigate','severity','enabled','scopes'){
  $old=ConvertTo-Json -InputObject $before.properties.$property -Depth 20 -Compress
  $new=ConvertTo-Json -InputObject $after.properties.$property -Depth 20 -Compress
  if($old -cne $new){throw "Alert property $property unexpectedly changed"}
 }
 $evidence+=@{Rule=$rule.Name;Group=$groupId;CriteriaPreserved=$true;Utc=[datetime]::UtcNow.ToString('o')}
 "Attached approved email group to $($rule.Name); conditions unchanged."
}
[IO.File]::WriteAllText("$PSScriptRoot\rule-attachments.json",(ConvertTo-Json -InputObject $evidence -Depth 10),(New-Object Text.UTF8Encoding($false)))
