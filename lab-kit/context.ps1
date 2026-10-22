$ErrorActionPreference = 'Stop'
$SUB = '<SUBSCRIPTION_ID>'
$TENANT = '<TENANT_ID>'
$RG = 'rg-hyperv-arc-monitor-demo'
$ResourcePrefix = "/subscriptions/$SUB/resourceGroups/$RG"
$ArcPrefix = "$ResourcePrefix/providers/Microsoft.HybridCompute/machines"
$script:LabRoot = Split-Path $PSScriptRoot -Parent

function Assert-LabContext {
    $raw = & az account show --only-show-errors -o json
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI sign-in required in a visible operator window.' }
    $account = ($raw | Out-String) | ConvertFrom-Json
    if ($account.id -ne $SUB -or $account.tenantId -ne $TENANT) {
        throw 'Wrong subscription or tenant; no changes are permitted.'
    }
}
function Assert-LabResourceId([string]$Id) {
    if (-not $Id.StartsWith($ResourcePrefix + '/', [StringComparison]::OrdinalIgnoreCase) -and
        -not $Id.Equals($ResourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Resource is outside the authorized group.'
    }
}
function Invoke-LabAz {
    $Arguments = @($args)
    Assert-LabContext
    $a = @($Arguments | ForEach-Object { [string]$_ })
    if ($a.Count -lt 2) { throw 'Azure command missing.' }
    $text = $a -join ' '
    if ($text -match '(?i)(provider\s+(register|unregister)|policy\s+|vm\s+run-command|security\s+pricing|group\s+delete)') {
        throw 'Subscription changes, VM Run Command and teardown are excluded from this helper.'
    }
    foreach ($flag in '-g','--resource-group') {
        $i = [Array]::IndexOf($a,$flag)
        if ($i -ge 0 -and ($i+1 -ge $a.Count -or $a[$i+1] -ne $RG)) { throw 'Wrong resource group.' }
    }
    if ($a[0] -eq 'group' -and ($a[1] -ne 'create' -or $text -notmatch [regex]::Escape($RG))) {
        throw 'Only the named lab group creation is permitted.'
    }
    if ($a[0] -eq 'rest') {
        $i = [Array]::IndexOf($a,'--url')
        if ($i -lt 0) { throw 'REST URL missing.' }
        $url = $a[$i+1]
        $expected = 'https://management.azure.com' + $ResourcePrefix
        if (-not $url.StartsWith($expected+'/',[StringComparison]::OrdinalIgnoreCase) -and
            -not $url.StartsWith($expected+'?',[StringComparison]::OrdinalIgnoreCase)) {
            throw 'REST endpoint is outside this group.'
        }
    }
    foreach ($flag in '--resource-id','--resource','--ids') {
        $i = [Array]::IndexOf($a,$flag)
        if ($i -ge 0) { Assert-LabResourceId $a[$i+1] }
    }
    $output = & az @a --subscription $SUB --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed ($LASTEXITCODE); inspect its non-secret error." }
    $output
}
function Get-LabSettings {
    $path = Join-Path $script:LabRoot 'ENVIRONMENT.txt'
    if (-not (Test-Path -LiteralPath $path)) { throw 'ENVIRONMENT.txt not found in the repository root.' }
    $settings = @{}
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=(.*)$') {
            $key=$matches[1];$value=$matches[2]
            if($key -match 'PASSWORD|TOKEN|SECRET|PRODUCT_KEY|WEBHOOK_URI'){$settings[$key]=$value}
            else{$settings[$key]=$value.Trim()}
        }
    }
    if ($settings.SUBSCRIPTION_ID -ne $SUB -or $settings.RESOURCE_GROUP -ne $RG) {
        throw 'Private settings name another scope.'
    }
    return $settings
}
function Get-LabCredential {
    param([ValidateSet('HV-HOST-01','WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','SQL2019-GUEST')][string]$Machine)
    $key = switch ($Machine) {
        'HV-HOST-01' { 'HOST_ADMIN_PASSWORD' }
        'WIN2019-GUEST' { 'WIN2019_GUEST_PASSWORD' }
        'WIN2022-GUEST' { 'WIN2022_GUEST_PASSWORD' }
        'WIN2025-GUEST-01' { 'WIN2025_GUEST_PASSWORD' }
        'SQL2019-GUEST' { 'SQL_GUEST_PASSWORD' }
    }
    $settings = Get-LabSettings
    if (-not $settings[$key]) { throw 'Required private guest credential missing.' }
    $secure = ConvertTo-SecureString $settings[$key] -AsPlainText -Force
    New-Object Management.Automation.PSCredential('labadmin',$secure)
}
function ConvertTo-LabHex([string]$Value) {
    'x' + ([BitConverter]::ToString([Text.Encoding]::ASCII.GetBytes($Value))).Replace('-','').ToLowerInvariant()
}
function Invoke-LabArcScript {
    param(
        [ValidateSet('HV-HOST-01','WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','RHEL94-GUEST','SQL2019-GUEST')][string]$Machine,
        [Parameter(Mandatory=$true)][string]$ScriptPath,
        [System.Collections.IDictionary]$Parameters=@{},
        [System.Collections.IDictionary]$Protected=@{},
        [int]$TimeoutSeconds=3600
    )
    Assert-LabContext
    $source = (Resolve-Path -LiteralPath $ScriptPath).Path
    $region = & az connectedmachine show -g $RG -n $Machine --subscription $SUB --query location -o tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or -not $region) { throw 'Cannot resolve the actual Arc machine region.' }
    $name = 'hv-run-' + [guid]::NewGuid().ToString('N').Substring(0,16)
    $private = Join-Path $env:USERPROFILE 'HV-Private'
    New-Item -ItemType Directory -Path $private -Force | Out-Null
    & icacls.exe $private /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot secure non-synced private parameter directory.' }
    $files = @()
    $created = $false
    try {
        $args = @('connectedmachine','run-command','create','-g',$RG,
            '--machine-name',$Machine,'--location',$region,'--name',$name,
            '--script',"@$source",'--timeout-in-seconds',"$TimeoutSeconds",
            '--async-execution','false','-o','none')
        foreach ($p in @(@{Values=$Parameters;Flag='--parameters'},@{Values=$Protected;Flag='--protected-parameters'})) {
            if ($p.Values.Count -eq 0) { continue }
            $file = Join-Path $private ($name + '-' + $files.Count + '.json')
            $files += $file
            $values = @($p.Values.Keys | ForEach-Object { @{name=[string]$_;value=[string]$p.Values[$_]} })
            [IO.File]::WriteAllText($file,(ConvertTo-Json -InputObject $values -Depth 5 -Compress),(New-Object Text.UTF8Encoding($false)))
            $args += @($p.Flag,"@$file")
        }
        $created = $true
        Invoke-LabAz @args | Out-Null
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds+120)
        do {
            $raw = Invoke-LabAz connectedmachine run-command show -g $RG --machine-name $Machine --name $name --query instanceView -o json
            $view = ($raw | Out-String) | ConvertFrom-Json
            if ($view.executionState -in 'Succeeded','Failed','TimedOut','Canceled') { break }
            Start-Sleep -Seconds 15
        } while ((Get-Date) -lt $deadline)
        if ($view.executionState -ne 'Succeeded' -or [int]$view.exitCode -ne 0) {
            throw "Arc script failed: state=$($view.executionState), exit=$($view.exitCode). Inspect Portal securely."
        }
        $view.output -replace 'eyJ[A-Za-z0-9_.-]{40,}','[redacted token]'
    }
    finally {
        foreach ($file in $files) { Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue }
        if ($created) {
            & az connectedmachine run-command delete -g $RG --machine-name $Machine --name $name --yes --subscription $SUB --only-show-errors -o none
            if ($LASTEXITCODE -ne 0) { Write-Warning "Cleanup requires review: Arc Run Command $name" }
        }
    }
}
function Invoke-LabQuery {
    param([Parameter(Mandatory=$true)][string]$QueryFile,
        [Parameter(Mandatory=$true)][string]$OutputPath,
        [string]$Workspace='law-arc-monitor-lab')
    Assert-LabContext
    if ($Workspace -notin 'law-arc-monitor-lab','law-arc-ct-sea') { throw 'Workspace outside lab query scope.' }
    $id = & az monitor log-analytics workspace show -g $RG -n $Workspace --subscription $SUB --query customerId -o tsv --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Workspace lookup failed.' }
    $query = [IO.File]::ReadAllText((Resolve-Path $QueryFile).Path)
    $raw = & az monitor log-analytics query --workspace $id --analytics-query $query --subscription $SUB --only-show-errors -o json
    if ($LASTEXITCODE -ne 0) { throw 'Log Analytics query failed; no success export written.' }
    New-Item -ItemType Directory -Path (Split-Path $OutputPath -Parent) -Force | Out-Null
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($OutputPath),($raw | Out-String),(New-Object Text.UTF8Encoding($false)))
    Write-Output "Query saved: $OutputPath"
}
Assert-LabContext
