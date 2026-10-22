$ErrorActionPreference = 'Stop'
$ExpectedBootUtc = '<BOOT_TIME_UTC>'  # the guest's LastBootUpTime in UTC (round-trip format), recorded before the maintenance test
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Wrong machine' }
$sql = Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER'"
$agent = Get-CimInstance Win32_Service -Filter "Name='SQLSERVERAGENT'"
$os = Get-CimInstance Win32_OperatingSystem
$defender = Get-MpComputerStatus
$wuPolicy = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
$pending = @{
    Cbs = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    WindowsUpdate = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
}
$wuHistory = @()
try {
    $searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
    $count = [math]::Min(20, $searcher.GetTotalHistoryCount())
    if ($count -gt 0) {
        $wuHistory = @($searcher.QueryHistory(0,$count) | Where-Object { $_.Title -like '*KB2267602*' } |
            Select-Object -First 3 Title,@{n='DateReported';e={$_.Date.ToString('o')}},@{n='DateKind';e={[string]$_.Date.Kind}},ResultCode,Operation,ClientApplicationID)
    }
}
catch { $wuHistory = @(@{ HistoryReadError = 'Optional Windows Update history query was unavailable.' }) }
$result = [ordered]@{
    Utc = [datetime]::UtcNow.ToString('o'); Machine = $env:COMPUTERNAME
    SqlState = $sql.State; SqlStartMode = $sql.StartMode
    SqlAgentState = $agent.State; SqlAgentStartMode = $agent.StartMode
    LastBootUtc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
    ExpectedBootUnchanged = ($os.LastBootUpTime.ToUniversalTime().ToString('o') -eq $ExpectedBootUtc)
    Os = $os.Caption; Version = $os.Version
    WindowsUpdateAUOptions = $wuPolicy.AUOptions; WindowsUpdateNoAutoUpdate = $wuPolicy.NoAutoUpdate
    DefenderSignatureVersion = $defender.AntivirusSignatureVersion
    DefenderSignatureUpdatedUtc = $defender.AntivirusSignatureLastUpdated.ToUniversalTime().ToString('o')
    RebootPending = $pending
    DefenderWindowsUpdateHistory = $wuHistory
    FixtureHash = (Get-FileHash 'C:\HV-Demo\ChangeTracking-v22\fixture-demo.txt' -Algorithm SHA256).Hash
    FixtureRegistryValue = (Get-ItemProperty 'HKLM:\SOFTWARE\HV-Demo\ChangeTracking-v22').DemoState
}
$result | ConvertTo-Json -Depth 8
if ($sql.State -ne 'Running' -or $sql.StartMode -ne 'Auto' -or -not $result.ExpectedBootUnchanged) { throw 'Final SQL or no-reboot safety check failed' }
