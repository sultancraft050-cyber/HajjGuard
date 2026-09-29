# README

HajjGuard is a Django decision-support prototype for crowd telemetry, risk analysis, routing, group drift, SOS workflows, and privacy-aware lost-pilgrim recovery.

**The system is evaluated on public benchmark images and generated movement data. It has not been field validated or deployed at a holy site.**

Verified implementation includes the Django modular monolith, migrations, core workflows, tests, explicit consent, privacy-minimized QR payloads, retention tooling, and honest benchmark artifacts. Nusuk, SCADA, Ministry, Civil Defense, CCTV infrastructure, wallet, and emergency-service adapters are simulated or future integrations unless separately authorized and evidenced.

Use Python 3.12, install `requirements.txt`, set environment variables from `.env.example`, run migrations, and execute `manage.py test`. Run `manage.py prune_location_pings --hours 24 --dry-run` before retention deletion. Run `manage.py evaluate_system_metrics` only with the required raw scenarios; missing metrics remain `NOT MEASURED`.
