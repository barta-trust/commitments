# Scripts

```bash
# Generate today's ledger snapshot
python scripts/generate_daily_snapshot.py

# Update policy version manifests
python scripts/update_policy_versions.py

# Compute canonical hash of a document
python scripts/canonicalize_and_hash.py --md policies/privacy_policy.md
python scripts/canonicalize_and_hash.py --yaml catalogs/fees.yaml
```

Requires `pyyaml`. Run from repo root.
