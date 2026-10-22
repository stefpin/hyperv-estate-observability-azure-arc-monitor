# 8. RHEL 9.4: registration, nginx victim and latency logger

This chapter builds the Linux guest `RHEL94-GUEST`, registers it with Red Hat, and installs the simple demonstration services that later produce useful monitoring data: an nginx web server (the "victim" of the load scenes), an HTTP response-time logger and a block-device storage observer. RHEL means Red Hat Enterprise Linux. SSH is the secure remote terminal connection you use to reach the Linux guest from the host. Before you start, the host must have Hyper-V, the `VmNAT` switch and `LocalNAT` ([Chapter 6](06-host-os-hyper-v-and-guest-network.md)), the lab kit must be on the host at `F:\Build\lab-kit` (see [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)), and you need the RHEL 9.4 x86_64 Binary DVD from your own authorized Red Hat account (see [section 2.3](02-tools-secrets-and-conventions.md#23-secrets-and-media-prerequisites)). The VM creation and installer steps are for the initial build only.

## 8.1 RHEL installation

**What you are doing:** you are downloading the correct RHEL installation ISO and creating the `RHEL94-GUEST` virtual machine in Hyper-V.

> **RUN ON - Hyper-V host, desktop and elevated PowerShell**
>
> Do this on: the Hyper-V host environment for this lab. Use the host desktop browser for the Red Hat download. Use Hyper-V Manager or an elevated PowerShell window on the host for the VM creation.

For the ISO download and Hyper-V wizard:

1. On the host desktop, open a browser.
2. Go to the authorized Red Hat download portal.
3. Choose RHEL.
4. Choose version **9.4**.
5. Choose x86_64.
6. Choose **Binary DVD**, not Boot ISO.
7. Save `F:\ISO\rhel-9.4-x86_64-dvd.iso`.
8. In Hyper-V Manager, create a new VM named `RHEL94-GUEST`.
9. Choose Gen2.
10. Set 8192 MB static memory.
11. Create a 127 GB disk.
12. Connect the VM to `VmNAT`.
13. Set four processors.
14. Open **Settings > Management > Automatic Start Action**, choose **Always start this virtual machine automatically** and set the startup delay to 30 seconds.
15. Open **Settings > Management > Automatic Stop Action** and choose **Save the virtual machine state**. [Chapter 9](09-lab-only-azure-vm-disguise-and-imds-protection.md) checks this setting and the start action on every guest.
16. Open **Settings > Management > Checkpoints** and clear **Use automatic checkpoints**.
17. Open **Settings > Security**.
18. Set the Secure Boot template to **Microsoft UEFI Certificate Authority**, not Microsoft Windows.
19. Start the VM and connect to it.

Inside the RHEL installer, complete the installation carefully:

1. Select Install RHEL 9.4.
2. Choose English.
3. Choose the Server environment.
4. Use automatic storage on the blank VHDX.
5. Keep root login disabled.
6. Create `labadmin` and give it wheel/admin membership.
7. Configure the network manually as `.14/24`.
8. Set the gateway to `.1`.
9. Set DNS to `8.8.8.8,1.1.1.1`.
10. Set the hostname to `RHEL94-GUEST`.
11. Set the time zone to the lab's local time zone, UTC+7 (the same offset as `SE Asia Standard Time` on the Windows machines). In the installer's list, choose a UTC+7 city, for example `Asia/Bangkok`.
12. Keep SELinux enforcing.
13. After installation, remove the DVD in Hyper-V Settings.
14. Reboot into the installed OS.

> **RUN ON - Hyper-V host, elevated PowerShell, initial build only**
>
> Do this on: the Hyper-V host, in an elevated PowerShell window. Only do this during the initial build.

```powershell
New-VM -Name RHEL94-GUEST -Generation 2 -MemoryStartupBytes 8GB `
  -NewVHDPath F:\VMs\RHEL94-GUEST.vhdx -NewVHDSizeBytes 127GB -SwitchName VmNAT
Set-VM -Name RHEL94-GUEST -ProcessorCount 4 -AutomaticCheckpointsEnabled $false `
  -AutomaticStartAction Start -AutomaticStartDelay 30 -AutomaticStopAction Save
Set-VMFirmware -VMName RHEL94-GUEST `
  -SecureBootTemplate MicrosoftUEFICertificateAuthority
Add-VMDvdDrive -VMName RHEL94-GUEST -Path F:\ISO\rhel-9.4-x86_64-dvd.iso
Set-VMFirmware -VMName RHEL94-GUEST `
  -FirstBootDevice (Get-VMDvdDrive -VMName RHEL94-GUEST)
Start-VM RHEL94-GUEST
vmconnect.exe localhost RHEL94-GUEST
```

**What you should see:** the RHEL installer should boot successfully. The interactive RHEL installer has no Azure CLI counterpart; both access paths complete the same guest installation. Do not bypass authorized download/account terms with a cached third-party ISO.

## 8.2 Registration and network validation

**What you are doing:** you are connecting to the Linux guest, confirming that its network settings are correct, and registering the operating system with Red Hat so package repositories are available.

> **RUN ON - Hyper-V host (open the SSH session), then RHEL94-GUEST (Bash)**
>
> Do this on: first the Bastion-connected host, where you open the SSH connection, and then inside the `RHEL94-GUEST` Bash shell itself. Bash is the normal Linux command shell.

To open the Linux session:

1. On the Bastion-connected host, open an elevated PowerShell window.
2. Run `ssh -l labadmin 192.168.100.14` (`-l` sets the user name).
3. Enter the guest's password privately.
4. Wait for the Bash prompt on `RHEL94-GUEST`.

There is no Azure Portal Red Hat registration blade for this nested guest. Execute the following in the resulting **RHEL Bash** shell.

> **RUN ON - RHEL94-GUEST, Bash, through SSH**
>
> Do this on: `RHEL94-GUEST`, in Bash, through the SSH session you just opened.

```bash
hostnamectl
ip -br addr
ip route show default
sudo -v
sudo subscription-manager register
sudo dnf repolist
getenforce
update-crypto-policies --show
```

**What you should see:** the IP should be `.14/24`, the default gateway should be `.1`, and `sudo` should work. You should see BaseOS/AppStream repositories, SELinux should show Enforcing, and the crypto policy should show DEFAULT. Registration prompts for the operator's authorized Red Hat username and password; those are user-provided credentials, never a literal placeholder in a saved command. If repositories are unavailable, do not present Update Manager's absence of packages as fully patched. An offline DVD fallback supplies packages but is not a current patch repository.

If the connection name is unclear, `nmcli -t -f NAME,DEVICE connection show --active` returns it. Use that exact name in quotes for `nmcli connection modify`. Changing networking can interrupt SSH; keep VMConnect open as the recovery console.

## 8.3 HTTP victim and persistent response-time collection

**What you are doing:** you are installing `nginx` (a web server), enabling it, and installing the small observer that writes repeated HTTP response-time measurements to log files for the demo.

> **RUN ON - RHEL94-GUEST, Bash, through SSH**
>
> Do this on: `RHEL94-GUEST`, in the same SSH Bash session from the previous section. Azure Portal cannot start `nginx` inside a nested guest, so this must be done in the Linux terminal.

First, transfer the lab kit script from the host to the Linux guest:

> **RUN ON - Hyper-V host, PowerShell**
>
> Do this on: the Hyper-V host, in a PowerShell window.

```powershell
scp -o User=labadmin F:\Build\lab-kit\install-rhel-observers.sh `
  192.168.100.14:install-rhel-observers.sh
```

After the file transfer finishes, go back to the SSH window for `RHEL94-GUEST` and run:

> **RUN ON - RHEL94-GUEST, Bash, through SSH**
>
> Do this on: `RHEL94-GUEST`, in Bash, through SSH.

```bash
sudo dnf install -y nginx curl sysstat
sudo systemctl enable --now nginx
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://localhost
sudo mkdir -p /var/log/hv-demo
sudo bash ./install-rhel-observers.sh
systemctl is-active hv-http-latency
tail -5 /var/log/hv-demo/http-latency.json
```

**What you should see:** `curl` should return HTTP 200. The `hv-http-latency` service should be active. The log file should contain timestamped response samples in **milliseconds**. The script records curl's time in seconds multiplied by 1,000. It runs one lightweight request every second; this is a lab observation of the nginx victim, not a synthetic application transaction. The service in the lab kit logs to `/var/log/hv-demo`.

## 8.4 Linux disk latency is not a classic AMA Perf counter

**What you are doing:** you are verifying the Linux disk-latency observer and understanding where this data really comes from. AMA means Azure Monitor Agent. DCR means Data Collection Rule, which tells Azure Monitor what to collect and where to send it.

> **RUN ON - RHEL94-GUEST (Linux commands), then Azure Portal (DCR and Logs)**
>
> Do this on: `RHEL94-GUEST` for the Linux commands, and later in Azure Portal when you verify the DCR and Logs output.

In the Linux guest, you are checking the actual storage observer, `hv-storage-collector.service`. It writes timestamp-prefixed JSON lines to `/var/log/hv-storage/disk-YYYYMMDD.log`.

In Azure Portal, verify the monitoring side carefully:

1. Go to the Azure portal.
2. In the search box, find `dcr-linux-guests`.
3. Open the Data Collection Rule.
4. Click **Data sources**.
5. Confirm there is a custom TEXT source plus a JSON-parsing transform.
6. Confirm the output table is `HvLinuxDisk_CL`.
7. Open the Logs view and inspect the actual fields.

Do not select a nonexistent Linux `Avg. Disk sec/Transfer` counter and claim latency is covered.

> **RUN ON - RHEL94-GUEST, Bash, through SSH**
>
> Do this on: `RHEL94-GUEST`, in Bash, through SSH.

```bash
iostat -x -y 15 2
systemctl is-active hv-storage-collector
ls -l /var/log/hv-storage
```

**What you should see:** the output should show the device name and `r_await`, `w_await` in **milliseconds**, plus reads/writes per second and throughput. Ignore iostat's first since-boot report (`-y`) for interval comparisons. A no-I/O device can have zero/empty latency; that is not proof of excellent response under load. If the deployed telemetry schema, logger path or service name differs from what is written here, the verified deployed values take precedence; compare them with `lab-kit/schema/linux-disk-table.json` before redeploying a collector.

If you need a fresh installation of the actual block-device observer, transfer the two lab kit files from the host first. The observer runs `iostat`, which comes from the `sysstat` package installed in section 8.3, and `lsblk`:

> **RUN ON - Hyper-V host, PowerShell**
>
> Do this on: the Hyper-V host, in a PowerShell window.

```powershell
scp -o User=labadmin F:\Build\lab-kit\storage\hv-storage-collector.py `
  192.168.100.14:hv-storage-collector.py
scp -o User=labadmin F:\Build\lab-kit\storage\hv-storage-collector.service `
  192.168.100.14:hv-storage-collector.service
```

Then install and start the observer inside the Linux guest.

> **RUN ON - RHEL94-GUEST, Bash, fresh observer installation only**
>
> Do this on: `RHEL94-GUEST`, in Bash. Only do this for a fresh observer installation.

```bash
sudo install -d -m 0755 /usr/local/libexec /var/log/hv-storage
sudo install -m 0755 hv-storage-collector.py /usr/local/libexec/hv-storage-collector.py
sudo install -m 0644 hv-storage-collector.service /etc/systemd/system/hv-storage-collector.service
sudo systemctl daemon-reload
sudo systemctl enable --now hv-storage-collector
systemctl is-active hv-storage-collector
sudo tail -2 /var/log/hv-storage/disk-$(date -u +%Y%m%d).log
```

**What you should see:** the service should be active, and you should see one timestamp-prefixed JSON row per real block device each **60-second** interval. The script excludes dm/loop/ram/DVD devices to prevent layered double-counting, maps block devices to mounted volumes, and retains seven days of observer files (minimum two full days for AMA tailing). Device counters are not independent per-filesystem latencies; `MountedVolumes` explains which filesystems share the device. Back in Azure Portal, inspect `HvLinuxDisk_CL` and the Linux DCR (`dcr-linux-guests`); the cloud-side deployment is done by `lab-kit/Deploy-LabMonitoring.ps1` (see [Chapter 11](11-azure-monitor-agent-and-dcrs.md)), not by `systemctl`.
