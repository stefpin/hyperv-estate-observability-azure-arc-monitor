# 17. CPU contention, response time and the tagged Windows group

This chapter explains the host-side CPU contention metric that a guest cannot see from inside itself, shows how to run a bounded CPU scene on the three noisy-neighbour Windows guests, how to keep baseline, load and recovery windows separate, and how to read the tagged Windows group summary and the local HTTP response time of the RHEL guest. A noisy neighbour is a guest that uses enough of the shared host CPU to slow down other guests on the same host; the "victim" is the light RHEL web server. Use it after the monitoring data is flowing ([chapter 11](11-azure-monitor-agent-and-dcrs.md)); the workbook sections it refers to are described in [chapter 18](18-workbook.md).

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. Commands marked as running on the host assume the lab kit copy in `F:\Build\lab-kit` on `HV-HOST-01` (`Copy-LabPublicSources.ps1 -Target Host`, [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)). The copy helper does not target the Windows noisy-neighbour guests or the RHEL guest, so `cpu-burn.ps1` and the `http-latency-*.sh` helpers reach a guest only if you transfer them yourself, as shown in the steps below.

## 17.1 The metric the guest cannot see

**What you are doing:** you explain a host-side CPU contention metric that the guest cannot see from inside itself.

In the workbook, use the Azure Portal and follow this path:

1. Open the workbook.
2. Go to the first panels of the workbook, **Host hypervisor processor utilization (%)** and **Per-guest scheduling wait**.
3. Show host CPU.
4. Show each guest's Hyper-V virtual processor runtime.
5. Show **CPU Wait Time Per Dispatch**.

Explain this plainly: a busy guest can wait for a host processor before it is scheduled. Its own guest CPU chart does not show that host scheduling wait. The host's logical processors are shared by all guests, so when more virtual processors are ready to run than the host has logical processors, some of them have to wait their turn, and only the host can see that waiting.

> **Warning:** CPU wait is a time per dispatch (nanoseconds per dispatch in this lab), **not** a percentage, and it is not a "CPU ready percent". Never read it as a share of CPU capacity.

The supplied `lab-kit/queries/cpu-wait.kql` filters to the host computer `HV-HOST-01`, takes the VM name from the Hyper-V instance name (the text before the colon) and reports the raw counter average as `WaitNs`, so the unit stays visible.

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell.** This is read-only.

```powershell
Get-Counter -ListSet 'Hyper-V Hypervisor Virtual Processor' |
  Select-Object -ExpandProperty PathsWithInstances
Get-Counter '\Hyper-V Hypervisor Virtual Processor(*)\CPU Wait Time Per Dispatch'
```

**What you should see:** virtual processor samples for each guest. **Wait is a time per dispatch, not a percentage.** The supplied query records the raw units and the conversion; keep both the raw and the labelled displayed values. Do not average an already-summed sample as if it were host utilization. For orientation only: in an earlier validation run, host CPU rose from about 11% to about 93% while the wait rose roughly fiftyfold. Treat that as an order of magnitude, not as the result to expect from the scene in section 17.2.

## 17.2 Run a bounded three-guest CPU scene

**What you are doing:** you start a controlled CPU load on the three noisy-neighbour Windows guests only. The load is bounded and self-terminating.

Follow these steps:

1. From Bastion on the host, open PowerShell Direct to each of `WIN2019-GUEST`, `WIN2022-GUEST` and `WIN2025-GUEST-01`.
2. Confirm the pre-run checks first: SQL is running and no other load scene is active.
3. Execute the supplied `lab-kit/Start-LabCpuScene.ps1` or the guest workload only after that confirmation.
4. The orchestrator creates four bounded workers on **each of the three guests**.
5. Do not start a SQL workload.
6. Do not burn the host itself.
7. Keep the RHEL nginx request sampler light.

There are three ways to run the same bounded scene. Each starts four self-terminating workers on each of the three Windows noisy neighbours and none on the SQL guest, and each runs for a fixed duration, not indefinitely:

- **Host wrapper:** `lab-kit/Start-LabCpuScene.ps1` runs only on `HV-HOST-01` (it stops with `Execute only on the host.` elsewhere), prompts privately for the `labadmin` password of each of the three guests, and accepts `-Seconds` from 30 to 900 (default 240, four minutes).
- **From the operator PC through Arc Run Command:** `lab-kit/demo/host-cpu-rehearsal.ps1` takes the three guest passwords as protected parameters (`Win2019PasswordHex`, `Win2022PasswordHex`, `Win2025PasswordHex`) and `LoadSeconds` from 240 to 900 (default 240). It also records the baseline, loaded and recovery windows (see [section 17.3](#173-baseline-load-and-recovery-are-separate-windows)). `lab-kit/email/real-alert-test.ps1` ([chapter 19](19-alerts.md)) and `lab-kit/sources/demo-v22/run-cpu-storage-rehearsal.ps1` call the identical copy in `lab-kit/sources/demo-v22`; the latter ran the 900-second reference scene below followed by the 180-second storage scene of [section 16.4](16-storage-telemetry.md#164-a-safe-storage-only-demonstration).
- **Inside one guest:** `lab-kit/cpu-burn.ps1` accepts `-Seconds` from 30 to 600 (default 300) and runs only on the three noisy-neighbour guests. The lab-kit copy helper does not target those guests, so place the file in the guest first (for example in `C:\lab-kit`) and run it from there.

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell.** The wrapper prompts privately for the credentials of the three Windows guests only.

```powershell
Set-Location F:\Build\lab-kit
.\Start-LabCpuScene.ps1 -Seconds 300
```

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**
>
> Do this on: your own computer, in the `lab-kit` folder with the lab context loaded. Use it instead of the host wrapper when you do not want to type the guest passwords. The passwords are read from the private `ENVIRONMENT.txt` in the repository root ([Chapter 2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)) and sent only as protected parameters; the one-time SSH preparation that follows the command is required first.

```powershell
$settings = Get-LabSettings
$protected = @{
    Win2019PasswordHex = (ConvertTo-LabHex $settings.WIN2019_GUEST_PASSWORD)
    Win2022PasswordHex = (ConvertTo-LabHex $settings.WIN2022_GUEST_PASSWORD)
    Win2025PasswordHex = (ConvertTo-LabHex $settings.WIN2025_GUEST_PASSWORD)
}
$settings = $null
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\demo\host-cpu-rehearsal.ps1 `
  -Parameters @{ LoadSeconds = '900' } -Protected $protected -TimeoutSeconds 2400
$protected = $null
```

`host-cpu-rehearsal.ps1` also reads the RHEL `hv-http-latency` observer ([chapter 8](08-rhel-guest-and-linux-collectors.md)) from the host over SSH without a password prompt. It expects the private key `F:\Build\ssh\rhel_ed25519` and the pinned host-key file `F:\Build\ssh\known_hosts` on the host and connects as `labadmin@192.168.100.14` with strict host-key checking. The lab kit does not create these two files. Prepare them once with the standard OpenSSH tools, and compare the host-key fingerprint that SSH shows with the one printed on the RHEL console before you answer `yes`.

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell.** The `ssh-keygen` command asks for a passphrase: press Enter twice, because the scene runs unattended and cannot type one. The `scp` command asks for the private RHEL password. Keep the private key only on the host.

```powershell
New-Item -ItemType Directory -Force -Path F:\Build\ssh | Out-Null
ssh-keygen.exe -q -t ed25519 -f F:\Build\ssh\rhel_ed25519
scp.exe -o User=labadmin F:\Build\ssh\rhel_ed25519.pub 192.168.100.14:hv-host.pub
```

> **RUN ON - RHEL94-GUEST, Bash, through SSH**

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat ~/hv-host.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
rm ~/hv-host.pub
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell.** SSH shows the host-key fingerprint on the first connection; compare it with the fingerprint printed in the previous step, then answer `yes`. The command asks for nothing else once the key is accepted by RHEL.

```powershell
ssh.exe -i F:\Build\ssh\rhel_ed25519 -o UserKnownHostsFile=F:\Build\ssh\known_hosts `
  -o StrictHostKeyChecking=ask labadmin@192.168.100.14 'systemctl is-active hv-http-latency'
```

**What you should see for the key check:** the single word `active`, and a second run that connects without any prompt.

> **RUN ON - one noisy-neighbour Windows guest (inside the guest), elevated PowerShell**

```powershell
.\cpu-burn.ps1 -Seconds 300
```

**What you should see:** four child processes start, their PIDs are recorded, and they stop at the deadline in a `finally` block. The host wrapper prints `Started bounded workers on <guest>; SQL guest not loaded.` for each guest and, at the end, `Only recorded bounded CPU worker PIDs cleaned up; SQL remains running.` `cpu-burn.ps1` prints `Four bounded CPU workers; PIDs=<list>; duration=<n> seconds.` The Arc route prints one summary line per window (`baseline`, `loaded`, `recovery`: host CPU average, RHEL mean scheduling wait, samples, and the RHEL localhost HTTP mean and P95 of the last 300 samples), one `Bounded CPU workers on <guest>: <PIDs>; auto-exit in <n> seconds.` line per guest, and ends with `CPU-REHEARSAL-DONE: worker processes were self-terminating; no SQL service stopped.` It also writes `F:\Build\hv-cpu-baseline.csv`, `hv-cpu-loaded.csv` and `hv-cpu-recovery.csv` on the host. If you must stop early, use Ctrl+C in the controlling console. The finalizer stops only those child PIDs.

> **Warning:** Never run `Stop-Process -Name powershell` or kill unrelated agents. Confirm recovery before SQL memory tests.

## 17.3 Baseline, load and recovery are separate windows

**What you are doing:** you keep the measurement windows separate so the comparison is valid. Do not mix quiet time, load time and recovery time into one average.

In the Azure Portal, do this:

1. Record the UTC start and end of at least five quiet minutes.
2. Record the UTC start and end of at least five load minutes.
3. Record the UTC start and end of at least five recovery minutes.
4. If you use the scripted scene instead, note that its windows may be shorter than five minutes; record the actual windows it uses. The Arc scene `host-cpu-rehearsal.ps1` samples every 5 seconds: a 30-second baseline before the workers start, a 150-second loaded window that starts 45 seconds after they start, and a 60-second recovery window that starts when the workers' deadline passes.
5. In the workbook, open the time picker.
6. Choose **Custom**.
7. Enter the exact corresponding boundaries.
8. Click **Apply**.

Read the HTTP response from the RHEL terminal, not from a fabricated Azure HTTP tile. Do not average "last 30 minutes" together and call it a controlled baseline.

Use `lab-kit/queries/cpu-wait.kql`, `lab-kit/queries/host-cpu.kql` and the guest-local `lab-kit/http-latency-stats.sh`. The installed `hv-http-latency` service does not copy that helper to the guest: transfer it with `scp` from the host exactly as `http-latency-live.sh` is transferred in [section 17.4](#174-cluster-summary-and-per-machine-detail), then run `bash ~/http-latency-stats.sh`. It reads the last 300 samples of `/var/log/hv-demo/http-latency.json` and prints their mean, P95, maximum and failure count. Replace the KQL's default `> ago(30m)` with a `between` filter that uses the exact ISO timestamps you recorded for the window:

```kql
| where TimeGenerated between (datetime(<START_UTC>) .. datetime(<END_UTC>))
```

`<START_UTC>` and `<END_UTC>` are placeholders for your own recorded boundaries, not literal query values. Save each result.

Important interpretation rules:

- HTTP is a **local observer**, not a deployed `HvHttpLatency` custom table.
- Expected: load affects host CPU and wait; a response-time change, if demonstrated, is recorded quantitatively.
- If the victim's wait is not the highest, do not say it is.
- If the HTTP response does not degrade, report the limitation rather than inventing an outage.

## 17.4 Cluster summary and per-machine detail

**What you are doing:** you show the tagged Windows group summary and then the individual guest details. This is a monitoring group only, not Windows Server Failover Clustering (WSFC).

In the Azure Portal, follow these steps:

1. Open the workbook.
2. Go to the **WIN-CLUSTER-01** section.
3. Confirm the member list first.
4. Show group CPU, memory and wait.
5. Then show the separate guest series.
6. Say clearly: "tagged monitoring group, not WSFC."
7. Note that the SQL guest is shown separately and excluded from group aggregation.

> **Say this:** "This is a tagged monitoring group, not WSFC."

For the query route, use Resource Graph or Arc tag inventory within this resource group, then use the cluster queries in `lab-kit/queries/` (`cluster-cpu.kql`, `cluster-memory.kql` and `cluster-contention.kql`). They select the three members by name (`WIN2019-GUEST`, `WIN2022-GUEST`, `WIN2025-GUEST-01`): `cluster-cpu.kql` returns the group mean `ClusterCPU` and the busiest member; `cluster-memory.kql` converts each member's `Available Bytes` against its 8 GiB of memory into a used percentage and returns the group mean and the busiest member; `cluster-contention.kql` returns the mean and the 95th percentile of the members' CPU wait per dispatch in nanoseconds. For group CPU, use an explicitly labelled mean or weighted mean consistent with the equal four-vCPU members, not the sum of three percentages. For memory utilization, physical used/total weighted across members is preferable to summing percentages; record the formula you use.

**What you should see:** exactly three members, plus both group-level and per-guest observations. The wait ratio uses each guest's own quiet baseline. Missing samples or no samples do not mean zero utilization. CPU ratios are not a universal consolidation policy.

**Reference results.** A reference CPU scene used twelve self-terminating workers (four on each of the three Windows noisy neighbours) for **900 seconds**, with SQL idle and Running:

| Measure | Baseline | Load | Recovery |
|---|---|---|---|
| Host CPU | 25.82 % | 94.44 % | 17.03 % |
| RHEL mean dispatch wait (ns) | 48,408.94 | 85,539.54 | 19,161.43 |
| Localhost HTTP mean (ms) | 1.623 | 2.857 | 1.353 |
| Localhost HTTP P95 (ms) | 4.357 | 7.843 | 1.928 |

The Windows noisy neighbours had higher wait than RHEL; do not say the light victim was the worst-waiting guest. The HTTP statistics come from rolling windows of the last 300 samples. They are local observations, not a network benchmark from a remote client. If you cannot run the full 15-minute scene, use a recorded replay and label it clearly as a replay (see [section 18.3](18-workbook.md#183-historical-replay-is-allowed-only-when-labelled)).

For a live HTTP comparison without installing or replacing any observer service, use this route:

1. Open **Bastion** to the host.
2. SSH to RHEL from the host.
3. First transfer the public source from the host.
4. Verify the SSH host key before accepting it.
5. Enter only the private RHEL password when prompted.

> **RUN ON - Hyper-V host (HV-HOST-01), PowerShell.** This step transfers public source only.

```powershell
$rhelHost = '192.168.100.14'
scp.exe "F:\Build\lab-kit\http-latency-live.sh" `
  "labadmin@${rhelHost}:~/http-latency-live.sh"
```

> **RUN ON - RHEL94-GUEST, Bash terminal.** Run this separately during quiet, load and recovery.

```bash
bash ~/http-latency-live.sh 60
```

**What you should see:** the bounded helper takes 60 localhost curl samples with a one-second delay (it accepts 5 to 300 samples and runs only on `RHEL94-GUEST`), prints the mean, P95, failures and UTC boundaries, and writes no file. It is a supplied repeat helper; it does not require the optional `hv-http-latency` service to be installed.
