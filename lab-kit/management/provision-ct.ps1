. "$PSScriptRoot\common.ps1"
$workspace = "$HvRoot/providers/Microsoft.OperationalInsights/workspaces/law-arc-ct-sea"
$dcr = "$HvRoot/providers/Microsoft.Insights/dataCollectionRules/dcr-sql2019-change-tracking"
Invoke-HvRest PUT "$workspace`?api-version=2023-09-01" @{
    location = 'southeastasia'
    tags = @{ purpose = 'HV-demo-ChangeTracking' }
    properties = @{
        sku = @{ name = 'PerGB2018' }
        retentionInDays = 30
        features = @{ enableLogAccessUsingOnlyResourcePermissions = $true }
        publicNetworkAccessForIngestion = 'Enabled'
        publicNetworkAccessForQuery = 'Enabled'
    }
} 'ct-workspace.json' | Out-Null
$solutionName = 'ChangeTracking(law-arc-ct-sea)'
Invoke-HvRest PUT "$HvRoot/providers/Microsoft.OperationsManagement/solutions/$solutionName`?api-version=2015-11-01-preview" @{
    location = 'southeastasia'
    properties = @{ workspaceResourceId = $workspace }
    plan = @{ name = $solutionName; product = 'OMSGallery/ChangeTracking'; promotionCode = ''; publisher = 'Microsoft' }
} 'ct-solution.json' | Out-Null
$template = Get-Content -LiteralPath "$PSScriptRoot\..\schema\CtDcrCreation.json" -Raw | ConvertFrom-Json
$source = $template.resources[1].properties.template.resources[0].properties.dataSources.extensions[0]
$source.extensionSettings.registrySettings.registryCollectionFrequency = 3000
$source.extensionSettings.registrySettings.registryInfo = @(@{
    name = 'HV-Demo-Registry'; groupTag = 'HV-Demo'; enabled = $true; recurse = $false
    description = 'Harmless dedicated demo key; no SQL settings'; keyName = 'HKEY_LOCAL_MACHINE\SOFTWARE\HV-Demo\ChangeTracking-v22'; valueName = 'DemoState'
})
$source.extensionSettings.fileSettings.fileCollectionFrequency = 1800
$source.extensionSettings.fileSettings | Add-Member NoteProperty fileInfo @(@{
    name = 'HV-Demo-File'; enabled = $true; description = 'Harmless demo fixture only'
    path = 'C:\HV-Demo\ChangeTracking-v22\fixture-demo.txt'; recurse = $false
    pathType = 'File'; type = 'File'; links = 'Follow'; groupTag = 'HV-Demo'
    maxContentsReturnable = 500000; maxOutputSize = 500000
}) -Force
$source.extensionSettings.servicesSettings.serviceCollectionFrequency = 600
$source.extensionSettings.softwareSettings.softwareCollectionFrequency = 1800
$source.extensionSettings.inventorySettings.inventoryCollectionFrequency = 36000
$body = @{
    location = 'southeastasia'; kind = 'Windows'
    tags = @{ purpose = 'HV-demo-ChangeTracking' }
    properties = @{
        description = 'SQL2019-GUEST dedicated CT AMA rule; no changes to shared perf DCRs.'
        dataSources = @{ extensions = @($source) }
        destinations = @{ logAnalytics = @(@{ workspaceResourceId = $workspace; name = 'Microsoft-CT-Dest' }) }
        dataFlows = @(@{ streams = @('Microsoft-ConfigurationChange','Microsoft-ConfigurationChangeV2','Microsoft-ConfigurationData'); destinations = @('Microsoft-CT-Dest') })
    }
}
Save-HvJson 'ct-dcr-request.json' $body
Invoke-HvRest PUT "$dcr`?api-version=2023-03-11" $body 'ct-dcr.json' | Out-Null
Invoke-HvRest PUT "$HvMachine/providers/Microsoft.Insights/dataCollectionRuleAssociations/assoc-SQL2019-GUEST-ct`?api-version=2023-03-11" @{
    properties = @{ dataCollectionRuleId = $dcr; description = 'Dedicated AMA Change Tracking' }
} 'ct-association.json' | Out-Null
& az connectedmachine extension create --subscription $HvSub -g $HvRg --machine-name SQL2019-GUEST --location southeastasia `
    --name ChangeTracking-Windows --publisher Microsoft.Azure.ChangeTrackingAndInventory --type ChangeTracking-Windows `
    --type-handler-version 2.20 --enable-auto-upgrade true --only-show-errors -o json |
    Out-File -LiteralPath "$PSScriptRoot\ct-extension.json" -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'CT extension deployment failed' }
Write-Output 'CT workspace, dedicated DCR, association, and extension provisioned.'
