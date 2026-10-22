import io
import re
import zipfile
from collections import Counter
from unittest.mock import patch
from xml.etree import ElementTree as ET

import fitz
import xlsxwriter
from reportlab.pdfgen.canvas import Canvas

from artifacts import dashboard, workbook
from domain import ControlledError, LIMITATIONS, sha, stamp
from queries import contracts
from tests.fakes import NOW, OfflineCase, evidence, job
from tests.synthetic import large_workbook
from workbook_pdf import (BOLD, FONT, LEFT, NS, RIGHT, ROW_LABEL, _bands, _lines,
                          parse_workbook, render_workbook_pdf)


def make_book(write):
    stream = io.BytesIO()
    book = xlsxwriter.Workbook(stream, {"in_memory": True})
    write(book)
    book.close()
    return stream.getvalue()


def change_xml(data, path, change):
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(result, "w") as target:
        for name in source.namelist():
            raw = source.read(name)
            if name == path:
                root = ET.fromstring(raw)
                change(root)
                raw = ET.tostring(root)
            target.writestr(name, raw)
    return result.getvalue()


def compact(text):
    return re.sub(r"\s+", "", text)


class WorkbookPDFTests(OfflineCase):
    def assert_visible(self, data):
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                self.assertAlmostEqual(page.rect.width, 841.89, places=1)
                self.assertAlmostEqual(page.rect.height, 595.28, places=1)
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            self.assertGreaterEqual(span["size"], 7)
                            x0, y0, x1, y1 = span["bbox"]
                            self.assertGreaterEqual(x0, 0)
                            self.assertGreaterEqual(y0, 0)
                            self.assertLessEqual(x1, page.rect.width)
                            self.assertLessEqual(y1, page.rect.height)

    def audit_cells(self, xlsx):
        sheets = parse_workbook(xlsx)
        drawn = Counter()
        original = Canvas.drawString

        def capture(canvas, x, y, text, *args, **kwargs):
            drawn[text] += 1
            return original(canvas, x, y, text, *args, **kwargs)

        with patch.object(Canvas, "drawString", capture):
            pdf = render_workbook_pdf(xlsx)
        expected = Counter()
        for sheet in sheets:
            bands, preferred = _bands(sheet)
            first = min(sheet["rows"], default=None)
            for band in bands:
                extra = ((RIGHT - LEFT - ROW_LABEL - sum(preferred[c] for c in band)) / len(band)
                         if band else 0)
                for row, cells in sheet["rows"].items():
                    for col in band:
                        if col in cells:
                            text = cells[col]
                            lines = _lines(text, preferred[col] + extra - 8,
                                           BOLD if row == first else FONT)
                            self.assertEqual("".join(lines), text.replace("\n", "").replace(
                                "\r", "\\r").replace("\t", "\\t"))
                            expected.update(lines)
        # Includes every occurrence, blanks, duplicates, horizontal bands and caches.
        self.assertFalse(expected - drawn)
        with fitz.open(stream=pdf, filetype="pdf") as document:
            extracted = compact("".join(page.get_text() for page in document))
            for fragment in expected:
                if compact(fragment):
                    self.assertIn(compact(fragment), extracted)
        self.assert_visible(pdf)
        return pdf, sheets

    def test_actual_workbook_all_twenty_sheets_summary_caches_and_banner(self):
        e = evidence()
        _, parity = dashboard(e)
        data, _ = workbook(e, contracts(job(), stamp(NOW)), parity)
        before = sha(data)
        pdf, sheets = self.audit_cells(data)
        self.assertEqual(sha(data), before)
        self.assertEqual(len(sheets), 20)
        self.assertEqual(sheets[0]["name"], "Shift Summary")
        self.assertEqual(sheets[-2]["name"], "Provenance")
        self.assertEqual(sheets[-1]["name"], "Frozen Chart Data")
        self.assertTrue(sheets[0]["images"])
        values = [v for row in sheets[0]["rows"].values() for v in row.values()]
        self.assertTrue(all(value in values for value in LIMITATIONS))
        self.assertIn(e["job"]["sourceEndUtc"], values)
        self.assertIn("570", values)
        with fitz.open(stream=pdf, filetype="pdf") as document:
            self.assertTrue(document[0].get_images())

    def test_large_workbook_sample_every_cell_fragment_and_meaningful_page_count(self):
        data, stats = large_workbook()
        pdf, sheets = self.audit_cells(data)
        self.assertEqual(len(sheets), stats["sheets"])
        self.assertEqual(sum(len(s["rows"]) for s in sheets), stats["rows"])
        self.assertEqual(sum(len(r) for s in sheets for r in s["rows"].values()), stats["cells"])
        self.assertEqual(sum(v == "" for s in sheets for r in s["rows"].values()
                             for v in r.values()), stats["blank"])
        with fitz.open(stream=pdf, filetype="pdf") as document:
            self.assertGreater(len(document), 100)
            self.assertLess(len(document), 500)
        self.assertLess(len(pdf), 2 * 1024 * 1024)

    def test_zero_false_true_blank_formula_string_error_and_zero_caches(self):
        def write(book):
            sheet = book.add_worksheet("Values")
            sheet.write_row(0, 0, ["zero", "false", "true", "blank", "cache", "string", "empty", "error"])
            sheet.write_number(1, 0, 0)
            sheet.write_boolean(1, 1, False)
            sheet.write_boolean(1, 2, True)
            sheet.write_blank(1, 3, None, book.add_format({"bold": True}))
            sheet.write_formula(1, 4, "=0", None, 0)
            sheet.write_formula(1, 5, '="cached <&>"', None, "cached <&>")
            sheet.write_formula(1, 6, '=""', None, "")
            sheet.write_formula(1, 7, "=NA()", None, "#N/A")
        data = make_book(write)
        def explicit_empty_string_cache(root):
            root.find(".//s:c[@r='G2']", NS).set("t", "str")
        data = change_xml(data, "xl/worksheets/sheet1.xml", explicit_empty_string_cache)
        _, sheets = self.audit_cells(data)
        self.assertEqual(list(sheets[0]["rows"][2].values()),
                         ["0", "FALSE", "TRUE", "", "0", "cached <&>", "", "#N/A"])

    def test_wide_bands_tall_rows_long_tokens_urls_json_no_truncation(self):
        def write(book):
            sheet = book.add_worksheet("Wide and long")
            sheet.set_column(0, 29, 24)
            sheet.write_row(0, 0, [f"Column {n}" for n in range(30)])
            sheet.write_string(1, 0, "row identity")
            for col in range(1, 30):
                sheet.write_string(1, col, f"full-value-column-{col}-" + "abcdef0123456789" * 4)
            sheet.write_string(2, 29, "https://example.invalid/" + "a9" * 1500)
            sheet.write_string(3, 29, '{"json": "' + "z" * 32750 + '"}')
            sheet.write_string(4, 29, "timestamp=2026-07-29T00:00:00.000Z\nsecond line\tend\rCR")
        data = make_book(write)
        pdf, sheets = self.audit_cells(data)
        self.assertGreater(len(_bands(sheets[0])[0]), 3)
        with fitz.open(stream=pdf, filetype="pdf") as document:
            self.assertGreater(len(document), 20)
            self.assertIn("AD", "".join(p.get_text() for p in document))

    def test_oversized_header_is_fully_paginated_not_elided(self):
        def write(book):
            sheet = book.add_worksheet("Long header")
            sheet.write_string(0, 0, "header-" * 4000)
            sheet.write_string(1, 0, "final-data-after-entire-header")
        self.audit_cells(make_book(write))

    def test_empty_sheets_hidden_sheets_and_workbook_order(self):
        def write(book):
            book.add_worksheet("Second by name")
            hidden = book.add_worksheet("A hidden sheet")
            hidden.hide()
            hidden.write_string(0, 0, "hidden content must not disappear")
            book.add_worksheet("Empty data").write_string(0, 0, "No rows returned")
        pdf, sheets = self.audit_cells(make_book(write))
        self.assertEqual([s["name"] for s in sheets],
                         ["Second by name", "A hidden sheet", "Empty data"])
        with fitz.open(stream=pdf, filetype="pdf") as document:
            self.assertEqual(len(document), 3)
            self.assertIn("Empty worksheet", document[0].get_text())

    def test_empty_report_datasets_still_render_every_sheet_and_zero_cache(self):
        e = evidence()
        e["datasets"] = {name: [] for name in e["datasets"]}
        _, parity = dashboard(e)
        data, _ = workbook(e, contracts(job(), stamp(NOW)), parity)
        _, sheets = self.audit_cells(data)
        self.assertEqual(len(sheets), 20)
        self.assertIn("0", [v for row in sheets[0]["rows"].values() for v in row.values()])

    def test_deterministic_compressed_pdf_and_budget_exhaustion(self):
        data = make_book(lambda b: b.add_worksheet("Data").write_string(0, 0, "A readable workbook"))
        first = render_workbook_pdf(data)
        self.assertEqual(first, render_workbook_pdf(data))
        self.assertIn(b"/FlateDecode", first)
        with self.assertRaisesRegex(ControlledError, "budget"):
            render_workbook_pdf(data, max_bytes=len(first) - 1)

    def test_missing_or_empty_numeric_formula_cache_fails_closed(self):
        data = make_book(lambda b: b.add_worksheet().write_formula(0, 0, "=1", None, 1))
        for remove in (True, False):
            def change(root):
                cell = root.find(".//s:c", NS)
                value = cell.find("s:v", NS)
                if remove:
                    cell.remove(value)
                else:
                    value.text = None
            bad = change_xml(data, "xl/worksheets/sheet1.xml", change)
            with self.assertRaisesRegex(ControlledError, "cache"):
                render_workbook_pdf(bad)

    def test_bad_archives_xml_numeric_and_cell_types_are_controlled_errors(self):
        data = make_book(lambda b: b.add_worksheet().write_number(0, 0, 1))
        for bad in (b"", b"not a workbook", b"PK broken archive"):
            with self.assertRaises(ControlledError):
                render_workbook_pdf(bad)
        for kind, value in (("n", "NaN"), ("n", "infinity"), ("n", "not numeric"),
                            ("b", "2"), ("unknown", "value"), ("s", "-1")):
            def change(root):
                cell = root.find(".//s:c", NS)
                cell.set("t", kind)
                cell.find("s:v", NS).text = value
            bad = change_xml(data, "xl/worksheets/sheet1.xml", change)
            with self.assertRaises(ControlledError):
                render_workbook_pdf(bad)

    def test_unsupported_glyph_and_invalid_controls_are_never_replaced_silently(self):
        for text in ("unsupported \U0001f600", "invalid \x01", "unpaired \ud800"):
            if "\ud800" in text:
                data = make_book(lambda b: b.add_worksheet().write_string(0, 0, "safe"))
                def change(root):
                    root.find(".//s:t", NS).text = "_xD800_"
                data = change_xml(data, "xl/sharedStrings.xml", change)
            else:
                data = make_book(lambda b: b.add_worksheet().write_string(0, 0, text))
            with self.assertRaises(ControlledError):
                render_workbook_pdf(data)

    def test_notdef_glyph_mapping_fails_closed_even_when_character_is_in_cmap(self):
        from reportlab.pdfbase import pdfmetrics
        data = make_book(lambda b: b.add_worksheet().write_string(0, 0, "A"))
        parse_workbook(data)
        with patch.dict(pdfmetrics.getFont(FONT).face.charToGlyph, {ord("A"): 0}):
            with self.assertRaisesRegex(ControlledError, "glyph"):
                render_workbook_pdf(data)

    def test_escaped_literal_text_is_decoded_once_and_rich_text_is_complete(self):
        def write(book):
            sheet = book.add_worksheet("Strings")
            sheet.write_string(0, 0, "literal _x0041_ remains literal")
            sheet.write_rich_string(1, 0, "first ", book.add_format({"bold": True}),
                                    "middle", " last")
        _, sheets = self.audit_cells(make_book(write))
        self.assertEqual(sheets[0]["rows"][1][0], "literal _x0041_ remains literal")
        self.assertEqual(sheets[0]["rows"][2][0], "first middle last")

    def test_duplicate_coordinate_and_missing_worksheet_fail_closed(self):
        data = make_book(lambda b: b.add_worksheet().write_string(0, 0, "one"))
        def duplicate(root):
            row = root.find("s:sheetData/s:row", NS)
            row.append(ET.fromstring(ET.tostring(row[0])))
        bad = change_xml(data, "xl/worksheets/sheet1.xml", duplicate)
        with self.assertRaises(ControlledError):
            render_workbook_pdf(bad)
        def missing(root):
            root.find("s:sheets", NS).clear()
        with self.assertRaises(ControlledError):
            render_workbook_pdf(change_xml(data, "xl/workbook.xml", missing))

    def test_inline_strings_are_complete(self):
        data = make_book(lambda b: b.add_worksheet().write_string(0, 0, "placeholder"))
        def inline(root):
            cell = root.find(".//s:c", NS)
            cell.set("t", "inlineStr")
            cell.remove(cell.find("s:v", NS))
            string = ET.SubElement(cell, "{" + NS["s"] + "}is")
            ET.SubElement(string, "{" + NS["s"] + "}t").text = "inline <&> literal value"
        data = change_xml(data, "xl/worksheets/sheet1.xml", inline)
        _, sheets = self.audit_cells(data)
        self.assertEqual(sheets[0]["rows"][1][0], "inline <&> literal value")

    def test_external_relationship_and_unsupported_drawing_fail_not_omit(self):
        data, _ = large_workbook()
        def external(root):
            root[0].set("TargetMode", "External")
        with self.assertRaisesRegex(ControlledError, "external"):
            render_workbook_pdf(change_xml(data, "xl/_rels/workbook.xml.rels", external))
        def unsupported(root):
            anchor = root[0]
            anchor.remove(anchor.find("d:pic", NS))
            ET.SubElement(anchor, "{" + NS["d"] + "}graphicFrame")
        with self.assertRaisesRegex(ControlledError, "drawing"):
            render_workbook_pdf(change_xml(data, "xl/drawings/drawing1.xml", unsupported))
