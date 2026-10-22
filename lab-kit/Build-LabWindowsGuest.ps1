param([ValidateSet('WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','SQL2019-GUEST')][string]$GuestName)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'HV-HOST-01') { throw 'Execute on HV-HOST-01 only.' }
if (Get-VM -Name $GuestName -ErrorAction SilentlyContinue) { throw 'Existing guest is preserved; do not rebuild.' }
$map = @{
    'WIN2019-GUEST'=@('WindowsServer2019.iso','192.168.100.11',8)
    'WIN2022-GUEST'=@('WindowsServer2022.iso','192.168.100.12',8)
    'WIN2025-GUEST-01'=@('WindowsServer2025.iso','192.168.100.13',8)
    'SQL2019-GUEST'=@('WindowsServer2022.iso','192.168.100.15',12)
}
$secret=Read-Host "Private labadmin password for $GuestName" -AsSecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $pw=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $p=@{GuestName=$GuestName;IsoFile=$map[$GuestName][0];IpAddress=$map[$GuestName][1];
        MemoryGB=[int]$map[$GuestName][2];Cpu=4;GuestPassword=$pw;ReplaceStaleDisk='no'}
    if ($GuestName -eq 'WIN2025-GUEST-01') { $p.UnattendName='WIN2025-GUEST-0';$p.DnsHostName=$GuestName }
    & "$PSScriptRoot\build-guest.ps1" @p
} finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$pw=$null;$p=$null }
