"""Local, pinned standing authorization. No credentials, storage or service calls."""

import datetime as dt
import json
import re
from pathlib import Path, PureWindowsPath

from domain import (ControlledError, PILOT_RECIPIENT, RG, SCOPE, canonical, due_boundary, local_time,
                    parse_utc, sha, stamp, validate_inline_assets, validate_job,
                    validate_report_attachments)
from email_assets import brand_images
from email_template import present_email, render_summary

ROOT = Path(__file__).parent
POLICY_PATH = ROOT / "config" / "scheduled-send-policy.json"
POLICY_ID = "scheduled-send-v2-workbook-pdf"
FIRST_BOUNDARY = "2026-07-25T15:00:00Z"  # example: earliest dispatch boundary the standing policy may send for
SENDER = "donotreply@00000000-0000-0000-0000-000000000000.azurecomm.net"  # replace with your ACS sender address
RECIPIENTS = [PILOT_RECIPIENT]
# Illustrative approval metadata: record your own review evidence here before pinning the policy.
APPROVAL = {
    "approvedBy": PILOT_RECIPIENT,
    "approvedAt": "2026-07-24T09:00:00Z",
    "previewReportId": "dryrun-00000000-0000-0000-0000-000000000001",
    "previewNote": "Replace with the rehearsal report you reviewed before approving the recurring format.",
}
REVISION = {
    "status": "awaiting-operator-activation",
    "requestedAt": "2026-07-24T12:00:00Z",
    "request": "Example revision record: add the workbook-content PDF as a third report file and keep the original PDF and XLSX.",
    "previousPolicyId": "scheduled-send-v1",
    "previousPolicySha256": "1" * 64,
    "approvalMeaning": "approval records the earlier two-attachment approval only, not a new preview approval.",
    "approvedBy": PILOT_RECIPIENT,
    "approvedAt": "2026-07-24T13:00:00Z",
    "userReply": "Example approval reply recorded by the operator",
    "previewReportId": "dryrun-00000000-0000-0000-0000-000000000002",
    "previewEnvelopeSha256": "2" * 64,
    "approvalScope": "Recurring three-attachment format and scoped deployment; not manual test dispatch.",
    "activationRequirement": "Operator must verify the deployed package and configure the exact approved revision pin.",
}
PINNED_FILES = (
    "adapters.py", "artifacts.py", "automation.py", "domain.py", "email_assets.py",
    "email_template.py", "function_app.py", "health_rules.py", "queries.py",
    "runtime.py", "workbook_pdf.py", "host.json", "requirements.txt", "config\\alert-rules.json",
    "config\\banner.png", "config\\build_dashboards.py", "config\\query-manifest.json",
    "config\\email-branding\\manifest.json", "config\\email-branding\\brand-primary.png",
    "config\\email-branding\\brand-secondary.png",
)
POLICY_CONTRACT = {
    "schemaVersion": 1, "policyId": POLICY_ID, "approval": APPROVAL, "revision": REVISION,
    "resourceGroup": RG, "scope": SCOPE, "mode": "scheduled",
    "recipientAllowlist": RECIPIENTS, "sender": SENDER,
    "templateVersion": "hv-table-email-v1", "envelopeSchemaVersion": 3,
    "reportFiles": [".pdf", ".xlsx", "-workbook.pdf"],
    "timezone": "UTC+7", "dispatchUtc": ["07:00", "15:00", "23:00"],
    "dispatchLt": ["14:00", "22:00", "06:00 (+1 UTC date)"],
    "sourceCutoffMinutes": 5, "sourceWindowHours": 8,
    "firstBoundaryUtc": FIRST_BOUNDARY,
}


def fingerprints():
    return {name: sha(ROOT.joinpath(*PureWindowsPath(name).parts).read_bytes())
            for name in PINNED_FILES}


def load_policy(settings, require_pin=True):
    """Every enabled use rechecks local inputs and the operator's exact hash pin."""
    try:
        raw = POLICY_PATH.read_bytes()
        policy = json.loads(raw)
        digest = sha(raw)
        if (not isinstance(policy, dict) or
                set(policy) != set(POLICY_CONTRACT) | {"files", "inlineAssets"} or
                any(policy.get(key) != value for key, value in POLICY_CONTRACT.items())):
            raise ControlledError("Standing policy approval/contract mismatch")
        if policy["files"] != fingerprints():
            raise ControlledError("Standing policy format/input fingerprint mismatch")
        assets = [{key: asset[key] for key in
                   ("name", "contentId", "contentType", "size", "sha256")}
                  for asset, _ in brand_images()]
        if policy["inlineAssets"] != assets:
            raise ControlledError("Standing policy logo fingerprint mismatch")
        if require_pin and (not re.fullmatch("[0-9a-f]{64}", settings.auto_send_policy_sha256)
                            or settings.auto_send_policy_sha256 != digest):
            raise ControlledError("AUTO_SEND_POLICY_SHA256 does not match the approved local policy")
        if list(settings.recipients) != RECIPIENTS or settings.sender != SENDER:
            raise ControlledError("Standing policy sender/recipient configuration mismatch")
        return policy, digest
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ControlledError("Standing policy files are missing or invalid") from error


def scheduled_policy(settings, boundary):
    if not settings.auto_send_enabled:
        return None
    policy, digest = load_policy(settings)
    if boundary < parse_utc(policy["firstBoundaryUtc"]):
        raise ControlledError("Scheduled boundary precedes standing policy effective start")
    return policy, digest


def integrity_record(state, envelope, policy=None):
    """Small immutable receipt binds the Ready ledger to the original evidence."""
    return {
        "schemaVersion": 1, "job": state["job"], "health": state["health"],
        "createdUtc": state["createdUtc"], "startedUtc": state["startedUtc"],
        "finishedUtc": state["finishedUtc"], "freezeAtUtc": state["freezeAtUtc"],
        "extractedUtc": state["extractedUtc"], "sourceEndUtc": state["sourceEndUtc"],
        "evidenceSha256": state["evidenceSha256"], "envelopeSha256": state["envelopeSha256"],
        "attachments": state["attachments"], "inlineAssets": state["inlineAssets"],
        "emailSummarySha256": sha(canonical(envelope["emailSummary"])),
        "policyId": policy[0]["policyId"] if policy else None,
        "policySha256": policy[1] if policy else None,
    }


def verify_scheduled(settings, now, report_id, state, envelope, receipt, policy):
    """No old job, rehearsal, forged body or late Ready can inherit authorization."""
    approved, digest = policy
    boundary = due_boundary(now, "dispatch")
    if (not settings.auto_send_enabled or not settings.schedule_enabled or boundary is None
            or boundary < parse_utc(approved["firstBoundaryUtc"])
            or report_id != "shift-" + boundary.strftime("%Y%m%dT%H%M%SZ")):
        raise ControlledError("Standing policy requires the exact effective dispatch boundary")
    job = state["job"]
    validate_job(job)
    if (state["status"] != "Ready" or job["schemaVersion"] != 1 or job["mode"] != "scheduled"
            or job["reportId"] != report_id or job["boundaryUtc"] != stamp(boundary)
            or job["nominalStartUtc"] != job["sourceStartUtc"]
            or state["sourceEndUtc"] != job["sourceEndUtc"]
            or state["createdUtc"] != job["createdUtc"]):
        raise ControlledError("Standing policy requires original scheduled Ready job provenance")
    cutoff = boundary - dt.timedelta(minutes=5)
    created, started, freeze, extracted, finished = (
        parse_utc(state[key]) for key in
        ("createdUtc", "startedUtc", "freezeAtUtc", "extractedUtc", "finishedUtc"))
    if not cutoff <= created <= started <= freeze <= extracted <= finished < boundary:
        raise ControlledError("Scheduled extraction/Ready deadline or provenance mismatch")
    if (not re.fullmatch("[0-9a-f]{64}", state["evidenceSha256"])
            or receipt != integrity_record(state, envelope, policy)
            or sha(canonical(receipt)) != state.get("dispatchIntegritySha256")):
        raise ControlledError("Original evidence/envelope/Ready integrity receipt mismatch")
    if (envelope.get("schemaVersion") != approved["envelopeSchemaVersion"]
            or envelope.get("templateVersion") != approved["templateVersion"]
            or envelope["reportId"] != report_id or envelope["sender"] != approved["sender"]
            or envelope["to"] != approved["recipientAllowlist"]):
        raise ControlledError("Standing policy branded envelope/recipient mismatch")
    if len(canonical(envelope)) > 64 * 1024:
        raise ControlledError("Standing policy envelope exceeds reader budget")
    inline = validate_inline_assets(envelope)
    if [{key: asset[key] for key in ("name", "contentId", "contentType", "size", "sha256")}
            for asset in inline] != approved["inlineAssets"]:
        raise ControlledError("Standing policy requires the two exact approved inline logos")
    validate_report_attachments(envelope, require_three=True)
    summary = envelope["emailSummary"]
    skeleton = present_email({"job": job, "freezeAtUtc": state["freezeAtUtc"],
                              "health": state["health"], "datasets": {}})["summary"]
    if (set(summary) != set(skeleton) or
            any(summary[key] != skeleton[key] for key in
                set(skeleton) - {"sections", "freshness"}) or
            len(summary["sections"]) != len(skeleton["sections"])):
        raise ControlledError("Standing policy summary branding/health/provenance mismatch")
    for section, original in zip(summary["sections"], skeleton["sections"]):
        if (set(section) != set(original) or section["title"] != original["title"]
                or section["headers"] != original["headers"]):
            raise ControlledError("Standing policy summary table schema mismatch")
    rendered = render_summary(summary, job)
    if (envelope["subject"] != rendered["subject"] or envelope["body"] != rendered["plainText"]
            or envelope["htmlBody"] != rendered["html"]):
        raise ControlledError("Stored subject/plaintext/HTML differs from approved renderer")
    return {"authorizationMode": "standingPolicy", "policyId": approved["policyId"],
            "policySha256": digest, "policyApprovedAt": approved["revision"]["approvedAt"],
            "dispatchIntegritySha256": state["dispatchIntegritySha256"],
            "evidenceSha256": state["evidenceSha256"]}


def _time_pair(moment):
    return {"utc": stamp(moment), "lt": local_time(stamp(moment))}


def automation_status(settings, now):
    """Read only package files and clock; invalid opt-in never looks ready."""
    now = parse_utc(stamp(now))
    result = {
        "status": "Disabled", "appKind": settings.kind, "resourceGroup": RG,
        "scheduleEnabled": settings.schedule_enabled, "sendEnabled": settings.send_enabled,
        "autoSendEnabled": settings.auto_send_enabled, "effectiveAutoSend": False,
        "policyId": POLICY_ID, "policySha256": None, "policyVerified": False,
        "configuredPolicySha256": (settings.auto_send_policy_sha256 if
                                  re.fullmatch("[0-9a-f]{64}", settings.auto_send_policy_sha256)
                                  else None),
        "formatVerified": False, "allowedRecipients": RECIPIENTS, "allowedSender": SENDER,
        "sourceCutoffMinutes": 5, "sourceWindowHours": 8, "timezone": "UTC+7",
        "firstBoundary": _time_pair(parse_utc(FIRST_BOUNDARY)),
        "boundaries": [{"utc": "07:00", "lt": "14:00", "ltDateOffset": 0},
                       {"utc": "15:00", "lt": "22:00", "ltDateOffset": 0},
                       {"utc": "23:00", "lt": "06:00", "ltDateOffset": 1}],
        "nextCollection": None, "nextDispatch": None,
    }
    try:
        policy, digest = load_policy(settings, require_pin=settings.auto_send_enabled or
                                     bool(settings.auto_send_policy_sha256))
    except ControlledError as error:
        result.update(status="InvalidPolicy", error=str(error))
        return result
    result.update(policySha256=digest, formatVerified=True, fingerprints=policy["files"],
                  inlineAssets=policy["inlineAssets"], templateVersion=policy["templateVersion"],
                  approval=policy["approval"], revision=policy["revision"],
                  policyVerified=settings.auto_send_policy_sha256 == digest)
    boundaries = []
    anchor = max(now, parse_utc(FIRST_BOUNDARY))
    for days in range(3):
        date = anchor + dt.timedelta(days=days)
        boundaries.extend(date.replace(hour=hour, minute=0, second=0, microsecond=0)
                          for hour in (7, 15, 23))
    boundaries = [b for b in boundaries if b >= parse_utc(FIRST_BOUNDARY)]
    for phase, advance, key in (("collect", 5, "nextCollection"), ("dispatch", 0, "nextDispatch")):
        upcoming = next(b for b in boundaries if
                        b - dt.timedelta(minutes=advance) >= now or due_boundary(now, phase) == b)
        result[key] = _time_pair(upcoming - dt.timedelta(minutes=advance))
    if settings.auto_send_enabled:
        result["effectiveAutoSend"] = (settings.schedule_enabled and settings.send_enabled
                                       and bool(settings.acs_endpoint))
        result["status"] = ("Enabled" if result["effectiveAutoSend"] else "Gated")
    return result
