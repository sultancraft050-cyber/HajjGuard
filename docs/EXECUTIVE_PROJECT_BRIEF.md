# HajjGuard: executive project brief

**Verdict:** HajjGuard is a **functional academic prototype**, not a pilot or operational safety system. The current branch (`codex/full-project-audit`, assessed at `96eb3de`) should **not be merged yet**. Its most valuable contribution is the integration of pilgrim group awareness, zone and route modeling, incident handling and Arabic-first presentation in one inspectable Django application. Its highest risk is unauthenticated access to identity and personal/location workflows, documented in `docs/FINAL_PROJECT_ASSESSMENT.md` with source references.

## What exists

The repository has six Django apps, migrations, 15 standalone page templates, local/synthetic zone and incident data, directed NetworkX routing, a group-drift calculation, a linear 20-minute forecast function, a local digital-card concept, dashboards and 75 existing tests. A fresh Python 3.12.14 environment installed the repository requirements; `pip check`, Django `check`, clean SQLite migrations and the 75-test suite passed. The original Antigravity checkout remained at `6b20b5d` when inspected. The current branch's benchmark JSON says `overall_passed: false`; six supervisor measurements are `NOT MEASURED`. Four numerical entries are local harness timings or a configured horizon, not field outcomes.

## What is not established

There is no verified official Nusuk, Nafath, Ministry, Civil Defense, SCADA, CCTV infrastructure, wallet or emergency-service integration. The camera counter is a file-size simulation. There is no PostgreSQL 16 test run, field validation, sensor provenance, controlled battery/offline/drift study, operational safety case, secure deployment or authority to use official identity branding. The current README does not provide a complete clean-install runbook. Arabic/RTL structure exists, while full translation, mobile-device and accessibility quality are unverified.

## Readiness and decision

| Use | Assessment | Condition |
|---|---|---|
| Internal team demo | Conditional | Synthetic data and isolated environment |
| Supervisor demo | Conditional | Show limitations, avoid sensitive routes and official claims |
| University defense | Partial | Close critical security gaps; present missing metrics honestly |
| Public demo | No | Data disclosure and identity-switch risks |
| Controlled pilot | No | Requires authorization, expert review and validated sensors |
| Real operations | No | No safety case or operational controls |

**Next action:** assign a developer to remove the account-switch and registration-takeover paths, then apply a role/object access matrix to pilgrim lookup, telemetry, exports, simulation and incident changes. Add attack regression tests and rerun the full suite on SQLite **and genuine PostgreSQL 16**. This takes precedence over new features or visual polish.

## Five strengths

1. The domain is relevant and the project tells a coherent safety story (`README.md`, models).
2. The modular monolith is inspectable and appropriate for its current scale (`apps/`, `hajjguard_core/`).
3. Directed routing and group drift are real code paths, though not field validated (`services/routing.py`, `apps/groups/services.py`).
4. The Arabic/RTL shell and responsive templates provide a credible localized demonstration (`templates/base.html`).
5. The corrected benchmark artifact explicitly records missing evidence (`evaluation_results.json`).

## Five weaknesses

1. Public identity switch and account registration reuse defeat authentication (`apps/accounts/views.py`).
2. Public group/profile/lost-person routes expose sensitive data (`apps/groups/views.py`, `apps/accounts/views.py`).
3. Public telemetry, simulation and CSV routes allow spoofing, mutation or export (`apps/zones/views.py`, `apps/analytics/views.py`).
4. PostgreSQL, clean-install and field data are missing (`docs/POSTGRESQL_VALIDATION.md`).
5. UI language and some code comments imply official/live capability beyond evidence (`templates/`, `services/cctv.py`).

The full report, staged plan, defense script and decision rationale are in the four companion documents. Their evidence labels matter: **VERIFIED** is restricted to code and fresh runtime proof; **SIMULATED**, **PARTIAL**, **BLOCKED** and **NOT MEASURED** must remain visible in any presentation.
