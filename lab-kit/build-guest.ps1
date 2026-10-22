# build-guest.ps1 - runs ON THE HYPER-V HOST (operator guide chapter 7, automated path; parameters -MemoryGB and -GuestPasswordHex).
# Builds one Windows Server guest with no installer screens:
#   1 mounts the evaluation ISO and picks the "<Edition> ... (Desktop Experience)" image
#   2 creates a 127 GB dynamic VHDX on F:\VMs with the three UEFI partitions (system, MSR, Windows)
#   3 applies the image, then writes the boot files with the image's OWN bcdboot (the host's newer
#     bcdboot fails on Windows Server 2019 and 2022 images)
#   4 adds an answer file (name, time zone, passwords, no setup screens) and a first-boot script
#     (static address, ping allowed, Windows Update notify-only, labadmin password never expires)
#   5 creates the Hyper-V VM (Generation 2, static memory, VmNAT switch, starts with the host) and
#     waits until the guest answers on its address
# The answer file holds the password, so the first-boot script deletes it.
param(
    [string]$GuestName,
    [string]$IsoFile,
    [string]$Edition = 'Standard',
    [string]$IpAddress,
    [int]$Cpu = 4,
    [string]$UnattendName,
    [string]$DnsHostName = '',
    [string]$Dns1 = '8.8.8.8',
    [string]$Dns2 = '1.1.1.1',
    [string]$ReplaceStaleDisk = 'no',
    [int]$MemoryGB = 8,
    [string]$GuestPassword = '',
    [string]$GuestPasswordHex = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'HV-HOST-01') { throw 'Run only on HV-HOST-01.' }
if ($GuestName -notin 'WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01','SQL2019-GUEST') { throw 'Guest is outside the intended lab Windows set.' }
$t0 = Get-Date
function Log([string]$m) { "{0:HH:mm:ss} {1}" -f (Get-Date), $m }

if ($GuestPasswordHex -match '^x([0-9a-f]{2})+$') {
    $h = $GuestPasswordHex.Substring(1); $bb = New-Object byte[] ($h.Length / 2)
    for ($i = 0; $i -lt $bb.Length; $i++) { $bb[$i] = [Convert]::ToByte($h.Substring($i * 2, 2), 16) }
    $GuestPassword = [Text.Encoding]::ASCII.GetString($bb)
}
if (-not $GuestPassword) { throw 'GuestPassword missing' }
if ($MemoryGB -lt 2 -or $MemoryGB -gt 32) { throw "MemoryGB $MemoryGB is out of range" }
if (-not $UnattendName) { $UnattendName = $GuestName }
if ($UnattendName.Length -gt 15) { throw "UnattendName '$UnattendName' is longer than 15 characters" }
$vhd = "F:\VMs\$GuestName.vhdx"
if (Get-VM -Name $GuestName -ErrorAction SilentlyContinue) { throw "VM $GuestName already exists" }
if (Test-Path $vhd) {
    if ($ReplaceStaleDisk -ne 'yes') { throw "$vhd already exists" }
    if (Get-VM | Get-VMHardDiskDrive | Where-Object Path -eq $vhd) { throw "$vhd is attached to a VM - not removing it" }
    Dismount-VHD -Path $vhd -ErrorAction SilentlyContinue
    Remove-Item -Path $vhd -Force
    Log "Removed stale $vhd left by an earlier failed attempt"
}

$isoPath = "F:\ISO\$IsoFile"
if ((Get-DiskImage -ImagePath $isoPath).Attached) { Dismount-DiskImage -ImagePath $isoPath | Out-Null }
$iso = Mount-DiskImage -ImagePath $isoPath -PassThru
try {
    $isoLetter = ($iso | Get-Volume).DriveLetter
    $wim = "$($isoLetter):\sources\install.wim"
    if (-not (Test-Path $wim)) { $wim = "$($isoLetter):\sources\install.esd" }
    $img = Get-WindowsImage -ImagePath $wim |
        Where-Object { $_.ImageName -like "*$Edition*" -and $_.ImageName -like '*Desktop Experience*' } |
        Select-Object -First 1
    if (-not $img) { throw "No '$Edition (Desktop Experience)' image in $IsoFile" }
    Log ("Image [{0}] {1}" -f $img.ImageIndex, $img.ImageName)

    New-VHD -Path $vhd -SizeBytes 127GB -Dynamic | Out-Null
    $disk = Mount-VHD -Path $vhd -Passthru | Get-Disk
    try {
        Initialize-Disk -Number $disk.Number -PartitionStyle GPT
        $sys = New-Partition -DiskNumber $disk.Number -Size 260MB -GptType '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}'
        Format-Volume -Partition $sys -FileSystem FAT32 -NewFileSystemLabel 'System' -Confirm:$false -Force | Out-Null
        New-Partition -DiskNumber $disk.Number -Size 16MB -GptType '{e3c9e316-0b5c-4db8-817d-f92df00215ae}' | Out-Null
        $win = New-Partition -DiskNumber $disk.Number -UseMaximumSize -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}'
        Format-Volume -Partition $win -FileSystem NTFS -NewFileSystemLabel 'Windows' -Confirm:$false -Force | Out-Null
        $sys | Add-PartitionAccessPath -AssignDriveLetter
        $win | Add-PartitionAccessPath -AssignDriveLetter
        $S = (Get-Partition -DiskNumber $disk.Number -PartitionNumber $sys.PartitionNumber).AccessPaths |
            Where-Object { $_ -match '^[A-Z]:\\$' } | Select-Object -First 1
        $W = (Get-Partition -DiskNumber $disk.Number -PartitionNumber $win.PartitionNumber).AccessPaths |
            Where-Object { $_ -match '^[A-Z]:\\$' } | Select-Object -First 1
        if (-not $S -or -not $W) { throw 'Could not assign drive letters to the new partitions' }
        $S = $S.TrimEnd('\'); $W = $W.TrimEnd('\')
        Log "Partitions ready: system=$S windows=$W"

        Expand-WindowsImage -ImagePath $wim -Index $img.ImageIndex -ApplyPath "$W\" | Out-Null
        Log 'Image applied'

        # Use the bcdboot that ships in the applied image (Microsoft apply-image procedure); a newer host bcdboot
        # can fail on older images. Fall back to the host copy in offline mode.
        $b = & "$W\Windows\System32\bcdboot.exe" "$W\Windows" /s $S /f UEFI 2>&1
        if ($LASTEXITCODE -eq 0) { Log 'Boot files written (image bcdboot)' }
        else {
            Log "Image bcdboot failed: $b"
            $b2 = & bcdboot.exe "$W\Windows" /s $S /f UEFI /offline 2>&1
            if ($LASTEXITCODE -ne 0) { throw "bcdboot failed. Image copy: $b | Host copy /offline: $b2" }
            Log 'Boot files written (host bcdboot /offline)'
        }

        New-Item -ItemType Directory -Force -Path "$W\Windows\Panther", "$W\Windows\Setup\Scripts" | Out-Null
        $pw = [Security.SecurityElement]::Escape($GuestPassword)
        $unattend = @"
<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
  <settings pass="specialize">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <ComputerName>$UnattendName</ComputerName>
      <TimeZone>SE Asia Standard Time</TimeZone>
    </component>
  </settings>
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-International-Core" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <InputLocale>en-US</InputLocale>
      <SystemLocale>en-US</SystemLocale>
      <UILanguage>en-US</UILanguage>
      <UserLocale>en-US</UserLocale>
    </component>
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <OOBE>
        <HideEULAPage>true</HideEULAPage>
        <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
        <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
        <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
        <ProtectYourPC>3</ProtectYourPC>
        <SkipMachineOOBE>true</SkipMachineOOBE>
        <SkipUserOOBE>true</SkipUserOOBE>
      </OOBE>
      <UserAccounts>
        <AdministratorPassword>
          <Value>$pw</Value>
          <PlainText>true</PlainText>
        </AdministratorPassword>
        <LocalAccounts>
          <LocalAccount wcm:action="add">
            <Name>labadmin</Name>
            <DisplayName>Lab Admin</DisplayName>
            <Group>Administrators</Group>
            <Password>
              <Value>$pw</Value>
              <PlainText>true</PlainText>
            </Password>
          </LocalAccount>
        </LocalAccounts>
      </UserAccounts>
      <RegisteredOwner>Lab Admin</RegisteredOwner>
      <RegisteredOrganization>Lab</RegisteredOrganization>
    </component>
  </settings>
</unattend>
"@
        [IO.File]::WriteAllText("$W\Windows\Panther\unattend.xml", $unattend, (New-Object Text.UTF8Encoding($false)))

        $firstboot = @'
$ErrorActionPreference = 'Continue'
Start-Transcript -Path 'C:\Windows\Setup\Scripts\firstboot.log' -Append | Out-Null
# 1. Static address on the lab network
$a = $null
for ($i = 0; $i -lt 60 -and -not $a; $i++) {
    $a = Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $a) { Start-Sleep -Seconds 2 }
}
Set-NetIPInterface -InterfaceIndex $a.ifIndex -Dhcp Disabled -ErrorAction SilentlyContinue
Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Get-NetRoute -InterfaceIndex $a.ifIndex -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
New-NetIPAddress -InterfaceIndex $a.ifIndex -IPAddress '__IP__' -PrefixLength 24 -DefaultGateway '192.168.100.1' | Out-Null
Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses '__DNS1__','__DNS2__'
# 2. Allow ping from the host
New-NetFirewallRule -Name 'LAB-ICMPv4-In' -DisplayName 'Lab - allow ICMPv4 echo' -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
# 3. Windows Update: notify only, never restart automatically
$au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
New-Item -Path $au -Force | Out-Null
New-ItemProperty -Path $au -Name 'NoAutoUpdate' -Value 0 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $au -Name 'AUOptions' -Value 2 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $au -Name 'NoAutoRebootWithLoggedOnUsers' -Value 1 -PropertyType DWord -Force | Out-Null
# 4. No Server Manager pop-up at sign-in
New-Item -Path 'HKLM:\SOFTWARE\Microsoft\ServerManager' -Force | Out-Null
New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\ServerManager' -Name 'DoNotOpenServerManagerAtLogon' -Value 1 -PropertyType DWord -Force | Out-Null
# 5. DNS host name longer than 15 characters - takes effect at the next restart
$dnsName = '__DNSHOST__'
if ($dnsName) {
    Add-Type -Namespace Lab -Name Native -MemberDefinition '[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern bool SetComputerNameEx(int NameType, string lpBuffer);'
    "SetComputerNameEx($dnsName): " + [Lab.Native]::SetComputerNameEx(5, $dnsName)
}
# 6. Lab passwords must not expire before the lab is removed
Set-LocalUser -Name 'labadmin' -PasswordNeverExpires $true -ErrorAction SilentlyContinue
# 7. Remove the answer file - it held the password
Remove-Item -Path 'C:\Windows\Panther\unattend.xml' -Force -ErrorAction SilentlyContinue
Remove-Item -Path 'C:\Windows\Panther\Unattend' -Recurse -Force -ErrorAction SilentlyContinue
Set-Content -Path 'C:\Windows\Setup\Scripts\firstboot.done' -Value (Get-Date -Format s)
Stop-Transcript | Out-Null
'@
        $firstboot = $firstboot.Replace('__IP__', $IpAddress).Replace('__DNS1__', $Dns1).Replace('__DNS2__', $Dns2).Replace('__DNSHOST__', $DnsHostName)
        [IO.File]::WriteAllText("$W\Windows\Setup\Scripts\firstboot.ps1", $firstboot, (New-Object Text.UTF8Encoding($false)))
        $cmd = "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File %WINDIR%\Setup\Scripts\firstboot.ps1`r`nexit /b 0`r`n"
        [IO.File]::WriteAllText("$W\Windows\Setup\Scripts\SetupComplete.cmd", $cmd, [Text.Encoding]::ASCII)
        Log 'Answer file and first-boot script written'
    }
    finally {
        Dismount-VHD -Path $vhd
    }
}
finally {
    Dismount-DiskImage -ImagePath $isoPath | Out-Null
}

New-VM -Name $GuestName -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -VHDPath $vhd -SwitchName 'VmNAT' -Path 'F:\VMs' | Out-Null
Set-VM -Name $GuestName -ProcessorCount $Cpu -StaticMemory -AutomaticCheckpointsEnabled $false `
    -AutomaticStartAction Start -AutomaticStartDelay 30 -AutomaticStopAction Save
Set-VMFirmware -VMName $GuestName -FirstBootDevice (Get-VMHardDiskDrive -VMName $GuestName)
Enable-VMIntegrationService -VMName $GuestName -Name 'Guest Service Interface'
Start-VM -Name $GuestName
Log ("VM started with {0} vCPU and {1} GB static memory" -f $Cpu, $MemoryGB)

$deadline = (Get-Date).AddMinutes(25)
$ok = $false
while ((Get-Date) -lt $deadline) {
    if (Test-Connection -ComputerName $IpAddress -Count 1 -Quiet) { $ok = $true; break }
    Start-Sleep -Seconds 15
}
Log ("Ping {0}: {1}" -f $IpAddress, $ok)
"Elapsed {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes
if (-not $ok) { throw "$GuestName did not answer on $IpAddress within 25 minutes" }
