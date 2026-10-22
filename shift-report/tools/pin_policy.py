"""Rewrite app/config/scheduled-send-policy.json and print its SHA-256 (the value for AUTO_SEND_POLICY_SHA256).

Run after editing the constants in app/automation.py or any other pinned input (templates, queries, brand images):
    python tools/pin_policy.py
"""
import json
import pathlib
import sys

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import automation  # noqa: E402
from domain import sha  # noqa: E402


def main():
    policy = dict(automation.POLICY_CONTRACT)
    policy["files"] = automation.fingerprints()
    policy["inlineAssets"] = [
        {key: asset[key] for key in ("name", "contentId", "contentType", "size", "sha256")}
        for asset, _ in automation.brand_images()
    ]
    automation.POLICY_PATH.write_bytes((json.dumps(policy, indent=2) + "\n").encode("utf-8"))
    print(sha(automation.POLICY_PATH.read_bytes()))


if __name__ == "__main__":
    main()
