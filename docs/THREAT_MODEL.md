# Threat Model

Assets include location pings, group membership, emergency incidents, and card references. Threats include ID enumeration, QR replay, unauthorized incident operations, export leakage, CSRF, and retained camera frames. Current mitigations are role gates, explicit consent, minimized QR payloads, audit logging, CSRF middleware, and retention tooling. Rate limiting and production deployment controls remain review items.
