param([switch]$ApprovedCpuTest)
$ErrorActionPreference='Stop'
if(-not $ApprovedCpuTest){throw 'Pass -ApprovedCpuTest: only the bounded three-Windows-guest CPU scene is supported.'}
. "$PSScriptRoot\..\context.ps1"
$settings=Get-LabSettings
$protected=@{
    Win2019PasswordHex=(ConvertTo-LabHex $settings.WIN2019_GUEST_PASSWORD)
    Win2022PasswordHex=(ConvertTo-LabHex $settings.WIN2022_GUEST_PASSWORD)
    Win2025PasswordHex=(ConvertTo-LabHex $settings.WIN2025_GUEST_PASSWORD)
}
$settings=$null
$start=[datetime]::UtcNow
try {
    $output=Invoke-LabArcScript -Machine HV-HOST-01 `
        -ScriptPath "$PSScriptRoot\..\sources\demo-v22\host-cpu-rehearsal.ps1" `
        -Parameters @{LoadSeconds=900} -Protected $protected -TimeoutSeconds 2400
    $output
    $evidence=@{
        StartUtc=$start.ToString('o');EndUtc=[datetime]::UtcNow.ToString('o')
        Output=($output|Out-String);ThresholdChanged=$false;SQLStopRequested=$false
    }
    [IO.File]::WriteAllText("$PSScriptRoot\real-workload-evidence.json",
        (ConvertTo-Json $evidence -Depth 8),(New-Object Text.UTF8Encoding($false)))
} finally {
    $protected=$null
}
