param([Parameter(Mandatory=$true)][string]$MediaPath)
. "$PSScriptRoot\guest-sql.ps1"
if (Get-Service MSSQLSERVER -ErrorAction SilentlyContinue) { Write-Output 'SQL already installed; no setup or restart performed.';return }
foreach($path in 'E:\SQLData','E:\TempDB','E:\SQLBackup','L:\SQLLog'){
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
$setup=Join-Path $MediaPath 'setup.exe'
$sig=Get-AuthenticodeSignature $setup
if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation'){throw 'Invalid SQL installer signature.'}
if ((Get-Item $setup).VersionInfo.FileMajorPart -ne 15) { throw 'Setup is not SQL Server 2019; no installation performed.' }
$args=@('/QUIET','/ACTION=Install','/FEATURES=SQLENGINE','/INSTANCENAME=MSSQLSERVER',
    '/INSTANCEID=MSSQLSERVER','/IACCEPTSQLSERVERLICENSETERMS','/UpdateEnabled=False',
    '/SQLSVCACCOUNT="NT Service\MSSQLSERVER"','/SQLSVCSTARTUPTYPE=Automatic',
    '/AGTSVCACCOUNT="NT Service\SQLSERVERAGENT"','/AGTSVCSTARTUPTYPE=Automatic',
    '/SQLSYSADMINACCOUNTS="SQL2019-GUEST\labadmin" "NT AUTHORITY\SYSTEM"',
    '/SQLCOLLATION=SQL_Latin1_General_CP1_CI_AS','/SQLUSERDBDIR="E:\SQLData"',
    '/SQLUSERDBLOGDIR="L:\SQLLog"','/SQLTEMPDBDIR="E:\TempDB"',
    '/SQLTEMPDBLOGDIR="L:\SQLLog"','/SQLBACKUPDIR="E:\SQLBackup"',
    '/SQLTEMPDBFILECOUNT=4','/SQLTEMPDBFILESIZE=64','/SQLTEMPDBFILEGROWTH=64',
    '/SQLTEMPDBLOGFILESIZE=64','/SQLTEMPDBLOGFILEGROWTH=64',
    '/SQLSVCINSTANTFILEINIT=True','/TCPENABLED=1','/NPENABLED=0')
$p=Start-Process $setup -ArgumentList $args -Wait -PassThru
if($p.ExitCode -notin 0,3010){throw "SQL setup failed ($($p.ExitCode)); inspect Setup Bootstrap Summary.txt."}
Set-Service MSSQLSERVER -StartupType Automatic
Set-Service SQLSERVERAGENT -StartupType Automatic
Start-Service MSSQLSERVER
Start-Service SQLSERVERAGENT
Invoke-LabSql "EXEC sp_configure 'show advanced options',1; RECONFIGURE; EXEC sp_configure 'max server memory (MB)',8192; RECONFIGURE;"
$check=Invoke-LabSql "SELECT SERVERPROPERTY('Edition') AS Edition,SERVERPROPERTY('ProductVersion') AS Version;"
if($check.Edition -notmatch 'Enterprise Edition: Core-based Licensing'){throw 'Wrong SQL media/edition; do not onboard PAYG without review.'}
$check
if($p.ExitCode -eq 3010){Write-Warning 'Setup requests a restart: restart the guest in a planned maintenance window; no automatic reboot was performed.'}
