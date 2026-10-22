import copy
import re

from domain import ControlledError, stamp
from queries import SOURCES, compile_query, contracts, manifest, parse_arg, parse_logs
from tests.fakes import NOW, OfflineCase, job


class QueryTests(OfflineCase):
    def test_original_16_contracts_and_health_policy_have_ingestion_cutoff(self):
        compiled = contracts(job(), stamp(NOW))
        self.assertEqual(len(compiled), 17)
        for original, frozen in zip(manifest()["exportDatasets"], compiled):
            if original["service"] == "logs":
                n = original["query"].count("$__timeFilter(TimeGenerated)")
                self.assertEqual(frozen["query"].count("ingestion_time() <="), n, original["id"])
                self.assertEqual(frozen["query"].count("TimeGenerated >="), n)
                self.assertEqual(frozen["query"].count("TimeGenerated < datetime"), n)
                self.assertEqual(frozen["query"].count("isnotnull(ingestion_time())"), n)
                self.assertNotIn("$__", frozen["query"])
                self.assertNotIn("${", frozen["query"])
                self.assertIn("2026-07-25T06:55:00Z", frozen["query"])
            else:
                self.assertNotIn("ingestion_time()", frozen["query"])
        health = compiled[-1]
        self.assertEqual(health["id"], "alert-health")
        self.assertIn("ingestion_time() <=", health["query"])
        self.assertIn("2026-07-25T06:45:00Z", health["query"])
        self.assertIn("2026-07-25T06:50:00Z", health["query"])
        self.assertIn("summarize Value=min(PendingGrants)", health["query"])
        self.assertNotIn("now()", health["query"])

    def test_known_tables_qualified_and_inline_union_all_bounded(self):
        for table in SOURCES:
            template = f"{table} | where $__timeFilter(TimeGenerated)"
            q = compile_query(template, job(), stamp(NOW))
            self.assertIn(f"{table} | where TimeGenerated >=", q)
            qualified = "workspace('approved')." + template
            self.assertIn("ingestion_time() <=", compile_query(qualified, job(), stamp(NOW)))
        template = "(Perf | where $__timeFilter(TimeGenerated)) | union (Heartbeat | where $__timeFilter(TimeGenerated))"
        self.assertEqual(compile_query(template, job(), stamp(NOW)).count("ingestion_time() <="), 2)

    def test_unbounded_or_unknown_source_rejected(self):
        for query in ("Perf | summarize count()", "Evil | where $__timeFilter(TimeGenerated)",
                      "Perf | where $__timeFilter(TimeGenerated) | union (Heartbeat | summarize count())"):
            with self.assertRaises(ControlledError):
                compile_query(query, job(), stamp(NOW))

    def test_buckets_and_sql_min_do_not_rewrite_peak_semantics(self):
        compiled = {q["id"]: q for q in contracts(job(), stamp(NOW))}
        self.assertIn("bin(TimeGenerated,5m)", compiled["cpu"]["query"])
        self.assertIn("PendingGrants=max(PendingGrants)", compiled["sql-memory"]["query"])
        self.assertIn("PendingGrantsMin=min(PendingGrants)", compiled["sql-memory"]["query"])
        self.assertIn("real(null)", compiled["storage"]["query"])

    def test_logs_partial_errors_and_truncation_fail(self):
        good = {"tables": [{"name": "PrimaryResult", "columns": [{"name": "X"}], "rows": [[1]]}]}
        self.assertEqual(parse_logs(good), [{"X": 1}])
        for change in ({"error": {"code": "PartialError"}}, {"truncated": True},
                       {"nextLink": "x"}, {"partialError": "x"}):
            with self.assertRaises(ControlledError):
                parse_logs({**good, **change})
        for tables in ([], good["tables"] + [{"name": "QueryStatus", "rows": []}]):
            with self.assertRaises(ControlledError):
                parse_logs({"tables": tables})
        bad = copy.deepcopy(good)
        bad["tables"][0]["rows"] = [[1, 2]]
        with self.assertRaises(ControlledError):
            parse_logs(bad)

    def test_arg_inventory_no_silent_partial(self):
        good = {"data": [{"Machine": "SQL2019-GUEST"}], "totalRecords": 1, "resultTruncated": "false"}
        self.assertEqual(len(parse_arg(good)), 1)
        for extra in ({"totalRecords": 2}, {"$skipToken": "next"}, {"resultTruncated": "true"},
                      {"error": "partial"}):
            with self.assertRaises(ControlledError):
                parse_arg({**good, **extra})
