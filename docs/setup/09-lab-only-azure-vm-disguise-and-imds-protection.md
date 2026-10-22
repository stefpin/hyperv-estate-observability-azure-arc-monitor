# 9. Lab-only Azure-VM disguise and IMDS protection

This chapter explains the lab simulation boundary: the lab-only measures that let the outer Azure VM stand in for an on-premises server, and how to verify that the Azure Instance Metadata Service (IMDS), the metadata endpoint at `169.254.169.254`, is not reachable from the host or from the nested guests. These steps are only for the lab behavior described here. Before you start, the host and the guests must be built ([Chapter 5](05-create-the-hyper-v-host.md) to [Chapter 8](08-rhel-guest-and-linux-collectors.md)). On an existing lab, the checks in this chapter are read-only inspection; the changes marked "fresh build" are applied only when you build the lab from scratch. On a fresh build the order is: the machine variable and the metadata block on the host (section 9.2), the metadata block on RHEL (section 9.3), Azure Arc onboarding ([Chapter 10](10-azure-arc-onboarding.md)), and finally `host-azure-vm-disguise.ps1` through Arc Run Command (section 9.4).

## 9.1 Why this exists and what it cannot prove

**What you are doing:** you are understanding the limits of this lab setup before making any changes. This helps you explain the lab honestly and avoid claiming production support where it does not exist.

Arc-enabled server onboarding is intended for non-Azure servers. The lab's outer Azure VM is deliberately configured as a lab simulation; it is not a supported production pattern for disguising Azure VMs as physical servers. Removing or disabling the Azure VM guest agent affects VM Run Command, password reset and extensions. The Arc agent and Arc Run Command are a different plane. Keep Bastion credentials safe; do not promise that Azure VM password reset remains available.

In Azure Portal, inspect the two management planes separately:

1. Go to **Virtual machines**.
2. Open `HV-HOST-01`.
3. Click **Extensions + applications** to see the Azure VM plane.
4. Then go to **Azure Arc**.
5. Open **Machines**.
6. Open `HV-HOST-01`.
7. Click **Extensions** to see the Arc plane.

Explain the difference, rather than deleting every extension blindly. On an existing lab, inspect only.

> **RUN ON - Operator PC, PowerShell with Azure CLI**
>
> Do this on: your own computer, in PowerShell with Azure CLI.

```powershell
az vm extension list -g $RG --vm-name HV-HOST-01 --query "[].{Name:name,State:provisioningState}" -o table
az connectedmachine extension list -g $RG --machine-name HV-HOST-01 `
  --query "[].{Name:name,State:provisioningState}" -o table
```

**What you should see:** Arc extensions appear as distinct resources from the Azure VM extensions. Do not remove AMA or Defender from the Arc plane while attempting a host simulation.

## 9.2 Host and Windows nested guest metadata reachability

**What you are doing:** you are checking whether the metadata endpoint is reachable from the host or from a Windows nested guest after the lab-only protection has been applied.

Before making any fresh-build change, inspect `lab-kit/host-azure-vm-disguise.ps1` (section 9.4). It does not create the metadata block itself: it disables the Azure VM guest agent only if the machine variable `MSFT_ARC_TEST` and the firewall rule `BlockAzureIMDS` already exist on the host. On a fresh build, create both first. This is the evaluation procedure that Microsoft documents for Azure Arc-enabled servers on an Azure VM ([Chapter 27](27-references.md)); the machine variable lets the Azure Connected Machine agent install on an Azure VM for evaluation, and the rule blocks outbound access from the host to the metadata endpoint.

> **RUN ON - Hyper-V host, elevated PowerShell, fresh build only, before Arc onboarding**
>
> Do this on: the Hyper-V host, in an elevated PowerShell window. Do not run it on an existing lab: both settings are already in place there.

```powershell
[Environment]::SetEnvironmentVariable('MSFT_ARC_TEST', 'true', [EnvironmentVariableTarget]::Machine)
New-NetFirewallRule -Name BlockAzureIMDS -DisplayName 'Block access to Azure IMDS' `
  -Enabled True -Profile Any -Direction Outbound -Action Block -RemoteAddress 169.254.169.254
```

On nested Windows guests, confirm the protected route is unavailable. There is no need to alter application-facing TLS or outbound Azure service connectivity.

> **RUN ON - Hyper-V host or a Windows guest, elevated PowerShell**
>
> Do this on: the Hyper-V host or a Windows guest, in an elevated PowerShell window. The machine variable and the `BlockAzureIMDS` rule are checked on the host; on a guest, the connection test is the relevant check.

For read-only verification, run:

```powershell
[Environment]::GetEnvironmentVariable('MSFT_ARC_TEST', 'Machine')
Test-NetConnection 169.254.169.254 -Port 80 -WarningAction SilentlyContinue
Get-NetFirewallRule -Name BlockAzureIMDS -ErrorAction SilentlyContinue |
  Select-Object Name,DisplayName,Enabled,Direction,Action
```

**What you should see:** `true` for the machine variable, and the metadata endpoint should be unreachable (`TcpTestSucceeded : False`). The rule `BlockAzureIMDS` is listed as `Enabled True`, `Outbound`, `Block`. The short TCP test is not a request for an identity token. Do not display tokens if diagnosing identity endpoints. The host can still have `ComputerEnvironment=Azure` in Heartbeat; the reported fact is recorded, not suppressed deceptively. For a Windows guest, `lab-kit/verify-guest.ps1` ([section 7.3](07-build-the-guests.md#73-verify-and-remove-installation-dvds)) also reports whether the metadata service is reachable from inside that guest.

## 9.3 RHEL can reach host-routed IMDS unless explicitly blocked

**What you are doing:** you are applying the Linux-side metadata block so the RHEL guest cannot reach IMDS through the host route.

> **RUN ON - RHEL94-GUEST, Bash, fresh build**
>
> Do this on: `RHEL94-GUEST`, in Bash, for fresh-build protection. Keep SELinux enforcing and the default crypto policy. Use a dedicated egress rule, not a broad firewall shutdown.

```bash
sudo firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 0 \
  -d 169.254.169.254/32 -j REJECT
sudo firewall-cmd --reload
curl --max-time 3 -sS -H Metadata:true \
  'http://169.254.169.254/metadata/instance?api-version=2021-02-01'
```

**What you should see:** `curl` should fail or return no metadata, while general HTTPS should still work. Verify with `sudo firewall-cmd --direct --get-all-rules`. A timeout is expected for metadata, not for Arc regional endpoints. Never turn off firewalld or SELinux as an Arc troubleshooting shortcut.

## 9.4 Disable the Azure VM guest agent on the host (fresh build, after Arc onboarding)

**What you are doing:** you finish the disguise by disabling the Azure VM guest agent on the host and proving that the setting survives a restart. Do this once, only on a fresh build, and only after `HV-HOST-01` shows **Connected** in Azure Arc ([Chapter 10](10-azure-arc-onboarding.md)), because the script runs through Arc Run Command. On an existing lab, do not run it again.

`lab-kit/host-azure-vm-disguise.ps1` runs on `HV-HOST-01`. It first lists every Hyper-V guest with its stop and start action and stops without changing anything unless every guest is set to **Save** and **Start** ([section 7.1](07-build-the-guests.md#71-windows-media-and-three-noisy-neighbours)). It also stops without changing anything if the machine variable `MSFT_ARC_TEST` is not `true` (`MSFT_ARC_TEST is not set - nothing changed`) or if the firewall rule `BlockAzureIMDS` is missing (`Metadata block missing - nothing changed`). Then it disables and stops the `WindowsAzureGuestAgent` service, reports the state of the `RdAgent` service, and schedules a restart of the host 90 seconds later (`shutdown /r /t 90`), so that the script can report back before the restart and you can confirm that the disguise survives a reboot. The restart saves and resumes the guests; it does not reboot them. From now on the Azure Portal can no longer use Run Command or reset the password on the Azure VM resource of `HV-HOST-01`; Arc Run Command and Bastion remain.

> **RUN ON - Operator PC, PowerShell in the lab-kit folder, fresh build only**
>
> Do this on: your own computer, in the `lab-kit` folder, after loading the lab context and signing in as described in [Chapter 2](02-tools-secrets-and-conventions.md). Choose a time when nobody is using the lab: the host restarts about 90 seconds after the script ends.

```powershell
. .\context.ps1
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\host-azure-vm-disguise.ps1 -TimeoutSeconds 600
```

**What you should see:** a `guests:` line that lists every guest with `stop=Save` and `start=Start`, then `WindowsAzureGuestAgent now Stopped/Disabled`, an `RdAgent service:` line (state and start type, or `not present`) and `restart scheduled at <time> (+90 s), shutdown exit 0`. After the restart, reconnect to the host through Bastion and check the result:

> **RUN ON - Hyper-V host, elevated PowerShell**
>
> Do this on: the `HV-HOST-01` virtual machine itself, after it has restarted and you have connected again through Bastion.

```powershell
Get-Service WindowsAzureGuestAgent | Select-Object Name,Status,StartType
Get-VM | Select-Object Name,State
```

**What you should see:** `WindowsAzureGuestAgent` is `Stopped` and `Disabled`, every guest returns to `Running` within a few minutes, and `HV-HOST-01` shows **Connected** again in **Azure Arc > Machines**.
