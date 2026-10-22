#!/bin/bash
set -euo pipefail
file=/var/log/hv-demo/http-latency.json
python3 - "$file" <<'PY'
import json, sys
from collections import deque
from statistics import mean
from datetime import datetime, timezone
with open(sys.argv[1], encoding="utf-8") as source:
    rows = [json.loads(line) for line in deque(source, maxlen=300)]
if not rows:
    raise SystemExit("No HTTP observer samples; not a valid zero-latency result.")
values = sorted(row["ResponseMs"] for row in rows)
index = max(0, min(len(values)-1, int(len(values)*0.95+0.999999)-1))
print(json.dumps({"ObservedUtc":datetime.now(timezone.utc).isoformat(),
                  "Samples":len(rows),"MeanMs":round(mean(values),3),
                  "P95Ms":values[index],"MaxMs":values[-1],
                  "LatestSampleUtc":rows[-1]["TimeGenerated"],
                  "Failures":sum(row["HttpCode"] != 200 for row in rows)}, indent=2))
PY
