# Privacy and Retention

Consent defaults to false. QR payloads use an opaque card reference and exclude raw medical and identity data. `prune_location_pings --hours N [--dry-run]` deletes old location pings transactionally. Camera processing deletes source files in success and error paths. Sensitive lookups create audit records. The prototype remains subject to legal and operational review.
