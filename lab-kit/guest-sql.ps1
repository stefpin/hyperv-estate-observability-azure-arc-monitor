$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Run SQL helpers only on SQL2019-GUEST.' }
function Invoke-LabSql {
    param([string]$Query,[int]$TimeoutSeconds=120)
    $c=New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Application Name=HV-LabKit;Connect Timeout=15')
    try {
        $c.Open();$cmd=$c.CreateCommand();$cmd.CommandText=$Query;$cmd.CommandTimeout=$TimeoutSeconds
        $adapter=New-Object Data.SqlClient.SqlDataAdapter($cmd)
        $data=New-Object Data.DataSet
        $null=$adapter.Fill($data)
        foreach ($table in $data.Tables) { foreach ($row in $table.Rows) {
            $obj=[ordered]@{};foreach($column in $table.Columns){$obj[$column.ColumnName]=$row[$column]}
            [pscustomobject]$obj
        } }
    } finally {$c.Dispose()}
}
function Invoke-LabSqlScalar([string]$Query) {
    $c=New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Connect Timeout=15')
    try {$c.Open();$cmd=$c.CreateCommand();$cmd.CommandText=$Query;$cmd.ExecuteScalar()}finally{$c.Dispose()}
}
