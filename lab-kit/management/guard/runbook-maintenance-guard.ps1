param(
    [object]$WebhookData,
    [ValidateSet('Pre', 'Post')][string]$Phase,
    [bool]$DemoOnly = $false
)

# Cloud: PS7.4 / Az12.3. Local tests: PS5.1, no Az modules required.
# Real Pre requires these two Arc tags (ordinal, case-insensitive values):
# HvUmApproval=Approved
# HvUmTarget=SQL2019-GUEST
# Guest policy must disable automatic installation or explicitly be notify-only.
# Demo databases match demo; all user database states are reported.
# Checkpoints are non-secret, append-only variables, one per delivery. The earliest
# server-created healthy Pre is the baseline; later deliveries cannot overwrite it.
# No runbook performs installation, SQL mutation, service changes, or reboots.
$ErrorActionPreference = 'Stop'

function Get-GuardScope {
    $subscription = '<SUBSCRIPTION_ID>'
    $root = "/subscriptions/$subscription/resourceGroups/rg-hyperv-arc-monitor-demo/providers"
    [pscustomobject]@{
        Subscription = $subscription
        Machine = "$root/Microsoft.HybridCompute/machines/SQL2019-GUEST"
        Configuration = "$root/Microsoft.Maintenance/maintenanceConfigurations/mc-hv-sql2019-definitions-gated"
        Account = "$root/Microsoft.Automation/automationAccounts/aa-hv-sql-maintenance"
        Region = 'southeastasia'
    }
}

function Get-GuardUtcNow { [datetimeoffset]::UtcNow }

function Get-GuardProperty {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) { return ,$Object[$Name] }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return ,$property.Value }
    return $null
}

function ConvertTo-GuardDate {
    param($Value, [string]$Field)
    # PS7 ConvertFrom-Json may materialize ISO dates as DateTime; PS5 leaves strings.
    # Unspecified dates are rejected because a timezone is mandatory.
    if ($Value -is [datetimeoffset]) { return $Value.ToUniversalTime() }
    if ($Value -is [datetime]) {
        if ($Value.Kind -eq [DateTimeKind]::Unspecified) { throw "Malformed $Field timestamp without timezone." }
        return ([datetimeoffset]$Value).ToUniversalTime()
    }
    $parsed = [datetimeoffset]::MinValue
    if ($Value -isnot [string] -or $Value -notmatch '\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})\z' -or
        -not [datetimeoffset]::TryParse($Value, [cultureinfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::None, [ref]$parsed)) {
        throw "Malformed $Field timestamp."
    }
    return $parsed.ToUniversalTime()
}

function Get-GuardEvents {
    param($WebhookData, [string]$RequestedPhase, [bool]$DemoOnly)
    if ($DemoOnly) {
        if ($null -ne $WebhookData) { throw 'DemoOnly cannot consume webhook events.' }
        if ($RequestedPhase -notin @('Pre', 'Post')) { throw 'DemoOnly requires an explicit Pre or Post phase.' }
        return [pscustomobject]@{ Phase = $RequestedPhase; RunId = $null; Deadline = $null; DemoOnly = $true }
    }
    if ($null -eq $WebhookData) { throw 'Manual checks require DemoOnly=true and an explicit phase.' }
    # Automation can bind WebhookData as a serialized envelope in PS7 runtimes.
    if ($WebhookData -is [string]) {
        if ($WebhookData.Length -gt 196608) { throw 'Oversized serialized webhook envelope.' }
        try { $WebhookData = $WebhookData | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'Malformed serialized webhook envelope; payload is not logged.' }
    }
    $body = Get-GuardProperty $WebhookData 'RequestBody'
    if ($body -isnot [string] -or $body.Length -eq 0 -or $body.Length -gt 131072) {
        throw 'Malformed or oversized webhook envelope.'
    }
    try { $parsedEvents = $body | ConvertFrom-Json -ErrorAction Stop; $events = @($parsedEvents) }
    catch { throw 'Malformed webhook JSON; payload is not logged.' }
    if ($events.Count -eq 0 -or $events.Count -gt 16) { throw 'Invalid event batch size.' }
    $scope = Get-GuardScope
    foreach ($event in $events) {
        $type = Get-GuardProperty $event 'eventType'
        $topic = Get-GuardProperty $event 'topic'
        $data = Get-GuardProperty $event 'data'
        $config = Get-GuardProperty $data 'MaintenanceConfigurationId'
        $known = $type -in @('Microsoft.Maintenance.PreMaintenanceEvent', 'Microsoft.Maintenance.PostMaintenanceEvent')
        if (-not $known) {
            if ($topic -eq $scope.Configuration -or $config -eq $scope.Configuration) {
                throw 'Unknown event type on the protected maintenance configuration.'
            }
            if ($topic -isnot [string] -or [string]::IsNullOrWhiteSpace($topic) -or $type -isnot [string]) {
                throw 'Malformed Event Grid event.'
            }
            Write-Warning 'Ignored unrelated Event Grid event; no authentication or writes performed for it.'
            continue
        }
        if ($topic -isnot [string] -or $config -isnot [string] -or
            [string]::IsNullOrWhiteSpace($topic) -or [string]::IsNullOrWhiteSpace($config)) {
            throw 'Recognized maintenance event is missing topic or configuration.'
        }
        if ($topic -ne $scope.Configuration -and $config -ne $scope.Configuration -and $topic -eq $config) {
            if ($topic -notmatch '\A/subscriptions/[A-Za-z0-9-]+/resourceGroups/[A-Za-z0-9_.()-]+/providers/Microsoft\.Maintenance/maintenanceConfigurations/[A-Za-z0-9_-]+\z') {
                throw 'Recognized unrelated maintenance event has a malformed resource path.'
            }
            Write-Warning 'Ignored maintenance event for an unrelated configuration; no writes performed for it.'
            continue
        }
        if ($topic -ne $scope.Configuration -or $config -ne $scope.Configuration) {
            throw 'Maintenance event topic/configuration mismatch.'
        }
        $id = Get-GuardProperty $event 'id'
        if ($id -isnot [string] -or [string]::IsNullOrWhiteSpace($id) -or $id.Length -gt 1024) {
            throw 'Recognized maintenance event has an invalid event ID.'
        }
        $subscriptions = Get-GuardProperty $data 'ResourceSubscriptionIds'
        if ($subscriptions -isnot [System.Array] -or $subscriptions.Count -ne 1 -or
            $subscriptions[0] -isnot [string] -or $subscriptions[0] -ne $scope.Subscription) {
            throw 'Maintenance event subscription array is outside the authorized scope.'
        }
        $runId = Get-GuardProperty $data 'CorrelationId'
        $pattern = '\A' + [regex]::Escape($scope.Configuration) + '/providers/microsoft\.maintenance/applyupdates/[A-Za-z0-9][A-Za-z0-9_-]{0,127}\z'
        if ($runId -isnot [string] -or $runId -notmatch $pattern) {
            throw 'Unsafe maintenance correlation path.'
        }
        $actualPhase = if ($type -eq 'Microsoft.Maintenance.PreMaintenanceEvent') { 'Pre' } else { 'Post' }
        if ($RequestedPhase -and $RequestedPhase -ne $actualPhase) { throw 'Explicit phase conflicts with the scoped event type.' }
        $start = ConvertTo-GuardDate (Get-GuardProperty $data 'StartDateTime') 'StartDateTime'
        $end = ConvertTo-GuardDate (Get-GuardProperty $data 'EndDateTime') 'EndDateTime'
        if ($end -le $start -or ($end - $start).TotalHours -gt 24) { throw 'Maintenance event dates are outside bounded limits.' }
        $cutoff = $null
        if ($actualPhase -eq 'Pre') {
            $cutoff = ConvertTo-GuardDate (Get-GuardProperty $data 'CancellationCutOffDateTime') 'CancellationCutOffDateTime'
            if ($cutoff -gt $start -or $cutoff -lt $start.AddHours(-2)) { throw 'Maintenance cancellation cutoff is outside bounded limits.' }
        }
        $now = Get-GuardUtcNow
        if ($actualPhase -eq 'Pre' -and ($now -lt $start.AddHours(-2) -or $now -gt $end.AddHours(1))) {
            throw 'Pre event is outside the bounded delivery window.'
        }
        if ($actualPhase -eq 'Post' -and ($now -lt $start -or $now -gt $end.AddHours(48))) {
            throw 'Post event is outside the bounded delivery window.'
        }
        $deadline = $null
        if ($actualPhase -eq 'Pre') {
            $deadline = $start.AddMinutes(-10)
            if ($cutoff -lt $deadline) { $deadline = $cutoff }
        }
        [pscustomobject]@{
            Phase = $actualPhase; RunId = $runId; Deadline = $deadline
            Start = $start; End = $end; DemoOnly = $false
        }
    }
}

function Connect-GuardIdentity {
    $scope = Get-GuardScope
    try {
        Disable-AzContextAutosave -Scope Process -ErrorAction Stop | Out-Null
        $login = Connect-AzAccount -Identity -SkipContextPopulation -ErrorAction Stop
        $script:GuardContext = Set-AzContext -Subscription $scope.Subscription -DefaultProfile $login.Context -ErrorAction Stop
        if ($script:GuardContext.Subscription.Id -ne $scope.Subscription) { throw 'Wrong subscription context.' }
    }
    catch { throw 'Managed-identity authentication or scoped context failed.' }
}

function Invoke-GuardRest {
    param([string]$Path, [string]$Method, [string]$Payload, [string]$Purpose, [switch]$AllowNotFound)
    try {
        $args = @{ Path = $Path; Method = $Method; DefaultProfile = $script:GuardContext; ErrorAction = 'Stop' }
        if ($PSBoundParameters.ContainsKey('Payload')) { $args.Payload = $Payload }
        $response = Invoke-AzRestMethod @args
        if ($null -eq $response -or $null -eq $response.StatusCode) { throw 'Missing HTTP response.' }
        return $response
    }
    catch {
        $status = Get-GuardProperty $_.Exception 'StatusCode'
        if ($null -eq $status) { $status = Get-GuardProperty (Get-GuardProperty $_.Exception 'Response') 'StatusCode' }
        if ($AllowNotFound -and $Method -eq 'GET' -and $null -ne $status -and [int]$status -eq 404) {
            return [pscustomobject]@{ StatusCode = 404; Content = '' }
        }
        throw "ARM $Method failed for $Purpose; service response details are not logged."
    }
}

function ConvertFrom-GuardResponse {
    param($Response, [string]$Purpose)
    try { $value = $Response.Content | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "Invalid JSON response for $Purpose." }
    if ($null -eq $value) { throw "Empty JSON response for $Purpose." }
    return $value
}

function Assert-GuardPolicy {
    param([bool]$RequireApproval)
    $scope = Get-GuardScope
    $response = Invoke-GuardRest -Path "$($scope.Machine)?api-version=2025-01-13" -Method GET -Purpose 'Arc machine'
    if ($response.StatusCode -ne 200) { throw 'Could not read the authorized Arc machine.' }
    $machine = ConvertFrom-GuardResponse $response 'Arc machine'
    if ($machine.id -ne $scope.Machine -or $machine.location -ne $scope.Region -or $machine.properties.status -ne 'Connected') {
        throw 'Arc machine identity, connection, or region check failed.'
    }
    if ($RequireApproval -and ((Get-GuardProperty $machine.tags 'HvUmApproval') -ne 'Approved' -or
        (Get-GuardProperty $machine.tags 'HvUmTarget') -ne 'SQL2019-GUEST')) {
        throw 'Arc guest approval/target tags do not authorize this maintenance.'
    }
    $response = Invoke-GuardRest -Path "$($scope.Configuration)?api-version=2023-04-01" -Method GET -Purpose 'maintenance policy'
    if ($response.StatusCode -ne 200) { throw 'Could not read the authorized maintenance configuration.' }
    $config = ConvertFrom-GuardResponse $response 'maintenance policy'
    $patches = $config.properties.installPatches
    $windows = Get-GuardProperty $patches 'windowsParameters'
    $includeValue = Get-GuardProperty $windows 'kbNumbersToInclude'
    $includes = @($includeValue)
    $classificationValue = Get-GuardProperty $windows 'classificationsToInclude'
    $classifications = @($classificationValue | Where-Object { $null -ne $_ })
    $excludeValue = Get-GuardProperty $windows 'kbNumbersToExclude'
    $excludes = @($excludeValue | Where-Object { $null -ne $_ })
    $excludeReboot = Get-GuardProperty $windows 'excludeKbsRequiringReboot'
    if ($config.id -ne $scope.Configuration -or $config.location -ne $scope.Region -or
        $config.properties.maintenanceScope -ne 'InGuestPatch' -or
        $includeValue -isnot [System.Array] -or $includes.Count -ne 1 -or $includes[0] -notmatch '\A(?:KB)?2267602\z' -or $classifications.Count -ne 0 -or
        @($excludes | Where-Object { $_ -match '\A(?:KB)?2267602\z' }).Count -gt 0 -or
        $excludeReboot -isnot [bool] -or -not $excludeReboot -or
        (Get-GuardProperty $patches 'rebootSetting') -notin @('Never', 'NeverReboot') -or
        $null -ne (Get-GuardProperty $patches 'linuxParameters')) {
        throw 'Maintenance policy is not exclusively KB2267602 with reboot prohibited.'
    }
    return [pscustomobject]@{ ArcStatus = 'Connected'; Policy = 'KB2267602-only/no-reboot' }
}

function Get-GuardGuestScript {
    @'
$ErrorActionPreference = 'Stop'
$errors = New-Object 'System.Collections.Generic.List[string]'
$health = [ordered]@{ Host=$false; Services=$false; SqlProcess=$false; SqlQuery=$false; StartupEvidence=$false; Databases=$false; PendingReboot=$false; WindowsUpdatePolicy=$false; Headroom=$false }
$result = [ordered]@{ SchemaVersion=2; ObservedUtc=[datetime]::UtcNow.ToString('o'); Machine=$env:COMPUTERNAME; Health=$health; Errors=$errors; BootUtc=$null; WmiBootUtc=$null; StartupEvidence=$null; SqlProcessStartUtc=$null; SqlServerStartUtc=$null; Services=@(); Databases=@(); Disks=@(); MaxMemoryMB=$null; MemoryFreeMB=$null; PendingReboot=$null; WindowsUpdatePolicy=$null; HeadroomMeaning='Positive free capacity only, not a patch-capacity guarantee' }
$health.Host = $env:COMPUTERNAME -eq 'SQL2019-GUEST'
if (-not $health.Host) { $errors.Add('WrongHost') }
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $result.WmiBootUtc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
    $result.MemoryFreeMB = [math]::Round($os.FreePhysicalMemory / 1024, 2)
    # WMI's boot value can shift after a saved guest's clock is corrected.
    $bootEvent = Get-WinEvent -FilterHashtable @{
        LogName='System'; ProviderName='Microsoft-Windows-Kernel-General'; Id=12
    } -MaxEvents 1 -ErrorAction Stop
    [xml]$bootXml = $bootEvent.ToXml()
    $startFields = @($bootXml.Event.EventData.Data | Where-Object Name -eq 'StartTime')
    if ($startFields.Count -ne 1 -or $bootEvent.RecordId -le 0 -or
        $bootEvent.ProviderName -ne 'Microsoft-Windows-Kernel-General' -or $bootEvent.Id -ne 12) {
        throw 'Original startup event evidence is incomplete'
    }
    $bootStart = [datetimeoffset]::Parse([string]$startFields[0].'#text', [cultureinfo]::InvariantCulture)
    $bootWritten = [datetimeoffset]::Parse([string]$bootXml.Event.System.TimeCreated.SystemTime, [cultureinfo]::InvariantCulture)
    $result.BootUtc = $bootStart.ToUniversalTime().ToString('o')
    $result.StartupEvidence = [ordered]@{
        Source='System/Microsoft-Windows-Kernel-General/12'; BootRecordId=[long]$bootEvent.RecordId
        BootEventWrittenUtc=$bootWritten.ToUniversalTime().ToString('o')
        BootStartUtc=$result.BootUtc
        KernelTicksBefore=$null; KernelTicksAfter=$null; SqlCurrentTicks=$null; SqlStartTicks=$null
    }
    Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class HvGuardClock {
    [DllImport("kernel32.dll")]
    public static extern ulong GetTickCount64();
}
"@
} catch { $errors.Add('BootOrMemoryReadFailed') }
try {
    $services = @(Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER' OR Name='SQLSERVERAGENT'" -ErrorAction Stop)
    $result.Services = @($services | Select-Object Name, State, StartMode, ProcessId)
    $health.Services = $services.Count -eq 2 -and @($services | Where-Object { $_.State -ne 'Running' -or $_.StartMode -ne 'Auto' }).Count -eq 0
    $engine = @($services | Where-Object { $_.Name -eq 'MSSQLSERVER' })
    if ($engine.Count -ne 1 -or $engine[0].ProcessId -le 0) { throw 'Missing engine process' }
    $process = Get-Process -Id $engine[0].ProcessId -ErrorAction Stop
    $result.SqlProcessStartUtc = $process.StartTime.ToUniversalTime().ToString('o')
    $health.SqlProcess = $process.ProcessName -eq 'sqlservr'
} catch { $errors.Add('SqlServiceOrProcessReadFailed') }
if (-not $health.Services) { $errors.Add('ServicesNotRunningAutomatic') }
try {
    $session = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
    $rename = (Get-ItemProperty -LiteralPath $session -ErrorAction Stop).PSObject.Properties['PendingFileRenameOperations']
    $pendingRename = $null -ne $rename -and @($rename.Value | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count -gt 0
    $blockingRename = $pendingRename
    $renameAdvisories = New-Object 'System.Collections.Generic.List[object]'
    if ($pendingRename) {
        $pairs = @($rename.Value)
        if ($pairs.Count % 2 -ne 0) { throw 'Malformed pending rename pairs' }
        $blockingRename = $false
        for ($i=0; $i -lt $pairs.Count; $i+=2) {
            $source = [string]$pairs[$i]
            $destination = [string]$pairs[$i+1]
            $emptyEdgeCleanup = $false
            if ($destination -eq '' -and $source -match '\A\\\?\?\\C:\\Program Files \(x86\)\\Microsoft\\EdgeUpdate\\\d+\.\d+\.\d+\.\d+\z') {
                $nativePath = $source.Substring(4)
                if (-not (Test-Path -LiteralPath $nativePath -ErrorAction Stop)) {
                    $emptyEdgeCleanup = $true
                } else {
                    $item = Get-Item -LiteralPath $nativePath -ErrorAction Stop
                    $emptyEdgeCleanup = $item.PSIsContainer -and
                        -not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
                        [IO.Directory]::GetFileSystemEntries($nativePath).Length -eq 0
                }
            }
            if ($emptyEdgeCleanup) {
                $renameAdvisories.Add([pscustomobject]@{
                    Source=$source; Destination=$destination
                    Classification='EmptyEdgeUpdaterDirectoryDeletion'
                    EmptyOrAbsent=$true; ReparsePoint=$false; RegistryChanged=$false
                })
            } else { $blockingRename = $true }
        }
    }
    $cbs = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending' -ErrorAction Stop
    $wu = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired' -ErrorAction Stop
    $active = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName' -ErrorAction Stop
    $configured = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName' -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($active.ComputerName) -or [string]::IsNullOrWhiteSpace($configured.ComputerName)) { throw 'Computer-name evidence absent' }
    $renameComputer = $active.ComputerName -ne $configured.ComputerName
    $result.PendingReboot = [ordered]@{
        ComponentServicing=$cbs; WindowsUpdate=$wu; FileRename=$pendingRename
        BlockingFileRename=$blockingRename; FileRenameAdvisories=@($renameAdvisories.ToArray())
        ComputerRename=$renameComputer
    }
    $health.PendingReboot = -not ($cbs -or $wu -or $blockingRename -or $renameComputer)
    if (-not $health.PendingReboot) { $errors.Add('PendingRebootDetected') }
} catch { $errors.Add('PendingRebootReadFailed') }
try {
    $path = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
    if (-not (Test-Path -LiteralPath $path -ErrorAction Stop)) { throw 'Update policy absent' }
    $policy = Get-ItemProperty -LiteralPath $path -ErrorAction Stop
    $disabled = $policy.PSObject.Properties['NoAutoUpdate']
    $options = $policy.PSObject.Properties['AUOptions']
    $noReboot = $policy.PSObject.Properties['NoAutoRebootWithLoggedOnUsers']
    $result.WindowsUpdatePolicy = [ordered]@{ NoAutoUpdate=$(if ($null -ne $disabled) { $disabled.Value } else { $null }); AUOptions=$(if ($null -ne $options) { $options.Value } else { $null }); NoAutoRebootWithLoggedOnUsers=$(if ($null -ne $noReboot) { $noReboot.Value } else { $null }) }
    $health.WindowsUpdatePolicy = ($null -ne $disabled -and $disabled.Value -eq 1) -or
        ($null -ne $options -and $options.Value -eq 2 -and ($null -eq $disabled -or $disabled.Value -eq 0))
    if (-not $health.WindowsUpdatePolicy) { $errors.Add('AutomaticWindowsUpdateInstallationNotPrevented') }
} catch { $errors.Add('WindowsUpdatePolicyReadFailed') }
try {
    $disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop)
    $result.Disks = @($disks | ForEach-Object { [pscustomobject]@{ Drive=$_.DeviceID; FreeMB=[math]::Round($_.FreeSpace/1MB, 2); SizeMB=[math]::Round($_.Size/1MB, 2) } })
    $health.Headroom = $disks.Count -gt 0 -and $null -ne $result.MemoryFreeMB -and $result.MemoryFreeMB -gt 0 -and
        @($disks | Where-Object { $null -eq $_.FreeSpace -or $_.FreeSpace -le 0 -or $_.Size -le 0 }).Count -eq 0
    if (-not $health.Headroom) { $errors.Add('NoDiskOrMemoryHeadroom') }
} catch { $errors.Add('DiskHeadroomReadFailed') }
$connection = $null
$command = $null
$reader = $null
try {
    $connection = New-Object System.Data.SqlClient.SqlConnection
    $connection.ConnectionString = 'Server=localhost;Integrated Security=true;Connection Timeout=5;Application Name=HvMaintenanceReadOnlyGuard'
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandTimeout = 15
    $command.CommandText = 'SELECT 1'
    if ([int]$command.ExecuteScalar() -ne 1) { throw 'Connectivity probe failed' }
    $result.StartupEvidence.KernelTicksBefore = [long][HvGuardClock]::GetTickCount64()
    $command.CommandText = 'SELECT sqlserver_start_time,sqlserver_start_time_ms_ticks,ms_ticks FROM sys.dm_os_sys_info'
    $reader = $command.ExecuteReader()
    if (-not $reader.Read()) { throw 'SQL startup evidence returned no row' }
    $sqlStart = [datetime]$reader['sqlserver_start_time']
    $result.StartupEvidence.SqlStartTicks = [long]$reader['sqlserver_start_time_ms_ticks']
    $result.StartupEvidence.SqlCurrentTicks = [long]$reader['ms_ticks']
    $reader.Dispose(); $reader = $null
    $result.StartupEvidence.KernelTicksAfter = [long][HvGuardClock]::GetTickCount64()
    $result.SqlServerStartUtc = [datetime]::SpecifyKind($sqlStart, [DateTimeKind]::Local).ToUniversalTime().ToString('o')
    $ticks = $result.StartupEvidence
    $health.StartupEvidence = $ticks.SqlStartTicks -ge 0 -and
        $ticks.KernelTicksBefore -ge 0 -and $ticks.KernelTicksAfter -ge $ticks.KernelTicksBefore -and
        $ticks.SqlCurrentTicks -ge $ticks.SqlStartTicks -and
        $ticks.SqlCurrentTicks -ge $ticks.KernelTicksBefore-1000 -and
        $ticks.SqlCurrentTicks -le $ticks.KernelTicksAfter+1000
    if (-not $health.StartupEvidence) { $errors.Add('MonotonicStartupEvidenceInconsistent') }
    $command.CommandText = "SELECT CAST(value_in_use AS bigint) FROM sys.configurations WHERE name = 'max server memory (MB)'"
    $result.MaxMemoryMB = [long]$command.ExecuteScalar()
    if ($result.MaxMemoryMB -le 0) { throw 'Invalid memory configuration' }
    $command.CommandText = 'SELECT name, state_desc FROM sys.databases WHERE database_id > 4 ORDER BY name'
    $reader = $command.ExecuteReader()
    $databases = New-Object 'System.Collections.Generic.List[object]'
    while ($reader.Read()) {
        $name = [string]$reader['name']
        $databases.Add([pscustomobject]@{ Name=$name; State=[string]$reader['state_desc']; IsDemo=($name -match 'demo') })
    }
    $reader.Dispose(); $reader = $null
    $result.Databases = @($databases.ToArray())
    $demo = @($result.Databases | Where-Object { $_.IsDemo })
    $health.Databases = $demo.Count -gt 0 -and @($demo | Where-Object { $_.State -ne 'ONLINE' }).Count -eq 0
    if (-not $health.Databases) { $errors.Add('DemoDatabasesMissingOrNotOnline') }
    $health.SqlQuery = $true
} catch { $errors.Add('ReadOnlySqlProbeFailed') }
finally {
    try {
        if ($null -ne $reader) { $reader.Dispose() }
        if ($null -ne $command) { $command.Dispose() }
        if ($null -ne $connection) { $connection.Dispose() }
    } catch { $health.SqlQuery = $false; $errors.Add('SqlProbeCleanupFailed') }
}
$result.Healthy = @($health.Values | Where-Object { $_ -ne $true }).Count -eq 0 -and $errors.Count -eq 0 -and $null -ne $result.BootUtc
$result.Errors = @($errors.ToArray())
$result | ConvertTo-Json -Depth 8 -Compress
'@
}

function Assert-GuardGuest {
    param($Guest)
    if ($null -eq $Guest -or $Guest.SchemaVersion -ne 2 -or $Guest.Machine -ne 'SQL2019-GUEST' -or
        $Guest.Healthy -isnot [bool] -or -not $Guest.Healthy) { throw 'Guest health evidence is missing or unhealthy.' }
    foreach ($name in @('Host', 'Services', 'SqlProcess', 'SqlQuery', 'StartupEvidence', 'Databases', 'PendingReboot', 'WindowsUpdatePolicy', 'Headroom')) {
        $value = Get-GuardProperty $Guest.Health $name
        if ($value -isnot [bool] -or -not $value) { throw "Guest $name check failed." }
    }
    foreach ($name in @('ObservedUtc', 'BootUtc', 'WmiBootUtc', 'SqlProcessStartUtc', 'SqlServerStartUtc')) {
        $null = ConvertTo-GuardDate (Get-GuardProperty $Guest $name) $name
    }
    $observed = ConvertTo-GuardDate $Guest.ObservedUtc 'ObservedUtc'
    $boot = ConvertTo-GuardDate $Guest.BootUtc 'BootUtc'
    if ($boot -gt $observed -or @($Guest.Errors).Count -ne 0) { throw 'Guest boot/error evidence is inconsistent.' }
    foreach ($name in @('SqlProcessStartUtc', 'SqlServerStartUtc')) {
        $started = ConvertTo-GuardDate (Get-GuardProperty $Guest $name) $name
        if ($started -gt $observed) { throw 'Guest SQL start-time evidence is inconsistent.' }
    }
    Assert-GuardStartupEvidence $Guest
    $services = @($Guest.Services)
    if ($services.Count -ne 2) { throw 'Incomplete SQL service evidence.' }
    foreach ($name in @('MSSQLSERVER', 'SQLSERVERAGENT')) {
        $service = @($services | Where-Object { $_.Name -eq $name })
        if ($service.Count -ne 1 -or $service[0].State -ne 'Running' -or $service[0].StartMode -ne 'Auto') {
            throw 'SQL service evidence is not Running/Auto.'
        }
        if ($name -eq 'MSSQLSERVER' -and
            (($service[0].ProcessId -isnot [int] -and $service[0].ProcessId -isnot [long]) -or $service[0].ProcessId -le 0)) {
            throw 'SQL process identity evidence is missing or invalid.'
        }
    }
    foreach ($name in @('ComponentServicing', 'WindowsUpdate', 'BlockingFileRename', 'ComputerRename')) {
        $value = Get-GuardProperty $Guest.PendingReboot $name
        if ($value -isnot [bool] -or $value) { throw 'Guest pending-reboot evidence is incomplete or unsafe.' }
    }
    if ($Guest.PendingReboot.FileRename -isnot [bool]) { throw 'Raw pending-rename evidence is missing.' }
    $advisories = @($Guest.PendingReboot.FileRenameAdvisories)
    if ($Guest.PendingReboot.FileRename -and $advisories.Count -eq 0) { throw 'Pending-rename advisory classification is missing.' }
    foreach ($advisory in $advisories) {
        if ($advisory.Classification -ne 'EmptyEdgeUpdaterDirectoryDeletion' -or
            $advisory.Source -notmatch '\A\\\?\?\\C:\\Program Files \(x86\)\\Microsoft\\EdgeUpdate\\\d+\.\d+\.\d+\.\d+\z' -or
            $advisory.Destination -ne '' -or $advisory.EmptyOrAbsent -ne $true -or
            $advisory.ReparsePoint -ne $false -or $advisory.RegistryChanged -ne $false) {
            throw 'An unapproved pending rename was classified as advisory.'
        }
    }
    $disks = @($Guest.Disks)
    if ($disks.Count -eq 0 -or $null -eq $Guest.MemoryFreeMB -or $Guest.MemoryFreeMB -le 0 -or
        @($disks | Where-Object { $null -eq $_.FreeMB -or $_.FreeMB -le 0 -or $_.SizeMB -le 0 }).Count -ne 0) {
        throw 'Guest disk/memory headroom evidence is missing or exhausted.'
    }
    $demo = @($Guest.Databases | Where-Object { $_.Name -match 'demo' })
    if ($demo.Count -eq 0 -or @($demo | Where-Object { $_.State -ne 'ONLINE' }).Count -gt 0 -or $Guest.MaxMemoryMB -le 0 -or
        -not ($Guest.WindowsUpdatePolicy.NoAutoUpdate -eq 1 -or
            ($Guest.WindowsUpdatePolicy.AUOptions -eq 2 -and $Guest.WindowsUpdatePolicy.NoAutoUpdate -in @($null,0)))) {
        throw 'Guest database, reboot, memory, or update-policy evidence failed.'
    }
}

function Assert-GuardStartupEvidence {
    param($Guest)
    $evidence = $Guest.StartupEvidence
    if ($null -eq $evidence -or $evidence.Source -cne 'System/Microsoft-Windows-Kernel-General/12' -or
        ($evidence.BootRecordId -isnot [int] -and $evidence.BootRecordId -isnot [long]) -or
        $evidence.BootRecordId -le 0) {
        throw 'Original Windows boot-event identity is missing or invalid.'
    }
    $boot = ConvertTo-GuardDate $Guest.BootUtc 'BootUtc'
    $start = ConvertTo-GuardDate $evidence.BootStartUtc 'BootStartUtc'
    $written = ConvertTo-GuardDate $evidence.BootEventWrittenUtc 'BootEventWrittenUtc'
    $observed = ConvertTo-GuardDate $Guest.ObservedUtc 'ObservedUtc'
    if ($boot -ne $start -or $start -gt $observed -or $written -gt $observed) {
        throw 'Original Windows boot-event timestamps are inconsistent.'
    }
    foreach ($name in @('KernelTicksBefore','KernelTicksAfter','SqlCurrentTicks','SqlStartTicks')) {
        $value = Get-GuardProperty $evidence $name
        if (($value -isnot [int] -and $value -isnot [long]) -or $value -lt 0) {
            throw 'Monotonic startup evidence is missing, negative or non-integral.'
        }
    }
    # One second covers independent reads/timer resolution, not wall-clock skew.
    if ($evidence.KernelTicksAfter -lt $evidence.KernelTicksBefore -or
        $evidence.SqlStartTicks -gt $evidence.SqlCurrentTicks -or
        $evidence.SqlCurrentTicks -lt $evidence.KernelTicksBefore-1000 -or
        $evidence.SqlCurrentTicks -gt $evidence.KernelTicksAfter+1000) {
        throw 'Kernel and SQL startup tick evidence is inconsistent.'
    }
}

function Invoke-GuardGuestCheck {
    param([datetimeoffset]$CheckDeadline)
    $scope = Get-GuardScope
    $own = "$($scope.Machine)/runCommands/hv-guard-$([guid]::NewGuid().ToString('N'))"
    $primary = $null
    $guest = $null
    try {
        if ((Get-GuardUtcNow).AddSeconds(5) -ge $CheckDeadline) { throw 'Insufficient time for guest check.' }
        $seconds = [math]::Min(120, [math]::Floor(($CheckDeadline - (Get-GuardUtcNow)).TotalSeconds))
        $payload = @{ location = $scope.Region; properties = @{
            source = @{ script = Get-GuardGuestScript }; timeoutInSeconds = $seconds; asyncExecution = $false
        } } | ConvertTo-Json -Depth 10 -Compress
        $response = Invoke-GuardRest -Path "$own`?api-version=2025-01-13" -Method PUT -Payload $payload -Purpose 'own read-only Run Command'
        if ($response.StatusCode -notin @(200, 201, 202)) { throw 'Own Run Command creation failed.' }
        $complete = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if ((Get-GuardUtcNow) -ge $CheckDeadline) { throw 'Guest check timed out before the cancellation reserve.' }
            $response = Invoke-GuardRest -Path "$own`?api-version=2025-01-13&`$expand=instanceView" -Method GET -Purpose 'own Run Command status' -AllowNotFound
            if ($response.StatusCode -eq 404) {
                Start-Sleep -Seconds 5
                continue
            }
            if ($response.StatusCode -ne 200) { throw 'Own Run Command status could not be read.' }
            $state = ConvertFrom-GuardResponse $response 'own Run Command'
            $view = $state.properties.instanceView
            if ($view.executionState -eq 'Succeeded') {
                if ($null -eq $view.exitCode -or $view.exitCode -ne 0 -or $view.output -isnot [string] -or $view.output.Length -gt 65536) {
                    throw 'Own Run Command returned invalid completion evidence.'
                }
                try { $guest = $view.output | ConvertFrom-Json -ErrorAction Stop }
                catch { throw 'Guest output is not valid health JSON.' }
                Assert-GuardGuest $guest
                $observed = ConvertTo-GuardDate $guest.ObservedUtc 'ObservedUtc'
                if ([math]::Abs(((Get-GuardUtcNow) - $observed).TotalSeconds) -gt 300) { throw 'Guest health evidence is stale.' }
                $complete = $true
                break
            }
            if ($view.executionState -in @('Failed', 'TimedOut', 'Canceled', 'Cancelled')) { throw 'Guest check failed or timed out.' }
            if ((Get-GuardUtcNow).AddSeconds(5) -ge $CheckDeadline) { throw 'Guest check timed out before the cancellation reserve.' }
            Start-Sleep -Seconds 5
        }
        if (-not $complete) { throw 'Guest check did not complete within the bounded poll budget.' }
    }
    catch { $primary = $_.Exception }
    finally {
        try {
            $response = Invoke-GuardRest -Path "$own`?api-version=2025-01-13" -Method DELETE -Purpose 'own Run Command cleanup'
            if ($response.StatusCode -notin @(200, 202, 204, 404)) { throw 'Cleanup returned an unsuccessful HTTP status.' }
        }
        catch {
            Write-Warning 'Own Run Command cleanup failed; no other command was deleted.'
            if ($null -eq $primary) { $primary = New-Object System.InvalidOperationException('Own Run Command cleanup failed.') }
        }
    }
    if ($null -ne $primary) { throw $primary }
    return $guest
}

function Get-GuardRunStatus {
    param([string]$RunId, [switch]$AllowUnsupported)
    $response = Invoke-GuardRest -Path "$RunId`?api-version=2023-09-01-preview" -Method GET -Purpose 'existing maintenance run'
    if ($AllowUnsupported -and $response.StatusCode -eq 405) {
        return [pscustomobject]@{ Source = 'MaintenanceApplyUpdates'; Status = 'Unavailable'; HttpStatus = $response.StatusCode; InstallationResult = 'Not collected' }
    }
    if ($response.StatusCode -ne 200) { throw 'Existing maintenance run could not be verified; no run will be fabricated.' }
    $run = ConvertFrom-GuardResponse $response 'existing maintenance run'
    if ($run.id -ne $RunId -or $run.properties.status -isnot [string] -or [string]::IsNullOrWhiteSpace($run.properties.status)) {
        throw 'Maintenance run identity or status is invalid.'
    }
    return [pscustomobject]@{ Source = 'MaintenanceApplyUpdates'; Status = $run.properties.status; HttpStatus = 200; InstallationResult = 'Not collected: distinct machine installation-result permission is not provisioned' }
}

function Stop-GuardMaintenance {
    param($Event)
    if ($Event.DemoOnly -or $Event.Phase -ne 'Pre') { throw 'Cancellation is permitted only for a real scoped Pre event.' }
    if ((Get-GuardUtcNow) -ge $Event.Deadline) { throw 'Cancellation is too late: conservative cutoff has passed; cancellation was not submitted.' }
    $existing = Get-GuardRunStatus $Event.RunId
    if ($existing.Status -eq 'Cancelled') { return $existing }
    if ($existing.Status -notin @('Pending', 'Scheduled')) { throw 'Maintenance run is not pending; cancellation cannot be safely submitted.' }
    if ((Get-GuardUtcNow) -ge $Event.Deadline) { throw 'Cancellation is too late after verifying the existing run.' }
    # Never submit an empty object or any status other than Cancel: those can start patches.
    $response = Invoke-GuardRest -Path "$($Event.RunId)?api-version=2023-09-01-preview" -Method PUT -Payload '{"properties":{"status":"Cancel"}}' -Purpose 'exact maintenance cancellation'
    if ($response.StatusCode -notin @(200, 201, 202)) { throw 'Maintenance cancellation request failed.' }
    if (-not [string]::IsNullOrWhiteSpace($response.Content)) {
        $run = ConvertFrom-GuardResponse $response 'maintenance cancellation'
        if ($run.id -and $run.id -ne $Event.RunId) { throw 'Cancellation response belongs to a different run.' }
        if ($run.properties.status -eq 'Cancelled') {
            return [pscustomobject]@{ Source = 'MaintenanceApplyUpdates'; Status = 'Cancelled'; HttpStatus = $response.StatusCode }
        }
    }
    for ($attempt = 0; $attempt -lt 18; $attempt++) {
        if ((Get-GuardUtcNow) -ge $Event.Deadline) { throw 'Cancellation was submitted but not confirmed before cutoff.' }
        $status = Get-GuardRunStatus $Event.RunId
        if ($status.Status -eq 'Cancelled') { return $status }
        if ($status.Status -in @('Completed', 'InProgress', 'Failed')) { throw 'Maintenance run did not reach Cancelled.' }
        if ((Get-GuardUtcNow).AddSeconds(5) -ge $Event.Deadline) { break }
        Start-Sleep -Seconds 5
    }
    throw 'Cancellation was submitted but Cancelled could not be confirmed.'
}

function Get-GuardCheckpointPrefix {
    param([string]$RunId)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($RunId.ToLowerInvariant())) }
    finally { $sha.Dispose() }
    return 'hvg-' + ([System.BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant()) + '-'
}

function Read-GuardJournal {
    param([string]$RunId, [datetimeoffset]$ReadDeadline = [datetimeoffset]::MaxValue)
    $scope = Get-GuardScope
    $prefix = Get-GuardCheckpointPrefix $RunId
    $path = "$($scope.Account)/variables?api-version=2023-11-01"
    $base = "$($scope.Account)/variables"
    $records = New-Object 'System.Collections.Generic.List[object]'
    for ($page = 0; $page -lt 20; $page++) {
        if ((Get-GuardUtcNow).AddSeconds(5) -ge $ReadDeadline) { throw 'Checkpoint read exhausted its bounded safety budget.' }
        $response = Invoke-GuardRest -Path $path -Method GET -Purpose 'guard checkpoint index'
        if ((Get-GuardUtcNow) -ge $ReadDeadline) { throw 'Checkpoint read exhausted its bounded safety budget.' }
        if ($response.StatusCode -ne 200) { throw 'Could not read guard checkpoint index.' }
        $index = ConvertFrom-GuardResponse $response 'guard checkpoint index'
        foreach ($variable in @($index.value)) {
            if ($variable.name -isnot [string] -or -not $variable.name.StartsWith($prefix, [StringComparison]::Ordinal)) { continue }
            if ($variable.name -notmatch ('\A' + [regex]::Escape($prefix) + '(pre|post)-\d{19}-[a-f0-9]{32}\z')) { throw 'Invalid guard checkpoint name.' }
            if ((Get-GuardUtcNow).AddSeconds(5) -ge $ReadDeadline) { throw 'Checkpoint read exhausted its bounded safety budget.' }
            $response = Invoke-GuardRest -Path "$base/$($variable.name)?api-version=2023-11-01" -Method GET -Purpose 'run-specific guard checkpoint'
            if ((Get-GuardUtcNow) -ge $ReadDeadline) { throw 'Checkpoint read exhausted its bounded safety budget.' }
            if ($response.StatusCode -ne 200) { throw 'Guard checkpoint could not be read.' }
            $asset = ConvertFrom-GuardResponse $response 'guard checkpoint'
            if ($asset.properties.isEncrypted -ne $false -or $asset.properties.value -isnot [string] -or $asset.properties.value.Length -gt 65536) {
                throw 'Guard checkpoint is not a bounded non-secret record.'
            }
            try { $record = $asset.properties.value | ConvertFrom-Json -ErrorAction Stop }
            catch { throw 'Guard checkpoint has invalid JSON.' }
            if ($record.SchemaVersion -ne 1 -or $record.RunId -ne $RunId -or $record.Phase -notin @('Pre', 'Post') -or
                $record.Decision -notin @('Allow', 'Cancelled', 'CancellationFailed', 'Healthy', 'Failed')) { throw 'Invalid run-specific checkpoint contract.' }
            if (($record.Phase -eq 'Pre' -and $record.Decision -notin @('Allow', 'Cancelled', 'CancellationFailed')) -or
                ($record.Phase -eq 'Post' -and $record.Decision -notin @('Healthy', 'Failed')) -or
                $variable.name -notmatch ('-' + $record.Phase.ToLowerInvariant() + '-\d{19}-[a-f0-9]{32}\z')) {
                throw 'Checkpoint phase and decision are inconsistent.'
            }
            $null = ConvertTo-GuardDate $record.RecordedUtc 'checkpoint RecordedUtc'
            $created = ConvertTo-GuardDate $asset.properties.creationTime 'checkpoint creationTime'
            $record | Add-Member -NotePropertyName JournalCreatedUtc -NotePropertyValue $created.ToString('o') -Force
            $record | Add-Member -NotePropertyName JournalName -NotePropertyValue $variable.name -Force
            $records.Add($record)
            if ($records.Count -gt 1000) { throw 'Run checkpoint limit exceeded.' }
        }
        $next = Get-GuardProperty $index 'nextLink'
        if ([string]::IsNullOrWhiteSpace($next)) { return @($records.ToArray() | Sort-Object JournalCreatedUtc, RecordedUtc, JournalName) }
        $uri = $null
        if (-not [uri]::TryCreate($next, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or
            $uri.Host -ne 'management.azure.com' -or $uri.Port -ne 443 -or $uri.UserInfo -or $uri.Fragment -or
            $uri.AbsolutePath -ne $base -or $uri.Query -notmatch 'api-version=2023-11-01' -or $uri.Query -match '%2f|%5c') {
            throw 'Unsafe checkpoint continuation link.'
        }
        $path = $uri.PathAndQuery
    }
    throw 'Checkpoint index exceeded the bounded page limit.'
}

function Write-GuardJournal {
    param($Event, [string]$Decision, $Guest, [string]$Failure, $PatchResult, [string]$BaselineName)
    if ($Event.DemoOnly) { throw 'DemoOnly cannot write checkpoints.' }
    $scope = Get-GuardScope
    $now = Get-GuardUtcNow
    $name = (Get-GuardCheckpointPrefix $Event.RunId) + $Event.Phase.ToLowerInvariant() + '-' +
        $now.UtcDateTime.Ticks.ToString('D19') + '-' + [guid]::NewGuid().ToString('N')
    $record = [ordered]@{
        SchemaVersion = 1; RunId = $Event.RunId; Phase = $Event.Phase; RecordedUtc = $now.ToString('o')
        Decision = $Decision; Guest = $Guest; Failure = $Failure; PatchResult = $PatchResult; BaselineName = $BaselineName
    }
    $payload = @{ name = $name; properties = @{
        isEncrypted = $false; description = 'Non-secret immutable maintenance guard evidence'
        value = ($record | ConvertTo-Json -Depth 14 -Compress)
    } } | ConvertTo-Json -Depth 16 -Compress
    $response = Invoke-GuardRest -Path "$($scope.Account)/variables/$name`?api-version=2023-11-01" -Method PUT -Payload $payload -Purpose 'append-only guard checkpoint'
    if ($response.StatusCode -notin @(200, 201)) { throw 'Guard checkpoint persistence failed.' }
    # A write is not considered durable until the exact record has been read back.
    $response = Invoke-GuardRest -Path "$($scope.Account)/variables/$name`?api-version=2023-11-01" -Method GET -Purpose 'guard checkpoint verification'
    if ($response.StatusCode -ne 200) { throw 'Guard checkpoint persistence verification failed.' }
    $saved = ConvertFrom-GuardResponse $response 'guard checkpoint verification'
    $expected = $record | ConvertTo-Json -Depth 14 -Compress
    if ($saved.properties.value -cne $expected -or $saved.properties.isEncrypted -ne $false) { throw 'Guard checkpoint read-back mismatch.' }
    return $name
}

function Assert-GuardContinuity {
    param($Baseline, $Guest)
    Assert-GuardGuest $Baseline
    Assert-GuardGuest $Guest
    foreach ($field in @('BootUtc', 'SqlProcessStartUtc', 'SqlServerStartUtc')) {
        $before = ConvertTo-GuardDate (Get-GuardProperty $Baseline $field) $field
        $after = ConvertTo-GuardDate (Get-GuardProperty $Guest $field) $field
        if ($before -ne $after) { throw "Post detected changed $field; uninterrupted availability cannot be claimed." }
    }
    foreach ($field in @('Source','BootRecordId','BootEventWrittenUtc','BootStartUtc','SqlStartTicks')) {
        if ($Baseline.StartupEvidence.$field -ne $Guest.StartupEvidence.$field) {
            throw "Post detected changed startup identity $field; uninterrupted availability cannot be claimed."
        }
    }
    $oldEngine = @($Baseline.Services | Where-Object Name -eq 'MSSQLSERVER')[0]
    $newEngine = @($Guest.Services | Where-Object Name -eq 'MSSQLSERVER')[0]
    if ($oldEngine.ProcessId -le 0 -or $newEngine.ProcessId -ne $oldEngine.ProcessId -or
        $Guest.StartupEvidence.KernelTicksBefore -lt $Baseline.StartupEvidence.KernelTicksAfter -or
        $Guest.StartupEvidence.SqlCurrentTicks -lt $Baseline.StartupEvidence.SqlCurrentTicks) {
        throw 'Post detected changed SQL process identity or regressed kernel/SQL uptime.'
    }
}

function Invoke-GuardEvent {
    param($Event)
    if ($Event.DemoOnly) {
        $policy = Assert-GuardPolicy -RequireApproval $false
        $guest = Invoke-GuardGuestCheck -CheckDeadline (Get-GuardUtcNow).AddSeconds(180)
        return [pscustomobject]@{
            Evidence = 'Independent read-only test ONLY'; DemoOnly = $true; Phase = $Event.Phase
            HandlerHealth = 'Healthy'; Guest = $guest; Policy = $policy
            PatchResult = 'Not checked'; CancellationSubmitted = $false; CheckpointWritten = $false
            Continuity = 'Not established'; PatchInstallRequested = $false
        }
    }
    $journal = @()
    $guest = $null
    $patch = $null
    $baseline = $null
    try {
        $now = Get-GuardUtcNow
        $journalDeadline = $now.AddSeconds(60)
        if ($Event.Phase -eq 'Pre' -and $Event.Deadline -gt $now -and
            $Event.Deadline.AddSeconds(-30) -lt $journalDeadline) {
            $journalDeadline = $Event.Deadline.AddSeconds(-30)
        }
        $journal = @(Read-GuardJournal $Event.RunId -ReadDeadline $journalDeadline)
        $cancelled = @($journal | Where-Object { $_.Phase -eq 'Pre' -and $_.Decision -eq 'Cancelled' })
        if ($Event.Phase -eq 'Pre') {
            if ($cancelled.Count -gt 0) {
                return [pscustomobject]@{ Phase = 'Pre'; RunId = $Event.RunId; HandlerHealth = 'Blocked'; Decision = 'Cancelled'; Duplicate = $true; PatchInstallRequested = $false }
            }
            $patch = Get-GuardRunStatus $Event.RunId
            if ($patch.Status -eq 'Cancelled') {
                $null = Write-GuardJournal $Event 'Cancelled' $null 'Already cancelled' $patch $null
                return [pscustomobject]@{ Phase = 'Pre'; RunId = $Event.RunId; HandlerHealth = 'Blocked'; Decision = 'Cancelled'; Duplicate = $true; PatchInstallRequested = $false }
            }
            $failedCancellation = @($journal | Where-Object { $_.Phase -eq 'Pre' -and $_.Decision -eq 'CancellationFailed' })
            if ($failedCancellation.Count -gt 0) { throw 'A previous Pre delivery has an unresolved cancellation failure; Allow is not a safe fallback.' }
            $allowed = @($journal | Where-Object { $_.Phase -eq 'Pre' -and $_.Decision -eq 'Allow' })
            if ($allowed.Count -gt 0) {
                $policy = Assert-GuardPolicy -RequireApproval $true
                Assert-GuardGuest $allowed[0].Guest
                return [pscustomobject]@{ Phase = 'Pre'; RunId = $Event.RunId; HandlerHealth = 'PreviouslyChecked'; Decision = 'Allow'; Duplicate = $true; Baseline = $allowed[0].JournalName; Policy = $policy; PatchResult = $patch; PatchInstallRequested = $false }
            }
            if ($patch.Status -notin @('Pending', 'Scheduled')) { throw 'Real Pre run is not pending.' }
            $checkDeadline = (Get-GuardUtcNow).AddSeconds(180)
            if ($Event.Deadline.AddSeconds(-90) -lt $checkDeadline) { $checkDeadline = $Event.Deadline.AddSeconds(-90) }
            if ((Get-GuardUtcNow).AddSeconds(30) -ge $checkDeadline) { throw 'Insufficient Pre check budget before the cancellation reserve.' }
            $policy = Assert-GuardPolicy -RequireApproval $true
            $guest = Invoke-GuardGuestCheck -CheckDeadline $checkDeadline
            if ((Get-GuardUtcNow) -ge $checkDeadline) { throw 'Pre completion exceeded its cancellation reserve.' }
            $name = Write-GuardJournal $Event 'Allow' $guest $null $patch $null
            if ((Get-GuardUtcNow) -ge $Event.Deadline.AddSeconds(-30)) { throw 'Pre checkpoint completion exhausted the safety reserve.' }
            return [pscustomobject]@{
                Phase = 'Pre'; RunId = $Event.RunId; HandlerHealth = 'Healthy'; Decision = 'Allow'
                Guest = $guest; Checkpoint = $name; Policy = $policy; PatchResult = $patch
                Continuity = 'Pre snapshot only; during-window monitoring is separate'; PatchInstallRequested = $false
            }
        }
        $patch = Get-GuardRunStatus -RunId $Event.RunId -AllowUnsupported
        if ($cancelled.Count -gt 0) { throw 'Post received for a guard-cancelled run; no successful installation is claimed.' }
        if (@($journal | Where-Object { $_.Phase -eq 'Pre' -and $_.Decision -eq 'CancellationFailed' }).Count -gt 0) {
            throw 'Post has an unresolved Pre cancellation failure; healthy handling cannot be claimed.'
        }
        $allowed = @($journal | Where-Object { $_.Phase -eq 'Pre' -and $_.Decision -eq 'Allow' })
        if ($allowed.Count -eq 0) { throw 'Post baseline is missing; continuity cannot be established.' }
        $baseline = $allowed[0]
        $policy = Assert-GuardPolicy -RequireApproval $false
        $guest = Invoke-GuardGuestCheck -CheckDeadline (Get-GuardUtcNow).AddSeconds(180)
        Assert-GuardContinuity $baseline.Guest $guest
        $name = Write-GuardJournal $Event 'Healthy' $guest $null $patch $baseline.JournalName
        return [pscustomobject]@{
            Phase = 'Post'; RunId = $Event.RunId; HandlerHealth = 'Healthy'; Guest = $guest
            Baseline = $baseline.JournalName; Checkpoint = $name; Policy = $policy; PatchResult = $patch
            Continuity = 'Endpoint start-times unchanged; not proof of during-window connectivity'
            PatchInstallRequested = $false
        }
    }
    catch {
        $primary = $_.Exception.Message
        if ($Event.Phase -eq 'Pre') {
            try {
                if ($null -eq $patch -or $patch.Status -ne 'Cancelled') { $patch = Stop-GuardMaintenance $Event }
            }
            catch {
                $cancelFailure = $_.Exception.Message
                try { $null = Write-GuardJournal $Event 'CancellationFailed' $guest $primary $null $null }
                catch { Write-Warning 'Cancellation failure checkpoint could not be persisted.' }
                throw "Pre guard failed: $primary Cancellation failed: $cancelFailure"
            }
            try { $null = Write-GuardJournal $Event 'Cancelled' $guest $primary $patch $null }
            catch { throw "Pre guard failed: $primary Cancellation confirmed Cancelled, but failure evidence could not be persisted." }
            throw "Pre guard failed: $primary Exact existing maintenance run confirmed Cancelled."
        }
        try {
            $baselineName = if ($null -ne $baseline) { $baseline.JournalName } else { $null }
            $null = Write-GuardJournal $Event 'Failed' $guest $primary $patch $baselineName
        }
        catch { Write-Warning 'Post failure evidence could not be persisted; the primary failure is retained.' }
        throw "Post guard failed: $primary"
    }
}

function Invoke-MaintenanceGuard {
    param($WebhookData, [string]$Phase, [bool]$DemoOnly = $false)
    # Validate the entire batch before authentication or any guest/checkpoint writes.
    $events = @(Get-GuardEvents $WebhookData $Phase $DemoOnly)
    if ($events.Count -eq 0) { return }
    Connect-GuardIdentity
    foreach ($event in $events) {
        Invoke-GuardEvent $event | ConvertTo-Json -Depth 16 -Compress
    }
}

Invoke-MaintenanceGuard -WebhookData $WebhookData -Phase $Phase -DemoOnly $DemoOnly
