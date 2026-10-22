"""Package-local, verified PNGs for Outlook-compatible CID images."""

import hashlib
import json
from pathlib import Path


def brand_images():
    root = Path(__file__).parent / "config" / "email-branding"
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    output = []
    for asset in manifest["assets"]:
        if asset["name"] not in ("brand-primary.png", "brand-secondary.png"):
            raise ValueError("Unapproved email brand asset.")
        data = (root / asset["name"]).read_bytes()
        if len(data) != asset["size"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise ValueError("Packaged email brand asset changed.")
        output.append((asset, data))
    if {item[0]["contentId"] for item in output} != {"brand-primary", "brand-secondary"} or len(output) != 2:
        raise ValueError("Both inline brand images are required.")
    return output
