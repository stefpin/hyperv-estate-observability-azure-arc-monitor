$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\sql-install\arc-run.ps1"
$path = (Join-Path $PSScriptRoot '..\..\..\ENVIRONMENT.txt')
$environment = @{}
foreach ($line in [IO.File]::ReadAllLines($path)) { if ($line -match '^([A-Z0-9_]+)=(.*)$') { $environment[$matches[1]] = $matches[2] } }
if (-not $environment.ContainsKey('SQL_COLLECTOR_PASSWORD')) {
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random = New-Object byte[] 24; $rng.GetBytes($random) } finally { $rng.Dispose() }
    $password = [Convert]::ToBase64String($random).Replace('+','-').Replace('/','_') + 'aB7!'
    $text = [IO.File]::ReadAllText($path)
    $nl = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $prefix = if ($text.EndsWith("`n")) { '' } else { $nl }
    [IO.File]::AppendAllText($path, $prefix + "SQL_COLLECTOR_USER=SQL2019-GUEST\HvSqlCollector${nl}SQL_COLLECTOR_PASSWORD=$password$nl", (New-Object Text.UTF8Encoding($false)))
    $environment.SQL_COLLECTOR_PASSWORD = $password
}
$hex = 'x' + (([Text.Encoding]::ASCII.GetBytes($environment.SQL_COLLECTOR_PASSWORD) | ForEach-Object { $_.ToString('x2') }) -join '')
$content = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PSScriptRoot\memory-collector.ps1"))
foreach ($file in Get-ChildItem $PSScriptRoot -Filter *.ps1) {
    $t = $null; $e = $null
    [void][Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$t, [ref]$e)
    if ($e.Count) { throw ($e | Out-String) }
}
$result = Invoke-HvArc -Machine SQL2019-GUEST -Name sql-memory-setup -ScriptPath "$PSScriptRoot\guest-memory-setup.ps1" `
    -Parameters @{CollectorBase64=$content} -Protected @{CollectorPasswordHex=$hex} -Timeout 1200
$result.Output
Remove-HvArcCommand -Machine $result.Machine -Name $result.Name
