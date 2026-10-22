$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Unexpected guest.' }
$sql = Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER'"
$agent = Get-CimInstance Win32_Service -Filter "Name='SQLSERVERAGENT'"
$os = Get-CimInstance Win32_OperatingSystem
$process = Get-Process -Id $sql.ProcessId
$connection = New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Connect Timeout=15;Application Name=HV-Maintenance-ReadOnly')
try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandTimeout = 15
    $command.CommandText = 'SELECT 1'
    $queryResult = [int]$command.ExecuteScalar()
    $command.CommandText = "SELECT CONVERT(bigint,value_in_use) FROM sys.configurations WHERE name='max server memory (MB)'"
    $maxMemory = [long]$command.ExecuteScalar()
    $command.CommandText = "SELECT COUNT(*) FROM sys.databases WHERE state_desc <> 'ONLINE'"
    $notOnline = [int]$command.ExecuteScalar()
} finally { $connection.Dispose() }
$defender = Get-MpComputerStatus
$result = [ordered]@{
    Utc = [datetime]::UtcNow.ToString('o')
    Machine = $env:COMPUTERNAME
    SqlState = $sql.State
    SqlStartMode = $sql.StartMode
    SqlAgentState = $agent.State
    SqlAgentStartMode = $agent.StartMode
    SqlProcessId = $sql.ProcessId
    SqlProcessStartUtc = $process.StartTime.ToUniversalTime().ToString('o')
    LastBootUtc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
    QueryResult = $queryResult
    MaxServerMemoryMb = $maxMemory
    DatabasesNotOnline = $notOnline
    DefenderSignatureVersion = $defender.AntivirusSignatureVersion
    CbsRebootPending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    WindowsUpdateRebootPending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
}
$result | ConvertTo-Json
if ($sql.State -ne 'Running' -or $agent.State -ne 'Running' -or
    $sql.StartMode -ne 'Auto' -or $agent.StartMode -ne 'Auto' -or
    $queryResult -ne 1 -or $notOnline -ne 0) { throw 'SQL availability baseline failed.' }
