param([string]$OutputDirectory="$PSScriptRoot\exports\preflight")
. "$PSScriptRoot\context.ps1"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$items=@(
    @{File='arc-machines.json';Args=@('connectedmachine','list','-g',$RG,'--query','[].{name:name,location:location,status:status,tags:tags}','-o','json')}
    @{File='resources.json';Args=@('resource','list','-g',$RG,'--query','[].{name:name,type:type,location:location,id:id}','-o','json')}
    @{File='alert-rules.json';Args=@('monitor','scheduled-query','list','-g',$RG,'-o','json')}
)
foreach($item in $items){
    $argsToRun=$item.Args
    $raw=Invoke-LabAz @argsToRun
    [IO.File]::WriteAllText((Join-Path $OutputDirectory $item.File),($raw | Out-String),(New-Object Text.UTF8Encoding($false)))
}
foreach($name in 'heartbeat','counter-inventory','sql-memory','storage-windows','cpu-wait'){
    Invoke-LabQuery -QueryFile "$PSScriptRoot\queries\$name.kql" -OutputPath (Join-Path $OutputDirectory "$name.json")
}
[IO.File]::WriteAllText((Join-Path $OutputDirectory 'snapshot-time.txt'),[datetime]::UtcNow.ToString('o'))
Write-Output 'Read-only public evidence export completed; no guest commands or Azure writes.'
