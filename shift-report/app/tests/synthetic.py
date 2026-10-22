"""Deterministic synthetic workbook of realistic shape: many sheets, tall and wide sheets, blanks, one image."""

import hashlib
import io
from pathlib import Path

import xlsxwriter

BANNER = Path(__file__).resolve().parents[1] / "config" / "banner.png"
ROWS_BASE = 60
ROWS_STEP = 12


def large_workbook(sheets=20):
    stream = io.BytesIO()
    book = xlsxwriter.Workbook(stream, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
    header = book.add_format({"bold": True})
    plain = book.add_format({"font_name": "Arial"})
    stats = {"sheets": sheets, "rows": 0, "cells": 0, "blank": 0}
    for s in range(sheets):
        ws = book.add_worksheet(f"Dataset {s + 1:02d}")
        columns = 5 + (s % 4) * 2
        rows = ROWS_BASE + (s % 5) * ROWS_STEP
        ws.set_column(0, columns - 1, 22)
        ws.write_row(0, 0, [f"Column {c + 1}" for c in range(columns)], header)
        stats["rows"] += 1
        stats["cells"] += columns
        if s == 0:
            ws.insert_image(0, columns + 1, str(BANNER), {"x_scale": 0.25, "y_scale": 0.25})
        for r in range(1, rows + 1):
            stats["rows"] += 1
            for c in range(columns):
                kind = (r + 2 * c + s) % 7
                if kind == 0:
                    ws.write_blank(r, c, None, plain)
                    stats["blank"] += 1
                elif kind in (1, 2):
                    ws.write_number(r, c, (r * 31 + c * 7 + s) % 1000 / 8, plain)
                elif kind == 3:
                    ws.write_string(r, c, f"2026-07-25T{(r // 12) % 24:02d}:{(r % 12) * 5:02d}:00Z", plain)
                elif kind == 4:
                    ws.write_string(r, c, hashlib.sha256(f"{s}-{r}-{c}".encode()).hexdigest(), plain)
                elif kind == 5:
                    ws.write_boolean(r, c, bool((r + c) % 2), plain)
                else:
                    ws.write_string(r, c, f"Machine-{(r + c) % 6} / Counter-{c} / sheet {s + 1}", plain)
                stats["cells"] += 1
    book.close()
    return stream.getvalue(), stats
