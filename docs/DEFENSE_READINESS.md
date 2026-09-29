# Defense readiness: what HajjGuard can honestly demonstrate

**Current status:** conditional academic prototype demonstration; not release-approved. Source HEAD assessed: `96eb3de` on `codex/full-project-audit`. The earlier SQLite run passed 75 tests, but a passing suite is not security approval. PostgreSQL 16 and an adversarial release suite were not completed. See `FINAL_PROJECT_ASSESSMENT.md` and `POSTGRESQL_VALIDATION.md`.

## Safe demonstration boundary

Use only synthetic identities, local data, an isolated machine/network and a resettable database. The safe narrative is a guided walkthrough of zone status, directed graph comparison, group-drift example, SOS model/queue and explicit unknown benchmarks. Do not expose the public demo-switch, registration, lost-person lookup, CSV export or simulation APIs to an audience or public network until their vulnerabilities are fixed. Show `evaluation_results.json` with `overall_passed: false`; explain that map refresh, route decision and lookup numbers are local harness timings and 20 minutes is a configured horizon. The current display is a prototype decision aid, not guidance for a real pilgrim.

| Demonstration | Evidence available | Required spoken qualification |
|---|---|---|
| Zone/map screen | `zones/views.py`, `templates/zones/live_map.html` | Local/synthetic records; no live sensor feed |
| Directed route comparison | `services/routing.py`, tests | Computes a path on a modeled graph; route safety unvalidated |
| Group drift | `apps/groups/services.py`, tests | Synthetic positions and threshold; false-alarm rate unknown |
| Risk score | `zones/views.py:zone_detail_view` | Explainable arithmetic, uncalibrated weights |
| Forecast | `services/prediction.py` | Produces a nonnegative estimate; no held-out accuracy |
| SOS queue | `safety/models.py`, queue template | Local ticket simulation; no emergency-service dispatch |
| Digital card | `nusuk/models.py`, view | Locally generated prototype; no official permit |
| Fiqh assistant | `services/fiqh_ai.py` | Informational local rules; no scholar approval |
| CCTV/image count | `services/cctv.py` | File-size simulator, not vision inference |
| Benchmark table | `evaluation_results.json` | Six metrics not measured; four numbers are limited |

## Evidence packet to bring

- Branch/base/HEAD and clean status: `git log`, `git status`.
- Full 75-test SQLite output and fresh environment record from the reviewer workspace (`../review-evidence`); explain that these are local tests.
- `artifacts/sqlite/` and `artifacts/final/route-inventory.txt` as historical branch artifacts, not independent proof of all claims.
- `evaluation_results.json`, `docs/BENCHMARK_METHODOLOGY.md` and a table of all ten metric statuses.
- A source-level threat list from `FINAL_PROJECT_ASSESSMENT.md`; do not conceal it if asked.
- A screen count note: 17 HTML files = 15 standalone page templates + base + drawer partial. “17 screens” is a design label, not 17 verified workflows.

## Statements to avoid

Do not say **field validated**, **live crowd telemetry**, **98.5% accuracy**, **official Nusuk/Ministry/SCADA**, **CCTV person detection**, **emergency dispatch integration**, **all benchmarks passed**, **privacy compliant**, **production ready**, or **safe routing**. The code and runtime evidence do not establish any of those. Do not repeat the historical 23.4% routing reduction, 4.6% battery, 0.12-second offline or 2.1% false-alarm values as current results. Replace “AI predicts crowd” with “a simple local linear forecast is computed and its accuracy remains unmeasured.”

## Likely examiner questions and sound answers

| Question | Evidence-based answer |
|---|---|
| What is the novel contribution? | Integration and testability of localized group/zone/route/incident workflows; individual algorithms are established methods. |
| Is the map live? | No verified field feed. It renders local records and simulations. |
| How accurate is the forecast? | Unknown; MAE requires labeled future counts and a held-out protocol. |
| Does the detour reduce load 15%? | Not measured in a controlled scenario. Route computation time is not load reduction. |
| Is the card official? | No; it is a locally generated prototype card. |
| What does CCTV use? | A deterministic file-size simulation, not a trained detector. |
| Is user data protected? | Some improvements exist, but source review found critical access-control gaps. Only synthetic data are appropriate now. |
| Why SQLite? | It demonstrates the academic prototype. PostgreSQL 16 validation is a required next gate. |
| Why a monolith? | It keeps a small team’s prototype understandable and transactions local; splitting is premature. |
| What would make it operational? | Institutional authority, safety/privacy review, validated data and algorithms, secure infrastructure, live procedures and field trials. |

## Gate to a credible defense

Before presenting a network-accessible build, fix critical identity, lookup, telemetry, export and simulation vulnerabilities; add regression tests; run full SQLite and PostgreSQL 16 suites; test clean install; remove unsupported UI claims; run at least one documented browser/mobile/RTL/accessibility pass; keep all unmeasured benchmark cells explicit. The supervisor should decide whether negative and incomplete results meet the academic contract. If not, narrow the defense scope rather than inventing evidence.
