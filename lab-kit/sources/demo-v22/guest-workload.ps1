param([ValidateSet('Prepare','Baseline','WarmCache','GrantLoad','Recovery')][string]$Stage, [int]$Seconds = 180)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Wrong guest' }
$root = 'C:\HV-Demo'
function Set-Stage([string]$Name) { [IO.File]::WriteAllText("$root\stage.txt", $Name) }
$connection = New-Object Data.SqlClient.SqlConnection('Server=localhost;Database=OrdersDemo;Integrated Security=true;Application Name=HV-DEMO-MEMORY;Connect Timeout=30')
try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandTimeout = 600
    switch ($Stage) {
        'Prepare' {
            Set-Stage 'prepare'
            $command.CommandText = @"
IF OBJECT_ID('dbo.OrderLines','U') IS NULL
 CREATE TABLE dbo.OrderLines(Id int NOT NULL PRIMARY KEY, GroupKey int NOT NULL, Payload char(1024) NOT NULL);
IF NOT EXISTS(SELECT 1 FROM dbo.OrderLines)
BEGIN
 WITH digits AS (SELECT n FROM (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9))v(n)),
 numbers AS (SELECT TOP(250000) ROW_NUMBER() OVER(ORDER BY (SELECT NULL)) AS n
 FROM digits a CROSS JOIN digits b CROSS JOIN digits c CROSS JOIN digits d CROSS JOIN digits e CROSS JOIN digits f)
 INSERT dbo.OrderLines(Id,GroupKey,Payload)
 SELECT CONVERT(int,n), CONVERT(int,n%997), REPLICATE(CHAR(65+CONVERT(int,n%26)),1024) FROM numbers;
 CHECKPOINT;
END;
SELECT COUNT_BIG(*) FROM dbo.OrderLines;
"@
            $rows = $command.ExecuteScalar()
            "Synthetic OrderLines rows=$rows; no business data."
            Set-Stage 'idle'
        }
        'Baseline' { Set-Stage 'baseline'; Start-Sleep -Seconds $Seconds }
        'WarmCache' {
            Set-Stage 'warm-cache'
            $deadline = (Get-Date).AddSeconds($Seconds)
            $command.CommandText = 'SELECT SUM(CONVERT(bigint,CHECKSUM(Payload))) FROM dbo.OrderLines OPTION(MAXDOP 1)'
            do { $null = $command.ExecuteScalar(); Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline)
        }
        'GrantLoad' {
            Set-Stage 'query-grants'
            # A deliberately generous bounded workspace makes allocated-versus-used visible; this is not production tuning advice.
            $command.CommandText = 'SELECT Id,GroupKey,Payload FROM dbo.OrderLines ORDER BY CHECKSUM(Id,GroupKey),Payload OPTION(MAXDOP 1,MIN_GRANT_PERCENT=30,MAX_GRANT_PERCENT=40)'
            $reader = $command.ExecuteReader()
            $deadline = (Get-Date).AddSeconds($Seconds)
            $count = 0
            try {
                while ($reader.Read() -and (Get-Date) -lt $deadline) {
                    $count++
                    if ($count % 16 -eq 0) { Start-Sleep -Milliseconds 20 }
                }
            }
            finally { $command.Cancel(); $reader.Close() }
            "Bounded sort query returned $count rows; grant is now released."
        }
        'Recovery' { Set-Stage 'recovery'; Start-Sleep -Seconds $Seconds }
    }
}
finally { $connection.Dispose(); if ($Stage -ne 'Prepare') { Set-Stage 'idle' } }
"Completed stage $Stage; SQL service=$((Get-Service MSSQLSERVER).Status)."
