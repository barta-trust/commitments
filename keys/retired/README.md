# Retired Keys

When an attestation signing key is rotated, move the old `.pub` file here.

Retired keys remain valid for signature verification during a grace period
so that ledger entries signed before rotation can still be verified.

To rotate:

1. Generate a new Ed25519 key pair
2. Move the current key from `keys/` to `keys/retired/`
3. Add the new `.pub` file to `keys/`
4. Update `TRUST_SIGNING_KEY` in the barta-api GHA production secrets
