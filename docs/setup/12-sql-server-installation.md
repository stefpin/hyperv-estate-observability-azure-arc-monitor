# 12. SQL data/log disks and SQL Server 2019 installation

This chapter prepares separate virtual disks for SQL Server data and log files on `SQL2019-GUEST`, verifies and mounts the SQL Server 2019 Enterprise Core installation media, installs the default instance with the exact options the lab needs, and verifies the patch level and that the SQL services keep running. Use it when you build the SQL guest. After it, continue with SQL Server enabled by Azure Arc ([chapter 13](13-sql-server-enabled-by-azure-arc.md)) and the memory ceiling ([chapter 14](14-sql-memory-ceiling-and-what-it-means.md)).

> **Before you start:** run the commands marked "your own computer" from the `lab-kit` folder (`cd lab-kit`), in a PowerShell session where `lab-kit/context.ps1` is loaded. The commands use the lab variables and the `Invoke-Lab*` helpers that it provides. Commands marked as running inside the SQL guest assume that the lab-kit scripts they call are in `C:\lab-kit` on `SQL2019-GUEST` (copied there with `Copy-LabPublicSources.ps1 -Target SqlGuest`, see [section 2.4](02-tools-secrets-and-conventions.md#24-copy-the-lab-kit-to-the-host-and-the-sql-guest)) and are run from that folder; the host scripts run through Arc Run Command are sent from your own computer.

> **Note:** `ENVIRONMENT.txt` is the private settings file of the lab. It lives in the repository root, one folder above `lab-kit/`, and is git-ignored. You create it once with `lab-kit/Initialize-LabSecrets.ps1`, which prompts privately for the passwords ([section 2.2](02-tools-secrets-and-conventions.md#placeholders-and-environmenttxt)). It holds the lab's secrets (for example the guest passwords that `Get-LabSettings` returns), so never commit it, print it or paste it into a document.

## 12.1 Additional VHDX files and guest formatting

**What you are doing:** you prepare separate virtual disks for SQL Server data and SQL Server log files. This keeps the demo layout clear and matches the intended storage design. A VHDX is a Hyper-V virtual hard disk file.

In the Azure Portal, first connect to the host and then open the guest VM settings in Hyper-V:

1. Open **Bastion** for the host VM.
2. From the Bastion session, open **Hyper-V Manager**.
3. In Hyper-V Manager, select **SQL2019-GUEST**.
4. Open **Settings**.
5. Select **SCSI Controller**.
6. Select **Hard Drive**.
7. Click **Add**.
8. Click **New**.
9. Create a dynamic `F:\VMs\SQL2019-GUEST-data.vhdx`, 64 GB.
10. Create a dynamic `SQL2019-GUEST-log.vhdx`, 32 GB, in the same folder.
11. Attach the disks while the guest is running if supported.

Then go inside the SQL guest and finish the guest-side disk setup:

1. Open **Disk Management** inside the SQL guest.
2. Identify the two blank disks by **size**.
3. Initialize both disks as GPT.
4. Format the 64 GB disk as drive E: with label **SQLDATA**.
5. Format the 32 GB disk as drive L: with label **SQLLOG**.
6. Use **NTFS**.
7. Use allocation unit size **64 KB**.
8. Never format C: or an already-used disk.
9. Create these folders:
   - `E:\SQLData`
   - `E:\TempDB`
   - `E:\SQLBackup`
   - `L:\SQLLog`

The supplied `add-sql-disks.ps1` is the scoped host-side procedure that uses PowerShell Direct. It runs on `HV-HOST-01` through Arc Run Command and refuses any guest other than `SQL2019-GUEST`; the guest must be running. It creates the two dynamic VHDX files `F:\VMs\SQL2019-GUEST-data.vhdx` and `F:\VMs\SQL2019-GUEST-log.vhdx` if they do not exist, hot-adds them to the SCSI controller if they are not attached, and then, inside the guest, initializes only the blank (RAW) disk of exactly the data size and the blank disk of exactly the log size as GPT. It formats them as NTFS with 64 KB allocation units (E: `SQLDATA`, L: `SQLLOG`), creates `E:\SQLData`, `E:\TempDB` and `L:\SQLLog`, selects the High performance power plan, and reports the sector size that SQL Server will see, which must be 512 B or 4 KB. `E:\SQLBackup` is created later by the SQL installation script. Use private credentials from the host. If you only want to inspect the current state first, use the read-only verification step below.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI**

```powershell
$settings = Get-LabSettings
$private = @{ GuestPasswordHex = (ConvertTo-LabHex $settings.SQL_GUEST_PASSWORD) }
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\add-sql-disks.ps1 `
  -Parameters @{ GuestName='SQL2019-GUEST'; DataGB='64'; LogGB='32' } `
  -Protected $private -TimeoutSeconds 900
$private = $null
$settings = $null
```

**What you should see:** existing intended disks are kept (the script can be run again: `Exists`, `Already attached`, `E: already exists`). If new data/log VHDX files are needed, they are attached to the SQL guest only. The output lists the new disks and volumes and ends with `SQL-DISKS-DONE`; it stops with `A SQL Server disk reports a sector size above 4 KB - SQL Server would not start` if a disk would not be usable. No plaintext credential is sent in ordinary parameters. Do not display the settings or the private variables.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** This is a read-only verification step.

```powershell
Get-Disk | Format-Table Number,Size,PartitionStyle
Get-Volume -DriveLetter E,L | Format-Table DriveLetter,FileSystemLabel,FileSystem,Size
fsutil fsinfo ntfsinfo E:
fsutil fsinfo ntfsinfo L:
Get-ChildItem E:\SQLData,E:\TempDB,L:\SQLLog
```

**What you should see:** E: is 64 GB, L: is 32 GB, and Bytes Per Cluster is 65536. The dynamic VHDX file size on F: can still be smaller than its virtual capacity. Initial expansion, the filesystem cache and the shared outer disk can all affect a storage scene.

## 12.2 Verify and mount the Enterprise Core media

**What you are doing:** you make sure you are using the exact SQL Server installation ISO you intend to use and then attach it to the SQL guest safely.

In the environment, follow these steps:

1. On the host, open **File Explorer**.
2. Browse to `F:\ISO`.
3. Right-click the SQL ISO.
4. Click **Mount**.
5. From the host terminal, verify the file hash with the command below.
6. Attach the ISO to the SQL guest DVD drive in Hyper-V **Settings**, or copy it through a protected PowerShell Direct session.
7. Mount it inside the guest.
8. Do not copy the embedded product key into a document or a public setup parameter.

> **RUN ON - Hyper-V host (HV-HOST-01), elevated PowerShell**

```powershell
$iso = 'F:\ISO\en_sql_server_2019_enterprise_core_x64_dvd_5e1ecc6b.iso'
$expected = 'C206420A13CB07936FC8ECE6AF20E04EB32A3E13CFB63813F3E339250B8C0952'
if ((Get-FileHash $iso -Algorithm SHA256).Hash -ne $expected) {
  throw 'SQL ISO SHA-256 mismatch; do not install'
}
Get-VMDvdDrive -VMName SQL2019-GUEST | Set-VMDvdDrive -Path $iso
```

**What you should see:** no hash error. This SHA-256 is the verified hash for these exact bits, not a hash of every SQL Server 2019 download. If you use different media (for example evaluation media), compare against the SHA-256 published for your own download, and expect a different file name and a different edition string after installation. After mounting, signature-check `setup.exe` (for example with `Get-AuthenticodeSignature`); the publisher must be Microsoft and the signature must be valid.

## 12.3 SQL Setup wizard - exact choices

**What you are doing:** you install SQL Server 2019 on the SQL guest and choose the exact options the lab requires. Follow each setup screen carefully.

> **RUN ON - SQL2019-GUEST desktop**, reached through Bastion to the host and then VMConnect from the host.

In the UI, click through this path:

1. Open **Bastion**.
2. From the host, open **VMConnect** to **SQL2019-GUEST**.
3. On the guest desktop, open the mounted SQL DVD.
4. Run **setup.exe**.
5. In **SQL Server Installation Center**, click **Installation**.
6. Click **New SQL Server stand-alone installation**.

Then make these exact choices:

1. **Product key:** leave the value embedded in the licensed media. Never show or capture the key on screen, and never copy it into a document or a script. Accept the licence terms only if you are entitled to use this media (for example under an existing licence, or as evaluation media).
2. **Feature Selection:** choose **Database Engine Services** only. Under Instance Configuration, choose **Default instance**, instance ID `MSSQLSERVER`.
3. **Server Configuration:** set the Database Engine account to **NT Service\MSSQLSERVER**, SQL Server Agent to **NT Service\SQLSERVERAGENT**, and startup to **Automatic** for both. These virtual accounts need no password.
4. **Database Engine Configuration > Server Configuration:** choose **Windows authentication mode**. Add `SQL2019-GUEST\labadmin` (the current administrator) and `NT AUTHORITY\SYSTEM` as sysadmin; the prepared script adds both, and the Arc Run Command scripts of the later chapters run as Local System and connect with Windows authentication. Do not select Mixed Mode or create an `sa` password.
5. **Data Directories:** set the user database directory to `E:\SQLData`, the user log directory to `L:\SQLLog`, and the backup directory to `E:\SQLBackup`. For TempDB, set four data files, each 64 MB initial size and 64 MB growth, in `E:\TempDB`; set the TempDB log to 64 MB initial size and 64 MB growth in `L:\SQLLog`.
6. Use collation `SQL_Latin1_General_CP1_CI_AS`; TCP enabled, Named Pipes disabled; enable instant file initialization for this lab. Review, then click **Install**. If setup fails, read `Summary.txt`.
7. Set a safe initial max server memory of 8192 MB before the demo configuration, then set the precise 80% ceiling as described in [chapter 14](14-sql-memory-ceiling-and-what-it-means.md). SQL Server and SQL Server Agent remain Automatic and Running. Eject the DVD after verification.

The lab kit's `Install-LabSql2019.ps1` implements these settings on the **SQL guest**. It sources `guest-sql.ps1`, which stops unless the computer is `SQL2019-GUEST`. It skips an already installed default instance (`SQL already installed; no setup or restart performed.`), creates the four data, tempdb, backup and log folders if they are missing, and checks that `setup.exe` in the media folder has a valid Microsoft signature and major version 15 before it runs setup silently with the choices above. It does not check the ISO hash; do that on the host as in section 12.2. It uses the embedded key without printing it, applies the initial max server memory of 8192 MB, and stops with `Wrong SQL media/edition; do not onboard PAYG without review.` if the edition is not Enterprise Core-based licensing.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** Use this for the initial install only.

```powershell
Set-Location C:\lab-kit
.\Install-LabSql2019.ps1 -MediaPath 'D:\'
```

> **Warning:** The DVD drive letter can differ. Before choosing `MediaPath`, run `Get-Volume | Where-Object DriveType -eq 'CD-ROM'` in the guest. Pass the returned drive letter plus colon and backslash. The supplied parameter is a directory, not a product key.

**What you should see:** setup exit code 0 or 3010; the SQL services exist; edition **Enterprise Edition: Core-based Licensing**; and the initial RTM version 15.0.2000.5 before patches. On exit code 3010 the script warns `Setup requests a restart: restart the guest in a planned maintenance window; no automatic reboot was performed.`

## 12.4 Patch level and keep-running verification

**What you are doing:** you verify the installed SQL build and confirm the SQL services are still running. For an initial installation only, you can apply the SQL Server 2019 update packages. Do not repeat patching on a running lab just to demonstrate the step.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** If SSMS is installed, the GUI equivalent is: connect with Windows authentication, click **New Query**, and run `SELECT @@VERSION`.

Also check the Services UI in the guest:

1. Open **Services**.
2. Find **SQL Server (MSSQLSERVER)**.
3. Find **SQL Server Agent**.
4. Confirm both are **Running**.
5. Confirm the startup type is **Automatic**.

For an initial installation only, apply the verified CU32 package first, then the CU32 + GDR package, using each installer's update wizard. Review the prerequisites, run **Update**, and check whether a restart is required. Repeating this on a running lab is a disruptive maintenance operation; do it only in a planned maintenance window.

> **RUN ON - SQL2019-GUEST (inside the guest), elevated PowerShell.** This step is read-only.

```powershell
Set-Location C:\lab-kit
. .\guest-sql.ps1
Invoke-LabSql "SELECT SERVERPROPERTY('Edition') AS Edition,
 SERVERPROPERTY('ProductVersion') AS Version,
 SERVERPROPERTY('IsIntegratedSecurityOnly') AS WindowsOnly;"
Get-CimInstance Win32_Service `
  -Filter "Name='MSSQLSERVER' OR Name='SQLSERVERAGENT'" |
  Select-Object Name,State,StartMode,StartName
```

**What you should see:** the current build **15.0.4490.9** (SQL 2019 CU32 plus the GDR update); `WindowsOnly=1`; and both services Running/Auto using virtual accounts. CU32 is KB5054833 (build 15.0.4430.1); the GDR is KB5122772. The GDR installer returns exit code 3010 (restart required); only the SQL guest needs that restart, not the host or the other guests. Do not reapply patch packages or reboot just to demonstrate the step. The Arc `currentVersion` property can retain the media version; use `patchLevel` and the guest query for the installed build.

For a fresh initial installation, `host-patch.ps1` supplies the official package URLs and the published SHA-256 values. Follow this route in the environment:

1. Open **Bastion** to the host.
2. Open PowerShell on the host.
3. Run the **Download** stage below.
4. Open `F:\Build\sql2019-updates`.
5. Confirm both verified packages are present.
6. Use a private PowerShell Direct session to copy them into the SQL guest's protected staging folder.
7. Run the CU installer first, then the GDR installer.
8. In each wizard, accept the terms, select `MSSQLSERVER`, review the prerequisites, then click **Update**.
9. Read the result and `SQL Setup Summary.txt`.
10. Exit code 3010 requests a restart of the SQL guest, which is a separate decision; it does not require a host reboot.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI.** This is **Download only**. It does not install or restart anything.

```powershell
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\host-patch.ps1 `
  -Parameters @{ Stage='Download' } -TimeoutSeconds 2400
```

The **Apply** stage is a gated change: it requires an explicit confirmation parameter and may restart SQL services. Do not use it on a running lab merely to repeat a completed update. The `InitialBuildMaintenanceApproved='yes'` parameter is the explicit confirmation the script requires before it applies patches.

> **RUN ON - your own computer, Windows PowerShell with Azure CLI.** Use this only for an initial install in a maintenance window.

```powershell
$settings = Get-LabSettings
$private = @{ GuestPasswordHex=(ConvertTo-LabHex $settings.SQL_GUEST_PASSWORD) }
Invoke-LabArcScript -Machine HV-HOST-01 -ScriptPath .\host-patch.ps1 `
  -Parameters @{ Stage='Apply'; InitialBuildMaintenanceApproved='yes' } `
  -Protected $private -TimeoutSeconds 3600
$private=$null
$settings=$null
```

**What you should see:** Microsoft signatures and hashes verified; each applicable patch exits with 0 or 3010; the build is checked; and SQL Server and SQL Server Agent are restored to Automatic/Running. `/norestart` is **not a supported switch for these SQL patch executables**; an installer started with it is rejected, so the script omits it. This script never reboots automatically. Restarting the guest after a 3010 is a separate decision, followed by the read-only service, build and database checks.
