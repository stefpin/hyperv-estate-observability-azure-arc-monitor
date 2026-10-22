<#
.SYNOPSIS
    Replaces the placeholders in this repository with the values of your own environment.

.DESCRIPTION
    The code folders of this repository (lab-kit, monitoring, shift-report) contain neutral placeholders instead of
    real identifiers:

        <SUBSCRIPTION_ID>   your Azure subscription ID
        <TENANT_ID>         your Microsoft Entra tenant ID
        <PRIMARY_REGION>    the Azure region that hosts the lab (for example swedencentral)
        <SUFFIX>            a short unique suffix (3-8 lowercase letters or digits) for globally unique names such as
                            storage accounts and Function apps (optional here; the ARM templates need it before deployment)
        rg-hyperv-arc-monitor-demo   the default resource group name (optional rename)
        operator@example.com         the single allowed notification recipient (optional)
        donotreply@00000000-0000-0000-0000-000000000000.azurecomm.net   the Azure Communication Services sender (optional)
        00000000-0000-0000-0000-000000000009   workspace ID (customerId) of the Log Analytics workspace law-arc-monitor-lab (optional)
        00000000-0000-0000-0000-000000000018   workspace ID (customerId) of the Log Analytics workspace law-arc-ct-sea (optional)
        <GRAFANA_ENDPOINT>  the host name of your Azure Managed Grafana instance, for example name-abcd.sea.grafana.azure.com (optional)
        00000000-0000-0000-0000-000000000010   principal ID of the Automation account's managed identity (optional)

    By default the script only reports what it WOULD change. Add -Apply to write the files. The docs folder keeps
    its placeholders unless you add -IncludeDocs (Markdown files inside lab-kit, monitoring and shift-report are always processed). Files keep their encoding (a UTF-8 byte-order mark is preserved) and
    their line endings.

    After -Apply, the shift-report application must be re-pinned because its policy file fingerprints the files that
    were changed:  python shift-report/tools/pin_policy.py  (see shift-report/README.md).

    Not replaced automatically (edit them by hand): any ID or host name you did not pass. The other sentinel GUIDs (0000...0005 workbook, 0000...0008 and similar) are fixed
    identifiers that the scripts create and then refer to; leave them as they are.

.EXAMPLE
    .\tools\Set-RepoContext.ps1 -SubscriptionId 11111111-2222-3333-4444-555555555555 `
        -TenantId 22222222-3333-4444-5555-666666666666 -PrimaryRegion swedencentral

    Dry run: lists the number of replacements per placeholder and writes nothing.

.EXAMPLE
    .\tools\Set-RepoContext.ps1 -SubscriptionId $sub -TenantId $tenant -PrimaryRegion westeurope `
        -ResourceGroup rg-my-hyperv-lab -Recipient me@example.org -Apply
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$TenantId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9]{3,30}$')]
    [string]$PrimaryRegion,

    [ValidatePattern('^[A-Za-z0-9._()-]{1,90}$')]
    [string]$ResourceGroup,

    [ValidatePattern('^[^@\s]+@[^@\s]+\.[^@\s]+$')]
    [string]$Recipient,

    [ValidatePattern('^[^@\s<>]+@[^@\s<>]+$')]
    [string]$AcsSender,

    [ValidatePattern('^[a-z0-9]{3,8}$')]
    [string]$Suffix,

    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$WorkspaceId,

    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$CtWorkspaceId,

    [ValidatePattern('^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')]
    [string]$AutomationPrincipalId,

    [ValidatePattern('^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$')]
    [string]$GrafanaEndpoint,

    [switch]$IncludeDocs,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

$replacements = [ordered]@{
    '<SUBSCRIPTION_ID>' = $SubscriptionId
    '<TENANT_ID>'       = $TenantId
    '<PRIMARY_REGION>'  = $PrimaryRegion
}
if ($Suffix)        { $replacements['<SUFFIX>'] = $Suffix }
if ($WorkspaceId)   { $replacements['00000000-0000-0000-0000-000000000009'] = $WorkspaceId }
if ($CtWorkspaceId) { $replacements['00000000-0000-0000-0000-000000000018'] = $CtWorkspaceId }
if ($AutomationPrincipalId) { $replacements['00000000-0000-0000-0000-000000000010'] = $AutomationPrincipalId }
if ($GrafanaEndpoint) { $replacements['<GRAFANA_ENDPOINT>'] = $GrafanaEndpoint }
if ($ResourceGroup) { $replacements['rg-hyperv-arc-monitor-demo'] = $ResourceGroup }
if ($Recipient)     { $replacements['operator@example.com'] = $Recipient }
if ($AcsSender)     { $replacements['donotreply@00000000-0000-0000-0000-000000000000.azurecomm.net'] = $AcsSender }

$folders = @('lab-kit', 'monitoring', 'shift-report')
if ($IncludeDocs) { $folders += 'docs' }
$extensions = @('.ps1', '.py', '.json', '.kql', '.sh', '.txt', '.md', '.service', '.drawio', '.yml')

$counts = [ordered]@{}
foreach ($token in $replacements.Keys) { $counts[$token] = [pscustomobject]@{ Files = 0; Occurrences = 0 } }
$changedFiles = New-Object System.Collections.Generic.List[string]
$encoding = New-Object System.Text.UTF8Encoding($false)

foreach ($folder in $folders) {
    $root = Join-Path $repo $folder
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File) {
        if ($extensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
        $bytes = [IO.File]::ReadAllBytes($file.FullName)
        if ($bytes -contains 0) { continue }
        $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
        $skip = if ($hasBom) { 3 } else { 0 }
        $text = $encoding.GetString($bytes, $skip, $bytes.Length - $skip)
        $updated = $text
        foreach ($token in $replacements.Keys) {
            $hits = ([regex]::Matches($updated, [regex]::Escape($token))).Count
            if ($hits -gt 0) {
                $counts[$token].Files++
                $counts[$token].Occurrences += $hits
                $updated = $updated.Replace($token, $replacements[$token])
            }
        }
        if ($updated -ne $text) {
            $changedFiles.Add($file.FullName.Substring($repo.Length + 1))
            if ($Apply) {
                $out = $encoding.GetBytes($updated)
                if ($hasBom) { $out = [byte[]](@(0xEF, 0xBB, 0xBF) + $out) }
                [IO.File]::WriteAllBytes($file.FullName, $out)
            }
        }
    }
}

$counts.GetEnumerator() | ForEach-Object {
    [pscustomobject]@{ Placeholder = $_.Key; Files = $_.Value.Files; Occurrences = $_.Value.Occurrences }
} | Format-Table -AutoSize

if ($Apply) {
    "Updated $($changedFiles.Count) file(s)."
    if ($changedFiles | Where-Object { $_ -like 'shift-report*' }) {
        'Shift-report files changed: re-pin the policy with  python shift-report/tools/pin_policy.py  and run the tests (shift-report/README.md).'
    }
    'Reminder: pass -WorkspaceId, -CtWorkspaceId, -AutomationPrincipalId and -GrafanaEndpoint (or edit the placeholders by hand) if you have not set them yet.'
}
else {
    "Dry run: $($changedFiles.Count) file(s) would change. Re-run with -Apply to write them."
}
