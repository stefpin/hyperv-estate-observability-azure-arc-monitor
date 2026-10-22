. "$PSScriptRoot\common.ps1"
Initialize-LabArm
$submitted = foreach ($phase in @('Pre','Post')) {
    $jobId = [guid]::NewGuid().ToString()
    $path = "$Account/jobs/$jobId"
    $null = Invoke-LabArm PUT "$path`?api-version=2024-10-23" @{
        properties = @{
            runbook = @{ name = 'Test-HvSqlMaintenanceAvailability' }
            parameters = @{ Phase = $phase; DemoOnly = 'true' }
        }
    }
    [pscustomobject]@{ Phase = $phase; Id = $jobId; Path = $path }
}
Save-LabEvidence 'guard-independent-jobs.json' @($submitted)
$results = foreach ($job in $submitted) {
    $deadline = [datetime]::UtcNow.AddMinutes(12)
    do {
        Start-Sleep -Seconds 10
        $state = Invoke-LabArm GET "$($job.Path)?api-version=2024-10-23"
        if ($state.properties.status -in @('Completed','Failed','Stopped','Suspended')) { break }
    } while ([datetime]::UtcNow -lt $deadline)
    $streams = Invoke-LabArm GET "$($job.Path)/streams?api-version=2024-10-23"
    $output = Invoke-LabArm GET "$($job.Path)/output?api-version=2024-10-23"
    Save-LabEvidence "guard-independent-$($job.Phase)-streams.json" $streams
    $record = if ($output -is [string]) { $output | ConvertFrom-Json } else { $output }
    Save-LabEvidence "guard-independent-$($job.Phase)-output.txt" $record
    if ($state.properties.status -ne 'Completed') {
        throw "Independent $($job.Phase) safeguard job ended with $($state.properties.status); see its safe job streams."
    }
    if ($record.Phase -ne $job.Phase -or $record.HandlerHealth -ne 'Healthy' -or
        $record.DemoOnly -ne $true -or $record.Guest.Health.SqlQuery -ne $true -or $record.Guest.Healthy -ne $true -or
        $record.PatchInstallRequested -isnot [bool] -or $record.PatchInstallRequested -or
        $record.CancellationSubmitted -isnot [bool] -or $record.CancellationSubmitted -or
        $record.CheckpointWritten -isnot [bool] -or $record.CheckpointWritten) {
        throw 'Cloud check did not return the exact independent, healthy, no-patch/no-cancel/no-state-write contract.'
    }
    [pscustomobject]@{
        Phase = $job.Phase
        JobId = $job.Id
        Status = $state.properties.status
        StartedUtc = $state.properties.startTime
        EndedUtc = $state.properties.endTime
        EvidenceType = 'Independent read-only handler execution, not a scheduled installation or real cancellation'
        ContractVerified = $true
    }
}
Save-LabEvidence 'guard-cloud-validation.json' @{
    Completed = $true
    ContractVerified = $true
    Jobs = @($results)
    RealScheduledInstallation = $false
    RealCancellationExercised = $false
    CheckedUtc = [datetime]::UtcNow.ToString('o')
}
$results | ConvertTo-Json -Depth 5
