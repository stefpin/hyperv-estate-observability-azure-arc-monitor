# Managed Grafana dashboards

Eleven Azure Managed Grafana dashboards in four families. Every dashboard is **read-only**: it queries existing telemetry
(Log Analytics through the Azure Monitor data source and Azure Resource Graph) and never changes the lab.

| Family | Folder | Dashboards (uid) | Data source uid |
|---|---|---|---|
| Operations | [`grafana/operations`](grafana/operations/) | **Infrastructure & SQL Operations Cockpit** (`hv-operations-cockpit`), **PDF & Excel Evidence Report** (`hv-operations-report`) | `hv-azure-monitor` |
| Command Center V1 | [`grafana/command-center-v1`](grafana/command-center-v1/) | Estate Overview (`hv-cc-estate`), Selected Workload Deep Dive (`hv-cc-workload`), Incident Investigation (`hv-cc-incident`) | `hv-cc-azure-monitor` |
| Command Center V2 | [`grafana/command-center-v2`](grafana/command-center-v2/) | 01 Estate attention (`hv-cc-v2-estate`), 02 Workload evidence (`hv-cc-v2-workload`), 03 Incident investigation (`hv-cc-v2-incident`) | `hv-cc-v2-azure-monitor` |
| Command Center V3 Core | [`grafana/command-center-v3-core`](grafana/command-center-v3-core/) | 01 Estate attention (`hv-cc-v3-core-estate`), 02 Guided workload evidence (`hv-cc-v3-core-workload`), 03 Incident replay & handoff (`hv-cc-v3-core-incident`) | `hv-cc-v3-core-azure-monitor` |

The families are alternative designs of the same questions, kept side by side so that you can compare them:

* **Operations** - one cockpit page plus a report page that is also the source of the native PDF export. It shows host
  saturation, per-guest P95 dispatch wait, guest-reported CPU, memory, SQL and storage.
* **Command Center V1** - estate overview, selected-workload deep dive and incident investigation with per-vCPU run time.
* **Command Center V2** - native Grafana panels, an explicit contrast between guest-reported CPU and the fixed host's
  hypervisor CPU, dispatch wait as sample P95 and a per-vCPU hot-spot matrix.
* **Command Center V3 Core** - V2 plus guided evidence, a configured-estate graph, hypotheses that cite the panels they
  rest on, and an incident replay page with "return to live" links.

The report dashboard used by the automated shift e-mail (`hv-shift-health-report`) is **not** stored here: the
[shift-report](../shift-report/) application generates it at run time from frozen evidence.

## Import

Each family expects an Azure Monitor data source with the uid in the table above (you can use one Grafana instance per
family, as the reference lab did, or one instance with four data sources - the uid is what the panels refer to).

```powershell
az extension add --name amg
$grafana = '<your-grafana-name>'; $rg = '<your-resource-group>'

# 1. Azure Monitor data source with the uid the dashboards use (managed identity authentication)
$definition = @{
    name = 'hv-azure-monitor'; uid = 'hv-azure-monitor'; type = 'grafana-azure-monitor-datasource'; access = 'proxy'
    jsonData = @{ azureAuthType = 'msi'; subscriptionId = '<SUBSCRIPTION_ID>' }
} | ConvertTo-Json -Depth 5 -Compress
az grafana data-source create -n $grafana -g $rg --definition $definition

# 2. Dashboards of one family
Get-ChildItem .\monitoring\grafana\operations\*.json | ForEach-Object {
    az grafana dashboard import -n $grafana -g $rg --definition $_.FullName --overwrite true
}
```

Give the Grafana managed identity read access to the two Log Analytics workspaces and to the resource group (Resource
Graph panels), for example *Log Analytics Reader* and *Reader*. Dashboards use the `browser` time zone; the documentation
uses UTC+7 as its worked example ("LT"), so set your own display time zone in Grafana if you want the same reading.

## Things to know

* **Recorded windows.** Some panels and links ("Recorded ...", "HISTORICAL REPLAY") point at time windows that were
  recorded in the reference lab. In your environment they show no data until you record your own scenes; change the `from`
  and `to` values in the link or use the time picker.
* **Machine variable.** The `machine` (and, on the operations dashboards, `member`) variables are custom variables with the
  six lab machine names. Edit them if your machines are called something else.
* **Names are consistent with the lab kit.** Panels query `Perf`, `Heartbeat`, `HvSqlMemory_CL`, `HvLinuxDisk_CL` and
  `ConfigurationChange` in `law-arc-monitor-lab` and `law-arc-ct-sea`, and scope Resource Graph to
  `rg-hyperv-arc-monitor-demo`. Run `tools/Set-RepoContext.ps1` (`-IncludeDocs` is not needed) to replace the placeholders
  in these files.
* **Banner.** Text panels embed a neutral generated banner as a data URI; replace it with your own artwork if you like.
* **Reading guides.** [`docs/demo/02`](../docs/demo/02-reading-dashboards-anatomy-and-method.md) to
  [`05`](../docs/demo/05-reading-cards-and-worked-examples.md) explain how to read each panel type, and Acts 9 to 11 of the
  storyline walk through the dashboards.
