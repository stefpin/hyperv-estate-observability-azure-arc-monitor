param([Parameter(Mandatory = $true)][string]$Query,[string]$WorkspaceId='00000000-0000-0000-0000-000000000009')
$ErrorActionPreference = 'Stop'
if ($WorkspaceId -match '^0{8}-0{4}-0{4}-0{4}-0{10}[0-9]{2}$') { throw 'Pass -WorkspaceId (the Log Analytics workspace ID) or run tools\Set-RepoContext.ps1 -WorkspaceId first.' }
$path = Join-Path $env:TEMP ('hv-query-{0}.kql' -f [guid]::NewGuid().ToString('N'))
try {
    [IO.File]::WriteAllText($path, $Query, (New-Object Text.UTF8Encoding($false)))
    for($attempt=1;$attempt -le 3;$attempt++){
        $ErrorActionPreference='Continue'
        $raw = & az monitor log-analytics query --workspace $WorkspaceId --analytics-query "@$path" -o json --only-show-errors 2>&1 | Out-String
        $code=$LASTEXITCODE
        $ErrorActionPreference='Stop'
        if($code -eq 0){break}
        if($raw -notmatch 'ConnectionResetError|Connection aborted|10054' -or $attempt -eq 3){throw "Log Analytics query failed: $raw"}
        Write-Warning "Transient Log Analytics network reset; retry $attempt of 3."
        Start-Sleep -Seconds 10
    }
    foreach ($row in ($raw | ConvertFrom-Json)) { $row }
}
finally { if (Test-Path $path) { Remove-Item -LiteralPath $path -Force } }
