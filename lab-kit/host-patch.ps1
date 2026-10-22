param(
    [ValidateSet('Download', 'Apply')][string]$Stage = 'Download',
    [string]$GuestPasswordHex = '', [ValidateSet('no','yes')][string]$InitialBuildMaintenanceApproved='no'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if($env:COMPUTERNAME -ne 'HV-HOST-01'){throw 'Only HV-HOST-01 is permitted.'}
if($Stage -eq 'Apply' -and $InitialBuildMaintenanceApproved -ne 'yes'){throw 'Pass -InitialBuildMaintenanceApproved yes to apply SQL patches; they can restart services.'}
$folder = 'F:\Build\sql2019-updates'
$patches = @(
    @{
        Name = 'SQLServer2019-KB5054833-x64.exe'
        Version = '15.0.4430.1'
        Url = 'https://download.microsoft.com/download/6/e/7/6e72dddf-dfa4-4889-bc3d-e5d3a0fd11ce/SQLServer2019-KB5054833-x64.exe'
        Hash = '864AA01854D124BD907920B26271F9F2ED3F5F82880ADB746DBBC681EF32B371'
    },
    @{
        Name = 'SQLServer2019-KB5122772-x64.exe'
        Version = '15.0.4490.9'
        Url = 'https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/secu/2026/09/sqlserver2019-kb5122772-x64_8c43e4df34e5afd5dcc34512bc955ab7bebddf8f.exe'
        Hash = '6E270345C450E8876CD7A440142C2C76919E23F69945233887A25182FC158F1C'
    }
)
New-Item -ItemType Directory -Path $folder -Force | Out-Null
foreach ($patch in $patches) {
    $path = Join-Path $folder $patch.Name
    if (-not (Test-Path $path)) {
        $part = "$path.part"
        & "$env:WINDIR\System32\curl.exe" --fail --location --silent --show-error --retry 3 --connect-timeout 30 --max-time 1800 --output $part $patch.Url
        if ($LASTEXITCODE -ne 0) { throw "Downloading $($patch.Name) failed" }
        if ((Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash -ne $patch.Hash) { throw "Downloaded patch checksum mismatch: $($patch.Name)" }
        Move-Item -LiteralPath $part -Destination $path
    }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $patch.Hash) { throw "Patch checksum mismatch: $($patch.Name)" }
    $signature = Get-AuthenticodeSignature -FilePath $path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw "Patch signature invalid: $($patch.Name)" }
    "Verified $($patch.Name): $([math]::Round((Get-Item $path).Length / 1MB)) MB; Microsoft signed; published SHA256 matches."
}
if ($Stage -eq 'Download') { 'SQL-PATCH-DOWNLOAD-DONE'; return }
if ($GuestPasswordHex -notmatch '^x([0-9a-f]{2})+$') { throw 'Guest credential missing' }
$hex = $GuestPasswordHex.Substring(1)
$bytes = New-Object byte[] ($hex.Length / 2)
for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16) }
$credential = New-Object Management.Automation.PSCredential('labadmin', (ConvertTo-SecureString ([Text.Encoding]::ASCII.GetString($bytes)) -AsPlainText -Force))
$session = New-PSSession -VMName 'SQL2019-GUEST' -Credential $credential
try {
    foreach ($patch in $patches) {
        Invoke-Command -Session $session -ScriptBlock { New-Item -ItemType Directory -Path 'C:\HV-Staging\sql2019' -Force | Out-Null }
        $guestPath = Join-Path 'C:\HV-Staging\sql2019' $patch.Name
        $staged = Invoke-Command -Session $session -ArgumentList $guestPath, $patch.Hash -ScriptBlock {
            param($Path, $Hash)
            (Test-Path $Path) -and (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -eq $Hash
        }
        if (-not $staged) { Copy-Item -LiteralPath (Join-Path $folder $patch.Name) -Destination $guestPath -ToSession $session -Force }
        Invoke-Command -Session $session -ArgumentList $guestPath, $patch.Hash, $patch.Version -ScriptBlock {
            param($Path, $Hash, $TargetVersion)
            $ErrorActionPreference = 'Stop'
            if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Hash) { throw 'Guest patch checksum mismatch' }
            $sqlExe = 'C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Binn\sqlservr.exe'
            $fileVersion = (Get-Item $sqlExe).VersionInfo
            $current = [version]("$($fileVersion.FileMajorPart).$($fileVersion.FileMinorPart).$($fileVersion.FileBuildPart).$($fileVersion.FilePrivatePart)")
            $target = [version]$TargetVersion
            # sqlservr.exe uses 2019.150.build.revision; compare the build and revision.
            if ($current.Build -gt $target.Build -or ($current.Build -eq $target.Build -and $current.Revision -ge $target.Revision)) {
                "Patch $(Split-Path $Path -Leaf) already superseded; current executable $current."
                return
            }
            $process = Start-Process -FilePath $Path -ArgumentList '/quiet', '/IAcceptSQLServerLicenseTerms', '/Action=Patch', '/InstanceName=MSSQLSERVER' -Wait -PassThru
            $process.Refresh()
            $code = $process.ExitCode
            "Patch $(Split-Path $Path -Leaf): exit $code."
            if ($code -notin 0, 3010) { throw "SQL update failed with exit $code; inspect SQL Setup Bootstrap logs" }
            Set-Service MSSQLSERVER -StartupType Automatic
            Set-Service SQLSERVERAGENT -StartupType Automatic
            Start-Service MSSQLSERVER
            Start-Service SQLSERVERAGENT
        }
    }
    Invoke-Command -Session $session -ScriptBlock {
        $ErrorActionPreference = 'Stop'
        $connection = New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Connect Timeout=30')
        try {
            $connection.Open()
            $command = $connection.CreateCommand()
            $command.CommandText = "SELECT CONVERT(nvarchar(50), SERVERPROPERTY('ProductVersion'))"
            $version = [string]$command.ExecuteScalar()
            "Patched SQL version: $version"
            if ($version -ne '15.0.4490.9') { throw "SQL version differs from target: $version" }
        }
        finally { $connection.Dispose() }
        Get-CimInstance Win32_Service -Filter "Name='MSSQLSERVER' OR Name='SQLSERVERAGENT'" |
            ForEach-Object { "Service $($_.Name): $($_.State); startup=$($_.StartMode)." }
        'SQL-PATCH-DONE'
    }
}
finally { Remove-PSSession -Session $session }
