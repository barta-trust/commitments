#!/usr/bin/env python3
"""Canonicalization and SHA-256 hashing helpers for commitment documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonicalize_json_bytes(path: str) -> bytes:
    """Read JSON and return canonical UTF-8 bytes with sorted keys and compact separators."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canonical.encode("utf-8")


def canonicalize_yaml_bytes(path: str) -> bytes:
    """Read YAML and return raw UTF-8 bytes (no transformation).

    Matches the digest computation in barta-api's attestation pipeline,
    which hashes the raw file content as-is.
    """
    return Path(path).read_bytes()


def canonicalize_markdown_bytes(path: str) -> bytes:
    """Normalize markdown line endings and ensure a single trailing newline."""
    text = Path(path).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines).rstrip("\n") + "\n"
    return normalized.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return lowercase SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonicalize and hash JSON or Markdown files")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", dest="json_path", help="Path to JSON file")
    group.add_argument("--yaml", dest="yaml_path", help="Path to YAML file")
    group.add_argument("--md", dest="md_path", help="Path to Markdown file")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.json_path:
        canonical_bytes = canonicalize_json_bytes(args.json_path)
    elif args.yaml_path:
        canonical_bytes = canonicalize_yaml_bytes(args.yaml_path)
    else:
        canonical_bytes = canonicalize_markdown_bytes(args.md_path)

    print(sha256_hex(canonical_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
