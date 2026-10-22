# OFFLINE ONLY. Native PS5.1/PS7 test runner; every Azure/auth/sleep call is mocked.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$runbook = Join-Path $root 'runbook-maintenance-guard.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($runbook, [ref]$tokens, [ref]$parseErrors)
if (@($parseErrors).Count -ne 0) { throw 'Runbook parser validation failed.' }
# Load definitions only, never the runbook entrypoint. Az is neither loaded nor installed.
foreach ($statement in $ast.EndBlock.Statements) {
    if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($statement.Extent.Text))
    }
}
$script:Passed = 0
$script:Failed = 0

function Assert {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$Pattern)
    $message = $null
    try { & $Action | Out-Null } catch { $message = $_.Exception.Message }
    Assert ($null -ne $message) 'Expected failure, but operation returned.'
    Assert ($message -match $Pattern) "Unexpected failure: $message"
    Assert ($message -notmatch 'MOCK_SECRET') 'Underlying service exception was disclosed.'
}

function Test {
    param([string]$Name, [scriptblock]$Case)
    Reset-Mocks
    try {
        & $Case
        $script:Passed++
        Write-Host "PASS $Name"
    }
    catch {
        $script:Failed++
        Write-Host "FAIL $Name : $($_.Exception.Message)"
    }
}

function Reset-Mocks {
    $script:Now = [datetimeoffset]'2027-01-04T11:25:00Z'
    $script:Calls = New-Object 'System.Collections.Generic.List[object]'
    $script:Assets = @{}
    $script:AuthCalls = 0
    $script:RunStatus = 'Pending'
    $script:CancelMode = 'Immediate'
    $script:GuestMode = 'Healthy'
    $script:CleanupFails = $false
    $script:PolicyMode = 'Healthy'
    $script:TagsMissing = $false
    $script:Disconnected = $false
    $script:WrongRegion = $false
    $script:RunMissing = $false
    $script:RunUnsupported = $false
    $script:CheckpointFailOnce = $false
    $script:UnsafeNextLink = $false
    $script:GuestClockSkew = $false
    $script:AuthFails = $false
    $script:IndexDelaySeconds = 0
    $script:GuestStatusNotFoundCount = 0
    $script:GuardContext = $null
}

function Get-GuardUtcNow { return $script:Now }
function Start-Sleep { param([int]$Seconds); $script:Now = $script:Now.AddSeconds($Seconds) }
function Disable-AzContextAutosave { param($Scope, $ErrorAction); $script:AuthCalls++ }
function Connect-AzAccount {
    param([switch]$Identity, [switch]$SkipContextPopulation, $ErrorAction)
    Assert ($Identity -and $SkipContextPopulation) 'Authentication did not use scoped managed identity.'
    if ($script:AuthFails) { throw 'MOCK_SECRET authentication failure' }
    return [pscustomobject]@{ Context = [pscustomobject]@{ Offline = $true } }
}
function Set-AzContext {
    param($Subscription, $DefaultProfile, $ErrorAction)
    Assert ($Subscription -eq (Get-GuardScope).Subscription) 'Wrong subscription selected.'
    return [pscustomobject]@{ Subscription = [pscustomobject]@{ Id = $Subscription } }
}

function New-Response {
    param([int]$Code, $Value)
    $content = if ($null -eq $Value) { '' } else { $Value | ConvertTo-Json -Depth 24 -Compress }
    return [pscustomobject]@{ StatusCode = $Code; Content = $content }
}

function New-Guest {
    $observed = if ($script:GuestClockSkew) { $script:Now.AddMinutes(-20) } else { $script:Now }
    $health = [ordered]@{ Host=$true; Services=$true; SqlProcess=$true; SqlQuery=$true; StartupEvidence=$true; Databases=$true; PendingReboot=$true; WindowsUpdatePolicy=$true; Headroom=$true }
    $uptime=[long](900000000+($script:Now-[datetimeoffset]'2027-01-04T11:25:00Z').TotalMilliseconds)
    $guest = [pscustomobject]@{
        SchemaVersion=2; ObservedUtc=$observed.ToString('o'); Machine='SQL2019-GUEST'; Healthy=$true
        Health=$health; Errors=@(); BootUtc='2026-12-24T03:00:00.0000000Z'
        WmiBootUtc='2026-12-24T03:00:00.0000000Z'
        StartupEvidence=[pscustomobject]@{
            Source='System/Microsoft-Windows-Kernel-General/12';BootRecordId=635
            BootStartUtc='2026-12-24T03:00:00.0000000Z';BootEventWrittenUtc='2026-12-24T03:00:00.1000000Z'
            KernelTicksBefore=$uptime-30;KernelTicksAfter=$uptime
            SqlCurrentTicks=$uptime;SqlStartTicks=120000
        }
        SqlProcessStartUtc='2026-12-24T03:02:00.0000000Z'; SqlServerStartUtc='2026-12-24T03:02:01.0000000Z'
        Services=@([pscustomobject]@{ Name='MSSQLSERVER'; State='Running'; StartMode='Auto';ProcessId=3816 },
            [pscustomobject]@{ Name='SQLSERVERAGENT'; State='Running'; StartMode='Auto';ProcessId=4292 })
        Databases=@([pscustomobject]@{ Name='DemoDb'; State='ONLINE'; IsDemo=$true },
            [pscustomobject]@{ Name='UnrelatedArchive'; State='OFFLINE'; IsDemo=$false })
        Disks=@([pscustomobject]@{ Drive='C:'; FreeMB=20480; SizeMB=81920 })
        MaxMemoryMB=4096; MemoryFreeMB=1024
        PendingReboot=[pscustomobject]@{
            ComponentServicing=$false; WindowsUpdate=$false; FileRename=$false
            BlockingFileRename=$false; FileRenameAdvisories=@(); ComputerRename=$false
        }
        WindowsUpdatePolicy=[pscustomobject]@{ NoAutoUpdate=1; AUOptions=2; NoAutoRebootWithLoggedOnUsers=1 }
    }
    switch ($script:GuestMode) {
        'Unhealthy' { $guest.Healthy=$false; $health.SqlQuery=$false; $guest.Errors=@('ReadOnlySqlProbeFailed') }
        'Restart' { $guest.SqlServerStartUtc='2027-01-04T12:45:00.0000000Z' }
        'Reboot' {
            $guest.BootUtc='2027-01-04T12:45:00.0000000Z'
            $guest.StartupEvidence.BootStartUtc=$guest.BootUtc
            $guest.StartupEvidence.BootEventWrittenUtc=$guest.BootUtc
            $guest.StartupEvidence.BootRecordId=1001
        }
        'ProcessRestart' { $guest.SqlProcessStartUtc='2027-01-04T12:45:00.0000000Z' }
        'UpdatePolicy' { $guest.WindowsUpdatePolicy.NoAutoUpdate=0; $guest.WindowsUpdatePolicy.AUOptions=4 }
        'NotifyOnly' { $guest.WindowsUpdatePolicy.NoAutoUpdate=0; $guest.WindowsUpdatePolicy.AUOptions=2 }
        'ResumeClockCorrection' { $guest.WmiBootUtc='2027-01-04T07:26:55.1358090Z' }
        'MissingStartupEvidence' { $guest.StartupEvidence=$null }
        'PendingReboot' { $guest.PendingReboot.WindowsUpdate=$true }
        'UnsafeRename' { $guest.PendingReboot.FileRename=$true; $guest.PendingReboot.BlockingFileRename=$true }
        'EdgeCleanup' {
            $guest.PendingReboot.FileRename=$true
            $guest.PendingReboot.FileRenameAdvisories=@([pscustomobject]@{
                Source='\??\C:\Program Files (x86)\Microsoft\EdgeUpdate\1.3.275.13'
                Destination=''; Classification='EmptyEdgeUpdaterDirectoryDeletion'
                EmptyOrAbsent=$true; ReparsePoint=$false; RegistryChanged=$false
            })
        }
        'AgentStopped' { $guest.Services[1].State='Stopped' }
        'DemoOffline' { $guest.Databases[0].State='OFFLINE' }
    }
    return $guest
}

function New-Event {
    param([string]$Phase = 'Pre')
    $scope = Get-GuardScope
    $event = [pscustomobject]@{
        id='offline-event-1'; topic=$scope.Configuration
        eventType="Microsoft.Maintenance.$($Phase)MaintenanceEvent"
        data=[pscustomobject]@{
            MaintenanceConfigurationId=$scope.Configuration
            CorrelationId="$($scope.Configuration)/providers/microsoft.maintenance/applyupdates/20270104120000"
            StartDateTime='2027-01-04T12:00:00Z'; EndDateTime='2027-01-04T13:00:00Z'
            CancellationCutOffDateTime='2027-01-04T11:50:00Z'
            ResourceSubscriptionIds=@($scope.Subscription)
        }
    }
    if ($Phase -eq 'Post') { $event.data.PSObject.Properties.Remove('CancellationCutOffDateTime') }
    return $event
}

function Invoke-Event {
    [CmdletBinding()]
    param($Event, [string]$Phase)
    $envelope = [pscustomobject]@{ RequestBody = (ConvertTo-Json -InputObject @($Event) -Depth 12 -Compress) }
    $output = @(Invoke-MaintenanceGuard -WebhookData $envelope -Phase $Phase)
    if ($output.Count -gt 0) { return ($output[-1] | ConvertFrom-Json) }
}

function Get-Calls {
    param([string]$Method, [string]$Pattern)
    return @($script:Calls.ToArray() | Where-Object { $_.Method -eq $Method -and $_.Path -match $Pattern })
}

function Assert-Cancel {
    $cancel = @(Get-Calls PUT '/applyupdates/')
    Assert ($cancel.Count -eq 1) 'Expected exactly one maintenance cancellation PUT.'
    $event = New-Event
    Assert ($cancel[0].Path -ceq "$($event.data.CorrelationId)?api-version=2023-09-01-preview") 'Cancellation path is not the exact occurrence.'
    Assert ($cancel[0].Payload -ceq '{"properties":{"status":"Cancel"}}') 'Cancellation payload was not exactly Cancel.'
    Assert ($cancel[0].At -lt [datetimeoffset]'2027-01-04T11:50:00Z') 'Cancellation was submitted after cutoff.'
}

function Assert-OwnCleanup {
    $created = @(Get-Calls PUT '/runCommands/')
    $deleted = @(Get-Calls DELETE '/runCommands/')
    Assert ($created.Count -eq $deleted.Count) 'Own-command cleanup count differs from create count.'
    for ($i=0; $i -lt $created.Count; $i++) {
        Assert ($deleted[$i].Path -ceq $created[$i].Path) 'A command other than the owned GUID was deleted.'
        Assert ($created[$i].Path -match '/runCommands/hv-guard-[a-f0-9]{32}\?api-version=2025-01-13$') 'Command is not uniquely GUID-scoped.'
    }
}

function Invoke-AzRestMethod {
    param([string]$Path, [string]$Method, [string]$Payload, $DefaultProfile, $ErrorAction)
    $script:Calls.Add([pscustomobject]@{ Path=$Path; Method=$Method; Payload=$Payload; At=$script:Now })
    Assert ($null -ne $DefaultProfile) 'ARM call missing scoped default profile.'
    $scope = Get-GuardScope
    $base = ($Path -split '\?', 2)[0]
    if ($base -eq $scope.Machine -and $Method -eq 'GET') {
        return New-Response 200 @{
            id=$scope.Machine; location=$(if ($script:WrongRegion) { 'eastus' } else { $scope.Region })
            properties=@{ status=$(if ($script:Disconnected) { 'Disconnected' } else { 'Connected' }) }
            tags=$(if ($script:TagsMissing) { @{} } else { @{ HvUmApproval='Approved'; HvUmTarget='SQL2019-GUEST' } })
        }
    }
    if ($base -eq $scope.Configuration -and $Method -eq 'GET') {
        $windows = @{ kbNumbersToInclude=@('KB2267602'); classificationsToInclude=@(); kbNumbersToExclude=@(); excludeKbsRequiringReboot=$true }
        $patches = @{ windowsParameters=$windows; rebootSetting='Never' }
        switch ($script:PolicyMode) {
            'OtherKB' { $windows.kbNumbersToInclude=@('KB2267602','KB9999999') }
            'Classification' { $windows.classificationsToInclude=@('Security') }
            'Reboot' { $patches.rebootSetting='IfRequired' }
            'RebootKB' { $windows.excludeKbsRequiringReboot=$false }
            'Linux' { $patches.linuxParameters=@{ classificationsToInclude=@('Security') } }
            'NeverReboot' { $patches.rebootSetting='NeverReboot' }
            'NumericKB' { $windows.kbNumbersToInclude=@('2267602') }
            'ExcludedApprovedKB' { $windows.kbNumbersToExclude=@('2267602') }
        }
        return New-Response 200 @{ id=$scope.Configuration; location=$scope.Region; properties=@{ maintenanceScope='InGuestPatch'; installPatches=$patches } }
    }
    if ($base -match '/providers/microsoft\.maintenance/applyupdates/') {
        if ($Method -eq 'GET') {
            if ($script:RunMissing) { return New-Response 404 $null }
            if ($script:RunUnsupported) { return New-Response 405 $null }
            return New-Response 200 @{ id=$base; properties=@{ status=$script:RunStatus } }
        }
        if ($Method -eq 'PUT') {
            Assert ($Payload -ceq '{"properties":{"status":"Cancel"}}') 'Unsafe applyUpdates write attempted.'
            switch ($script:CancelMode) {
                'Denied' { return New-Response 403 $null }
                'Transport' { throw 'MOCK_SECRET should never appear in errors' }
                'Accepted' { $script:RunStatus='Cancelled'; return New-Response 202 $null }
                'NeverConfirmed' { return New-Response 202 $null }
                'WrongId' { return New-Response 200 @{ id="$base-extra"; properties=@{ status='Cancelled' } } }
                default { $script:RunStatus='Cancelled'; return New-Response 200 @{ id=$base; properties=@{ status='Cancelled' } } }
            }
        }
    }
    if ($base.StartsWith("$($scope.Machine)/runCommands/")) {
        if ($Method -eq 'PUT') {
            if ($script:GuestMode -eq 'CreateFailure') { return New-Response 500 $null }
            if ($script:GuestMode -eq 'CreateTransport') { throw 'MOCK_SECRET create transport error' }
            $request = $Payload | ConvertFrom-Json
            Assert ($request.properties.timeoutInSeconds -le 120) 'Guest timeout too long.'
            Assert ($request.properties.source.script -match 'SELECT 1') 'Missing SQL availability query.'
            return New-Response 201 @{ properties=@{ provisioningState='Succeeded' } }
        }
        if ($Method -eq 'GET') {
            if ($script:GuestStatusNotFoundCount -gt 0) {
                $script:GuestStatusNotFoundCount--
                return New-Response 404 $null
            }
            if ($script:GuestMode -eq 'StatusFailure') { return New-Response 503 $null }
            Assert ($Path -match '\$expand=instanceView') 'Status read did not request instanceView.'
            $state = switch ($script:GuestMode) { 'Failed' { 'Failed' } 'TimedOut' { 'TimedOut' } 'PollTimeout' { 'Running' } default { 'Succeeded' } }
            $guest = New-Guest
            return New-Response 200 @{ properties=@{ instanceView=@{
                executionState=$state; exitCode=0; output=($guest | ConvertTo-Json -Depth 12 -Compress)
            } } }
        }
        if ($Method -eq 'DELETE') {
            if ($script:CleanupFails) { throw 'MOCK_SECRET cleanup error' }
            return New-Response 204 $null
        }
    }
    $variables = "$($scope.Account)/variables"
    if ($base -eq $variables -and $Method -eq 'GET') {
        $script:Now=$script:Now.AddSeconds($script:IndexDelaySeconds)
        $next = if ($script:UnsafeNextLink) { 'https://attacker.invalid/variables?api-version=2023-11-01' } else { $null }
        return New-Response 200 @{ value=@($script:Assets.Keys | ForEach-Object { @{ name=$_ } }); nextLink=$next }
    }
    if ($base.StartsWith("$variables/")) {
        $name = $base.Substring($variables.Length + 1)
        if ($Method -eq 'PUT') {
            if ($script:CheckpointFailOnce) { $script:CheckpointFailOnce=$false; return New-Response 403 $null }
            Assert (-not $script:Assets.ContainsKey($name)) 'Existing checkpoint was overwritten.'
            Assert ($name.Length -le 128) 'Automation variable name exceeds conservative name limit.'
            $script:Assets[$name] = $Payload | ConvertFrom-Json
            $script:Assets[$name].properties | Add-Member -NotePropertyName creationTime -NotePropertyValue $script:Now.ToString('o') -Force
            return New-Response 201 $script:Assets[$name]
        }
        if ($Method -eq 'GET') {
            if ($script:Assets.ContainsKey($name)) { return New-Response 200 $script:Assets[$name] }
            return New-Response 404 $null
        }
    }
    throw "Unmocked ARM request blocked: $Method $base"
}

Test 'Parser and guest script are PS5.1-compatible, read-only SELECT queries' {
    $guestTokens=$null; $guestErrors=$null
    $guestAst = [System.Management.Automation.Language.Parser]::ParseInput((Get-GuardGuestScript), [ref]$guestTokens, [ref]$guestErrors)
    Assert (@($guestErrors).Count -eq 0) 'Guest script has parser errors.'
    $commands = @($guestAst.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true))
    $allowed = @('Get-CimInstance','Get-Process','Get-WinEvent','Add-Type','Get-Item','Get-ItemProperty','Test-Path','New-Object','Select-Object','Where-Object','ForEach-Object','ConvertTo-Json')
    foreach ($command in $commands) { Assert ($command.GetCommandName() -in $allowed) 'Guest contains an unapproved command.' }
    $queryAssignments = @($guestAst.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$command.CommandText'
    }, $true))
    Assert ($queryAssignments.Count -eq 4) 'Unexpected SQL query count.'
    foreach ($query in $queryAssignments) { Assert ($query.Right.Extent.Text -match '^[''"]SELECT ') 'Non-SELECT SQL found.' }
    Assert ((Get-GuardGuestScript) -match '\$command.CommandTimeout = 15') 'SQL timeout is not bounded.'
}

Test 'Unrelated maintenance is explicitly ignored without auth' {
    $event=New-Event; $event.topic='/subscriptions/other/resourceGroups/other/providers/Microsoft.Maintenance/maintenanceConfigurations/other'
    $event.data.MaintenanceConfigurationId=$event.topic
    $warnings=$null
    $output=Invoke-Event $event -WarningVariable warnings -WarningAction SilentlyContinue
    Assert ($null -eq $output -and $script:AuthCalls -eq 0 -and $script:Calls.Count -eq 0) 'Unrelated event caused operations.'
    Assert (@($warnings).Count -gt 0 -and [string]$warnings[0] -match 'Ignored') 'Ignored event was not logged.'
}
Test 'Malformed JSON fails without exposing payload' {
    Assert-Throws { Invoke-MaintenanceGuard -WebhookData @{ RequestBody='MOCK_SECRET {' } } 'Malformed webhook JSON'
    Assert ($script:AuthCalls -eq 0) 'Malformed JSON authenticated.'
}
Test 'Recognized missing configuration is malformed' {
    $event=New-Event; $event.data.MaintenanceConfigurationId=$null
    Assert-Throws { Invoke-Event $event } 'missing topic or configuration'
}
Test 'Topic mismatch fails without auth' {
    $event=New-Event; $event.topic='/subscriptions/foreign'
    Assert-Throws { Invoke-Event $event } 'topic/configuration mismatch'
    Assert ($script:AuthCalls -eq 0) 'Scope mismatch authenticated.'
}
Test 'Wrong subscription, extra subscription, and scalar subscription are rejected' {
    foreach ($subscriptions in @(@('other'), @((Get-GuardScope).Subscription,'other'), (Get-GuardScope).Subscription)) {
        $event=New-Event; $event.data.ResourceSubscriptionIds=$subscriptions
        Assert-Throws { Invoke-Event $event } 'subscription array'
    }
}
Test 'Unsafe correlation suffixes and outside paths are rejected before auth' {
    foreach ($suffix in @('../another','occurrence/child','20270104120000?x=1','abc#fragment','a%2fb','a\b','.','a%252fb','a:b',"abc`n","abc`r`n")) {
        $event=New-Event; $event.data.CorrelationId=$event.data.CorrelationId -replace '20270104120000$', $suffix
        Assert-Throws { Invoke-Event $event } 'Unsafe maintenance correlation'
    }
    $event=New-Event; $event.data.CorrelationId=$event.data.CorrelationId -replace 'rg-hyperv-arc-monitor-demo','other'
    Assert-Throws { Invoke-Event $event } 'Unsafe maintenance correlation'
    Assert ($script:AuthCalls -eq 0) 'Unsafe path caused authentication.'
}
Test 'Unknown scoped type, phase conflict, and unbounded dates fail' {
    $event=New-Event; $event.eventType='Microsoft.Maintenance.Unknown'
    Assert-Throws { Invoke-Event $event } 'Unknown event type'
    $event=New-Event
    Assert-Throws { Invoke-Event $event -Phase Post } 'phase conflicts'
    $event.data.EndDateTime='2027-01-07T13:00:00Z'
    Assert-Throws { Invoke-Event $event } 'bounded limits'
    $event=New-Event; $event.data.StartDateTime='2027-01-04T12:00:00'
    Assert-Throws { Invoke-Event $event } 'Malformed StartDateTime'
}
Test 'Entire batch validates before operations' {
    $good=New-Event; $bad=New-Event; $bad.data.CorrelationId='/foreign'
    $body=ConvertTo-Json -InputObject @($good,$bad) -Depth 10
    Assert-Throws { Invoke-MaintenanceGuard -WebhookData @{ RequestBody=$body } } 'Unsafe maintenance correlation'
    Assert ($script:Calls.Count -eq 0) 'Partially validated batch performed writes.'
}
Test 'Healthy real Pre records durable non-secret baseline without installing' {
    $result=Invoke-Event (New-Event)
    Assert ($result.Phase -eq 'Pre' -and $result.Decision -eq 'Allow') 'Pre did not allow.'
    Assert ($script:Assets.Count -eq 1) 'Pre evidence not persisted.'
    $records=@(Read-GuardJournal (New-Event).data.CorrelationId)
    Assert ($records.Count -eq 1 -and $records[0].Guest.BootUtc -eq (New-Guest).BootUtc) 'Persisted baseline is wrong.'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Healthy Pre touched applyUpdates.'
    Assert-OwnCleanup
}
Test 'Automatic Post with empty webhook parameters uses the same baseline' {
    $pre=Invoke-Event (New-Event)
    $preValue=$script:Assets[$pre.Checkpoint].properties.value
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Completed'
    $post=Invoke-Event (New-Event Post)
    Assert ($post.Phase -eq 'Post' -and $post.HandlerHealth -eq 'Healthy') 'Post was not auto-derived.'
    Assert ($post.Baseline -eq $pre.Checkpoint) 'Post used another baseline.'
    Assert ($script:Assets[$pre.Checkpoint].properties.value -ceq $preValue) 'Post overwrote baseline.'
    Assert ($post.PatchResult.Status -eq 'Completed' -and $post.Continuity -match 'not proof') 'Patch/health/continuity are conflated.'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Post canceled or installed patches.'
    Assert-OwnCleanup
}
Test 'Duplicate successful Pre is harmless and preserves first times' {
    $pre=Invoke-Event (New-Event)
    $script:GuestMode='Restart'
    $duplicate=Invoke-Event (New-Event)
    Assert ($duplicate.Duplicate -eq $true -and $duplicate.Baseline -eq $pre.Checkpoint) 'Duplicate lost baseline.'
    Assert ($script:Assets.Count -eq 1 -and @(Get-Calls PUT '/runCommands/').Count -eq 1) 'Duplicate created new evidence/command.'
}
Test 'Failed guest Pre cancels exact existing run and records failure' {
    $script:GuestMode='Unhealthy'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel; Assert-OwnCleanup
    $records=@(Read-GuardJournal (New-Event).data.CorrelationId)
    Assert ($records[0].Decision -eq 'Cancelled') 'Cancellation decision missing.'
}
Test 'TimedOut terminal guest and exhausted poll budget cancel' {
    foreach ($mode in @('TimedOut','PollTimeout')) {
        Reset-Mocks; $script:GuestMode=$mode
        Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
        Assert-Cancel; Assert-OwnCleanup
    }
}
Test 'Accepted cancellation is confirmed using GET' {
    $script:GuestMode='Failed'; $script:CancelMode='Accepted'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
    Assert (@(Get-Calls GET '/applyupdates/').Count -ge 3) 'Accepted cancellation was not verified.'
}
Test 'Repeated canceled Pre is harmless even after cutoff' {
    $script:GuestMode='Failed'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    $script:Now=[datetimeoffset]'2027-01-04T12:05:00Z'
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Cancelled' -and $result.HandlerHealth -eq 'Blocked' -and $result.Duplicate) 'Canceled duplicate looked healthy.'
    Assert-Cancel
}
Test 'Conservative deadline takes earlier event cutoff' {
    $event=New-Event; $event.data.CancellationCutOffDateTime='2027-01-04T11:30:00Z'
    $parsed=@(Get-GuardEvents @{ RequestBody=(ConvertTo-Json -InputObject @($event) -Depth 10) } '' $false)[0]
    Assert ($parsed.Deadline -eq [datetimeoffset]'2027-01-04T11:30:00Z') 'Event cutoff was not respected.'
    $event.data.CancellationCutOffDateTime='2027-01-04T11:59:00Z'
    $parsed=@(Get-GuardEvents @{ RequestBody=(ConvertTo-Json -InputObject @($event) -Depth 10) } '' $false)[0]
    Assert ($parsed.Deadline -eq [datetimeoffset]'2027-01-04T11:50:00Z') 'Start-minus-ten-minutes cutoff was not respected.'
}
Test 'Too-late Pre throws, records failure, and never PUTs Cancel' {
    $script:Now=[datetimeoffset]'2027-01-04T11:51:00Z'
    Assert-Throws { Invoke-Event (New-Event) } 'Cancellation is too late'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0 -and @(Get-Calls PUT '/runCommands/').Count -eq 0) 'Late event did unsafe work.'
    $record=@(Read-GuardJournal (New-Event).data.CorrelationId)[0]
    Assert ($record.Decision -eq 'CancellationFailed') 'Late failure not persisted.'
}
Test 'Near-cutoff Pre skips guest check and cancels immediately' {
    $script:Now=[datetimeoffset]'2027-01-04T11:49:15Z'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
    Assert (@(Get-Calls PUT '/runCommands/').Count -eq 0) 'Near-cutoff guest check consumed cancellation reserve.'
}
Test 'Denied, unconfirmed, wrong-run, and transport cancellation fail clearly' {
    foreach ($mode in @('Denied','NeverConfirmed','WrongId','Transport')) {
        Reset-Mocks; $script:GuestMode='Failed'; $script:CancelMode=$mode
        Assert-Throws { Invoke-Event (New-Event) } 'Cancellation failed'
        Assert-Cancel
        $record=@(Read-GuardJournal (New-Event).data.CorrelationId)[0]
        Assert ($record.Decision -eq 'CancellationFailed') 'Cancellation failure was not persisted.'
    }
}
Test 'A nonexistent occurrence is never fabricated' {
    $script:RunMissing=$true
    Assert-Throws { Invoke-Event (New-Event) } 'no run will be fabricated'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Missing occurrence received PUT.'
}
Test 'Missing Post baseline fails and records post failure without cancellation' {
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'
    Assert-Throws { Invoke-Event (New-Event Post) } 'Post baseline is missing'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Post issued cancellation.'
    $record=@(Read-GuardJournal (New-Event).data.CorrelationId)[0]
    Assert ($record.Decision -eq 'Failed' -and $record.Phase -eq 'Post') 'Missing baseline failure not recorded.'
}
Test 'Post SQL start/process/boot changes and connectivity failure all fail' {
    foreach ($mode in @('Restart','ProcessRestart','Reboot','Unhealthy','AgentStopped')) {
        Reset-Mocks; $pre=Invoke-Event (New-Event); $value=$script:Assets[$pre.Checkpoint].properties.value
        $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:GuestMode=$mode
        Assert-Throws { Invoke-Event (New-Event Post) } 'Post guard failed'
        Assert ($script:Assets[$pre.Checkpoint].properties.value -ceq $value) 'Failed Post replaced baseline.'
        Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Failed Post canceled maintenance.'
        Assert-OwnCleanup
    }
}
Test 'DemoOnly Pre and Post are independent, with no cancellation or state writes' {
    foreach ($phase in @('Pre','Post')) {
        Reset-Mocks
        $result=Invoke-MaintenanceGuard -Phase $phase -DemoOnly $true | ConvertFrom-Json
        Assert ($result.DemoOnly -and $result.Evidence -match 'Independent' -and $result.Continuity -eq 'Not established') 'Demo evidence is not clearly independent.'
        Assert (@(Get-Calls PUT '/variables/').Count -eq 0 -and @(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Demo wrote state or cancellation.'
        Assert-OwnCleanup
    }
}
Test 'Failed DemoOnly never cancels or writes checkpoints' {
    $script:GuestMode='Failed'
    Assert-Throws { Invoke-MaintenanceGuard -Phase Pre -DemoOnly $true } 'Guest check failed'
    Assert ($script:Assets.Count -eq 0 -and @(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Failed demo performed writes.'
    Assert-OwnCleanup
}
Test 'Demo requires phase and forbids webhook combination; non-demo manual fails' {
    Assert-Throws { Invoke-MaintenanceGuard -DemoOnly $true } 'explicit Pre or Post'
    Assert-Throws { Invoke-MaintenanceGuard } 'Manual checks require'
    Assert-Throws { Invoke-MaintenanceGuard -WebhookData @{ RequestBody='[]' } -Phase Pre -DemoOnly $true } 'cannot consume webhook'
    Assert ($script:AuthCalls -eq 0) 'Invalid manual invocation authenticated.'
}
Test 'Unexpected maintenance policies cancel before guest execution' {
    foreach ($mode in @('OtherKB','Classification','Reboot','RebootKB','Linux')) {
        Reset-Mocks; $script:PolicyMode=$mode
        Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
        Assert-Cancel
        Assert (@(Get-Calls PUT '/runCommands/').Count -eq 0) 'Unsafe policy performed guest check.'
    }
}
Test 'Missing target approval, disconnected machine, wrong region cancel' {
    foreach ($mode in @('TagsMissing','Disconnected','WrongRegion')) {
        Reset-Mocks; Set-Variable -Name $mode -Scope Script -Value $true
        Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
        Assert-Cancel
    }
}
Test 'Pending reboot, unexpected WU policy, stopped Agent, offline demo fail' {
    foreach ($mode in @('PendingReboot','UpdatePolicy','AgentStopped','DemoOffline')) {
        Reset-Mocks; $script:GuestMode=$mode
        Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
        Assert-Cancel; Assert-OwnCleanup
    }
}
Test 'NeverReboot policy is accepted and unrelated offline DB is not a false failure' {
    $script:PolicyMode='NeverReboot'
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Allow') 'Safe alternative policy or unrelated offline database failed.'
}
Test 'Checkpoint write failure cancels rather than returning a healthy Pre' {
    $script:CheckpointFailOnce=$true
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
}
Test 'Cleanup failure surfaces and preserves primary guest failure' {
    $script:CleanupFails=$true; $script:GuestMode='Failed'
    Assert-Throws { Invoke-Event (New-Event) -WarningAction SilentlyContinue } 'Guest check failed or timed out'
    Assert-Cancel; Assert-OwnCleanup
}
Test 'Cleanup-only failure cancels and never reports healthy Pre' {
    $script:CleanupFails=$true
    Assert-Throws { Invoke-Event (New-Event) -WarningAction SilentlyContinue } 'Own Run Command cleanup failed'
    Assert-Cancel; Assert-OwnCleanup
}
Test 'Stale guest health output is rejected and canceled' {
    $script:GuestClockSkew=$true
    Assert-Throws { Invoke-Event (New-Event) } 'stale'
    Assert-Cancel; Assert-OwnCleanup
}
Test 'Unsafe Automation continuation link is never followed' {
    $script:UnsafeNextLink=$true
    Assert-Throws { Invoke-Event (New-Event) } 'Unsafe checkpoint continuation'
    Assert-Cancel
    Assert (@($script:Calls.ToArray() | Where-Object { $_.Path -match 'attacker' }).Count -eq 0) 'Foreign continuation was followed.'
}
Test 'Repeated Post appends evidence, never replacing first Pre' {
    $pre=Invoke-Event (New-Event); $first=$script:Assets[$pre.Checkpoint].properties.value
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Completed'
    $null=Invoke-Event (New-Event Post); $null=Invoke-Event (New-Event Post)
    Assert ($script:Assets.Count -eq 3) 'Post evidence was not append-only.'
    Assert ($script:Assets[$pre.Checkpoint].properties.value -ceq $first) 'Repeated Post overwrote Pre.'
    Assert-OwnCleanup
}
Test 'Serialized Automation webhook envelope derives phase automatically' {
    $event=New-Event
    $envelope=@{ RequestBody=(ConvertTo-Json -InputObject @($event) -Depth 12 -Compress); WebhookName='offline-pre'; RequestHeader=@{} }
    $result=Invoke-MaintenanceGuard -WebhookData ($envelope | ConvertTo-Json -Depth 14 -Compress) | ConvertFrom-Json
    Assert ($result.Phase -eq 'Pre' -and $result.Decision -eq 'Allow') 'Serialized WebhookData was not processed.'
}
Test 'PS7 materialized UTC/offset dates work but unspecified dates do not' {
    $utc=[datetime]::SpecifyKind([datetime]'2027-01-04T12:00:00', [DateTimeKind]::Utc)
    Assert ((ConvertTo-GuardDate $utc 'date') -eq [datetimeoffset]'2027-01-04T12:00:00Z') 'UTC materialized date changed.'
    Assert ((ConvertTo-GuardDate ([datetimeoffset]'2027-01-04T19:00:00+07:00') 'date') -eq [datetimeoffset]'2027-01-04T12:00:00Z') 'Offset materialized date changed.'
    Assert-Throws { ConvertTo-GuardDate ([datetime]::SpecifyKind($utc, [DateTimeKind]::Unspecified)) 'date' } 'without timezone'
}
Test 'Append-only competing healthy Pre evidence retains earliest baseline' {
    $event=@(Get-GuardEvents @{ RequestBody=(ConvertTo-Json -InputObject @((New-Event)) -Depth 12) } '' $false)[0]
    Connect-GuardIdentity
    $first=Write-GuardJournal $event 'Allow' (New-Guest) $null $null $null
    $script:Now=$script:Now.AddMinutes(1)
    $later=New-Guest; $later.SqlServerStartUtc='2027-01-04T11:00:00.0000000Z'
    $second=Write-GuardJournal $event 'Allow' $later $null $null $null
    Assert ($first -ne $second) 'Competing delivery did not get its own variable.'
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Completed'
    $post=Invoke-Event (New-Event Post)
    Assert ($post.Baseline -eq $first -and $post.HandlerHealth -eq 'Healthy') 'Later Pre replaced first recorded times.'
}
Test 'Unresolved cancellation failure must never fall back to an earlier Allow' {
    $pre=Invoke-Event (New-Event)
    $event=@(Get-GuardEvents @{ RequestBody=(ConvertTo-Json -InputObject @((New-Event)) -Depth 12) } '' $false)[0]
    $script:Now=$script:Now.AddMinutes(1)
    $null=Write-GuardJournal $event 'CancellationFailed' $null 'OFFLINE synthetic failure' $null $null
    $script:CancelMode='Denied'
    Assert-Throws { Invoke-Event (New-Event) } 'unresolved cancellation failure'
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'
    Assert-Throws { Invoke-Event (New-Event Post) } 'unresolved Pre cancellation failure'
    Assert ($script:Assets.ContainsKey($pre.Checkpoint)) 'Baseline was discarded after failure.'
}
Test 'Handler health and failed patch result remain distinct' {
    $null=Invoke-Event (New-Event)
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Failed'
    $post=Invoke-Event (New-Event Post)
    Assert ($post.HandlerHealth -eq 'Healthy' -and $post.PatchResult.Status -eq 'Failed') 'Handler health concealed patch failure.'
}
Test 'Unsupported occurrence read on Post is explicitly unavailable, not patch success' {
    $null=Invoke-Event (New-Event)
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunUnsupported=$true
    $post=Invoke-Event (New-Event Post)
    Assert ($post.HandlerHealth -eq 'Healthy' -and $post.PatchResult.Status -eq 'Unavailable') 'Unavailable patch evidence was fabricated.'
}
Test 'A missing occurrence on Post is an error, not an unsupported-success fallback' {
    $null=Invoke-Event (New-Event)
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunMissing=$true
    Assert-Throws { Invoke-Event (New-Event Post) } 'Existing maintenance run could not be verified'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Missing Post occurrence received a mutation.'
}
Test 'Authentication failure is sanitized and never returns healthy evidence' {
    $script:AuthFails=$true
    Assert-Throws { Invoke-Event (New-Event) } 'Managed-identity authentication'
    Assert ($script:Calls.Count -eq 0 -and $script:Assets.Count -eq 0) 'Auth failure performed ARM calls.'
}
Test 'Unconfirmed cancellation polling stops before the conservative cutoff' {
    $script:Now=[datetimeoffset]'2027-01-04T11:49:15Z'; $script:CancelMode='NeverConfirmed'
    Assert-Throws { Invoke-Event (New-Event) } 'not confirmed|could not be confirmed'
    Assert-Cancel
    Assert (@($script:Calls.ToArray() | Where-Object { $_.Path -match '/applyupdates/' -and $_.At -ge [datetimeoffset]'2027-01-04T11:50:00Z' }).Count -eq 0) 'Cancellation polling exceeded cutoff.'
}
Test 'A duplicate Pre cannot hide a subsequently broadened maintenance policy' {
    $pre=Invoke-Event (New-Event); $value=$script:Assets[$pre.Checkpoint].properties.value
    $script:PolicyMode='Classification'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
    Assert ($script:Assets[$pre.Checkpoint].properties.value -ceq $value) 'Rejected duplicate altered original baseline.'
    Assert (@(Get-Calls PUT '/runCommands/').Count -eq 1) 'Policy-rejected duplicate created another guest command.'
}
Test 'Slow checkpoint retrieval fails within its budget and cancels before guest work' {
    $script:IndexDelaySeconds=75
    Assert-Throws { Invoke-Event (New-Event) } 'Checkpoint read exhausted'
    Assert-Cancel
    Assert (@(Get-Calls PUT '/runCommands/').Count -eq 0) 'Timed-out checkpoint discovery performed guest work.'
}
Test 'An already-cancelled run remains truthfully cancelled when state persistence fails' {
    $script:RunStatus='Cancelled'; $script:CheckpointFailOnce=$true
    $script:Now=[datetimeoffset]'2027-01-04T12:05:00Z'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Confirmed cancellation was re-submitted.'
}
Test 'Very late but not expired Pre cancels immediately, without spending time on state discovery' {
    $script:Now=[datetimeoffset]'2027-01-04T11:49:40Z'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
    Assert (@(Get-Calls PUT '/runCommands/').Count -eq 0 -and @(Get-Calls GET '/variables\?').Count -eq 0) 'Near-cutoff event performed discovery or guest work.'
}
Test 'Creation and status API failures still clean only the owned command and cancel' {
    foreach ($mode in @('CreateFailure','CreateTransport','StatusFailure')) {
        Reset-Mocks; $script:GuestMode=$mode
        Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
        Assert-Cancel; Assert-OwnCleanup
    }
}
Test 'Server creation time preserves first baseline even if a later delivery clock regresses' {
    $event=@(Get-GuardEvents @{ RequestBody=(ConvertTo-Json -InputObject @((New-Event)) -Depth 12) } '' $false)[0]
    Connect-GuardIdentity
    $first=Write-GuardJournal $event 'Allow' (New-Guest) $null $null $null
    $script:Now=$script:Now.AddMinutes(-1)
    $later=New-Guest; $later.SqlServerStartUtc='2027-01-04T11:00:00.0000000Z'
    $second=Write-GuardJournal $event 'Allow' $later $null $null $null
    $script:Assets[$second].properties.creationTime='2027-01-04T11:26:00.0000000Z'
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Completed'
    $post=Invoke-Event (New-Event Post)
    Assert ($post.Baseline -eq $first) 'Client clock regression replaced first server-recorded baseline.'
}

Test 'Live ARM numeric KB representation retains the exact one-update restriction' {
    $script:PolicyMode='NumericKB'
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Allow') 'Bare numeric KB representation was rejected.'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Healthy numeric KB policy submitted cancellation.'
}
Test 'Excluded numeric approved KB cancels rather than claiming a usable update policy' {
    $script:PolicyMode='ExcludedApprovedKB'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
}
Test 'Existing notify-only Windows policy passes without changing the guest policy' {
    $script:GuestMode='NotifyOnly'
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Allow') 'Notify-only AUOptions=2 was rejected.'
    Assert ($result.Guest.WindowsUpdatePolicy.NoAutoUpdate -eq 0) 'Guest policy was changed.'
}
Test 'Official Post event needs no cancellation cutoff and infers Post from its payload' {
    $null=Invoke-Event (New-Event)
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z'; $script:RunStatus='Completed'
    $event=New-Event Post
    Assert ($null -eq $event.data.PSObject.Properties['CancellationCutOffDateTime']) 'Post fixture does not match the official schema.'
    $result=Invoke-Event $event
    Assert ($result.Phase -eq 'Post' -and $result.HandlerHealth -eq 'Healthy') 'Official Post event did not finish.'
}
Test 'Real resource-path event identifiers are supported without relaxing correlation scope' {
    $event=New-Event
    $event.data.CorrelationId=(Get-GuardScope).Configuration+'/providers/microsoft.maintenance/applyupdates/00000000-0000-0000-0000-000000000016'
    $event.id=$event.data.CorrelationId
    $parsed=@(Get-GuardEvents @{RequestBody=(ConvertTo-Json -InputObject @($event) -Depth 10)} '' $false)
    Assert ($parsed.Count -eq 1 -and $parsed[0].RunId -eq $event.data.CorrelationId) 'A scoped resource-path event ID was rejected.'
}
Test 'Newly created own Run Command tolerates bounded resource propagation 404s' {
    $script:GuestStatusNotFoundCount=2
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Allow') 'Own-command resource propagation caused a false failure.'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Propagation unnecessarily canceled maintenance.'
    Assert-OwnCleanup
}

Test 'An explicitly empty obsolete Edge directory deletion is retained as a non-mutating advisory' {
    $script:GuestMode='EdgeCleanup'
    $result=Invoke-Event (New-Event)
    Assert ($result.Decision -eq 'Allow' -and $result.Guest.PendingReboot.FileRename) 'Raw pending marker was hidden or harmless cleanup blocked.'
    Assert ($result.Guest.PendingReboot.FileRenameAdvisories[0].RegistryChanged -eq $false) 'Registry marker was changed.'
}
Test 'Unknown or nonempty pending file rename remains a maintenance blocker' {
    $script:GuestMode='UnsafeRename'
    Assert-Throws { Invoke-Event (New-Event) } 'confirmed Cancelled'
    Assert-Cancel
}
Test 'A fake cleanup advisory outside the exact versioned Edge directory cannot bypass the guard' {
    $script:GuestMode='EdgeCleanup'
    $guest=New-Guest
    $guest.PendingReboot.FileRenameAdvisories[0].Source='\??\C:\Windows\System32\critical.dll'
    Assert-Throws { Assert-GuardGuest $guest } 'unapproved pending rename'
}

Test 'Saved-state wall-clock correction cannot turn a stable boot into an inconsistent SQL startup' {
    $pre=New-Guest
    $post=New-Guest
    $post.WmiBootUtc='2027-01-04T07:26:55.1358090Z'
    $post.StartupEvidence.KernelTicksBefore=$pre.StartupEvidence.KernelTicksAfter+1000
    $post.StartupEvidence.KernelTicksAfter=$post.StartupEvidence.KernelTicksBefore+30
    $post.StartupEvidence.SqlCurrentTicks=$post.StartupEvidence.KernelTicksAfter
    Assert-GuardGuest $post
    Assert-GuardContinuity $pre $post
}
Test 'Missing original boot event identity fails closed despite all health flags' {
    $guest=New-Guest
    $guest.StartupEvidence=$null
    Assert-Throws {Assert-GuardGuest $guest} 'boot-event identity'
}
Test 'Changing the actual boot event record identifies a restart even with unchanged wall-clock dates' {
    $pre=New-Guest;$post=New-Guest
    $post.StartupEvidence.BootRecordId++
    Assert-Throws {Assert-GuardContinuity $pre $post} 'startup identity BootRecordId'
}
Test 'Changing SQL startup ticks detects an engine restart even with reused PID and timestamps' {
    $pre=New-Guest;$post=New-Guest
    $post.StartupEvidence.SqlStartTicks++
    Assert-Throws {Assert-GuardContinuity $pre $post} 'startup identity SqlStartTicks'
}
Test 'SQL process identity change remains a continuity failure' {
    $pre=New-Guest;$post=New-Guest
    $post.Services[0].ProcessId++
    Assert-Throws {Assert-GuardContinuity $pre $post} 'process identity'
}
Test 'Kernel uptime regression remains a reboot indicator' {
    $pre=New-Guest;$post=New-Guest
    $post.StartupEvidence.KernelTicksBefore=1000000
    $post.StartupEvidence.KernelTicksAfter=1000030
    $post.StartupEvidence.SqlCurrentTicks=1000020
    Assert-Throws {Assert-GuardContinuity $pre $post} 'regressed kernel'
}
Test 'SQL startup ticks cannot exceed current monotonic uptime' {
    $guest=New-Guest
    $guest.StartupEvidence.SqlStartTicks=$guest.StartupEvidence.SqlCurrentTicks+1
    Assert-Throws {Assert-GuardGuest $guest} 'tick evidence'
}
Test 'SQL and kernel uptime readings must corroborate within the read-resolution budget' {
    $guest=New-Guest
    $guest.StartupEvidence.SqlCurrentTicks=$guest.StartupEvidence.KernelTicksAfter+1001
    Assert-Throws {Assert-GuardGuest $guest} 'tick evidence'
}
Test 'Malformed boolean/string/fractional monotonic values are not accepted as numeric evidence' {
    foreach($invalid in @($true,'1000',1.5,$null)){
        $guest=New-Guest;$guest.StartupEvidence.SqlCurrentTicks=$invalid
        Assert-Throws {Assert-GuardGuest $guest} 'Monotonic startup'
    }
}
Test 'Legacy schema cannot be used as a silent startup-evidence fallback' {
    $guest=New-Guest;$guest.SchemaVersion=1
    Assert-Throws {Assert-GuardGuest $guest} 'missing or unhealthy'
}
Test 'Canonical boot date must equal the boot-event payload' {
    $guest=New-Guest;$guest.BootUtc='2026-12-25T03:00:00.0000000Z'
    Assert-Throws {Assert-GuardGuest $guest} 'boot-event timestamps'
}
Test 'The resume evidence has stable boot and SQL tick identity' {
    $guest=New-Guest
    $guest.ObservedUtc='2027-01-02T01:34:40.7966319Z'
    $guest.BootUtc='2027-01-01T00:52:43.5000000Z';$guest.WmiBootUtc='2027-01-01T07:26:55.1358090Z'
    $guest.SqlProcessStartUtc='2027-01-01T00:52:49.5493073Z';$guest.SqlServerStartUtc='2027-01-01T00:52:50.0470000Z'
    $guest.StartupEvidence.BootStartUtc=$guest.BootUtc
    $guest.StartupEvidence.BootEventWrittenUtc='2027-01-01T00:52:43.5899970Z'
    $guest.StartupEvidence.KernelTicksBefore=65265328;$guest.StartupEvidence.KernelTicksAfter=65265421
    $guest.StartupEvidence.SqlStartTicks=4069;$guest.StartupEvidence.SqlCurrentTicks=65265418
    Assert-GuardGuest $guest
}

Test 'A resumed Pre/Post chain keeps its journal baseline without false cancellation' {
    $pre=Invoke-Event (New-Event)
    $script:Now=[datetimeoffset]'2027-01-04T13:05:00Z';$script:RunStatus='Completed'
    $script:GuestMode='ResumeClockCorrection'
    $post=Invoke-Event (New-Event Post)
    Assert ($post.HandlerHealth -eq 'Healthy' -and $post.Baseline -eq $pre.Checkpoint) 'Resume correction broke same-run continuity.'
    Assert (@(Get-Calls PUT '/applyupdates/').Count -eq 0) 'Resume clock correction triggered false cancellation.'
}
Test 'A real Pre with missing boot evidence still cancels the exact maintenance occurrence' {
    $script:GuestMode='MissingStartupEvidence'
    Assert-Throws {Invoke-Event (New-Event)} 'confirmed Cancelled'
    Assert-Cancel
}

Write-Host "OFFLINE ONLY: $script:Passed passed; $script:Failed failed. No Azure or guest execution occurred."
if ($script:Failed -gt 0) { throw "$script:Failed offline tests failed." }
[pscustomobject]@{ OfflineOnly=$true; Passed=$script:Passed; Failed=$script:Failed }
