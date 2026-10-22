"""Pure shift, evidence, health and envelope contracts. All stored times are UTC."""

import datetime as dt
import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

UTC = dt.timezone.utc
LT = dt.timezone(dt.timedelta(hours=7), "UTC+7")
SUB = "<SUBSCRIPTION_ID>"
RG = "rg-hyperv-arc-monitor-demo"
SCOPE = f"/subscriptions/{SUB}/resourceGroups/{RG}"
WORKSPACES = {
    SCOPE + "/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab":
        "00000000-0000-0000-0000-000000000009",
    SCOPE + "/providers/Microsoft.OperationalInsights/workspaces/law-arc-ct-sea":
        "00000000-0000-0000-0000-000000000018",
}
MACHINES = ("HV-HOST-01", "RHEL94-GUEST", "SQL2019-GUEST", "WIN2019-GUEST",
            "WIN2022-GUEST", "WIN2025-GUEST-01")
DASHBOARD_UID = "hv-shift-health-report"
FOLDER_UID = "hv-shift-health"
DATASOURCE_UID = "hv-azure-monitor"
GRAFANA_ENDPOINT = "https://<GRAFANA_ENDPOINT>"
QUEUE = "hv-report-jobs"
PILOT_RECIPIENT = "operator@example.com"  # the single allowed recipient; replace before deploying
MAX_ATTACHMENTS = 5 * 1024 * 1024
LIMITATIONS = [
    "Five-minute source cutoff; only records ingested by freezeAt are included.",
    "ARG inventory is a current indexed snapshot, not an event-time frozen inventory.",
    "Missing/stale required telemetry means INSUFFICIENT EVIDENCE, never healthy.",
    "CPU scheduling wait is ns/dispatch, NOT CPU ready percent.",
    "SQL memory categories overlap; do not add committed, process, cache and grants.",
    "SQL cap is observed from records (baseline 9829 MiB), not an assumed new setting.",
    "Storage layers and RHEL aliases are NOT additive; idle latency is N/A.",
    "Windows logical group is NOT WSFC and provides no failover/cluster-health proof.",
    "BPA enabled/no run: Not assessed yet. Maintenance evidence remains open.",
    "Change Tracking is inventory/change evidence, not continuous service availability.",
    "ACS submission is not delivery or proof of inbox receipt.",
]


class ControlledError(RuntimeError):
    """Safe, public error text; never include raw service responses or credentials."""


class Conflict(ControlledError):
    pass


def utcnow():
    return dt.datetime.now(UTC)


def stamp(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("UTC timestamp required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta():
        raise ValueError("Timestamp must have explicit UTC Z or +00:00")
    return parsed.astimezone(UTC)


def local_time(value):
    return parse_utc(value).astimezone(LT).strftime("%Y-%m-%d %H:%M LT")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:shift-\d{8}T(?:07|15|23)0000Z|dryrun-[0-9a-f-]{36})", value):
        raise ValueError("Invalid reportId")
    return value


def due_boundary(now, phase):
    """Return only this timer's exact minute, never the most recent missed shift."""
    now = now.astimezone(UTC)
    target_minute = {"preflight": 50, "collect": 55, "dispatch": 0}[phase]
    hours = (7, 15, 23) if phase == "dispatch" else (6, 14, 22)
    if now.hour not in hours or now.minute != target_minute:
        return None
    boundary = now.replace(minute=0, second=0, microsecond=0)
    return boundary if phase == "dispatch" else boundary + dt.timedelta(hours=1)


def new_job(mode, now, boundary=None, job_id=None):
    now = now.astimezone(UTC).replace(microsecond=0)
    if mode not in ("dryrun", "scheduled"):
        raise ValueError("mode must be dryrun or scheduled")
    if job_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(job_id)):
        raise ValueError("jobId must be 1-80 safe characters")
    if mode == "scheduled":
        selected = parse_utc(boundary) if boundary else due_boundary(now, "collect")
        if selected is None or selected.hour not in (7, 15, 23) or any(
                (selected.minute, selected.second, selected.microsecond)):
            raise ValueError("A scheduled boundary must be UTC 07:00, 15:00 or 23:00")
        # Collection is permitted in this five-minute pre-boundary interval only.
        if not selected - dt.timedelta(minutes=5) <= now < selected:
            raise ValueError("No backfill or future scheduled extraction")
        report_id = "shift-" + selected.strftime("%Y%m%dT%H%M%SZ")
    else:
        if boundary is not None and parse_utc(boundary) != now:
            raise ValueError("A rehearsal boundary is the current clock, not a past shift")
        selected = now
        report_id = "dryrun-" + str(uuid.uuid4())
    return {
        "schemaVersion": 1, "reportId": report_id, "jobId": job_id or report_id,
        "mode": mode, "boundaryUtc": stamp(selected), "createdUtc": stamp(now),
        "nominalStartUtc": stamp(selected - dt.timedelta(hours=8)),
        "sourceStartUtc": stamp(selected - dt.timedelta(hours=8)),
        "sourceEndUtc": stamp(selected - dt.timedelta(minutes=5)), "bucket": "5m",
    }


def validate_job(job):
    valid_id(job["reportId"])
    start, end, boundary = (parse_utc(job[k]) for k in
                            ("sourceStartUtc", "sourceEndUtc", "boundaryUtc"))
    if boundary - start != dt.timedelta(hours=8) or boundary - end != dt.timedelta(minutes=5):
        raise ValueError("Invalid source interval")
    if job["bucket"] != "5m" or job["mode"] not in ("dryrun", "scheduled"):
        raise ValueError("Invalid job")
    expected = "shift-" + boundary.strftime("%Y%m%dT%H%M%SZ")
    if job["mode"] == "scheduled" and (job["reportId"] != expected or boundary.hour not in (7, 15, 23)):
        raise ValueError("Boundary/reportId mismatch")
    if job["mode"] == "dryrun" and not job["reportId"].startswith("dryrun-"):
        raise ValueError("Rehearsal reportId mismatch")


@dataclass(frozen=True)
class Settings:
    kind: str
    account: str
    sender: str
    acs_endpoint: str
    recipients: tuple
    send_enabled: bool
    schedule_enabled: bool
    grafana_endpoint: str = GRAFANA_ENDPOINT
    auto_send_enabled: bool = False
    auto_send_policy_sha256: str = ""

    @classmethod
    def load(cls):
        kind = os.environ.get("APP_KIND", "")
        account = os.environ.get("REPORT_STORAGE_ACCOUNT", "")
        if kind not in ("producer", "dispatcher") or not re.fullmatch(r"[a-z0-9]{3,24}", account):
            raise ValueError("APP_KIND and REPORT_STORAGE_ACCOUNT must be configured")
        grafana = os.environ.get("GRAFANA_ENDPOINT", GRAFANA_ENDPOINT).rstrip("/")
        if grafana != GRAFANA_ENDPOINT:
            raise ValueError("Unapproved Grafana endpoint")
        recipients = tuple(x.strip().lower() for x in
                           os.environ.get("RECIPIENT_ALLOWLIST", PILOT_RECIPIENT).split(",") if x.strip())
        if recipients != (PILOT_RECIPIENT,):
            raise ValueError("Pilot recipient must be exactly " + PILOT_RECIPIENT)
        sender = os.environ.get("ACS_SENDER", "").strip()
        endpoint = os.environ.get("ACS_ENDPOINT", "").rstrip("/")
        if endpoint:
            parsed = urlparse(endpoint)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                    or not parsed.hostname.endswith(".communication.azure.com")):
                raise ValueError("Invalid ACS endpoint")
        for flag in ("SEND_ENABLED", "SCHEDULE_ENABLED", "AUTO_SEND_ENABLED"):
            if os.environ.get(flag, "false").lower() not in ("true", "false"):
                raise ValueError("Boolean gates require true or false")
        if os.environ.get("WEBSITE_TIME_ZONE", "UTC") not in ("UTC", "Etc/UTC", ""):
            raise ValueError("Function timer host must remain UTC")
        return cls(kind, account, sender, endpoint, recipients,
                   os.environ.get("SEND_ENABLED", "false").lower() == "true",
                   os.environ.get("SCHEDULE_ENABLED", "false").lower() == "true", grafana,
                   os.environ.get("AUTO_SEND_ENABLED", "false").lower() == "true",
                   os.environ.get("AUTO_SEND_POLICY_SHA256", ""))


def sustained(rows, field, threshold, minutes=15):
    points = {}
    for row in rows:
        value = row.get(field)
        if isinstance(value, (int, float)) and math.isfinite(value) and row.get("TimeGenerated"):
            moment = parse_utc(row["TimeGenerated"])
            points[moment] = max(points.get(moment, -math.inf), value)
    consecutive = 0
    previous = None
    for moment, value in sorted(points.items()):
        consecutive = (consecutive + 5 if previous and moment - previous == dt.timedelta(minutes=5)
                       else 5) if value > threshold else 0
        if consecutive >= minutes:
            return True
        previous = moment
    return False


def assess(datasets, job):
    """14 required stream/machine pairs; CT inventory is a separate open caveat."""
    quality = {(r.get("Computer", "").upper(), r.get("Stream")): r
               for r in datasets.get("data-quality", [])}
    required = [(m, stream) for m in MACHINES for stream in ("Heartbeat", "Perf")]
    required += [("SQL2019-GUEST", "SQL memory"), ("RHEL94-GUEST", "Linux disk")]
    expected_buckets = math.ceil((parse_utc(job["sourceEndUtc"]) -
                                  parse_utc(job["sourceStartUtc"])).total_seconds() / 300)
    missing, stream_coverage = [], []
    for pair in required:
        row = quality.get(pair, {})
        try:
            age = (parse_utc(job["sourceEndUtc"]) - parse_utc(row["Latest"])).total_seconds()
            fresh = 0 <= age <= 300 and row.get("Samples", 0) > 0 and row.get("Quality") == "FRESH"
        except (KeyError, ValueError, TypeError):
            fresh = False
        if not fresh:
            missing.append("/".join(pair))
        observed = row.get("ObservedBuckets")
        if not isinstance(observed, (int, float)) or observed < expected_buckets * .9:
            stream_coverage.append("/".join(pair) + ": <90% source bucket coverage")
    problems, coverage = [], stream_coverage
    for dataset in ("cpu", "memory", "sql-memory", "sql-grants", "cluster-storage",
                    "contention", "storage", "sql-activity"):
        if not datasets.get(dataset):
            coverage.append(dataset + ": missing required report dataset")
    # Presence/freshness of a broad Perf stream alone does not prove CPU/RAM coverage.
    cpu = datasets.get("cpu", [])
    memory = datasets.get("memory", [])
    for machine in MACHINES:
        cp = [r for r in cpu if r.get("Computer", "").upper() == machine and
              r.get("Metric") == ("Host hypervisor CPU" if machine == "HV-HOST-01" else "OS CPU")]
        ram = [r for r in memory if r.get("Computer", "").upper() == machine]
        for label, rows, field in (("CPU", cp, "Value"), ("RAM", ram, "UsedPercent")):
            times = {r.get("TimeGenerated") for r in rows if isinstance(r.get(field), (int, float))}
            if len(times) < expected_buckets * .9:
                coverage.append(f"{machine}/{label}: <90% five-minute bucket coverage")
            source_times = [
                parse_utc(r.get("LastSampleUtc", r.get("TimeGenerated"))) for r in rows
                if isinstance(r.get(field), (int, float)) and r.get("LastSampleUtc", r.get("TimeGenerated"))
            ]
            if (not source_times or not 0 <=
                    (parse_utc(job["sourceEndUtc"]) - max(source_times)).total_seconds() <= 300):
                coverage.append(f"{machine}/{label}: stale or missing source sample")
    from health_rules import policy
    rules = policy()
    evaluations = datasets.get("alert-health", [])
    evaluated = {r.get("RuleName") for r in evaluations if r.get("Evaluated") is True}
    if evaluated != {r["name"] for r in rules["rules"]}:
        coverage.append("Original alert-policy evaluation incomplete")
    critical = False
    for row in evaluations:
        if row.get("Triggered") is True:
            dimensions = "/".join(str(row[k]) for k in ("Computer", "Guest", "ObjectName", "InstanceName") if row.get(k))
            problems.append(
                f"{row['RuleName']} {dimensions}: {row['Value']} {row['Operator']} "
                f"{row['Threshold']} over {row['WindowMinutes']}m at source cutoff"
            )
            critical = critical or row["Severity"] <= 1
    status = ("INSUFFICIENT EVIDENCE" if missing or coverage else
              "CRITICAL CONDITION OBSERVED" if critical else
              "ATTENTION REQUIRED" if problems else "MONITORED SIGNALS NORMAL")
    return {"status": status, "requiredSignals": 14, "freshSignals": 14 - len(missing),
            "missingOrStale": missing, "coverageGaps": coverage, "sustainedFindings": problems,
            "thresholdPolicy": "17 unchanged demo alert queries at cutoff (5m/10m windows); >=90% telemetry bucket coverage",
            "policySha256": rules["sha256"], "policyCapturedUtc": rules["capturedUtc"],
            "bpa": "Not assessed yet", "maintenance": "Open", "ctInventory": "Open inventory caveat"}


def _legacy_envelope(settings, evidence, attachments, workbook_copy=False):
    if not settings.sender or not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+", settings.sender):
        raise ControlledError("ACS_SENDER must be the actual Azure-provisioned sender")
    if settings.recipients != (PILOT_RECIPIENT,):
        raise ControlledError("Recipient not permitted")
    if not workbook_copy and (len(attachments) != 2 or {a["contentType"] for a in attachments} != {
            "application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}):
        raise ControlledError("Both PDF and Excel are required")
    if sum(a["size"] for a in attachments) > MAX_ATTACHMENTS:
        raise ControlledError("Attachment pair exceeds 5 MiB unencoded")
    job = evidence["job"]
    prefix = "REHEARSAL - NOT A SCHEDULED SHIFT" if job["mode"] == "dryrun" else "Shift health"
    subject = f"{prefix} | {local_time(job['boundaryUtc'])} | {evidence['health']['status']}"
    body = (
        f"Operations report {job['reportId']}\n{prefix}\n"
        f"Nominal shift: {local_time(job['nominalStartUtc'])} to {local_time(job['boundaryUtc'])}\n"
        f"Measurement cutoff: {job['sourceEndUtc']} ({local_time(job['sourceEndUtc'])})\n"
        f"Extraction freeze: {evidence['freezeAtUtc']}\nHealth: {evidence['health']['status']}\n"
        f"Fresh required signals: {evidence['health']['freshSignals']}/14\n"
        + "Key exceptions: " + ("; ".join(evidence["health"]["sustainedFindings"][:3]) or "None observed in evaluated rules") + "\n"
        + "Handover actions: review attached evidence; maintenance and Change Tracking evidence remain open; BPA has not been run.\n"
        + "\n".join(LIMITATIONS) + "\nPDF and complete XLSX share the immutable evidence snapshot."
    )
    envelope = {"reportId": job["reportId"], "sender": settings.sender,
                "to": list(settings.recipients), "subject": subject, "body": body,
                "attachments": sorted(attachments, key=lambda a: a["name"])}
    return envelope


ENVELOPE_FIELDS = ("reportId", "sender", "to", "subject", "body", "attachments")
HTML_ENVELOPE_FIELDS = ("schemaVersion", "templateVersion", "htmlBody", "inlineAssets", "emailSummary")


def envelope_payload(value):
    version = value.get("schemaVersion", 1)
    if version not in (1, 2, 3):
        raise ControlledError("Unsupported email envelope version")
    keys = ENVELOPE_FIELDS + (HTML_ENVELOPE_FIELDS if version in (2, 3) else ())
    return {key: value[key] for key in keys}


def validate_inline_assets(envelope):
    if envelope.get("schemaVersion", 1) == 1:
        if envelope.get("inlineAssets") or envelope.get("htmlBody"):
            raise ControlledError("HTML content requires a versioned envelope")
        return []
    if envelope.get("schemaVersion") not in (2, 3) or envelope.get("templateVersion") != "hv-table-email-v1":
        raise ControlledError("Unsupported branded email schema")
    assets = envelope.get("inlineAssets")
    if not isinstance(assets, list) or len(assets) != 2:
        raise ControlledError("Both inline brand images are required")
    names = {"brand-primary": "brand-primary.png", "brand-secondary": "brand-secondary.png"}
    seen = set()
    for asset in assets:
        if set(asset) != {"name", "blob", "size", "sha256", "contentType", "contentId"}:
            raise ControlledError("Unexpected inline brand metadata")
        cid = asset["contentId"]
        if cid not in names or cid in seen or asset["name"] != names[cid]:
            raise ControlledError("Invalid inline content ID or name")
        if (asset["contentType"] != "image/png" or type(asset["size"]) is not int
                or not 0 < asset["size"] <= 512 * 1024
                or not re.fullmatch("[0-9a-f]{64}", asset["sha256"])
                or asset["blob"] != envelope["reportId"] + "/inline/" + asset["name"]):
            raise ControlledError("Invalid inline brand path, type, size or hash")
        if "cid:" + cid not in envelope["htmlBody"]:
            raise ControlledError("Inline image is not referenced by the HTML")
        seen.add(cid)
    if sum(a["size"] for a in envelope["attachments"] + assets) > MAX_ATTACHMENTS:
        raise ControlledError("Report and inline images exceed 5 MiB unencoded")
    return assets


def validate_report_attachments(envelope, require_three=False):
    """V1/V2 retain exact old approvals; V3 binds the additional workbook PDF."""
    version = envelope.get("schemaVersion", 1)
    attachments = envelope.get("attachments")
    triple = version == 3
    if (version not in (1, 2, 3) or (require_three and not triple)
            or not isinstance(attachments, list) or len(attachments) != (3 if triple else 2)):
        raise ControlledError("Invalid report attachment count/version; three reports required for new schedules")
    seen = set()
    for attachment in attachments:
        if (not isinstance(attachment, dict)
                or set(attachment) != {"name", "blob", "size", "sha256", "contentType"}
                or not isinstance(attachment["name"], str)
                or not attachment["name"]
                or not isinstance(attachment["contentType"], str)
                or attachment["name"] in seen
                or type(attachment["size"]) is not int or attachment["size"] <= 0
                or not isinstance(attachment["sha256"], str)
                or not re.fullmatch("[0-9a-f]{64}", attachment["sha256"])
                or attachment["blob"] != envelope["reportId"] + "/" + attachment["name"]
                or "/" in attachment["name"] or "\\" in attachment["name"]):
            raise ControlledError("Invalid report attachment path, name, size or hash")
        seen.add(attachment["name"])
    xlsx_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if triple:
        report = "HV-" + envelope["reportId"]
        expected = {(report + ".pdf", "application/pdf"), (report + ".xlsx", xlsx_type),
                    (report + "-workbook.pdf", "application/pdf")}
        if {(a["name"], a["contentType"]) for a in attachments} != expected:
            raise ControlledError("Exact original PDF, Excel and workbook PDF are required")
    elif {a["contentType"] for a in attachments} != {"application/pdf", xlsx_type}:
        raise ControlledError("Legacy PDF and Excel pair is required")
    if sum(a["size"] for a in attachments) > MAX_ATTACHMENTS:
        raise ControlledError("Report attachments exceed 5 MiB unencoded")
    return attachments


def build_envelope(settings, evidence, attachments, inline_assets=None, workbook_copy=False):
    if workbook_copy and inline_assets is None:
        raise ControlledError("New workbook PDF requires a versioned branded envelope")
    envelope = _legacy_envelope(settings, evidence, attachments, workbook_copy)
    if inline_assets is None:
        return envelope
    from email_template import present_email
    presentation = present_email(evidence)
    envelope.update({
        "schemaVersion": 3 if workbook_copy else 2, "templateVersion": "hv-table-email-v1",
        "subject": presentation["subject"], "body": presentation["plainText"],
        "htmlBody": presentation["html"], "emailSummary": presentation["summary"],
        "inlineAssets": sorted(inline_assets, key=lambda a: a["name"]),
    })
    validate_report_attachments(envelope)
    validate_inline_assets(envelope)
    if len(canonical(envelope)) > 64 * 1024:
        raise ControlledError("Branded email envelope exceeds the approval reader budget")
    return envelope


def verify_approval(approval, envelope):
    if (approval.get("reportId") != envelope["reportId"] or approval.get("to") != envelope["to"]
            or approval.get("approved") is not True):
        raise ControlledError("No exact report/recipient approval")
    if approval.get("envelopeSha256") == sha(canonical(envelope)):
        return
    if envelope.get("schemaVersion") in (2, 3):
        raise ControlledError("Branded email requires approval of the complete HTML and inline images")
    if (approval.get("subjectSha256") != sha(envelope["subject"].encode()) or
            approval.get("bodySha256") != sha(envelope["body"].encode()) or
            approval.get("sender") != envelope["sender"] or
            approval.get("attachments") != envelope["attachments"]):
        raise ControlledError("Approval does not match this exact envelope")
