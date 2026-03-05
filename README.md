# Barta Commitments

Public trust commitments for the [Barta](https://barta.shop) marketplace.

This repo contains the source-of-truth policy documents and daily ledger snapshots that power the [Trust Center](https://trust.barta.shop).

## Structure

```
policies/              # Policy documents (markdown)
├── privacy_policy.md
├── creator_bill_of_rights.md
├── terms_of_service.md
└── versions/          # Version history manifests

catalogs/              # Fee schedule
ledger/roots/          # Daily cryptographic snapshots
```

## How it works

Every day, each commitment document is hashed (SHA-256) and recorded in `ledger/roots/<date>.json`. Each root includes a hash of the previous day's root for chain integrity.

When a policy's version is bumped, the old version is archived and the manifest is updated.

Anyone can verify that a commitment was active on a given date by checking the ledger root against the document hash.

## Verifying a document

```bash
python scripts/canonicalize_and_hash.py --md policies/privacy_policy.md
```

Compare the output against the corresponding `policy_hash` in any ledger root.
