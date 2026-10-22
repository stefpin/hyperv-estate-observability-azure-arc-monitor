param([ValidateRange(30,900)][int]$Seconds=240)
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ne 'HV-HOST-01'){throw 'Execute only on the host.'}
$credentials=@{}
foreach($machine in 'WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-01'){
    $credentials[$machine]=Get-Credential -UserName labadmin -Message "Private guest password for $machine"
}
$workers=@()
try{
    foreach($machine in $credentials.Keys){
        $created=Invoke-Command -VMName $machine -Credential $credentials[$machine] -ArgumentList $Seconds -ScriptBlock {
            param($Duration)
            $code="`$end=[datetime]::UtcNow.AddSeconds($Duration);while([datetime]::UtcNow -lt `$end){for(`$i=0;`$i -lt 100000;`$i++){`$x=[math]::Sqrt(`$i)}}"
            $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
            foreach($i in 1..4){
                $process=Start-Process powershell.exe -ArgumentList '-NoProfile','-EncodedCommand',$encoded -WindowStyle Hidden -PassThru
                [pscustomobject]@{Id=$process.Id;StartUtcTicks=$process.StartTime.ToUniversalTime().Ticks}
            }
        }
        $workers+=@{Machine=$machine;Workers=@($created)}
        Write-Output "Started bounded workers on $machine; SQL guest not loaded."
    }
    Start-Sleep -Seconds $Seconds
}finally{
    foreach($row in $workers){
        Invoke-Command -VMName $row.Machine -Credential $credentials[$row.Machine] -ArgumentList (,$row.Workers) -ScriptBlock {
            param($RecordedWorkers)
            foreach($worker in $RecordedWorkers){
                $p=Get-Process -Id $worker.Id -ErrorAction SilentlyContinue
                if($p -and $p.ProcessName -eq 'powershell' -and
                    $p.StartTime.ToUniversalTime().Ticks -eq $worker.StartUtcTicks){
                    Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }
    $credentials=$null
    Write-Output 'Only recorded bounded CPU worker PIDs cleaned up; SQL remains running.'
}
