param([string]$Win2019PasswordHex,[string]$Win2022PasswordHex,[string]$Win2025PasswordHex,[ValidateRange(240,900)][int]$LoadSeconds=240)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
if($env:COMPUTERNAME -ne 'HV-HOST-01'){throw 'Only HV-HOST-01 is permitted.'}
function Decode([string]$Hex) {
    if($Hex -notmatch '^x([0-9a-f]{2})+$'){throw 'Guest credential missing'}
    $s=$Hex.Substring(1);$b=New-Object byte[] ($s.Length/2)
    for($i=0;$i -lt $b.Length;$i++){$b[$i]=[Convert]::ToByte($s.Substring(2*$i,2),16)}
    [Text.Encoding]::ASCII.GetString($b)
}
$paths=@('\Hyper-V Hypervisor Logical Processor(_Total)\% Total Run Time','\Hyper-V Hypervisor Virtual Processor(*)\CPU Wait Time Per Dispatch')
$registry=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Perflib\009'
$counterNames=@($registry.Counter);$help=@($registry.Help)
for($i=0;$i -lt $counterNames.Count-1;$i+=2){
    if($counterNames[$i+1] -eq 'CPU Wait Time Per Dispatch'){
        $helpId=[string]([int]$counterNames[$i]+1)
        for($j=0;$j -lt $help.Count-1;$j+=2){if($help[$j] -eq $helpId){"Counter help: $($help[$j+1])";break}}
        break
    }
}
function Sample([string]$Stage,[int]$Samples){
    $data=Get-Counter -Counter $paths -SampleInterval 5 -MaxSamples $Samples
    $points=@()
    foreach($point in $data){
        $hostCPU=($point.CounterSamples|Where-Object{$_.Path -like '*logical processor*'}).CookedValue
        $guestRows=$point.CounterSamples|Where-Object{$_.Path -like '*virtual processor*' -and $_.InstanceName -like 'RHEL94-GUEST:*'}
        $average=($guestRows|Measure-Object CookedValue -Average).Average
        $points += [pscustomobject]@{Stage=$Stage;TimeUtc=$point.Timestamp.ToUniversalTime().ToString('o');HostCPU=$hostCPU;RHELMeanWait=$average}
    }
    $points|Export-Csv -Path "F:\Build\hv-cpu-$Stage.csv" -NoTypeInformation
    "$Stage HostCPU average=$([math]::Round(($points|Measure-Object HostCPU -Average).Average,2)) percent; RHEL mean scheduling wait=$([math]::Round(($points|Measure-Object RHELMeanWait -Average).Average,2)); samples=$($points.Count)."
    $latency=& "$env:WINDIR\System32\OpenSSH\ssh.exe" -i 'F:\Build\ssh\rhel_ed25519' -o BatchMode=yes -o ConnectTimeout=15 `
        -o StrictHostKeyChecking=yes -o UserKnownHostsFile='F:\Build\ssh\known_hosts' labadmin@192.168.100.14 `
        'systemctl is-active hv-http-latency >/dev/null && python3 -c "import json;from collections import deque;p=\"/var/log/hv-demo/http-latency.json\";rows=[json.loads(s) for s in deque(open(p),maxlen=300)];print(\"\n\".join(str(r[\"ResponseMs\"]) for r in rows))"'
    if($LASTEXITCODE -ne 0){throw 'Reading the installed RHEL hv-http-latency observer failed'}
    $values=@($latency|ForEach-Object{[double]::Parse($_,[Globalization.CultureInfo]::InvariantCulture)}|Sort-Object)
    if($values.Count -eq 0){throw 'RHEL HTTP observer returned no samples'}
    $mean=($values|Measure-Object -Average).Average
    $p95=$values[[math]::Ceiling(0.95*$values.Count)-1]
    "$Stage RHEL localhost HTTP latency last300: mean=$([math]::Round($mean,3)) ms; p95=$([math]::Round($p95,3)) ms."

}
Sample 'baseline' 6
$map=[ordered]@{'WIN2019-GUEST'=$Win2019PasswordHex;'WIN2022-GUEST'=$Win2022PasswordHex;'WIN2025-GUEST-01'=$Win2025PasswordHex}
foreach($name in $map.Keys){
    $credential=New-Object Management.Automation.PSCredential('labadmin',(ConvertTo-SecureString (Decode $map[$name]) -AsPlainText -Force))
    Invoke-Command -VMName $name -Credential $credential -ArgumentList $LoadSeconds -ScriptBlock {
        param($Seconds)
        $code="`$deadline=(Get-Date).AddSeconds($Seconds); while((Get-Date) -lt `$deadline){ for(`$i=1;`$i -le 100000;`$i++){`$null=[math]::Sqrt(`$i)} }"
        $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
        $ids=@()
        for($i=0;$i -lt 4;$i++){$p=Start-Process powershell.exe -ArgumentList '-NoProfile','-EncodedCommand',$encoded -WindowStyle Hidden -PassThru;$ids+=$p.Id}
        "Bounded CPU workers on ${env:COMPUTERNAME}: $($ids -join ','); auto-exit in $Seconds seconds."
    }
}
Start-Sleep -Seconds 45
Sample 'loaded' 30
Start-Sleep -Seconds ([math]::Max(0,$LoadSeconds-195))
Sample 'recovery' 12
'CPU-REHEARSAL-DONE: worker processes were self-terminating; no SQL service stopped.'
