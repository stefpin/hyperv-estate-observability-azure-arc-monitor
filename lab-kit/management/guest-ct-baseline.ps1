$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Wrong machine' }
$sql = Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER'"
if ($sql.State -ne 'Running' -or $sql.StartMode -ne 'Auto') { throw 'SQL must be Running and Automatic' }
$folder = 'C:\HV-Demo\ChangeTracking-v22'
$registry = 'HKLM:\SOFTWARE\HV-Demo\ChangeTracking-v22'
if ((Test-Path $folder) -or (Test-Path $registry)) { throw 'Dedicated fixture already exists; do not overwrite' }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
[IO.File]::WriteAllText("$folder\fixture-demo.txt", "Safe change tracking baseline`r`n", (New-Object Text.UTF8Encoding($false)))
New-Item -Path $registry -Force | Out-Null
New-ItemProperty -Path $registry -Name DemoState -Value 'Baseline' -PropertyType String | Out-Null
[pscustomobject]@{
    Utc = [datetime]::UtcNow.ToString('o')
    Computer = $env:COMPUTERNAME
    SqlState = $sql.State
    SqlStartMode = $sql.StartMode
    LastBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
    File = "$folder\fixture-demo.txt"
    Hash = (Get-FileHash "$folder\fixture-demo.txt" -Algorithm SHA256).Hash
    Registry = $registry
    DemoState = (Get-ItemProperty $registry).DemoState
} | ConvertTo-Json -Depth 8
