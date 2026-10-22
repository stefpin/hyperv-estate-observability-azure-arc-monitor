#!/bin/bash
set -euo pipefail
samples="${1:-60}"
[[ "$samples" =~ ^[1-9][0-9]{0,2}$ ]] && (( samples >= 5 && samples <= 300 )) || {
  echo "Choose 5-300 one-second samples." >&2; exit 1;
}
[[ "$(hostname -s | tr '[:lower:]' '[:upper:]')" == "RHEL94-GUEST" ]] || {
  echo "Run only on RHEL94-GUEST." >&2; exit 1;
}
python3 - "$samples" <<'PY'
import json, math, statistics, subprocess, sys, time
from datetime import datetime, timezone
start = datetime.now(timezone.utc).isoformat()
values, failures = [], 0
for _ in range(int(sys.argv[1])):
    sample = subprocess.run(
        ["curl", "--noproxy", "*", "--max-time", "5", "-sS", "-o", "/dev/null",
         "-w", "%{http_code} %{time_total}", "http://localhost"],
        capture_output=True, text=True
    )
    fields = sample.stdout.split()
    if sample.returncode or len(fields) != 2 or fields[0] != "200":
        failures += 1
    else:
        values.append(float(fields[1]) * 1000)
    time.sleep(1)
values.sort()
print(json.dumps({
    "StartUtc": start, "EndUtc": datetime.now(timezone.utc).isoformat(),
    "RequestedSamples": int(sys.argv[1]), "SuccessfulSamples": len(values),
    "Failures": failures, "MeanMs": round(statistics.mean(values), 3) if values else None,
    "P95Ms": round(values[math.ceil(0.95 * len(values))-1], 3) if values else None,
    "Scope": "RHEL localhost HTTP; no Azure ingestion"
}, indent=2))
if not values:
    raise SystemExit("No successful HTTP sample; not a valid zero-latency result.")
PY
