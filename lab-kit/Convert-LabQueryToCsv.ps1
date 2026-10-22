param([Parameter(Mandatory=$true)][string]$JsonPath,[Parameter(Mandatory=$true)][string]$CsvPath)
$ErrorActionPreference='Stop'
$data=Get-Content -LiteralPath $JsonPath -Raw | ConvertFrom-Json
if($data.tables){
    $table=$data.tables[0]
    $rows=@(foreach($row in $table.rows){
        $value=[ordered]@{}
        for($i=0;$i -lt $table.columns.Count;$i++){$value[$table.columns[$i].name]=$row[$i]}
        [pscustomobject]$value
    })
}else{$rows=@($data)}
if($rows.Count -eq 0){throw 'No query rows: refusing an apparently successful empty report.'}
$rows | Export-Csv -LiteralPath $CsvPath -NoTypeInformation -Encoding UTF8
Write-Output "CSV written with $($rows.Count) real rows."
