#!/usr/bin/env python3
"""Generate daily UTC snapshot of canonical commitment document hashes.

Pulls the latest signed attestation manifest from R2 (if available),
verifies its Ed25519 signature, and includes the attestation hash in the
daily ledger root. Supports hash chaining via prev_root_hash.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from glob import glob
from pathlib import Path

import yaml

from canonicalize_and_hash import (
    canonicalize_markdown_bytes,
    canonicalize_yaml_bytes,
    sha256_hex,
)

KEYS_DIR = Path("keys")
LEDGER_DIR = Path("ledger/roots")
ATTESTATION_CACHE = Path("attestations/latest.json")
FEE_CACHE = Path("catalogs/fees.yaml")
CATALOG_ARCHIVE = Path("catalogs/archive")
R2_PUBLIC_URL = "https://ledger.barta.shop"


def _load_public_keys() -> list[bytes]:
    """Load all active public keys (current + retired grace period)."""
    keys = []
    for pattern in ["keys/*.pub", "keys/retired/*.pub"]:
        for key_path in glob(pattern):
            raw = Path(key_path).read_text(encoding="utf-8").strip()
            keys.append(base64.b64decode(raw))
    return keys


def _verify_attestation(manifest: dict) -> bool:
    """Verify Ed25519 signature on an attestation manifest.

    Returns True if signature is valid, False if no signature or invalid.
    """
    sig_b64 = manifest.get("signature")
    if not sig_b64:
        print("  warning: attestation has no signature", file=sys.stderr)
        return False

    try:
        from nacl.signing import VerifyKey
    except ImportError:
        print("  warning: PyNaCl not installed, skipping verification", file=sys.stderr)
        return False

    # Build the payload that was signed (manifest without signature field)
    payload_dict = {k: v for k, v in manifest.items() if k != "signature"}
    payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode()
    sig = base64.b64decode(sig_b64)

    for pub_bytes in _load_public_keys():
        try:
            VerifyKey(pub_bytes).verify(payload, sig)
            return True
        except Exception:
            continue

    print("  error: attestation signature did not match any known key", file=sys.stderr)
    return False


def _fetch_from_r2(s3_key: str, local_path: Path) -> bool:
    """Fetch a file from the public R2 bucket via HTTPS.

    Falls back to the existing local cache if the fetch fails.
    Returns True if the local file exists after the attempt.
    """
    url = f"{R2_PUBLIC_URL}/{s3_key}"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, str(local_path))
    except Exception as exc:
        print(f"  warning: could not fetch {url}: {exc}", file=sys.stderr)

    return local_path.exists()


def _fetch_attestation() -> dict | None:
    """Fetch latest attestation from R2 or local cache."""
    if not _fetch_from_r2("attestations/latest.json", ATTESTATION_CACHE):
        return None

    try:
        return json.loads(ATTESTATION_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("  warning: attestation cache is malformed", file=sys.stderr)
        return None


def _get_prev_root_hash() -> str | None:
    """Find the most recent ledger root and return its hash."""
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    roots = sorted(LEDGER_DIR.glob("*.json"))
    if not roots:
        return None
    prev_content = roots[-1].read_text(encoding="utf-8")
    return hashlib.sha256(prev_content.encode("utf-8")).hexdigest()


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    policy_path = "policies/privacy_policy.md"
    bor_path = "policies/creator_bill_of_rights.md"
    tos_path = "policies/terms_of_service.md"

    # Fee schedule is pulled from R2 (published by backend attestation pipeline).
    # If the hash changes, archive the old copy before overwriting.
    old_fee_bytes: bytes | None = None
    if FEE_CACHE.exists():
        old_fee_bytes = FEE_CACHE.read_bytes()

    _fetch_from_r2("catalogs/fees.yaml", FEE_CACHE)
    if not FEE_CACHE.exists():
        print("  error: fee schedule not available (no R2 and no local cache)", file=sys.stderr)
        return 1
    fee_path = str(FEE_CACHE)

    if old_fee_bytes and old_fee_bytes != FEE_CACHE.read_bytes():
        CATALOG_ARCHIVE.mkdir(parents=True, exist_ok=True)
        archive_dest = CATALOG_ARCHIVE / f"fees_{today}.yaml"
        archive_dest.write_bytes(old_fee_bytes)
        old_hash = sha256_hex(old_fee_bytes)
        print(f"  fee schedule changed, archived old version -> {archive_dest} ({old_hash[:12]}…)", file=sys.stderr)

    # Write a JSON mirror for the trust-center (which doesn't parse YAML)
    fee_data = yaml.safe_load(FEE_CACHE.read_text(encoding="utf-8"))
    FEE_CACHE.with_suffix(".json").write_text(
        json.dumps(fee_data, indent=2) + "\n", encoding="utf-8",
    )

    snapshot: dict = {
        "date": today,
        "fee_path": "catalogs/fees.yaml",
        "fee_hash": sha256_hex(canonicalize_yaml_bytes(fee_path)),
        "policy_path": policy_path,
        "policy_hash": sha256_hex(canonicalize_markdown_bytes(policy_path)),
        "bor_path": bor_path,
        "bor_hash": sha256_hex(canonicalize_markdown_bytes(bor_path)),
        "tos_path": tos_path,
        "tos_hash": sha256_hex(canonicalize_markdown_bytes(tos_path)),
    }

    # Hash chaining: include previous root hash
    prev_hash = _get_prev_root_hash()
    if prev_hash:
        snapshot["prev_root_hash"] = prev_hash

    # Attestation: pull from R2, verify, and include
    attestation = _fetch_attestation()
    if attestation:
        print("  found attestation manifest", file=sys.stderr)
        if _verify_attestation(attestation):
            print("  attestation signature verified", file=sys.stderr)
            # Hash the full attestation manifest for inclusion in ledger
            att_canonical = json.dumps(attestation, sort_keys=True, separators=(",", ":"))
            snapshot["attestation_hash"] = hashlib.sha256(att_canonical.encode("utf-8")).hexdigest()
            snapshot["attestation_commit"] = attestation.get("commit_sha")
        else:
            print("  attestation verification failed, excluding from ledger", file=sys.stderr)
    else:
        print("  no attestation available, skipping", file=sys.stderr)

    out_path = LEDGER_DIR / f"{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    new_content = json.dumps(snapshot, indent=2) + "\n"
    if out_path.exists() and out_path.read_text(encoding="utf-8") == new_content:
        return 0

    out_path.write_text(new_content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
