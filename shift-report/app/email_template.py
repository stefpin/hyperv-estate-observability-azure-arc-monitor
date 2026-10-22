"""Deterministic, side-effect-free presentation of an already frozen report."""

import datetime as dt
import html
import math


UTC = dt.timezone.utc
LT = dt.timezone(dt.timedelta(hours=7))
MACHINES = (
    "HV-HOST-01", "RHEL94-GUEST", "SQL2019-GUEST", "WIN2019-GUEST",
    "WIN2022-GUEST", "WIN2025-GUEST-01",
)
TITLE = "Hyper-V Estate - Shift Report"
MOTTO = "Host-to-SQL observability"
MONITORING = "Monitored with Azure Monitor"
REHEARSAL = "TEST / REHEARSAL - not a scheduled shift"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
STATUSES = {
    "MONITORED SIGNALS NORMAL", "ATTENTION REQUIRED",
    "CRITICAL CONDITION OBSERVED", "INSUFFICIENT EVIDENCE",
}


def _time(value):
    if not isinstance(value, str):
        raise ValueError("An explicit UTC timestamp is required")
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid UTC timestamp") from error
    if result.tzinfo is None or result.utcoffset() != dt.timedelta():
        raise ValueError("An explicit UTC timestamp is required")
    return result.astimezone(UTC)


def _date(moment):
    return f"{moment.day:02d} {MONTHS[moment.month - 1]} {moment.year:04d}"


def _lt(value):
    moment = _time(value).astimezone(LT)
    return f"{_date(moment)} {moment:%H:%M:%S} LT"


def _utc(value):
    return _time(value).isoformat().replace("+00:00", "Z")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def _nonnegative(value):
    value = _number(value)
    return value if value is not None and value >= 0 else None


def _fmt(value, decimals=1):
    value = _nonnegative(value)
    return f"{value:,.{decimals}f}" if value is not None else "N/A"


def _text(value, default="N/A"):
    if isinstance(value, str):
        return value if value else default
    if _number(value) is not None:
        return str(value)
    return default


def _key(row):
    return tuple(sorted((str(key), repr(value)) for key, value in row.items()))


def _latest(rows, field="TimeGenerated"):
    candidates = [(_time(row[field]), _key(row), row) for row in rows if row.get(field)]
    return max(candidates, key=lambda item: item[:2])[2] if candidates else {}


def _machine(row):
    return _text(row.get("Computer"), "").upper()


def _freshness(row, field, cutoff, quality=None, samples=False, valid=True):
    if not row or not row.get(field) or not valid:
        return "MISSING"
    age = (cutoff - _time(row[field])).total_seconds()
    count = _nonnegative(row.get("Samples"))
    if samples and (count is None or count <= 0):
        return "MISSING"
    label = row.get(quality) if quality else "FRESH"
    if label == "MISSING":
        return "MISSING"
    return "FRESH" if 0 <= age <= 300 and label == "FRESH" else "STALE"


def _section(title, headers, rows, note):
    return {"title": title, "headers": headers, "rows": rows, "note": note}


def subject(evidence):
    """Use the measurement cutoff's LT date, never the shift-boundary date."""
    job = evidence["job"]
    cutoff = _time(job["sourceEndUtc"]).astimezone(LT)
    if job["mode"] not in ("dryrun", "scheduled"):
        raise ValueError("Unknown report mode")
    suffix = " [TEST]" if job["mode"] == "dryrun" else ""
    return f"{TITLE} - {_date(cutoff)} - Cutoff {cutoff:%H:%M} LT{suffix}"


def _estate(data, cutoff):
    rows = []
    fresh = 0
    for machine in MACHINES:
        cpu = [row for row in data.get("cpu", []) if _machine(row) == machine
               and row.get("Metric") == (
                   "Host hypervisor CPU" if machine == MACHINES[0] else "OS CPU")
               and row.get("Unit") == "percent"]
        weighted = [(_nonnegative(row.get("Value")), _nonnegative(row.get("Samples")))
                    for row in cpu]
        usable = [(value, count) for value, count in weighted
                  if value is not None and count is not None and count > 0]
        # Scaling the weights avoids overflow without taking a mean of bucket means.
        if usable:
            scale = max(count for _, count in usable)
            weight = math.fsum(count / scale for _, count in usable)
            average = math.fsum(value * ((count / scale) / weight)
                                for value, count in usable)
        else:
            average = None
        values = [_nonnegative(row.get("Value")) for row in cpu]
        peak = max((value for value in values if value is not None), default=None)
        ram = _latest([row for row in data.get("memory", []) if _machine(row) == machine])
        last_cpu = _latest(cpu)
        states = [
            _freshness(_latest([row for row in data.get("summary", [])
                               if _machine(row) == machine], "LastSeen"),
                       "LastSeen", cutoff, "Reporting", samples=True),
            _freshness(last_cpu, "LastSampleUtc" if "LastSampleUtc" in last_cpu else "TimeGenerated", cutoff, samples=True,
                       valid=_nonnegative(last_cpu.get("Value")) is not None),
            _freshness(ram, "LastSampleUtc" if "LastSampleUtc" in ram else "TimeGenerated", cutoff,
                       valid=_nonnegative(ram.get("UsedPercent")) is not None),
        ]
        streams = ["Heartbeat", "Perf"]
        if machine == "SQL2019-GUEST":
            streams.append("SQL memory")
        if machine == "RHEL94-GUEST":
            streams.append("Linux disk")
        for stream in streams:
            quality = _latest([row for row in data.get("data-quality", [])
                               if _machine(row) == machine and row.get("Stream") == stream],
                              "Latest")
            states.append(_freshness(quality, "Latest", cutoff, "Quality", samples=True))
        reporting = ("MISSING" if "MISSING" in states else
                     "STALE" if "STALE" in states else "FRESH")
        fresh += reporting == "FRESH"
        rows.append([machine, reporting, _fmt(average), _fmt(peak),
                     _fmt(ram.get("UsedPercent"))])
    return _section(
        "Estate health",
        ["Machine", "Reporting freshness", "Avg CPU %", "Peak 5m CPU %", "Latest RAM %"],
        rows,
        "CPU average is sample-weighted; peak is the highest 5-minute mean, not a raw peak. "
        "RAM is the latest 5-minute mean. Freshness uses source sample time, not bucket start or live health.",
    ), fresh


def _sql(data):
    memory = _latest(data.get("sql-memory", []))
    grants = _latest(data.get("sql-grants", []))
    metrics = [
        ("Observed SQL memory cap", "CapMiB"),
        ("Memory manager committed", "CommittedMiB"),
        ("SQL process memory", "ProcessMiB"),
        ("SQL cache (overlaps)", "CacheMiB"),
        ("OS available headroom", "OSAvailableMiB"),
    ]
    rows = [[label, _fmt(memory.get(field)) + " MiB"] for label, field in metrics]
    rows.append(["Grant allocated / used (paired record)",
                 f"{_fmt(grants.get('GrantedMiB'))} / {_fmt(grants.get('UsedMiB'))} MiB"])
    memory_bucket = _lt(memory["TimeGenerated"]) if memory else "N/A"
    sample = _lt(grants["SnapshotAt"]) if grants.get("SnapshotAt") else "N/A"
    memory_sample = _lt(memory["Latest"]) if memory.get("Latest") else "N/A"
    return _section(
        "SQL memory", ["Metric", "Observed value"], rows,
        f"Memory sample: {memory_sample} (5m bucket {memory_bucket}); grant snapshot: {sample}. "
        "Grant/use come from the same peak-allocation record. Values overlap: do not add. "
        "The cap is not a hard limit on the whole SQL process.",
    )


def _contention(data):
    ordered = sorted(
        data.get("contention", []),
        key=lambda row: (-(_nonnegative(row.get("P95Ns")) or 0),
                         _text(row.get("Guest")), _key(row)),
    )
    rows = [[_text(row.get("Guest")), _fmt(row.get("MeanNs"), 0),
             _fmt(row.get("P95Ns"), 0)] for row in ordered[:3]]
    return _section(
        "CPU contention - highest sampled P95", [
            "Guest", "Mean wait (ns/dispatch)", "Sampled P95 wait (ns/dispatch)",
        ], rows or [["N/A", "N/A", "N/A"]],
        "Top 3 sampled values: not CPU ready % and not a per-operation latency percentile.",
    )


def _latency(row, direction):
    rate = _nonnegative(row.get(direction + "IOPS"))
    return (_nonnegative(row.get(direction + "LatencyMs"))
            if rate is not None and rate > 0 else None)


def _storage(data):
    source = data.get("storage", [])
    by_device = {}
    for row in source:
        key = tuple(_text(row.get(field)) for field in ("Layer", "Computer", "Device"))
        by_device.setdefault(key, []).append(row)
    devices = [_latest(rows, "Latest") or min(rows, key=_key)
               for rows in by_device.values()]

    def rank(row):
        latencies = [_latency(row, "Read"), _latency(row, "Write"),
                     _latency(dict(row, TransferIOPS=row.get("TotalIOPS")), "Transfer")]
        score = max((value for value in latencies if value is not None), default=-1)
        return (-score, _text(row.get("Layer")), _machine(row),
                _text(row.get("Device")), _key(row))

    ordered = sorted(devices, key=rank)
    selected, remaining, represented = [], [], set()
    for row in ordered:
        layer_machine = (_text(row.get("Layer")), _machine(row))
        if layer_machine not in represented:
            selected.append(row)
            represented.add(layer_machine)
        else:
            remaining.append(row)
    selected = sorted((selected[:5] + remaining[:max(0, 5 - len(selected))]), key=rank)
    rows = []
    for row in selected:
        transfer = dict(row, TransferIOPS=row.get("TotalIOPS"))
        rows.append([
            " / ".join(_text(row.get(field)) for field in ("Layer", "Computer", "Device")),
            _fmt(row.get("ReadIOPS")), _fmt(row.get("WriteIOPS")),
            _fmt(_latency(row, "Read")), _fmt(_latency(row, "Write")),
            _fmt(_latency(transfer, "Transfer")),
        ])
    storage = _section(
        "Storage highlights",
        ["Layer / machine / device", "Read IOPS", "Write IOPS", "Read ms", "Write ms",
         "Transfer ms"],
        rows or [["N/A"] * 6],
        f"Highest mean latency across distinct layer/machine views; {len(source)} source rows "
        "in attachments. Rates/latencies are window means, not hourly peaks. Idle = N/A. "
        "Storage layers and RHEL aliases are not additive; RHEL latency is operation weighted.",
    )
    group = _latest(data.get("cluster-storage", []))
    members = _nonnegative(group.get("ObservedMembers"))
    complete = members == 3 and _nonnegative(group.get("ExpectedMembers")) == 3
    iops = _nonnegative(group.get("GroupIOPS")) if complete else None
    latency = (group.get("RateWeightedLatencyMs")
               if iops is not None and iops > 0 else None)
    logical = _section(
        "Windows logical group (not WSFC)",
        ["Latest 5m bucket (LT)", "Group IOPS", "Rate-weighted latency (ms)",
         "Observed members", "Distinct volumes"],
        [[_lt(group["TimeGenerated"]) if group else "N/A", _fmt(iops), _fmt(latency),
          f"{_fmt(members, 0)} / 3", _fmt(group.get("DistinctVolumes"), 0)]],
        "Distinct member volumes only, not a sum across storage layers. Missing members or "
        "idle latency show N/A. Logical group, not failover-health evidence.",
    )
    return storage, logical


def _summary(evidence):
    job, data = evidence["job"], evidence.get("datasets", {})
    cutoff = _time(job["sourceEndUtc"])
    start, boundary = _time(job["sourceStartUtc"]), _time(job["boundaryUtc"])
    if start >= cutoff or cutoff > boundary or job.get("bucket") != "5m":
        raise ValueError("Invalid five-minute source window")
    health = evidence.get("health", {})
    status = health.get("status", "INSUFFICIENT EVIDENCE")
    if status not in STATUSES:
        raise ValueError("Unknown central health status")
    estate, fresh = _estate(data, cutoff)
    storage, logical = _storage(data)
    count = _nonnegative(health.get("freshSignals"))
    count_text = _fmt(count, 0) if count is not None and count <= 14 and count.is_integer() else "N/A"
    findings = health.get("sustainedFindings", [])
    exceptions = ("Reported exceptions: " + "; ".join(_text(value) for value in findings[:3])
                  if findings else "No evaluated condition exceeded its threshold at cutoff."
                  if status == "MONITORED SIGNALS NORMAL" else
                  "No triggered conditions in available evidence; not proof of health.")
    if len(findings) > 3:
        exceptions += f" (+{len(findings) - 3} more in attachments)"
    sections = [estate, _sql(data), _contention(data), storage, logical, _section(
        "Open items and actions", ["Item", "Evidence state", "Handover action"], [
            ["Maintenance", _text(health.get("maintenance"), "Open"),
             "Review maintenance evidence before closing."],
            ["Change Tracking inventory", _text(health.get("ctInventory"), "Open inventory caveat"),
             "Verify inventory freshness; not continuous availability proof."],
            ["BPA", _text(health.get("bpa"), "Not assessed yet"),
             "Assessment pending; do not infer a passed assessment."],
        ], "Open evidence items are not, by themselves, proof of a current outage.",
    )]
    return {
        "title": TITLE, "motto": MOTTO, "monitoring": MONITORING, "status": status,
        "rehearsal": REHEARSAL if job["mode"] == "dryrun" else "",
        "metadata": [
            f"Measurement cutoff: {_lt(job['sourceEndUtc'])} (5-minute source cutoff)",
            f"Source window: {_lt(job['sourceStartUtc'])} to {_lt(job['sourceEndUtc'])}; 5-minute buckets",
            f"Nominal shift: {_lt(job['nominalStartUtc'])} to {_lt(job['boundaryUtc'])}",
        ],
        "freshness": f"Required signals: {count_text}/14 fresh; expected machines: {fresh}/6 fresh.",
        "historical": "Historical frozen evidence at source cutoff, not live estate availability.",
        "exceptions": exceptions,
        "gaps": f"Evidence gaps: {len(health.get('missingOrStale', []))} required streams missing/stale; "
                f"{len(health.get('coverageGaps', []))} coverage gaps. Details in attachments.",
        "sections": sections,
        "footer": [
            "Full PDF charts, Excel evidence and the workbook-content PDF are attached; full source/provenance in attachments.",
            "Demonstration environment - not production.",
            f"Report ID: {_text(job.get('reportId'))}",
            f"Evidence frozen: {_utc(evidence['freezeAtUtc'])}",
            f"Exact UTC source window: {_utc(job['sourceStartUtc'])} to {_utc(job['sourceEndUtc'])}",
        ],
    }


def _plain(model):
    lines = ["Hyper-V Estate Observability", model["motto"], "Azure Monitor", model["monitoring"], "", model["title"]]
    if model["rehearsal"]:
        lines.append(model["rehearsal"])
    lines.extend(model["metadata"] + ["", model["status"], model["freshness"],
                                    model["historical"], model["exceptions"], model["gaps"]])
    for section in model["sections"]:
        lines.extend(["", section["title"], "\t".join(section["headers"])])
        lines.extend("\t".join(row) for row in section["rows"])
        lines.append(section["note"])
    lines.extend([""] + model["footer"])
    return "\n".join(lines)


def _html(model, email_subject):
    escape = lambda value: html.escape(str(value), quote=True)
    table_style = "border-collapse:collapse;width:100%;table-layout:fixed;"
    cell = ("padding:8px 6px;border-bottom:1px solid #dce4ec;text-align:left;"
            "vertical-align:top;word-wrap:break-word;overflow-wrap:anywhere;")
    pieces = [
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(email_subject)}</title></head>"
        '<body style="margin:0;padding:0;background-color:#eef3f8;color:#24364b;'
        'font-family:Segoe UI,Arial,sans-serif;font-size:13px;line-height:1.5;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        'style="width:100%;border-collapse:collapse;"><tr><td align="center" style="padding:12px 4px;">'
        '<table role="presentation" width="100%" align="center" cellspacing="0" cellpadding="0" '
        'border="0" style="width:100%;max-width:760px;border-collapse:collapse;background-color:#ffffff;">'
        '<tr><td style="padding:0;"><table role="presentation" width="100%" cellspacing="0" '
        'cellpadding="0" border="0" style="width:100%;border-collapse:collapse;">'
        '<tr><td width="50%" bgcolor="#003b70" style="width:50%;padding:18px 14px;vertical-align:top;'
        'background-color:#003b70;color:#ffffff;">'
        '<img src="cid:brand-primary" alt="Hyper-V Estate Observability" width="140" '
        'style="display:block;border:0;width:140px;max-width:100%;height:auto;">'
        f'<div style="padding-top:8px;font-size:12px;">{escape(model["motto"])}</div></td>'
        '<td width="50%" bgcolor="#ffffff" style="width:50%;padding:18px 14px;'
        'vertical-align:top;background-color:#ffffff;color:#24364b;">'
        '<img src="cid:brand-secondary" alt="Azure Monitor" width="140" '
        'style="display:block;border:0;width:140px;max-width:100%;height:auto;">'
        f'<div style="padding-top:8px;font-size:12px;">{escape(model["monitoring"])}</div>'
        '</td></tr></table></td></tr><tr><td style="padding:18px 14px;">'
        f'<h1 style="margin:0 0 8px;font-size:21px;line-height:1.3;color:#003b70;">'
        f'{escape(model["title"])}</h1>',
    ]
    if model["rehearsal"]:
        pieces.append(f'<p style="margin:8px 0;color:#924b00;"><strong>'
                      f'{escape(model["rehearsal"])}</strong></p>')
    pieces.extend(f'<div style="font-size:12px;">{escape(line)}</div>'
                  for line in model["metadata"])
    pieces.append('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                  'border="0" style="width:100%;margin-top:14px;border-collapse:collapse;">'
                  '<tr><td style="padding:12px;background-color:#e9f0f8;border-left:4px solid #003b70;">'
                  f'<strong style="color:#003b70;">{escape(model["status"])}</strong>'
                  f'<div>{escape(model["freshness"])}</div>'
                  f'<div style="font-size:12px;">{escape(model["historical"])}</div>'
                  '</td></tr></table>')
    for key in ("exceptions", "gaps"):
        pieces.append(f'<p style="margin:8px 0;font-size:12px;">{escape(model[key])}</p>')
    for section in model["sections"]:
        pieces.append(f'<h2 style="margin:18px 0 6px;font-size:16px;color:#003b70;">'
                      f'{escape(section["title"])}</h2>')
        pieces.append(f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
                      f'style="{table_style}font-size:12px;"><thead><tr>')
        first_width = 40 if len(section["headers"]) > 4 else 50
        widths = [first_width] + [(100 - first_width) / (len(section["headers"]) - 1)] * (len(section["headers"]) - 1)
        pieces.extend(f'<th scope="col" style="{cell}width:{width:.1f}%;background-color:#e9f0f8;color:#003b70;">'
                      f'{escape(value)}</th>' for value, width in zip(section["headers"], widths))
        pieces.append("</tr></thead><tbody>")
        for row in section["rows"]:
            pieces.append("<tr>")
            pieces.extend(f'<td style="{cell}width:{width:.1f}%;">{escape(value)}</td>'
                          for value, width in zip(row, widths))
            pieces.append("</tr>")
        pieces.append("</tbody></table>")
        pieces.append(f'<p style="margin:6px 0;font-size:11px;color:#52677c;">'
                      f'{escape(section["note"])}</p>')
    pieces.append('</td></tr><tr><td style="padding:14px;background-color:#f3f6fa;'
                  'font-size:11px;color:#52677c;">')
    pieces.extend(f"<div>{escape(line)}</div>" for line in model["footer"])
    pieces.append("</td></tr></table></td></tr></table></body></html>")
    return "".join(pieces)


def present_email(evidence):
    """Return subject, faithful plaintext/HTML and a JSON-safe preview model.

    No assets, attachments, approvals, settings, or delivery state are read or changed.
    Missing/nonfinite measurements remain N/A; malformed timestamps fail explicitly.
    """
    email_subject = subject(evidence)
    model = _summary(evidence)
    return {"subject": email_subject, "plainText": _plain(model),
            "html": _html(model, email_subject), "summary": model}


def render_summary(model, job):
    """Reconstruct the exact approved bodies without loading source datasets."""
    email_subject = subject({"job": job})
    return {"subject": email_subject, "plainText": _plain(model),
            "html": _html(model, email_subject)}
