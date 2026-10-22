"""The digest stored in config/alert-rules.json covers the rules in that file."""

import hashlib
import json
import unittest
from pathlib import Path

RULES = Path(__file__).resolve().parents[1] / "config" / "alert-rules.json"


class AlertRulesDigestTest(unittest.TestCase):
    def test_digest_covers_the_shipped_rules(self):
        data = json.loads(RULES.read_text("utf-8"))
        canonical = json.dumps(data["rules"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(data["sha256"], hashlib.sha256(canonical.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
