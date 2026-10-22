import copy
import datetime as dt
import importlib
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from adapters import (ARM_AUDIENCE, GRAFANA_AUDIENCE, LOGS_AUDIENCE, AzureStore,
                      JobQueue, Mailer, Sources, credential)
from artifacts import dashboard
from domain import (ControlledError, DASHBOARD_UID, GRAFANA_ENDPOINT, SCOPE, SUB,
                    WORKSPACES, parse_utc, stamp)
from tests.fakes import NOW, OfflineCase, evidence, job, native_pdf, settings


class Response:
    def __init__(self, code=200, data=None, content=None):
        self.status_code, self.headers = code, {}
        self.content = content if content is not None else json.dumps(data or {}).encode()
        self.value = data or {}

    def json(self):
        return self.value


class AdapterTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.identity = MagicMock()
        self.identity.get_token.return_value = SimpleNamespace(token="not-a-real-token")
        self.session = MagicMock()
        self.source = Sources(settings(), self.identity, self.session, sleep=lambda _: None)

    def test_identity_selection_no_secret_fallback(self):
        with patch.dict(os.environ, {"WEBSITE_HOSTNAME": "test.azurewebsites.net"}, clear=True):
            with patch("azure.identity.ManagedIdentityCredential") as mi, patch("azure.identity.AzureCliCredential") as cli:
                credential()
                mi.assert_called_once_with()
                cli.assert_not_called()
        with patch.dict(os.environ, {}, clear=True):
            with patch("azure.identity.AzureCliCredential") as cli:
                credential()
                self.assertEqual(cli.call_args.kwargs["subscription"], SUB)

    def test_read_retries_only_429_503_not_timeout_500_or_mutation(self):
        url = GRAFANA_ENDPOINT + "/api/health"
        self.session.request.side_effect = [Response(429), Response(503), Response(data={"ok": True})]
        self.assertEqual(self.source.request("GET", url, GRAFANA_AUDIENCE), {"ok": True})
        self.assertEqual(self.session.request.call_count, 3)
        for failure in (Response(500), requests.Timeout()):
            self.session.reset_mock()
            self.session.request.side_effect = failure if isinstance(failure, Exception) else None
            self.session.request.return_value = failure
            with self.assertRaises(ControlledError):
                self.source.request("GET", url, GRAFANA_AUDIENCE)
            self.assertEqual(self.session.request.call_count, 1)
        self.session.reset_mock()
        self.session.request.side_effect = None
        self.session.request.return_value = Response(503)
        with self.assertRaises(ControlledError):
            self.source.request("POST", GRAFANA_ENDPOINT + "/api/dashboards/db", GRAFANA_AUDIENCE,
                                {"dashboard": {"uid": DASHBOARD_UID, "id": None}}, read=False)
        self.assertEqual(self.session.request.call_count, 1)

    def test_scope_mutation_and_redirect_guards(self):
        cases = [
            ("GET", "http://example.com", ARM_AUDIENCE, None, True),
            ("GET", "https://example.com", ARM_AUDIENCE, None, True),
            ("GET", "https://management.azure.com/subscriptions/other/resourceGroups/other/x", ARM_AUDIENCE, None, True),
            ("PUT", "https://management.azure.com" + SCOPE + "/x", ARM_AUDIENCE, {}, False),
            ("POST", GRAFANA_ENDPOINT + "/api/dashboards/db", GRAFANA_AUDIENCE,
             {"dashboard": {"uid": "hv-operations-report"}}, False),
            ("POST", GRAFANA_ENDPOINT + "/api/dashboards/db", GRAFANA_AUDIENCE,
             {"dashboard": {"uid": "hv-operations-cockpit"}}, False),
            ("POST", GRAFANA_ENDPOINT + "/api/ds/query", GRAFANA_AUDIENCE,
             {"queries": [{"azureLogAnalytics": {"query": "Perf"}}]}, True),
            ("POST", "https://api.loganalytics.io/v1/workspaces/other/query", LOGS_AUDIENCE, {}, True),
            ("POST", "https://management.azure.com/providers/Microsoft.ResourceGraph/resources",
             ARM_AUDIENCE, {"subscriptions": ["other"], "query": "resources"}, True),
        ]
        for method, url, audience, payload, read in cases:
            with self.assertRaises(ControlledError):
                self.source.request(method, url, audience, payload, read=read)
        self.session.request.assert_not_called()
        self.session.request.return_value = Response(302)
        with self.assertRaises(ControlledError):
            self.source.request("GET", GRAFANA_ENDPOINT + "/api/health", GRAFANA_AUDIENCE)
        self.assertFalse(self.session.request.call_args.kwargs["allow_redirects"])

    def test_logs_and_arg_exact_audiences(self):
        self.session.request.return_value = Response(data={"ok": True})
        self.source.request("POST", f"https://api.loganalytics.io/v1/workspaces/{next(iter(WORKSPACES.values()))}/query",
                            LOGS_AUDIENCE, {})
        self.identity.get_token.assert_called_with(LOGS_AUDIENCE)
        self.source.request("POST", "https://management.azure.com/providers/Microsoft.ResourceGraph/resources",
                            ARM_AUDIENCE, {"subscriptions": [SUB], "query": f"resources | where subscriptionId=='{SUB}' "
                                                                          f"and resourceGroup=='{SCOPE.split('/')[-1]}'"})
        self.identity.get_token.assert_called_with(ARM_AUDIENCE)

    def test_request_deadline_fails_before_network(self):
        self.source.deadline = 1
        with self.assertRaises(ControlledError):
            self.source.request("GET", GRAFANA_ENDPOINT + "/api/health", GRAFANA_AUDIENCE)
        self.session.request.assert_not_called()

    def frozen_frames(self, points):
        return {"results": {"A": {"status": 200, "frames": [{
            "schema": {"fields": [{"name": "TimeGenerated"}, {"name": "Series"}, {"name": "Value"}]},
            "data": {"values": [[int(parse_utc(t).timestamp()*1000) for t, _, _ in points],
                                [s for _, s, _ in points], [v for _, _, v in points]]},
        }]}}}

    def test_actual_grafana_frames_reconcile_frozen_rows(self):
        d, _ = dashboard(evidence())
        points = [p["_expectedPoints"] for p in d["panels"]]
        self.session.request.side_effect = [Response(data=self.frozen_frames(p)) for p in points]
        self.source.verify_frozen_frames(d, job(), points)
        self.assertEqual(self.session.request.call_count, 8)
        changed = self.frozen_frames(points[0])
        changed["results"]["A"]["frames"][0]["data"]["values"][2][0] += 1
        self.session.request.side_effect = [Response(data=changed)]
        with self.assertRaises(ControlledError):
            self.source.verify_frozen_frames(d, job(), points)

    def test_native_render_saved_uid_version_epochms_timeout(self):
        d, _ = dashboard(evidence())
        original = copy.deepcopy(d)
        existing = {"dashboard": {"uid": DASHBOARD_UID, "id": 777, "version": 5}}
        saved = {"dashboard": d}
        frames = [self.frozen_frames(p["_expectedPoints"]) for p in d["panels"]]
        self.session.request.side_effect = [Response(data=existing), Response(data={"status": "success"}),
                                            Response(data=saved)] + [Response(data=f) for f in frames] + [
                                                Response(content=native_pdf())]
        data = self.source.render(d, job())
        self.assertTrue(data.startswith(b"%PDF-"))
        calls = self.session.request.call_args_list
        save = calls[1].kwargs["json"]["dashboard"]
        self.assertEqual(save["uid"], DASHBOARD_UID)
        self.assertEqual(save["id"], 777)
        self.assertEqual(save["version"], 5)
        self.assertFalse(any("_expectedPoints" in p for p in save["panels"]))
        render = calls[-1]
        self.assertIn("/api/reports/render/pdfs?", render.args[1])
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(render.args[1]).query)
        selected = json.loads(query["dashboards"][0])
        self.assertEqual(int(selected[0]["timeRange"]["from"]),
                         int(parse_utc(job()["sourceStartUtc"]).timestamp() * 1000))
        self.assertLessEqual(render.kwargs["timeout"], 240)

    def test_private_storage_identity_capabilities(self):
        with patch("azure.storage.blob.BlobServiceClient"):
            producer = AzureStore(settings(), self.identity)
            dispatcher = AzureStore(settings("dispatcher"), self.identity)
        for store, container, write in ((producer, "approvals", False),
                                         (dispatcher, "evidence", False),
                                         (dispatcher, "reports", True),
                                         (dispatcher, "approvals", True)):
            with self.assertRaises(ControlledError):
                store._blob(container, "anything", write)

    def test_render_lease_renewal_loss_fails_and_releases(self):
        import time
        with patch("azure.storage.blob.BlobServiceClient"):
            store = AzureStore(settings(), self.identity)
        lease = MagicMock()
        lease.renew.side_effect = RuntimeError("lease lost")
        blob = MagicMock()
        blob.acquire_lease.return_value = lease
        with patch.object(store, "create"), patch.object(store, "_blob", return_value=blob), patch(
                "adapters.LEASE_RENEW_SECONDS", .005):
            with self.assertRaises(ControlledError):
                with store.rendering_lease() as check:
                    time.sleep(.03)
                    check()
        blob.acquire_lease.assert_called_once_with(lease_duration=60)
        lease.renew.assert_called()
        lease.release.assert_called_once()

    def test_queue_utf8_no_base64_matches_host_none(self):
        with patch("azure.storage.queue.QueueClient") as client:
            queue = JobQueue(settings(), self.identity)
            queue.enqueue(job())
            self.assertEqual(json.loads(client.return_value.send_message.call_args.args[0]), job())
            self.assertEqual(client.call_args.args[1], "hv-report-jobs")
            self.assertEqual(client.call_args.kwargs["retry_total"], 0)

    def test_email_sdk_durable_operation_and_documented_repeatability_headers(self):
        e = {"sender": "sender@example.com", "to": ["operator@example.com"], "subject": "approved",
             "body": "exact", "attachments": [{"name": "a.pdf", "contentType": "application/pdf"}]}
        with patch("azure.communication.email.EmailClient") as client, patch("adapters.utcnow", return_value=NOW):
            poller = client.return_value.begin_send.return_value
            poller.result.return_value = {"status": "Succeeded", "id": "operation"}
            poller.done.return_value = True
            result = Mailer(settings("dispatcher"), self.identity).submit(
                e, {"a.pdf": b"PDF"}, "12345678-1234-4234-8234-123456789012", stamp(NOW))
            self.assertEqual(result["acsStatus"], "Succeeded")
            args = client.return_value.begin_send.call_args
            self.assertEqual(args.kwargs["operation_id"], "12345678-1234-4234-8234-123456789012")
            self.assertEqual(args.kwargs["headers"]["Repeatability-First-Sent"], "Sat, 25 Jul 2026 06:55:00 GMT")
            self.assertEqual(args.kwargs["headers"]["Repeatability-Request-ID"],
                             args.kwargs["headers"]["x-ms-repeatability-request-id"])
            self.assertEqual(client.call_args.kwargs["retry_total"], 0)
            self.assertEqual(args.args[0]["content"]["plainText"], "exact")
            client.return_value.close.assert_called_once()

    def test_repeatability_expiry_never_calls_email_sdk(self):
        with patch("azure.communication.email.EmailClient") as client, patch(
                "adapters.utcnow", return_value=NOW + dt.timedelta(minutes=5)):
            with self.assertRaises(ControlledError):
                Mailer(settings("dispatcher"), self.identity).submit({}, {}, "id", stamp(NOW))
            client.assert_not_called()


class FunctionTests(OfflineCase):
    def load(self, kind):
        import function_app
        with patch.dict(os.environ, {"APP_KIND": kind}, clear=True):
            return importlib.reload(function_app)

    def test_producer_bindings_function_auth_queue_and_crons(self):
        module = self.load("producer")
        functions = module.app.get_functions()
        bindings = [b for function in functions for b in json.loads(function.get_function_json())["bindings"]]
        http = [b for b in bindings if b["type"] == "httpTrigger"]
        self.assertEqual({b["route"] for b in http}, {"prepare", "status", "connectivity", "automation"})
        self.assertTrue(all(b["authLevel"].lower() == "function" for b in http))
        queue = next(b for b in bindings if b["type"] == "queueTrigger")
        self.assertEqual(queue["connection"], "REPORT_QUEUE")
        timers = [b for b in bindings if b["type"] == "timerTrigger"]
        self.assertEqual({b["schedule"] for b in timers}, {"0 50 6,14,22 * * *", "0 55 6,14,22 * * *"})
        self.assertTrue(all(not b["runOnStartup"] for b in timers))

    def test_dispatcher_exposes_no_generation_or_queue(self):
        module = self.load("dispatcher")
        bindings = [b for f in module.app.get_functions() for b in json.loads(f.get_function_json())["bindings"]]
        self.assertEqual({b["route"] for b in bindings if b["type"] == "httpTrigger"},
                         {"preview", "dispatch", "status", "artifact", "automation"})
        self.assertFalse(any(b["type"] == "queueTrigger" for b in bindings))
        self.assertEqual(next(b for b in bindings if b["type"] == "timerTrigger")["schedule"],
                         "0 0 7,15,23 * * *")

    def test_http_invalid_no_leak_and_prepare_202(self):
        module = self.load("producer")
        result = module.respond(lambda: {"reportId": "test"}, 202)
        self.assertEqual(result.status_code, 202)
        def fail():
            raise RuntimeError("secret")
        result = module.respond(fail)
        self.assertEqual(result.status_code, 500)
        self.assertNotIn(b"secret", result.get_body())
