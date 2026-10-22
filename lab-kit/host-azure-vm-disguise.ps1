# host-azure-vm-disguise.ps1 - runs ON THE HYPER-V HOST through Arc Run Command (operator guide chapter 9).
# Disables the Azure guest agent (from now on the portal cannot use Run Command or reset the password on the
# Azure VM resource - Arc Run Command and Bastion remain), then schedules the restart that proves the
# disguise survives a reboot. The restart is delayed 90 seconds so this script can report back first.
# The guests are saved and resumed (AutomaticStopAction = Save), not rebooted.
$ErrorActionPreference = 'Stop'
$vms = Get-VM
"guests: " + (($vms | ForEach-Object { "{0} {1}/stop={2}/start={3}" -f $_.Name, $_.State, $_.AutomaticStopAction, $_.AutomaticStartAction }) -join ' | ')
$bad = @($vms | Where-Object { $_.AutomaticStopAction -ne 'Save' -or $_.AutomaticStartAction -ne 'Start' })
if ($bad.Count) { throw ("Guests not set to save and restart with the host: " + (($bad | ForEach-Object Name) -join ', ') + " - nothing changed") }
if ([Environment]::GetEnvironmentVariable('MSFT_ARC_TEST', 'Machine') -ne 'true') { throw 'MSFT_ARC_TEST is not set - nothing changed' }
if (-not (Get-NetFirewallRule -Name BlockAzureIMDS -ErrorAction SilentlyContinue)) { throw 'Metadata block missing - nothing changed' }
Set-Service -Name WindowsAzureGuestAgent -StartupType Disabled
Stop-Service -Name WindowsAzureGuestAgent -Force
$ga = Get-Service WindowsAzureGuestAgent
"WindowsAzureGuestAgent now {0}/{1}" -f $ga.Status, $ga.StartType
$rd = Get-Service RdAgent -ErrorAction SilentlyContinue
"RdAgent service: " + $(if ($rd) { "{0}/{1}" -f $rd.Status, $rd.StartType } else { 'not present' })
& shutdown.exe /r /t 90 /d p:4:1 /c "Host disguise: restart to confirm" 2>&1 | Out-Null
"restart scheduled at {0:HH:mm:ss} (+90 s), shutdown exit {1}" -f (Get-Date).AddSeconds(90), $LASTEXITCODE
