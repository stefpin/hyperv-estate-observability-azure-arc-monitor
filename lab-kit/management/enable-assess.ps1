. "$PSScriptRoot\common.ps1"
$body = @{ properties = @{ osProfile = @{ windowsConfiguration = @{ patchSettings = @{ assessmentMode = 'AutomaticByPlatform' } } } } }
Save-HvJson 'periodic-assessment-request.json' $body
Invoke-HvRest PATCH "$HvMachine`?api-version=2025-01-13" $body 'periodic-assessment-result.json' | Out-Null
Invoke-HvRest POST "$HvMachine/assessPatches`?api-version=2025-01-13" @{} 'assessment-submit.json'
