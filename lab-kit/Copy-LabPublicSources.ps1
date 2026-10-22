param([ValidateSet('Host','SqlGuest')][string]$Target='Host')
. "$PSScriptRoot\context.ps1"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$private=Join-Path $env:USERPROFILE 'HV-Private'
New-Item -ItemType Directory -Path $private -Force | Out-Null
$zip=Join-Path $private ('public-'+[guid]::NewGuid().ToString('N')+'.zip')
$transport=Join-Path $private ('copy-'+[guid]::NewGuid().ToString('N')+'.ps1')
try{
    foreach($file in Get-ChildItem $PSScriptRoot -Recurse -File){
        if($file.Name -match '(?i)(ENVIRONMENT|^protected-|^parameter-|webhook)' -or $file.Extension -notin '.ps1','.py','.json','.kql','.sh','.txt','.service','.md'){
            throw 'Unexpected or potentially private file in public bundle; inspect before transfer.'
        }
    }
    [IO.Compression.ZipFile]::CreateFromDirectory($PSScriptRoot,$zip)
    $base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($zip))
    $code=@'
param([string]$BundleBase64,[string]$Target,[string]$GuestPasswordHex)
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ne 'HV-HOST-01'){throw 'Wrong host.'}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root='F:\Build\lab-kit'
$archive='F:\Build\hv-lab-kit.zip'
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    [IO.File]::WriteAllBytes($archive,[Convert]::FromBase64String($BundleBase64))
    $opened=[IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach($entry in $opened.Entries){
            $dest=[IO.Path]::GetFullPath((Join-Path $root $entry.FullName))
            if(-not $dest.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Archive path outside bundle.'}
            if(-not $entry.Name){New-Item -ItemType Directory -Path $dest -Force | Out-Null;continue}
            New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$dest,$true)
        }
    }finally{$opened.Dispose()}
    if($Target -eq 'SqlGuest'){
        if($GuestPasswordHex -notmatch '^x([0-9a-f]{2})+$'){throw 'Private guest credential missing.'}
        $hex=$GuestPasswordHex.Substring(1);$b=New-Object byte[] ($hex.Length/2)
        for($i=0;$i -lt $b.Length;$i++){$b[$i]=[Convert]::ToByte($hex.Substring($i*2,2),16)}
        $cred=New-Object Management.Automation.PSCredential('labadmin',(ConvertTo-SecureString ([Text.Encoding]::ASCII.GetString($b)) -AsPlainText -Force))
        $s=New-PSSession -VMName SQL2019-GUEST -Credential $cred
        try {
            Invoke-Command -Session $s -ScriptBlock {New-Item -ItemType Directory -Path C:\lab-kit -Force | Out-Null}
            Copy-Item -Path "$root\*" -Destination C:\lab-kit -ToSession $s -Recurse -Force
        }finally{Remove-PSSession $s}
        'Public bundle copied to SQL2019-GUEST C:\lab-kit. No guest script executed.'
    }else{'Public bundle copied to host F:\Build\lab-kit. No guest script executed.'}
}finally{Remove-Item $archive -Force -ErrorAction SilentlyContinue}
'@
    [IO.File]::WriteAllText($transport,$code,(New-Object Text.UTF8Encoding($false)))
    $protected=@{}
    if($Target -eq 'SqlGuest'){
        $e=Get-LabSettings
        $protected.GuestPasswordHex=ConvertTo-LabHex $e.SQL_GUEST_PASSWORD
        $e=$null
    }
    Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath $transport `
        -Parameters @{BundleBase64=$base64;Target=$Target} -Protected $protected -TimeoutSeconds 900
}finally{
    Remove-Item $zip,$transport -Force -ErrorAction SilentlyContinue
    $protected=$null;$base64=$null
}
