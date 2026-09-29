# Known Limitations

- Full Django checks, migrations, and tests still require a compatible Python dependency environment.
- PostgreSQL validation has not yet run; settings currently default to SQLite and need a documented PostgreSQL configuration.
- External Nusuk, SCADA, Ministry, Civil Defense, CCTV, and emergency-service integrations are not evidenced as authorized live integrations.
- Existing views still need a complete authorization pass; this audit identifies that as the next security gate.
- Existing inherited tests contain assumptions about simulated adapters and must be separated from production evidence.
