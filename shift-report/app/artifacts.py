"""Unattended native PDF + cached-formula XLSX, both from one immutable record set."""

import io
import json
import math
import re

import fitz
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from domain import (ControlledError, DASHBOARD_UID, DATASOURCE_UID, LIMITATIONS,
                    WORKSPACES, canonical, local_time, parse_utc, sha)
from queries import CONFIG

CHARTS = (
    ("cpu", "CPU utilization (percent; processor queue excluded)", "Value"),
    ("memory", "Physical memory used (percent)", "UsedPercent"),
    ("sql-memory", "SQL memory (MiB; overlapping categories, NOT additive)", "CommittedMiB"),
    ("sql-grants", "SQL query grants (MiB; snapshot allocation vs used)", "GrantedMiB"),
    ("cluster-storage", "Windows logical group IOPS (NOT WSFC)", "GroupIOPS"),
    ("contention", "Guest scheduling wait (ns/dispatch; NOT CPU ready %)", "P95Ns"),
    ("storage", "Storage rates (IOPS; layers and aliases NOT additive)", "TotalIOPS"),
    ("sql-activity", "SQL activity (mixed units; see series unit)", "Mean"),
)


def chart_points(key, rows, end):
    points = []
    fields = {
        "sql-memory": ("CapMiB", "CommittedMiB", "ProcessMiB", "CacheMiB", "FreeMiB"),
        "sql-grants": ("GrantedMiB", "UsedMiB"),
    }.get(key)
    for row in rows:
        if key == "cpu" and row.get("Metric") == "Processor queue":
            continue
        selected = fields or (dict((c[0], c[2]) for c in CHARTS)[key],)
        label = "/".join(str(row[k]) for k in
                         ("Computer", "Guest", "Layer", "Device", "Metric", "Counter", "Unit")
                         if row.get(k) is not None)
        for field in selected:
            value = row.get(field)
            if value is None:
                continue
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ControlledError("Invalid numeric chart value")
            moment = row.get("TimeGenerated") or row.get("Latest") or end
            parse_utc(moment)
            points.append((moment, (label + "/" + field).strip("/"), value))
    return sorted(points)


def kql_string(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "\\r").replace("\n", "\\n") + "'"


def frozen_query(points):
    cells = [f"datetime({t}),{kql_string(label)},{float(value)!r}" for t, label, value in points]
    return ("datatable(TimeGenerated:datetime,Series:string,Value:real)[\n" +
            ",\n".join(cells) + "\n]\n| order by TimeGenerated asc,Series asc")


def dashboard(evidence):
    panels, parity = [], []
    for index, (key, title, _) in enumerate(CHARTS, 1):
        points = chart_points(key, evidence["datasets"][key], evidence["job"]["sourceEndUtc"])
        query = frozen_query(points)
        parity.append({"dataset": key, "datasetRows": len(evidence["datasets"][key]),
                       "chartPoints": len(points), "chartPointsSha256": sha(canonical(points)),
                       "frozenQuerySha256": sha(query.encode())})
        panels.append({
            "id": index, "title": title, "type": "timeseries",
            "description": f"Frozen evidence {evidence['job']['reportId']}; "
                           f"cutoff {evidence['job']['sourceEndUtc']}; extraction {evidence['freezeAtUtc']}. "
                           f"{len(points)} exact plotted points from {len(evidence['datasets'][key])} full XLSX rows.",
            "gridPos": {"x": 0, "y": (index - 1) * 10, "w": 24, "h": 10},
            "datasource": {"type": "grafana-azure-monitor-datasource", "uid": DATASOURCE_UID},
            "targets": [{
                "refId": "A", "datasource": {"type": "grafana-azure-monitor-datasource", "uid": DATASOURCE_UID},
                "queryType": "Azure Log Analytics",
                "azureLogAnalytics": {"query": query, "resultFormat": "time_series",
                                     "resources": [next(iter(WORKSPACES))],
                                     "dashboardTime": False, "timeColumn": "TimeGenerated"},
            }],
            "fieldConfig": {"defaults": {
                "noValue": "N/A / no evidence", "color": {"mode": "palette-classic"},
                "custom": {"drawStyle": "line", "lineWidth": 2, "showPoints": "always",
                           "spanNulls": False, "stacking": {"mode": "none", "group": "A"}},
            }, "overrides": []},
            "options": {"legend": {"showLegend": True, "displayMode": "table", "placement": "bottom"},
                        "tooltip": {"mode": "multi"}},
            "maxDataPoints": 10000, "interval": "5m",
            "_expectedPoints": points,
        })
    result = {
        "id": None, "uid": DASHBOARD_UID, "title": "Frozen shift health report",
        "schemaVersion": 39, "version": 0, "timezone": "Etc/GMT-7", "editable": False,
        "tags": ["hv-shift-private", evidence["job"]["reportId"]],
        "time": {"from": evidence["job"]["sourceStartUtc"], "to": evidence["job"]["sourceEndUtc"]},
        "refresh": "", "templating": {"list": []}, "panels": panels,
    }
    if len(canonical(result)) > 4 * 1024 * 1024:
        raise ControlledError("Frozen dashboard payload exceeds bounded size")
    return result, parity


def write_cell(sheet, row, col, value, fmt):
    if value is None:
        sheet.write_blank(row, col, None, fmt)
    elif isinstance(value, bool):
        sheet.write_boolean(row, col, value, fmt)
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ControlledError("Nonfinite XLSX value")
        sheet.write_number(row, col, value, fmt)
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else str(value)
        if len(text) > 32767:
            raise ControlledError("XLSX cell exceeds Excel limit; refusing silent truncation")
        sheet.write_string(row, col, text, fmt)


def workbook(evidence, contracts, parity):
    stream = io.BytesIO()
    book = xlsxwriter.Workbook(stream, {"in_memory": True, "strings_to_formulas": False,
                                      "strings_to_urls": False, "nan_inf_to_errors": False})
    book.formats[0].set_font_name("Arial")
    book.set_calc_mode("auto")
    normal = book.add_format({"font_name": "Arial", "font_size": 10})
    header = book.add_format({"font_name": "Arial", "font_color": "white", "bold": True,
                             "bg_color": "#003B70", "text_wrap": True})
    title = book.add_format({"font_name": "Arial", "font_size": 15, "bold": True, "font_color": "#003B70"})
    summary = book.add_worksheet("Shift Summary")
    summary.set_column(0, 0, 29)
    summary.set_column(1, 1, 110)
    summary.write_string(0, 0, "Shift Health", title)
    summary.insert_image(0, 3, str(CONFIG / "banner.png"), {"x_scale": .25, "y_scale": .25})
    metadata = [
        ("Report ID", evidence["job"]["reportId"]), ("Mode", evidence["job"]["mode"]),
        ("Health", evidence["health"]["status"]), ("Nominal start UTC", evidence["job"]["nominalStartUtc"]),
        ("Boundary UTC", evidence["job"]["boundaryUtc"]), ("Boundary UTC+7", local_time(evidence["job"]["boundaryUtc"])),
        ("Source start UTC (inclusive)", evidence["job"]["sourceStartUtc"]),
        ("Source cutoff UTC (exclusive)", evidence["job"]["sourceEndUtc"]),
        ("Freeze at UTC (ingest inclusive)", evidence["freezeAtUtc"]), ("Bucket", "5 minutes"),
        ("Health policy", evidence["health"]["thresholdPolicy"]),
        ("Fresh required signals", f"{evidence['health']['freshSignals']}/14"),
    ]
    for r, (label, value) in enumerate(metadata, 2):
        summary.write_string(r, 0, label, header)
        summary.write_string(r, 1, value, normal)
    r = 16
    for text in LIMITATIONS + evidence["health"]["coverageGaps"] + evidence["health"]["sustainedFindings"]:
        summary.write_string(r, 0, "Scope / findings", normal)
        summary.write_string(r, 1, text, normal)
        r += 1
    summary.freeze_panes(2, 0)
    counts = {}
    for item in contracts:
        rows = evidence["datasets"][item["id"]]
        sheet = book.add_worksheet(item["sheet"])
        columns = list(dict.fromkeys(k for row in rows for k in row))
        columns = columns or ["No rows returned"]
        if len(rows) + 1 > 1048576 or len(columns) > 16384:
            raise ControlledError("Dataset exceeds native Excel limits")
        sheet.write_row(0, 0, columns, header)
        sheet.set_column(0, len(columns) - 1, 24, normal)
        sheet.freeze_panes(1, 0)
        for row_number, row in enumerate(rows, 1):
            for col_number, column in enumerate(columns):
                write_cell(sheet, row_number, col_number, row.get(column), normal)
        sheet.autofilter(0, 0, len(rows), len(columns) - 1)
        counts[item["id"]] = len(rows)
        summary.write_string(r, 0, item["id"] + " full dataset rows", normal)
        formula = f"=ROWS('{item['sheet']}'!A2:A{len(rows) + 1})" if rows else "=0"
        summary.write_formula(r, 1, formula, normal, len(rows))
        r += 1
    provenance = book.add_worksheet("Provenance")
    provenance.write_row(0, 0, ["Dataset", "Service", "Rows", "Query SHA256", "Query line / source"], header)
    line = 1
    for item in contracts:
        for queryline in item["query"].splitlines():
            for c, value in enumerate((item["id"], item["service"], counts[item["id"]],
                                       item["querySha256"], queryline)):
                write_cell(provenance, line, c, value, normal)
            line += 1
    provenance.set_column(0, 3, 24)
    provenance.set_column(4, 4, 110)
    points_sheet = book.add_worksheet("Frozen Chart Data")
    points_sheet.write_row(0, 0, ["Dataset", "UTC source timestamp", "Series", "Value"], header)
    points_sheet.set_column(0, 2, 36, normal)
    points_sheet.set_column(3, 3, 20, normal)
    pointrow = 1
    for actual in parity:
        key = actual["dataset"]
        points = chart_points(key, evidence["datasets"][key], evidence["job"]["sourceEndUtc"])
        if len(points) != actual["chartPoints"] or sha(canonical(points)) != actual["chartPointsSha256"]:
            raise ControlledError("XLSX/native chart parity failed")
        for point in points:
            points_sheet.write_string(pointrow, 0, key, normal)
            for col, value in enumerate(point, 1):
                write_cell(points_sheet, pointrow, col, value, normal)
            pointrow += 1
    book.set_properties({"title": "Frozen Shift Health", "subject": evidence["job"]["reportId"],
                         "author": "Hyper-V observability report runtime",
                         "comments": "Arial; formula caches explicitly populated; no Excel COM or external links."})
    book.close()
    return stream.getvalue(), counts


def _wrapped(canvas, text, x, y, width, size=8, leading=10):
    canvas.setFont("Helvetica", size)
    words, line = text.split(), ""
    for word in words:
        candidate = (line + " " + word).strip()
        if canvas.stringWidth(candidate, "Helvetica", size) > width and line:
            canvas.drawString(x, y, line)
            y -= leading
            line = word
        else:
            line = candidate
    if line:
        canvas.drawString(x, y, line)
        y -= leading
    return y


def summary_pdf(evidence):
    stream = io.BytesIO()
    width, height = landscape(A4)
    c = Canvas(stream, pagesize=(width, height), invariant=1)
    banner = ImageReader(str(CONFIG / "banner.png"))
    iw, ih = banner.getSize()
    bh = min(75, (width - 50) * ih / iw)
    c.drawImage(banner, 25, height - bh - 15, width=width - 50, height=bh, mask="auto")
    y = height - bh - 35
    c.setFillColor(colors.HexColor("#003B70"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(25, y, "SHIFT HEALTH | " + evidence["health"]["status"])
    y -= 19
    c.setFillColor(colors.black)
    job = evidence["job"]
    lines = [
        f"Report {job['reportId']} | {job['mode'].upper()}" +
        (" - REHEARSAL, not a scheduled shift" if job["mode"] == "dryrun" else ""),
        f"Nominal shift: {local_time(job['nominalStartUtc'])} to {local_time(job['boundaryUtc'])}",
        f"UTC source window: [{job['sourceStartUtc']}, {job['sourceEndUtc']})",
        f"Five-minute cutoff: {job['sourceEndUtc']} | freezeAt extraction: {evidence['freezeAtUtc']}",
        f"Fresh required signals: {evidence['health']['freshSignals']}/14 | {evidence['health']['thresholdPolicy']}",
        "Missing/stale: " + (", ".join(evidence["health"]["missingOrStale"]) or "None"),
        "Coverage gaps: " + ("; ".join(evidence["health"]["coverageGaps"]) or "None"),
        "Sustained findings: " + ("; ".join(evidence["health"]["sustainedFindings"]) or "None observed"),
    ] + LIMITATIONS
    for text in lines:
        y = _wrapped(c, text, 25, y, width - 50)
        y -= 3
        if y < 35:
            c.showPage()
            y = height - 30
    c.save()
    return stream.getvalue()


def merge_pdf(evidence, native):
    try:
        charts = fitz.open(stream=native, filetype="pdf")
        if len(charts) != 8:
            raise ControlledError("Native Grafana PDF must contain exactly eight chart pages")
        if any(re.search(r"1970[-/]01[-/]01|01[-/]01[-/]1970", page.get_text()) for page in charts):
            raise ControlledError("Native PDF has an invalid epoch range")
        for page in charts:
            if page.rect.width < 400 or page.rect.height < 200:
                raise ControlledError("Native PDF chart page is unreadably small")
            if not page.get_images() and len(page.get_text().strip()) < 20 and not page.get_drawings():
                raise ControlledError("Native PDF chart page is blank")
        result = fitz.open(stream=summary_pdf(evidence), filetype="pdf")
        result.insert_pdf(charts)
        for index, page in enumerate(result):
            page.insert_text((page.rect.width - 95, page.rect.height - 12),
                             f"Page {index + 1} of {len(result)}", fontsize=8)
        text = result[0].get_text()
        if evidence["job"]["sourceEndUtc"] not in text or "SHIFT HEALTH" not in text:
            raise ControlledError("PDF summary/cutoff text validation failed")
        data = result.tobytes(garbage=4, deflate=True)
        result.close()
        charts.close()
        return data
    except ControlledError:
        raise
    except (RuntimeError, ValueError, OSError):
        raise ControlledError("PDF validation or merge failed") from None
