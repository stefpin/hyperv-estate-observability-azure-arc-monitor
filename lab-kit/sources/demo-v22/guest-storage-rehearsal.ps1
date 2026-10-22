param([int]$Seconds=180)
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ne 'SQL2019-GUEST' -or $Seconds -lt 30 -or $Seconds -gt 600){throw 'Only SQL2019-GUEST and 30-600 seconds are permitted.'}
$root='E:\HV-IO-Demo'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$worker={
    param($Path,$Duration)
    $ErrorActionPreference='Stop'
    $buffer=New-Object byte[] 8192
    $rng=New-Object Random(42)
    $rng.NextBytes($buffer)
    $stream=New-Object IO.FileStream($Path,[IO.FileMode]::Create,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read,8192,[IO.FileOptions]::WriteThrough)
    $operations=0
    try{
        $stream.SetLength(128MB)
        $deadline=(Get-Date).AddSeconds($Duration)
        while((Get-Date) -lt $deadline){
            $stream.Position=[int64]$rng.Next(0,16384)*8192
            $stream.Write($buffer,0,$buffer.Length)
            $operations++
        }
    }
    finally{$stream.Dispose()}
    @{Operations=$operations;Duration=$Duration;Path=$Path}
}
$jobs=@()
try{
    Start-Sleep -Seconds 60
    for($i=0;$i -lt 4;$i++){$jobs+=Start-Job -ScriptBlock $worker -ArgumentList "$root\worker-$i.bin",$Seconds}
    $null=$jobs|Wait-Job -Timeout ($Seconds+90)
    foreach($job in $jobs){
        if($job.State -ne 'Completed'){throw "Storage worker $($job.Id) failed or timed out: $($job.State)"}
        $result=Receive-Job $job -ErrorAction Stop
        "Storage worker operations=$($result.Operations); duration=$($result.Duration)s; bounded random 8KiB write-through."
    }
    Start-Sleep -Seconds 60
}
finally{
    foreach($job in $jobs){if($job.State -eq 'Running'){Stop-Job $job};Remove-Job $job -Force}
    foreach($i in 0..3){$path="$root\worker-$i.bin";if(Test-Path $path){Remove-Item $path -Force}}
}
"Storage rehearsal finished; SQL=$((Get-Service MSSQLSERVER).Status); only dedicated test files removed."
