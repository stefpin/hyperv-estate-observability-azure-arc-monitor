import copy
import io
import zipfile
import xml.etree.ElementTree as ET

import fitz

from artifacts import CHARTS, chart_points, dashboard, frozen_query, merge_pdf, workbook
from domain import ControlledError, DASHBOARD_UID, canonical, sha, stamp
from queries import contracts
from tests.fakes import NOW, OfflineCase, evidence, job, native_pdf

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class ArtifactTests(OfflineCase):
    def test_xlsx_full_rows_cached_formulas_arial_and_no_injection(self):
        e = evidence()
        d, parity = dashboard(e)
        compiled = contracts(job(), stamp(NOW))
        data, counts = workbook(e, compiled, parity)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            styles = ET.fromstring(archive.read("xl/styles.xml"))
            self.assertTrue(all(font.find("s:name", NS).get("val") == "Arial"
                                for font in styles.findall("s:fonts/s:font", NS)))
            summary = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            cached = [int(c.find("s:v", NS).text) for c in summary.findall(".//s:c", NS)
                      if c.find("s:f", NS) is not None]
            self.assertEqual(cached, [len(e["datasets"][c["id"]]) for c in compiled])
            for index, c in enumerate(compiled, 2):
                sheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
                self.assertEqual(len(sheet.findall("s:sheetData/s:row", NS)), counts[c["id"]] + 1)
                self.assertFalse(sheet.findall(".//s:f", NS))
            strings = archive.read("xl/sharedStrings.xml").decode()
            self.assertIn('=HYPERLINK', strings)
            self.assertFalse(any(name.startswith("xl/externalLinks") for name in archive.namelist()))
        self.assertTrue(data.startswith(b"PK"))

    def test_eight_dedicated_frozen_panels_and_no_production_uid(self):
        e = evidence()
        result, parity = dashboard(e)
        self.assertEqual(result["uid"], DASHBOARD_UID)
        self.assertEqual(len(result["panels"]), 8)
        self.assertNotIn(b"hv-operations-", canonical(result))
        for panel, record, (key, _, _) in zip(result["panels"], parity, CHARTS):
            query = panel["targets"][0]["azureLogAnalytics"]["query"]
            self.assertTrue(query.startswith("datatable("))
            self.assertNotIn("$__", query)
            self.assertEqual(record["datasetRows"], len(e["datasets"][key]))
            self.assertEqual(record["frozenQuerySha256"], sha(query.encode()))
            self.assertEqual(len(panel["_expectedPoints"]), record["chartPoints"])

    def test_xlsx_parity_tamper_refused(self):
        e = evidence()
        _, parity = dashboard(e)
        parity[0]["chartPoints"] += 1
        with self.assertRaises(ControlledError):
            workbook(e, contracts(job(), stamp(NOW)), parity)

    def test_pdf_nine_or_more_pages_readable_cutoff_and_numbering(self):
        e = evidence()
        data = merge_pdf(e, native_pdf())
        with fitz.open(stream=data, filetype="pdf") as pdf:
            self.assertGreaterEqual(len(pdf), 9)
            self.assertIn("SHIFT HEALTH", pdf[0].get_text())
            self.assertIn(e["job"]["sourceEndUtc"], pdf[0].get_text())
            for index, page in enumerate(pdf):
                self.assertIn(f"Page {index+1} of {len(pdf)}", page.get_text())

    def test_invalid_native_pdf_and_epoch_rejected(self):
        for data in (b"Not PDF", native_pdf(7), native_pdf(text="1970-01-01")):
            with self.assertRaises(ControlledError):
                merge_pdf(evidence(), data)
        document = fitz.open()
        for _ in range(8):
            document.new_page(width=842, height=595)
        blank = document.tobytes()
        document.close()
        with self.assertRaises(ControlledError):
            merge_pdf(evidence(), blank)

    def test_idle_latency_stays_missing_and_cpu_queue_not_percent(self):
        e = evidence()
        e["datasets"]["cpu"].append({"TimeGenerated": stamp(NOW), "Metric": "Processor queue",
                                      "Computer": "HV-HOST-01", "Value": 20})
        points = chart_points("cpu", e["datasets"]["cpu"], job()["sourceEndUtc"])
        self.assertFalse(any("Processor queue" in p[1] for p in points))
        self.assertIsNone(e["datasets"]["storage"][0]["ReadLatencyMs"])
        query = frozen_query([(stamp(NOW), "x'\\\nname", 1.)])
        self.assertIn("x\\'\\\\\\nname", query)
