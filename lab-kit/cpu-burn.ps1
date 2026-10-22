param([ValidateRange(30,600)][int]$Seconds=300)
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -notin 'WIN2019-GUEST','WIN2022-GUEST','WIN2025-GUEST-0','WIN2025-GUEST-01'){
    throw 'CPU scene allowed only on the three noisy-neighbour guests.'
}
$code="`$end=[datetime]::UtcNow.AddSeconds($Seconds);while([datetime]::UtcNow -lt `$end){for(`$i=0;`$i -lt 100000;`$i++){`$x=[math]::Sqrt(`$i)}}"
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
$workers=@()
try{
    foreach($i in 1..4){$workers+=Start-Process powershell.exe -ArgumentList '-NoProfile','-EncodedCommand',$encoded -PassThru -WindowStyle Hidden}
    Write-Output "Four bounded CPU workers; PIDs=$($workers.Id -join ','); duration=$Seconds seconds."
    Start-Sleep -Seconds $Seconds
}finally{
    foreach($worker in $workers){$worker.Refresh();if(-not $worker.HasExited){Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue}}
    Write-Output 'Only this scene worker PIDs stopped; SQL and agents unchanged.'
}
