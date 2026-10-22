"""Repository self-checks: JSON and Python syntax, Markdown relative links, forbidden private files.

Run from anywhere:  python tools/validate_repo.py
Exits with a non-zero status when a problem is found.
"""
import json
import pathlib
import py_compile
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")

errors = []


def files(suffix):
    for path in sorted(ROOT.rglob(f"*{suffix}")):
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            yield path


def check_json():
    count = 0
    for path in files(".json"):
        count += 1
        try:
            json.loads(path.read_text("utf-8-sig"))
        except ValueError as error:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({error})")
    return count


def check_python():
    count = 0
    cache = pathlib.Path(tempfile.gettempdir()) / "validate_repo.pyc"
    for path in files(".py"):
        count += 1
        try:
            py_compile.compile(str(path), cfile=str(cache), doraise=True)
        except py_compile.PyCompileError as error:
            errors.append(f"{path.relative_to(ROOT)}: {error.msg.strip()}")
    return count


def check_links():
    count = 0
    for path in files(".md"):
        in_fence = False
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for target in LINK.findall(INLINE_CODE.sub("", line)):
                if re.match(r"^(https?:|mailto:|#|data:)", target):
                    continue
                count += 1
                relative = target.split("#", 1)[0].split("?", 1)[0]
                if relative and not (path.parent / relative).exists():
                    errors.append(f"{path.relative_to(ROOT)}:{number}: broken link {target}")
    return count


def check_private_files():
    for name in ("ENVIRONMENT.txt",):
        if (ROOT / name).exists():
            errors.append(f"{name} must never be committed")
    for pattern in ("*.pfx", "*.pem", "*.key", "local.settings.json"):
        for path in ROOT.rglob(pattern):
            if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                errors.append(f"{path.relative_to(ROOT)}: private file type")


def main():
    summary = {"json": check_json(), "python": check_python(), "links": check_links()}
    check_private_files()
    print("checked", summary)
    for message in errors:
        print("ERROR", message)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
