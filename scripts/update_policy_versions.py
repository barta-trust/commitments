#!/usr/bin/env python3
"""Update version manifests for policy documents with YAML frontmatter.

Scans policies/*.md for frontmatter with `version` field, computes the
canonical SHA-256, and updates the corresponding version manifest in
policies/versions/. Archives the old file if the hash changed.

Run from repo root: python scripts/update_policy_versions.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from canonicalize_and_hash import canonicalize_markdown_bytes, sha256_hex

POLICIES_DIR = Path("policies")
VERSIONS_DIR = POLICIES_DIR / "versions"
ARCHIVE_DIR = VERSIONS_DIR / "archive"


def _parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from markdown text."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])


def main() -> int:
    changed = False

    for md_path in sorted(POLICIES_DIR.glob("*.md")):
        if md_path.name == "README.md":
            continue

        text = md_path.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        if not meta:
            print(f"  skip {md_path.name}: no frontmatter")
            continue

        if "version" not in meta:
            print(f"  skip {md_path.name}: no version in frontmatter")
            continue

        doc_version = str(meta["version"])
        effective = str(meta.get("effective", ""))

        current_hash = sha256_hex(canonicalize_markdown_bytes(str(md_path)))

        stem = md_path.stem
        manifest_path = VERSIONS_DIR / f"{stem}.json"

        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {
                "document": stem.replace("_", "-"),
                "current_version": doc_version,
                "versions": [],
            }

        latest_entry = manifest["versions"][0] if manifest["versions"] else None

        if latest_entry and latest_entry["version"] == doc_version:
            # Version field unchanged — minor edit (typo, formatting).
            # Update the hash on the existing entry but don't archive or bump.
            if latest_entry["sha256"] != current_hash:
                latest_entry["sha256"] = current_hash
                manifest_path.write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
                print(f"  {md_path.name}: minor edit detected, updated hash (version still {doc_version})")
                changed = True
            else:
                print(f"  {md_path.name}: unchanged, skipping")
            continue

        print(f"  {md_path.name}: version bumped to {doc_version}, updating manifest")

        if latest_entry:
            old_version = latest_entry["version"]
            archive_name = f"{stem}_v{old_version}.md"
            old_file = latest_entry["file"]
            # Get the previous committed content (before this push)
            result = subprocess.run(
                ["git", "show", f"HEAD~1:{old_file}"],
                capture_output=True,
            )
            if result.returncode == 0:
                ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
                (ARCHIVE_DIR / archive_name).write_bytes(result.stdout)
                print(f"  archived {old_file} (v{old_version}) -> {ARCHIVE_DIR / archive_name}")
            else:
                print(f"  warning: could not retrieve old version from git")

        new_entry = {
            "version": doc_version,
            "published": date.today().isoformat(),
            "effective": effective,
            "file": str(md_path),
            "sha256": current_hash,
        }
        manifest["versions"].insert(0, new_entry)
        manifest["current_version"] = doc_version

        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        changed = True

    if not changed:
        print("No policy version changes detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
