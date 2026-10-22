$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\context.ps1"
$script:HvSubscription = '<SUBSCRIPTION_ID>'
$script:HvGroup = 'rg-hyperv-arc-monitor-demo'

function Invoke-HvArc {
    param(
        [ValidateSet('HV-HOST-01', 'SQL2019-GUEST')][string]$Machine,
        [string]$Name,
        [string]$ScriptPath,
        [System.Collections.IDictionary]$Parameters = @{},
        [System.Collections.IDictionary]$Protected = @{},
        [int]$Timeout = 3600
    )
    $location = & az connectedmachine show --subscription $script:HvSubscription -g $script:HvGroup -n $Machine --query location -o tsv --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Arc machine region lookup failed' }
    $commandName = '{0}-{1:MMddHHmmss}' -f $Name, (Get-Date)
    $args = @('connectedmachine', 'run-command', 'create', '--subscription', $script:HvSubscription,
        '--resource-group', $script:HvGroup, '--machine-name', $Machine, '--location', $location,
        '--name', $commandName, '--script', "@$ScriptPath", '--timeout-in-seconds', "$Timeout",
        '--async-execution', 'false', '--only-show-errors', '-o', 'none')
    $parameterFiles = @()
    try {
        foreach ($item in @(@{ Values = $Parameters; Flag = '--parameters' }, @{ Values = $Protected; Flag = '--protected-parameters' })) {
            if ($item.Values.Count -eq 0) { continue }
            New-Item -ItemType Directory -Path (Join-Path $env:USERPROFILE 'HV-Private\protected-staging') -Force | Out-Null
            $file = Join-Path (Join-Path $env:USERPROFILE 'HV-Private\protected-staging') ('hv-parameters-{0}.json' -f [guid]::NewGuid().ToString('N'))
            $parameterFiles += $file
            [IO.File]::WriteAllText($file, '', (New-Object Text.UTF8Encoding($false)))
            & icacls.exe $file /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" '*S-1-5-18:(F)' '*S-1-5-32-544:(F)' | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not secure the Run Command parameter file' }
            $values = @($item.Values.Keys | ForEach-Object { @{ name = $_; value = [string]$item.Values[$_] } })
            [IO.File]::WriteAllText($file, (ConvertTo-Json -InputObject $values -Depth 5 -Compress), (New-Object Text.UTF8Encoding($false)))
            $args += @($item.Flag, "@$file")
        }
        Write-Host ("Running {0} on {1}" -f $commandName, $Machine)
        $cliOutput = & az @args 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw ("Arc execution request failed: " + $cliOutput) }
        $json = & az connectedmachine run-command show --subscription $script:HvSubscription -g $script:HvGroup `
            --machine-name $Machine --name $commandName --query instanceView -o json --only-show-errors
        if ($LASTEXITCODE -ne 0) { throw "Could not retrieve result for $commandName" }
        $result = ($json | Out-String) | ConvertFrom-Json
        if ($result.executionState -ne 'Succeeded' -or [int]$result.exitCode -ne 0) {
            throw ("Remote command failed: {0}; output: {1}; error: {2}" -f $result.executionState, $result.output, $result.error)
        }
        [pscustomobject]@{ Name = $commandName; Machine = $Machine; Output = $result.output }
    }
    finally {
        foreach ($file in $parameterFiles) { if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force } }
    }
}

function Remove-HvArcCommand([string]$Machine, [string]$Name) {
    & az connectedmachine run-command delete --subscription $script:HvSubscription -g $script:HvGroup `
        --machine-name $Machine --name $Name --yes --no-wait --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw "Could not remove Run Command $Name" }
}
