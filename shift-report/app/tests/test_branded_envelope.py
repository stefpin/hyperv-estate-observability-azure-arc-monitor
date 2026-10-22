import copy
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from adapters import Mailer
from domain import (ControlledError, build_envelope, canonical, envelope_payload,
                    sha, stamp, validate_inline_assets, verify_approval)
from email_assets import brand_images
from tests.fakes import NOW, OfflineCase, evidence, settings


class BrandedEnvelopeTests(OfflineCase):
    def docs(self):
        report = evidence()["job"]["reportId"]
        return [
            {"name": "report.pdf", "blob": report + "/report.pdf", "size": 3,
             "sha256": sha(b"PDF"), "contentType": "application/pdf"},
            {"name": "report.xlsx", "blob": report + "/report.xlsx", "size": 4,
             "sha256": sha(b"XLSX"),
             "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ]

    def inline(self):
        report = evidence()["job"]["reportId"]
        return [
            {k: a[k] for k in ("name", "size", "sha256", "contentType", "contentId")}
            | {"blob": report + "/inline/" + a["name"]}
            for a, _ in brand_images()
        ]

    def branded(self):
        return build_envelope(settings(), evidence(), self.docs(), self.inline())

    def test_new_email_binds_html_and_both_logos(self):
        value = self.branded()
        self.assertEqual(value["schemaVersion"], 2)
        self.assertEqual(len(value["attachments"]), 2)
        self.assertEqual(len(value["inlineAssets"]), 2)
        self.assertIn("Monitored with Azure Monitor", value["htmlBody"])
        self.assertEqual(envelope_payload({**value, "sendEnabled": False}), value)
        self.assertLess(len(canonical(value)), 64 * 1024)

    def test_html_and_inline_tamper_invalidate_approval(self):
        value = self.branded()
        approval = {"reportId": value["reportId"], "to": value["to"], "approved": True,
                    "envelopeSha256": sha(canonical(value))}
        verify_approval(approval, value)
        for key, changed in (("htmlBody", value["htmlBody"] + "changed"),
                             ("inlineAssets", copy.deepcopy(value["inlineAssets"]))):
            altered = copy.deepcopy(value)
            altered[key] = changed
            if key == "inlineAssets":
                altered[key][0]["sha256"] = "0" * 64
            with self.assertRaises(ControlledError):
                verify_approval(approval, altered)

    def test_body_only_approval_cannot_authorize_html(self):
        value = self.branded()
        approval = {
            "reportId": value["reportId"], "to": value["to"], "approved": True,
            "subjectSha256": sha(value["subject"].encode()), "bodySha256": sha(value["body"].encode()),
            "sender": value["sender"], "attachments": value["attachments"],
        }
        with self.assertRaises(ControlledError):
            verify_approval(approval, value)

    def test_inline_path_type_id_and_total_budget(self):
        for field, bad in (("blob", "../other"), ("contentType", "text/html"),
                           ("contentId", "other"), ("size", -1), ("sha256", "bad")):
            value = self.branded()
            value["inlineAssets"][0][field] = bad
            with self.assertRaises(ControlledError):
                validate_inline_assets(value)
        value = self.branded()
        value["attachments"][0]["size"] = 5 * 1024 * 1024
        with self.assertRaises(ControlledError):
            validate_inline_assets(value)

    def test_acs_message_keeps_docs_and_adds_two_cid_images(self):
        value = self.branded()
        blobs = {"report.pdf": b"PDF", "report.xlsx": b"XLSX"}
        blobs.update({a["name"]: data for a, data in brand_images()})
        with patch("azure.communication.email.EmailClient") as client, patch("adapters.utcnow", return_value=NOW):
            client.return_value.begin_send.return_value.result.return_value = {"id": "op", "status": "Succeeded"}
            client.return_value.begin_send.return_value.done.return_value = True
            Mailer(settings("dispatcher"), MagicMock()).submit(value, blobs, "request-id", stamp(NOW))
            message = client.return_value.begin_send.call_args.args[0]
        self.assertEqual(message["content"]["html"], value["htmlBody"])
        self.assertEqual(message["content"]["plainText"], value["body"])
        docs = [a for a in message["attachments"] if "contentId" not in a]
        images = [a for a in message["attachments"] if "contentId" in a]
        self.assertEqual(len(docs), 2)
        self.assertEqual({a["contentId"] for a in images}, {"brand-primary", "brand-secondary"})
        from azure.communication.email._operations._operations import build_email_send_request
        wire = build_email_send_request(json=message)
        serialized = json.loads(wire.content)
        self.assertEqual(serialized["content"]["html"], value["htmlBody"])
        self.assertEqual({a["contentId"] for a in serialized["attachments"] if "contentId" in a},
                         {"brand-primary", "brand-secondary"})

    def triple(self):
        report = evidence()["job"]["reportId"]
        docs = self.docs()
        blobs = {}
        for doc, ending, data in zip(docs, (".pdf", ".xlsx"), (b"PDF", b"XLSX")):
            doc["name"] = f"HV-{report}{ending}"
            doc["blob"] = report + "/" + doc["name"]
            blobs[doc["name"]] = data
        name = f"HV-{report}-workbook.pdf"
        data = b"Complete workbook PDF"
        docs.append({"name": name, "blob": report + "/" + name, "size": len(data),
                     "sha256": sha(data), "contentType": "application/pdf"})
        blobs[name] = data
        blobs.update({a["name"]: data for a, data in brand_images()})
        return build_envelope(settings(), evidence(), docs, self.inline(), workbook_copy=True), blobs

    def test_v3_acs_wire_has_three_report_files_plus_two_inline_images(self):
        value, blobs = self.triple()
        with patch("azure.communication.email.EmailClient") as client, patch("adapters.utcnow", return_value=NOW):
            client.return_value.begin_send.return_value.result.return_value = {"id": "op", "status": "Succeeded"}
            client.return_value.begin_send.return_value.done.return_value = True
            Mailer(settings("dispatcher"), MagicMock()).submit(value, blobs, "request-id", stamp(NOW))
            message = client.return_value.begin_send.call_args.args[0]
        from azure.communication.email._operations._operations import build_email_send_request
        wire = json.loads(build_email_send_request(json=message).content)
        documents = [a for a in wire["attachments"] if "contentId" not in a]
        self.assertEqual(len(documents), 3)
        self.assertEqual(len(wire["attachments"]), 5)
        self.assertEqual(sum(a["contentType"] == "application/pdf" for a in documents), 2)
        self.assertEqual(wire["content"]["html"], value["htmlBody"])
        self.assertEqual(envelope_payload(value), value)

    def test_v3_mailer_itself_fails_closed_for_missing_or_modified_third_report(self):
        for missing in (True, False):
            value, blobs = self.triple()
            name = next(a["name"] for a in value["attachments"] if a["name"].endswith("-workbook.pdf"))
            if missing:
                del blobs[name]
            else:
                blobs[name] = b"x" * len(blobs[name])
            with patch("azure.communication.email.EmailClient") as client, patch(
                    "adapters.utcnow", return_value=NOW):
                with self.assertRaisesRegex(ControlledError, "integrity"):
                    Mailer(settings("dispatcher"), MagicMock()).submit(value, blobs, "id", stamp(NOW))
                client.assert_not_called()

    def test_v3_total_budget_includes_three_reports_and_both_inline_images(self):
        value, _ = self.triple()
        other = sum(a["size"] for a in value["attachments"][1:] + value["inlineAssets"])
        value["attachments"][0]["size"] = 5 * 1024 * 1024 - other
        validate_inline_assets(value)
        value["attachments"][0]["size"] += 1
        with self.assertRaisesRegex(ControlledError, "5 MiB"):
            validate_inline_assets(value)
