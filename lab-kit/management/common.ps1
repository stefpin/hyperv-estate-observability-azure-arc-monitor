$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\context.ps1"
$HvSub = '<SUBSCRIPTION_ID>'
$HvRg = 'rg-hyperv-arc-monitor-demo'
$HvRoot = "/subscriptions/$HvSub/resourceGroups/$HvRg"
$HvMachine = "$HvRoot/providers/Microsoft.HybridCompute/machines/SQL2019-GUEST"
$HvWork = $PSScriptRoot
$HvAzPython = 'C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\python.exe'
function Save-HvJson {
    param([string]$Name, [object]$Value)
    $json = if ($null -eq $Value) { 'null' } else { ConvertTo-Json -InputObject $Value -Depth 80 }
    [IO.File]::WriteAllText((Join-Path $HvWork $Name), $json, (New-Object Text.UTF8Encoding($false)))
}
function Invoke-HvRest {
    param([string]$Method, [string]$Path, [object]$Body, [string]$Evidence)
    if ($Path -notlike "$HvRoot/*") { throw "Resource-group scope violation: $Path" }
    $args = @('rest', '--method', $Method, '--url', "https://management.azure.com$Path", '--only-show-errors', '-o', 'json')
    if ($null -ne $Body) {
        $file = Join-Path $HvWork ('request-{0}.json' -f [guid]::NewGuid().ToString('N'))
        Save-HvJson ([IO.Path]::GetFileName($file)) $Body
        $args += @('--body', "@$file")
    }
    try {
        $output = & az @args --subscription $HvSub 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw $output }
        $result = if ($output.Trim()) { $output | ConvertFrom-Json } else { $null }
        if ($Evidence) { Save-HvJson $Evidence $result }
        return $result
    }
    finally { if ($file -and (Test-Path -LiteralPath $file)) { Remove-Item -LiteralPath $file -Force } }
}

function Invoke-HvOwnedCommand {
    param([string]$Machine = 'SQL2019-GUEST', [string]$Script, [string]$Evidence)
    if ($Machine -notin @('SQL2019-GUEST','HV-HOST-01')) { throw 'Unexpected Arc Run Command target' }
    $name = 'hv-management-' + [guid]::NewGuid().ToString('N').Substring(0,12)
    $id = "$HvRoot/providers/Microsoft.HybridCompute/machines/$Machine/runCommands/$name"
    $location = if ($Machine -eq 'SQL2019-GUEST') { 'southeastasia' } else { '<PRIMARY_REGION>' }
    try {
        Invoke-HvRest PUT "$id`?api-version=2025-01-13" @{
            location = $location
            properties = @{
                source = @{ script = [IO.File]::ReadAllText((Join-Path $HvWork $Script)) }
                timeoutInSeconds = 300; asyncExecution = $false
            }
        } '' | Out-Null
        $status = $null
        for ($i=0; $i -lt 120; $i++) {
            Start-Sleep -Seconds 5
            $status = Invoke-HvRest GET "$id`?api-version=2025-01-13" $null ''
            if ($status.properties.instanceView.executionState -in @('Succeeded','Failed','TimedOut','Canceled')) { break }
        }
        $result = [pscustomobject]@{ Name=$name; Machine=$Machine; InstanceView=$status.properties.instanceView; Output=$status.properties.instanceView.output }
        Save-HvJson $Evidence $result
        if ($result.InstanceView.executionState -ne 'Succeeded' -or $result.InstanceView.exitCode -ne 0) { throw "Own Arc Run Command failed: $name; see $Evidence" }
        Write-Output $result.Output
    }
    finally {
        Invoke-HvRest DELETE "$id`?api-version=2025-01-13" $null '' | Out-Null
    }
}
