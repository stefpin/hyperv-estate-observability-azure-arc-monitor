import datetime as dt

from domain import assess, stamp, new_job
from email_template import present_email
from queries import contracts
from tests.fakes import NOW, OfflineCase, datasets, evidence, job


class SourceSampleFreshnessTests(OfflineCase):
    def boundary_data(self):
        selected = new_job("dryrun", NOW + dt.timedelta(minutes=5, seconds=4))
        data = datasets()
        for name in ("cpu", "memory"):
            for row in data[name]:
                row["LastSampleUtc"] = stamp(
                    dt.datetime.fromisoformat(row["TimeGenerated"].replace("Z", "+00:00"))
                    + dt.timedelta(minutes=4)
                )
        return data, selected

    def test_fresh_last_sample_not_stale_bucket_start(self):
        data, selected = self.boundary_data()
        self.assertEqual(assess(data, selected)["status"], "MONITORED SIGNALS NORMAL")
        snapshot = evidence()
        snapshot.update(job=selected, datasets=data, health=assess(data, selected))
        rows = present_email(snapshot)["summary"]["sections"][0]["rows"]
        self.assertTrue(all(row[1] == "FRESH" for row in rows))

    def test_truly_old_metric_sample_remains_insufficient(self):
        data, selected = self.boundary_data()
        for row in data["cpu"]:
            if row["Computer"] == "HV-HOST-01":
                row["LastSampleUtc"] = stamp(NOW - dt.timedelta(minutes=6))
        result = assess(data, selected)
        self.assertEqual(result["status"], "INSUFFICIENT EVIDENCE")
        self.assertIn("HV-HOST-01/CPU: stale or missing source sample", result["coverageGaps"])

    def test_queries_keep_raw_sample_timestamps_beside_bucket_means(self):
        compiled = {item["id"]: item for item in contracts(job(), stamp(NOW))}
        self.assertIn("Samples=count(),LastSampleUtc=max(TimeGenerated)", compiled["cpu"]["query"])
        self.assertEqual(compiled["memory"]["query"].count("LastSampleUtc=max(TimeGenerated)"), 2)
        self.assertIn("project TimeGenerated,Computer,LastSampleUtc,UsedPercent", compiled["memory"]["query"])
