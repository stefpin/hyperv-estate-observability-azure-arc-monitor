# Act 4. The storage story – read the layers together

Act 4 covers minutes 32–42 of the storyline (about 10 minutes). Its goal is to show that storage has **layers**, that latency must always be read **with** IOPS, and that the demo found a clear, safe, recorded example. Before you start, the Workbook from Act 2 must be open in Read mode, and you must be comfortable typing a custom time range (see Act 2, section 2.3). The recorded storage scene lasts only a few minutes, so say "Recorded" each time you show it.

## 4.1 The background story

> **Say this:** "After the CPU test we ran a separate, storage-only test on the SQL server's data drive, E:. We wrote four small disposable test files, each 128 megabytes, for three minutes. These were **not** SQL data files. SQL itself was not loaded."

| **Layer** | **What it is** | **Where you see it in the Workbook** |
|---|---|---|
| **Guest volume** | The drive letter inside the guest, for example `E:` on SQL2019-GUEST. | Windows guest volume latency (ms) / IOPS |
| **Virtual disk (VHDX)** | The file on the host that holds that guest drive. | Hyper-V virtual disk latency / IOPS |
| **Host physical disk** | The Azure data disk on the host (`F:`, Premium SSD P20: 2,300 IOPS, 150 MB/s). | Host disks read/write IOPS and latency |

> **Be honest:** "These three layers describe **the same I/O path from different angles**. They overlap. We never add them together, and we never convert a guest latency into an Azure disk guarantee."

## 4.2 Show it

> **Where to run it:** **Azure Portal → Workbook**.

> **Do this:** Click the **Time range** pill → **Custom**. Start: the date of the recording (`<INCIDENT_DATE>`, typed in the format the box shows) and `11:42:00 AM`. End: the same date and `11:54:00 AM`. Click **OK**. Wait 15 seconds. Scroll to **Windows guest volume latency (ms)** and the chart under it, **Windows guest volume IOPS**. The Portal uses the time zone of the browser, UTC+7 (LT) on the presenter PC, so the times you type are local time: 11:42–11:54 LT is 04:42–04:54 UTC.

The two charts, with the recorded storage window (11:42–11:54 LT) selected, show these parts in reading order:

- **(1)** The pink line is **SQL2019-GUEST / E:** (the test drive). Its latency rises to about **1.9 ms** between 11:46 and 11:50 LT (04:46–04:50 UTC).

- **(2)** The legend lists every guest volume. All the others stay near 0.5 ms.

- **(3)** The chart below shows IOPS. The same drive reaches roughly **800 operations per second** during the test.

> **Say this:** "Look at the pink line. When the test starts, the drive handles about 800 operations per second and the latency moves from about half a millisecond to nearly two milliseconds. The two charts must be read together: **latency without IOPS means nothing** – a drive that does no work has no meaningful latency."

> **What you should see:** Latency back to normal after about 11:51 LT (04:51 UTC). IOPS back to near zero.

> **Be honest:** "800 operations per second is **far below** the 2,300 that this disk type allows, so this test did **not** saturate the disk and does not prove that an application became slow. It proves that **we can see where and when storage was busy**."

## 4.3 Linux storage and the capacity view

> **Do this:** Keep the same time range. Scroll further to **RHEL block-device read/write IOPS (do not sum LVM aliases)** and **RHEL operation-weighted read/write latency**.

- Linux disk numbers come from a small collector that reads the block device once a minute.

- A quiet direction (for example reads when only writes happen) shows **empty**, not a fake zero. Empty means "no operations happened".

- The table **RHEL storage device to mounted-volume mapping** shows which device holds which mount.

> **Good to know:** A single latency figure would hide which layer is busy. Here the same question is answered by layer – guest volume, virtual disk, host disk – with explicit warnings against adding them up. The chapter on storage telemetry ([setup chapter 16](../setup/16-storage-telemetry.md)) shows how each layer is collected.

> **Beginner tip:** If a chart shows **N/A** or a gap, say: "There was no activity here, so there is no latency to measure." Never say "zero latency".
