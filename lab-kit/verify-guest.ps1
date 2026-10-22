# verify-guest.ps1 - runs ON THE HYPER-V HOST (operator guide chapter 7, automated path; supports
# -GuestPasswordHex and includes the Azure metadata-service check).
# Signs in to one Windows guest through PowerShell Direct (no network needed) and reports its
# name, address, internet access, Windows activation (activating it if needed), answer-file removal,
# Windows Update policy, time zone, labadmin password expiry, and whether the Azure Instance Metadata
# Service (169.254.169.254) is reachable - it must NOT be, or Azure Arc refuses to onboard the guest.
param(
    [string]$GuestName,
    [string]$GuestPassword = '',
    [string]$GuestPasswordHex = '',
    [string]$ExpectedHostName = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($GuestPasswordHex -match '^x([0-9a-f]{2})+$') {
    $h = $GuestPasswordHex.Substring(1); $bb = New-Object byte[] ($h.Length / 2)
    for ($i = 0; $i -lt $bb.Length; $i++) { $bb[$i] = [Convert]::ToByte($h.Substring($i * 2, 2), 16) }
    $GuestPassword = [Text.Encoding]::ASCII.GetString($bb)
}
if (-not $GuestPassword) { throw 'GuestPassword missing' }
if (-not $ExpectedHostName) { $ExpectedHostName = $GuestName }
$sec = ConvertTo-SecureString $GuestPassword -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential('labadmin', $sec)

$vm = Get-VM -Name $GuestName
"VM {0}: state={1} vCPU={2} memoryGB={3} dynamicMemory={4} heartbeat={5} autostart={6} checkpoints={7}" -f $vm.Name, $vm.State, $vm.ProcessorCount, ($vm.MemoryStartup / 1GB), $vm.DynamicMemoryEnabled, $vm.Heartbeat, $vm.AutomaticStartAction, $vm.AutomaticCheckpointsEnabled

$r = Invoke-Command -VMName $GuestName -Credential $cred -ScriptBlock {
    $ProgressPreference = 'SilentlyContinue'
    $os = Get-CimInstance Win32_OperatingSystem
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.100.*' }).IPAddress
    $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -First 1).NextHop
    $dns = (Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $_.ServerAddresses } | Select-Object -First 1).ServerAddresses -join ','
    $net = Test-NetConnection -ComputerName 'login.microsoftonline.com' -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue
    $imds = 'not reachable'
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri 'http://169.254.169.254/metadata/instance?api-version=2021-02-01' -Headers @{ Metadata = 'true' } -TimeoutSec 5
        $imds = 'REACHABLE'
    }
    catch { if ($_.Exception.Response) { $imds = 'REACHABLE (HTTP error)' } }
    $appId = '55c92734-d682-4d71-983e-d6ec3f16059f'
    $lic = Get-CimInstance SoftwareLicensingProduct -Filter "ApplicationID='$appId' AND PartialProductKey IS NOT NULL"
    $actOut = ''
    if ($lic.LicenseStatus -ne 1) {
        $actOut = (& cscript.exe //nologo "$env:SystemRoot\System32\slmgr.vbs" /ato 2>&1) -join ' '
        $lic = Get-CimInstance SoftwareLicensingProduct -Filter "ApplicationID='$appId' AND PartialProductKey IS NOT NULL"
    }
    [pscustomobject]@{
        DnsHostName  = [System.Net.Dns]::GetHostName()
        NetBiosName  = $env:COMPUTERNAME
        Caption      = $os.Caption
        Build        = $os.BuildNumber
        MemoryGB     = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
        Cpus         = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
        IPv4         = $ip
        Gateway      = $gw
        Dns          = $dns
        Internet443  = $net
        Imds         = $imds
        LicenseName  = $lic.Name
        LicenseState = $lic.LicenseStatus
        EvalDaysLeft = [math]::Round($lic.GracePeriodRemaining / 1440, 0)
        ActivateOut  = $actOut
        FirstBoot    = (Test-Path 'C:\Windows\Setup\Scripts\firstboot.done')
        AnswerFile   = (Test-Path 'C:\Windows\Panther\unattend.xml')
        AutoUpdate   = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue).AUOptions
        TimeZone     = (Get-TimeZone).Id
        PwExpires    = $(if ((Get-LocalUser -Name 'labadmin').PasswordExpires) { (Get-LocalUser -Name 'labadmin').PasswordExpires.ToString('yyyy-MM-dd') } else { 'never' })
    }
}
"Host name: DNS={0} NetBIOS={1} expected={2} match={3}" -f $r.DnsHostName, $r.NetBiosName, $ExpectedHostName, ($r.DnsHostName -eq $ExpectedHostName)
"OS: {0} (build {1}); guest sees {2} vCPU and {3} GB" -f $r.Caption, $r.Build, $r.Cpus, $r.MemoryGB
"Network: ip={0} gateway={1} dns={2} internet443={3}" -f $r.IPv4, $r.Gateway, $r.Dns, $r.Internet443
"Azure metadata service 169.254.169.254: {0}" -f $r.Imds
"Licence: {0} status={1} (1=licensed) days_left={2}" -f $r.LicenseName, $r.LicenseState, $r.EvalDaysLeft
if ($r.ActivateOut) { "Activation: " + $r.ActivateOut }
"First boot done={0} answer_file_left={1} WU_AUOptions={2} timezone={3} labadmin_password_expires={4}" -f $r.FirstBoot, $r.AnswerFile, $r.AutoUpdate, $r.TimeZone, $r.PwExpires
if ($r.Imds -ne 'not reachable') { throw 'The guest can reach the Azure metadata service - Azure Arc would refuse to onboard it' }
'VERIFY-DONE'
