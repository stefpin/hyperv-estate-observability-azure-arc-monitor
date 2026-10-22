#!/usr/bin/python3
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

INTERVAL = 60
LOG_DIR = pathlib.Path("/var/log/hv-storage")


def mounted_volumes(device):
    result = subprocess.run(
        ["/usr/bin/lsblk", "--json", "--paths", "--output", "NAME,TYPE,MAJ:MIN", "/dev/" + device],
        check=True, text=True, capture_output=True, timeout=10,
    )
    mount_map = {}
    # PID 1's mount namespace excludes this service's read-only/private bind mounts.
    for line in pathlib.Path("/proc/1/mountinfo").read_text().splitlines():
        fields = line.split(" - ", 1)[0].split()
        mount_map.setdefault(fields[2], []).append(fields[4])
    swaps = {line.split()[0] for line in pathlib.Path("/proc/swaps").read_text().splitlines()[1:]}
    mounts = []

    def walk(nodes):
        for node in nodes:
            for mount in mount_map.get(node["maj:min"], []):
                mounts.append(node["name"] + "=" + mount)
            if node["name"] in swaps:
                mounts.append(node["name"] + "=[SWAP]")
            walk(node.get("children") or [])

    walk(json.loads(result.stdout)["blockdevices"])
    return ";".join(mounts)


def collect():
    result = subprocess.run(
        ["/usr/bin/iostat", "-x", "-d", "-k", "-y", "-o", "JSON", str(INTERVAL), "1"],
        check=True, text=True, capture_output=True, timeout=INTERVAL + 30,
        env=dict(os.environ, LC_ALL="C", S_TIME_FORMAT="ISO"),
    )
    hosts = json.loads(result.stdout)["sysstat"]["hosts"]
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    for host in hosts:
        for sample in host["statistics"]:
            for disk in sample["disk"]:
                device = disk["disk_device"]
                # A partition is absent from /sys/block; device-mapper is another accounting layer.
                if not pathlib.Path("/sys/block", device).exists() or device.startswith(("dm-", "loop", "ram", "sr")):
                    continue
                row = {
                    "Device": device, "AccountingScope": "block-device",
                    "ReadIOPS": disk["r/s"], "WriteIOPS": disk["w/s"],
                    "ReadAwaitMs": disk["r_await"], "WriteAwaitMs": disk["w_await"],
                    "ReadKiBps": disk["rkB/s"], "WriteKiBps": disk["wkB/s"],
                    "AvgQueueDepth": disk["aqu-sz"], "UtilizationPct": disk["util"],
                    "IntervalSeconds": INTERVAL, "MountedVolumes": mounted_volumes(device),
                }
                line = now.strftime("%Y-%m-%dT%H:%M:%SZ") + " " + json.dumps(row, separators=(",", ":")) + "\n"
                with (LOG_DIR / now.strftime("disk-%Y%m%d.log")).open("a", encoding="utf-8") as log:
                    log.write(line)
                print(line.rstrip(), flush=True)
    # Daily files are never renamed into the wildcard; keep at least two full days for AMA tailing.
    cutoff = time.time() - 7 * 86400
    for old in LOG_DIR.glob("disk-????????.log"):
        if old.stat().st_mtime < cutoff:
            old.unlink()


if __name__ == "__main__":
    while True:
        try:
            collect()
        except Exception as error:
            print("storage collector error: " + str(error), file=sys.stderr, flush=True)
            time.sleep(10)
