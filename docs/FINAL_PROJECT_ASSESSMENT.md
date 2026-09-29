# HajjGuard: final evidence-based project assessment

**Assessment date:** 29 September 2026. **Source of truth:** `codex/full-project-audit` at `96eb3de2ee515d723bdae8cf7135b1f23d6e3d51`; baseline `6b20b5d87925c00225259d23146e7f55743c7619`; remote `https://github.com/sultancraft050-cyber/HajjGuard.git`. The working tree was clean before this documentation assessment. The original Antigravity checkout remained at the baseline SHA and had no reported changes when queried with a per-command Git safe-directory override. No application behavior was changed for this report.

## Executive verdict

**HajjGuard is a functional academic prototype built around a coherent safety decision-support concept. It is suitable for an explicitly simulated internal or supervisor demonstration after security-sensitive screens are isolated. It is not ready for public use, a controlled pilot, or operational crowd safety. Do not merge the current branch yet.** Its strongest contribution is the integration of zone status, directed routing, group drift, incident handling, and a bilingual pilgrim/operator interface in one inspectable Django system. Its largest weakness is that multiple identity, location, export, and incident routes trust unauthenticated or weakly authenticated requests. The difference between historical claims and verified state is substantial: the code contains local simulation and algorithms, while field sensors, authorized government services, measured safety outcomes, and external validation are absent. The most important next action is a security/privacy correction pass with adversarial tests and a fresh PostgreSQL 16 run. The earlier final review did not complete those gates, so its outcome is **FAIL as a release review**; the 75 passing SQLite tests do not cancel critical source-level flaws.

Readiness: internal demo **conditional** (synthetic data, isolated network); supervisor demo **conditional** (clear disclaimer); university defense **partial** (honest evidence and limitations required); public demo **no** with current endpoints; controlled pilot **no**; operational deployment **no**. Merge only after authentication/authorization, QR and export controls, reproducible clean install, PostgreSQL migrations/tests, claim cleanup, and a complete independent review. A defense may present the branch as an academic prototype with negative evidence displayed rather than a working public safety system.

### Evidence and confidence rules

Labels used below: **VERIFIED** = current source plus fresh successful local execution; **VERIFIED_WITH_LIMITATIONS** = tested only in a constrained setting; **PARTIAL** = workflow incomplete; **SIMULATED** = synthetic/mock/local result; **PLACEHOLDER** = interface with little real behavior; **DOCUMENTED_ONLY** = prose without corresponding code; **UNVERIFIED** = insufficient run evidence; **BLOCKED** = external prerequisite absent; **NOT_IMPLEMENTED** = no meaningful implementation found; **REMOVED_OR_CORRECTED** = historical claim or code intentionally corrected. Source and test evidence outrank the supervisor plan, repository prose, the handoff/dossier, and previous agent summaries. The fresh Python 3.12.14 environment installed `requirements.txt`; `pip check`, `manage.py check`, clean SQLite migrations and 75 tests passed before review-only, uncommitted experiments were discarded. `check --deploy` reported HSTS, SSL redirect, and review-secret warnings. PostgreSQL 16 was **not** run: neither `psql`, `pg_ctl`, Docker, nor an installed PostgreSQL directory was found. The review experiments were reverted; their passing runs do not describe HEAD. Raw pre-fix test output is in `../review-evidence` outside the repository; the prior branch artifacts in `artifacts/` are historical evidence only.

## Verified capability inventory

| Capability | Status | Evidence | User value | Limitations | Next action |
|---|---|---|---|---|---|
| Project configuration and Django modular monolith | VERIFIED_WITH_LIMITATIONS | `hajjguard_core/settings.py`, six `apps/`, SQLite test run | Understandable deployable prototype | No production deployment proof; wide dependency ranges | Lock versions and deploy-check profile |
| Accounts and identity | PARTIAL | `apps/accounts/views.py:demo_switch_user`, `register_view` | Profile entry | Public identity switch; registration can reuse an existing username and log in without password | Replace with password-backed auth; remove demo switch |
| Roles and permissions | PARTIAL | `PilgrimProfile.ROLE_CHOICES`; `apps/safety/views.py:staff_required` | Role vocabulary | Most views lack robust authorization/object scope | Define permission matrix and enforce centrally |
| Pilgrim profile and consent | PARTIAL | `accounts/models.py`, migration `0003_explicit_consent` | Personalization, consent state | Default false fixed; form checkbox starts checked; processing not consistently gated | Separate purposes, explicit unchecked UI, enforcement |
| Groups and membership | VERIFIED_WITH_LIMITATIONS | `groups/models.py`, `groups/views.py:api_join_group` | Cohesion | Four-hex join codes; unauthenticated fallback to first pilgrim | Authenticated join, longer codes, anti-abuse |
| Group drift | VERIFIED_WITH_LIMITATIONS | `groups/services.py`, `tests/test_system_integrity.py` | Detect separation | RMS dispersion and threshold tested on synthetic points; no labeled false-alarm study | Collect labeled trajectories |
| QR identity and lost lookup | PARTIAL | `accounts/models.py:save`, `nusuk/models.py:generate_qr_payload`, `groups/views.py:lost_pilgrim_lookup_view` | Rapid recovery | Predictable identifiers, open substring lookup, broad sensitive result | Opaque revocable token, scoped staff lookup, audit every attempt |
| Zones and location | PARTIAL | `zones/models.py`, `zones/views.py:api_location_ping` | Map position | Public CSRF-exempt ingest, spoofable identity, non-finite coordinates, no indoor validation | Authenticate devices/users and validate finite coordinates |
| Density records and maps | VERIFIED_WITH_LIMITATIONS | `zones/models.py:DensityRecord`, `zones/views.py:api_zones_status`, Leaflet template | Visual status | Seeded/simulated values; no sensor provenance or browser acceptance run | Display source/freshness, test browsers |
| Guidance and routing | VERIFIED_WITH_LIMITATIONS | `services/routing.py`, `tests/test_system_integrity.py` | Compare directed paths | Graph edge cost heuristic; disconnected fallback is not an authorized safe route | Validate graph and route constraints with experts |
| Risk scoring | PARTIAL | `zones/views.py:zone_detail_view`, `services/prediction.py` | Explainable score | Arbitrary weights, synthetic vulnerable fallback, no calibration | Calibrate and validate against labeled outcomes |
| 20-minute forecasting | VERIFIED_WITH_LIMITATIONS | `services/prediction.py`; tests | Computable forecast | Index-based linear regression assumes five-minute cadence; no held-out MAE | Use timestamps and prospective validation |
| Camera/image counting | SIMULATED | `services/cctv.py` uses file size modulus, deletes image in `finally` | Demonstrates interface | No vision model or CCTV integration; deletion failure only logged | Rename simulator; test purge failure; expert/privacy review |
| Haram sectional flow | SIMULATED | `services/sectional_telemetry.py`, `safety/views.py` | Section visualization | Synthetic headcounts and unsupported accuracy text | Label every source and remove accuracy claim |
| SOS and incidents | PARTIAL | `safety/models.py`, `safety/views.py` | Ticket workflow | No emergency-service handoff; assignment/resolution authorization and concurrency gaps | Transactional state machine and role tests |
| Dispatch/operations dashboard | PARTIAL | `safety/views.py`, dashboard and queue templates | Shared operator view | Dashboard public; field units may act across incidents | Restrict and scope by assignment |
| Analytics, CSV/JSON | PARTIAL | `analytics/views.py:export_*`, JSON APIs | Review records | Public incident export with personal location/name; formula injection risk | Operator-only export, safe cells, log purpose |
| Digital card/campaign | SIMULATED | `nusuk/models.py`, `nusuk/views.py:get_or_create_demo_card` | Demonstration pass | Fake Tasreeh/national ID, predictable references; no official issuance | Explicit prototype naming and opaque QR |
| Fiqh assistant | SIMULATED | `services/fiqh_ai.py`, `nusuk/views.py` | Guidance demonstration | Local rules are not scholar-approved authoritative advice | Scholarly review and bounded language |
| Prayer/Qibla/heritage/weather | PARTIAL | `services/weather.py`, templates; prayer surge constants | Contextual UI | Weather network falls back to astronomical estimate; fixed prayer offsets; Qibla/heritage value not validated | Provenance and real service scope |
| Offline/service worker | NOT_IMPLEMENTED or UNVERIFIED | No service-worker registration found in templates/static scan; metric 8 NOT MEASURED | Potential resilience | Browser offline fallback not demonstrated | Design real offline protocol before claim |
| Arabic/English/RTL | PARTIAL | `base.html` switches `lang` and `dir`; `LANGUAGES` in settings | Local relevance | Many literals and JS messages remain Arabic or English; no full translation catalog QA | Native review, RTL/LTR browser matrix |
| Accessibility/mobile | PARTIAL | responsive Bootstrap templates, scattered ARIA | Mobile-first prototype | No screen-reader, keyboard, contrast or device audit | WCAG audit with users |
| Audit/privacy/retention | PARTIAL | `AuditLog`; `prune_location_pings` command, `tests/test_retention.py` | Accountability | Logs omit failed/broad lookups; retention is manual command; other data categories lack schedules | Full purpose/audit matrix and scheduler |
| Administration/deployment | PARTIAL | Django admin registrations, `.env.example`, `docs/DEPLOYMENT.md` | Manage prototype | No production topology, backup, incident response or clean-install proof | Staging runbook and repeatable build |
| Tests/benchmarks/documentation | VERIFIED_WITH_LIMITATIONS | 75 passing SQLite tests; `evaluate_system_metrics`; `docs/` | Academic inspectability | Tests reward some insecure behavior; only 4 of 10 metrics carry numbers, several numbers are harness timings; PostgreSQL blocked | Adversarial tests, protocol-driven measurements |

### Route and screen accounting

There are **15 standalone page templates** including `home.html` and excluding `base.html` and the AI drawer partial; `templates/` contains 17 HTML files in total. The historical “17 screens” is therefore a design inventory claim, not 17 distinct standalone rendered pages. Aliases and modal/drawer states can increase UI states but should not be counted as independent screens. The route inventory at `artifacts/final/route-inventory.txt` also includes Django admin paths and aliases. All templates inherit `base.html` with conditional `lang`/`dir`, but many strings lack complete translation and accessibility testing. Responsive CSS exists; per-screen mobile browser behavior remains **UNVERIFIED**.

| URL(s) | View / template | Intended role; actual gate | Data/source and status | Failure or missing proof |
|---|---|---|---|---|
| `/`, `/home/` | `zones.landing_home` / `home.html` | public; public | sectional/weather local/simulated | “live” wording lacks sensor proof |
| `/accounts/register/` | `accounts.register_view` / `accounts/register.html` | pilgrim; public | local DB, PARTIAL | account takeover path, checked consent |
| `/accounts/profile/` | `accounts.profile_view` / `accounts/profile.html` | owner; public fallback | local personal data, PARTIAL | anonymous edit of first pilgrim |
| `/accounts/pilgrim/` | `accounts.pilgrim_portal` / `accounts/pilgrim_portal.html` | owner; public fallback | local/demo, PARTIAL | cross-user exposure |
| `/accounts/demo-switch/<username>/` | `accounts.demo_switch_user` / redirect | examiner; public | local users, CRITICAL | logs in as target without password |
| `/groups/my-group/` | `groups.my_group_view` / `groups/my_group.html` | member; public fallback | group/location, PARTIAL | first group and member locations exposed |
| `/groups/lost-pilgrim/` | `groups.lost_pilgrim_lookup_view` / `groups/lost_pilgrim_lookup.html` | authorized recovery staff; public | profile/group/location, PARTIAL | substring enumeration, sensitive fields |
| `/groups/api/join/` | `groups.api_join_group` / JSON | pilgrim; public CSRF exempt | local group, PARTIAL | joins as first pilgrim |
| `/zones/map/`, `/zones/live-map/` | `zones.live_map_view` / `zones/live_map.html` | public; public | local zones, PARTIAL | browser/field map unverified |
| `/zones/detail/<zone_id>/`, `/zones/<zone_id>/` | `zones.zone_detail_view` / `zones/zone_detail.html` | public; public | derived/local, PARTIAL | synthetic vulnerable fraction |
| `/zones/guidance/` | `zones.guidance_view` / `zones/guidance.html` | public; public | directed graph, limited | no safety certification |
| `/zones/api/status/` | `zones.api_zones_status` / JSON | public; public | local records and recent pings | source/freshness not explicit |
| `/zones/api/ping/`, `/zones/api/telemetry/ping/`, `/api/telemetry/ping/` | `zones.api_location_ping` / JSON | device; public CSRF exempt | DB write | spoofing and invalid coordinates |
| `/safety/dashboard/` | `safety.operations_dashboard` / `safety/operations_dashboard.html` | operator; public | incidents/local | incident exposure |
| `/safety/incidents/` | `safety.incident_queue_view` / `safety/incident_queue.html` | staff; broad staff | local incidents | field-wide visibility |
| `/safety/api/trigger-sos/` | `safety.api_trigger_sos` / JSON | pilgrim; login | local incident | profile fallback and input issues |
| `/safety/api/assign-incident/`, `/safety/api/resolve-incident/`, `/safety/api/resolve/<id>/` | `safety.api_*` / JSON | dispatcher; broad staff | incident writes | object scope/concurrency |
| `/safety/api/lookup-pilgrim/`, `/safety/api/sync-haramain/` | `safety.api_*` / JSON | staff; broad staff | sensitive lookup/simulation | no official sync evidence |
| `/safety/api/live-weather/`, `/safety/api/haram-sectional-status/` | `safety.api_*` / JSON | public; public | weather/simulation | “verified” accuracy unsupported |
| `/safety/api/simulate-section-gate-flow/` | `safety.api_simulate_section_gate_flow` / JSON | operator; broad staff | synthetic mutation | no production isolation |
| `/analytics/risk-board/` | `analytics.risk_board_view` / `analytics/risk_board.html` | operator; public | local/derived | role gate missing |
| `/analytics/reports/` | `analytics.reports_view` / `analytics/reports.html` | operator; public | local/derived | role gate missing |
| `/analytics/routing-comparison/` | `analytics.routing_comparison_view` / `analytics/routing_comparison.html` | examiner; public | graph simulation | counterfactual outcome not measured |
| `/analytics/reports/export/{density,incidents}/`, `/analytics/export/{density,incidents}/` | `analytics.export_*` / CSV | operator; public | records and personal incidents | unauthorized download/formula injection |
| `/analytics/api/{trigger-surge,reset-crowd}/` | `analytics.api_*` / JSON | simulator operator; public CSRF exempt | mutates local records | public simulation misuse |
| `/analytics/api/calculate-route/` | `analytics.api_calculate_route` / JSON | public; public | graph computation | no validated walkability |
| `/nusuk/card/`, `/nusuk/card/api/` | `nusuk.digital_card_view`, `api_card_details` / card or JSON | owner; login | generated local card | no official identity authority |
| `/nusuk/api/ai/chat/` | `nusuk.api_nusuk_ai_chat` / JSON | user; public CSRF exempt | local rule response | authority wording too strong |
| `/admin/`, `/i18n/` | Django admin and language endpoints | admin / normal Django gates | framework | standard admin security still needs deploy configuration |

## Strengths, trade-offs and surprises

The strongest contribution is **integration of smaller systems**, not a validated prediction model. Distinctive and preservable elements are (1) directed zone/corridor graph, (2) group-drift service, (3) explainable risk terms, (4) Arabic/RTL-first interface, (5) explicit missing-measurement flags. These matter to pilgrims, operators, examiners and future researchers because each can be inspected and challenged; none proves field safety. The modular monolith is sensible at present scale; splitting services would add deployment and transaction complexity before boundaries and evidence are mature. Tests and model constraints give a useful base; the same tests also create false confidence because they sometimes require an insecure demo behavior. Consent default false, no committed production secret, nonnegative forecast clamp and deletion in the CCTV `finally` path are useful corrections, though their surrounding workflows remain incomplete. A surprising weakness is that `register_view` and demo switching defeat identity security despite the improved settings. Another is that the “CCTV” counter is a deterministic file-size formula and the QR reference is a predictable Tasreeh string. UI polish is stronger than data provenance.

Top ten strengths: coherent safety problem; single inspectable Django repository; six domain apps; seeded zone/corridor model; directed routing; group drift computation; explicit risk breakdown; Arabic/RTL shell; 75 runnable SQLite tests; honest `NOT MEASURED` markers. Top five impressive defense elements: runnable graph comparison, group drift trace, incident state demo, risk formula display, admission of unmeasured targets. Most partner-relevant possibilities: accessible group recovery, localized guidance, route modeling, privacy/audit design, controlled synthetic testbed. Preserve their *ideas and interfaces* while replacing unsafe trust assumptions.

## Weaknesses and risk register

| Weakness (category) | Severity | Evidence | Consequence / likelihood | Required correction | Effort |
|---|---|---|---|---|---|
| Passwordless demo switch and registration reuse (security) | CRITICAL | `apps/accounts/views.py:demo_switch_user`, `register_view` | Account/operator takeover; trivial if reachable | Remove bypass, real authentication, adversarial tests | M |
| Public profile/group/lost lookup (privacy/security) | CRITICAL | `accounts/views.py`, `groups/views.py` | Personal, medical and location disclosure; high | Owner/staff object scope, exact opaque lookup, audit | M |
| Public telemetry and simulation writes (security/data quality) | CRITICAL | `zones/views.py:api_location_ping`; `analytics/views.py:api_trigger_surge` | Spoofed location and crowd state; high | Authenticated device/user identity, CSRF or token protocol, rate limits | M |
| Public incident CSV (privacy) | CRITICAL | `analytics/views.py:export_incidents_csv` | Bulk names/coordinates; high | Operator gate, safe export, minimization and audit | S–M |
| Predictable QR identifiers (privacy) | HIGH | `accounts/models.py:save`, `nusuk/models.py:generate_qr_payload` | Guess/replay and association; high | Opaque random revocable token and scanner validation | M |
| Broad incident assignment/resolution (safety/security) | HIGH | `safety/views.py:staff_required`, `api_assign_incident` | Wrong unit/ticket state; medium | Role/object policy, transactions, idempotency, locking | M |
| PostgreSQL never exercised (database/testing) | HIGH | `docs/POSTGRESQL_VALIDATION.md`; no local server | Portability unknown; certain evidence gap | PostgreSQL 16 clean and upgrade tests | S–M |
| Benchmark numbers lack protocols (scientific validity) | HIGH | `evaluation_results.json`, `evaluate_system_metrics.py` | Defense overclaim; high | Raw trials, datasets, intervals, negative results | L |
| Synthetic sensors and file-size “vision” (data quality) | HIGH | `services/cctv.py`, sectional engine | False safety decisions if mistaken as live; high | Relabel, provenance, validated sensor pipeline | L–XL |
| Forecast cadence and routing heuristic (correctness) | MEDIUM/HIGH | `services/prediction.py`, `services/routing.py` | Uncalibrated predictions/routes; medium | Time-based fitting, topology audits, expert review | M–L |
| Manual partial retention and audit (privacy) | HIGH | `prune_location_pings`, `AuditLog`, lookup views | Data outlives purpose and access gaps | Scheduled multi-category retention and complete audit | M |
| Deployment/accessibility/localization gaps (reliability/usability) | MEDIUM | deploy warnings; templates/locale | Broken secure/public experience | Staging, WCAG, language QA | M–L |
| External/official claims in UI (governance) | HIGH | `templates/base.html`, `services/nusuk.py`, `safety/views.py` | User/examiner misinformation | Remove seals/verified language unless authorized | S |

Ten technical weaknesses: auth bypass, object scope, CSV, spoofed telemetry, weak QR, unsafe simulation, state races, SQLite-only proof, no dependency lock, no observability. Ten product weaknesses: unclear authority, unsafe demo switch, card resemblance to official pass, unsupported live status, limited offline behavior, unvalidated guidance, thin registration security, weak error states, inconsistent languages, no user research. Ten evidence weaknesses: no PostgreSQL, no field data, no labeled forecast test, no counterfactual routing study, no device battery trial, no browser offline trial, no labeled drift false-alarm data, no CCTV benchmark protocol, no accessibility study, no real emergency exercise. Defense risks follow those same evidence gaps plus questions about official authorization and measured vs synthetic data. Operational blockers add institutional permission, privacy/legal basis, sensor contracts, incident response, backups, monitoring, capacity testing, on-call ownership, and domain expert approval.

## Architecture, database and algorithm assessment

Keep the **Django modular monolith**. Accounts, groups, zones, safety, analytics and nusuk are recognizable boundaries, but views mix access control, ORM queries, workflow mutations and presentation. `get_or_create_demo_card` provisions identity objects during a GET; `api_location_ping` resolves a person from untrusted input; risk and routing logic mix stored counts with defaults. Put identity policies, incident state transitions, telemetry ingestion and export selection in small service functions with explicit inputs. Create selectors for scoped reads. Avoid microservices until a controlled pilot exposes a genuine scaling boundary; likely later candidates are telemetry ingestion and image processing, not account or group CRUD.

Domain schema has useful explicit models (`Zone`, `Corridor`, `LocationPing`, `DensityRecord`, `PilgrimGroup`, `GroupMembership`, `SosIncident`, `FieldUnit`, `NusukCard`, `AuditLog`). The strongest relationships are foreign keys, unique memberships and migrations. Weaknesses are no demonstrated PostgreSQL 16 upgrade, no geometry/PostGIS, permissive payload fields, predictable identity references, weak consent-purpose model, and state transitions that are not atomic. SQLite passing migrations proves only SQLite. Do not infer PostgreSQL behavior from the psycopg dependency or settings branch. At scale, hot location writes, dashboard aggregations and route graph rebuilds would fail first; use TTL/partitioning, cache with freshness, and measured query plans before architectural splitting.

Circular zones and Haversine are appropriate for a teaching prototype, but real multilevel corridors require validated geometry, indoor location uncertainty and closed-edge controls. The NetworkX directed graph and Dijkstra-like weighted shortest path are correct *for the modeled graph*; no proof exists that the model is walkable, wheelchair-safe, or capacity-optimal. Returning straight-line time on disconnected graphs must never be offered as a route. A* offers little until a trustworthy admissible heuristic exists. Multi-route allocation is a research extension requiring demand and conflict modeling. The linear forecaster clamps negative output but fits sample indices while claiming a five-minute spacing; irregular samples undermine the 20-minute meaning. Horizon code is VERIFIED_WITH_LIMITATIONS; forecast MAE is BLOCKED. Risk weights, prayer offsets, 18% vulnerability fallback and weather assumptions need calibration. `services/cctv.py` is SIMULATED, not object detection. Its `finally` attempts deletion, but OS deletion errors leave a file; a privacy guarantee would require quarantine/retry/monitoring. No algorithm has evidence for real-world safety effectiveness.

## Security, privacy, safety and operational assessment

Threat actors include an unauthenticated web user, a legitimate pilgrim probing other groups, an overprivileged field user, an exporter, and an accidental operator. Specific attack paths are directly supported by source: `/accounts/demo-switch/operator/` switches identity; registration of an existing username reuses it; lost lookup accepts substring phone/name and exposes medical/location details; profile/portal/group views fall back to another pilgrim; telemetry accepts national ID and fallback; public CSV and simulation routes allow disclosure or mutation. `@csrf_exempt` on user-facing JSON endpoints compounds these paths. Incident assignment and resolution do not enforce one operator-owned transition. No fresh adversarial suite against HEAD was completed; these are source-level findings, not penetration-test certification. Apply a deny-by-default route policy, then tests for anonymous/other-user/field/operator roles, CSRF, ID substitution, rate limits, finite coordinates, duplicate joins/dispatch and CSV formula cells.

Privacy positives: consent model defaults false, there is a location pruning command, and the card payload no longer carries direct medical/phone fields. Privacy negatives: form consent is prechecked, processing is not gated consistently, QR still carries a predictable permit reference and camp/logistics, location and incident exports are broad, lookup audit covers successes rather than all access attempts, and retention is manual/location-only. An audit log row is not proof of PDPL compliance. Define controller/purpose/legal basis, data map, minimization, access justification, retention for every data class, deletion proofs, subject rights and incident procedures with a qualified reviewer. Until then all personal data should be synthetic in demonstrations.

Safety case is far from operational. No validated inputs, failsafe behavior, incident handoff, SOP, on-call response, training, hazard analysis, capacity calibration, end-to-end latency study, backup or disaster recovery was evidenced. The current map should be described as decision-support visualization using generated/local records, never live operational awareness. A wrong detour or missed SOS can harm users; retain a human operator gate for any future live recommendation.

## UX, localization, testing and evidence

The interface is visually substantial: Bootstrap RTL, Leaflet, modals and mobile-oriented templates. `base.html` toggles `lang`/`dir` for Arabic/Urdu vs English/Indonesian, which is a real structural provision. However, many strings are literals, external CSS/fonts/maps are network dependencies, controls have uneven ARIA, and no keyboard, screen-reader, low-bandwidth, outdoor-glare or mixed-direction number study was supplied. The 15 standalone templates are not equivalent to 15 fully usable workflows. Protect the navigation concept and Arabic-first design, then test with real participants.

Fresh SQLite: Python 3.12.14, dependency installation from `requirements.txt`, `pip check` passed, `manage.py check` passed, `check --deploy` had 3 warnings, clean migrations passed, 75 tests passed in about 10 seconds. This is meaningful code health, but tests include assertions for insecure open screens and static benchmarks. A previous review attempt added five security tests and temporary fixes, then reverted all of them when this documentation-only task superseded code changes; **they are not part of HEAD**. Browser exercise of every route, clean checkout installation, PostgreSQL 16, and schema-upgrade migration test remain UNVERIFIED/BLOCKED. README contains only a short prose installation instruction and does not establish a fully reproducible clean installation.

The ten supervisor measurements must be separated from branch claims. Current `evaluation_results.json` says `overall_passed: false`: ingestion NOT MEASURED; map refresh `0.001 s` harness timing; forecast horizon `20 min` a configured property, not accuracy; MAE NOT MEASURED; dual-pass route time `3.63 ms` local harness; load reduction NOT MEASURED; battery NOT MEASURED; offline NOT MEASURED; lookup `0.38 ms` local DB harness; drift false-alarm NOT MEASURED. The exact local timings change by run and are not field performance. Four entries carry numbers, but only three are timings and one is a configured horizon; none validates safety effectiveness. Claims such as 23.4% load reduction, 4.6% battery, 0.12-second offline fallback and 2.1% false alarm are REMOVED_OR_CORRECTED as unsupported historical numbers. Recompute only from versioned raw data and a protocol with scenario hash, trial count, warm-up, environment, failures and uncertainty. A negative measured result is stronger evidence than a fabricated pass.

## SWOT tied to HajjGuard

**Strengths:** integrated inspectable prototype, local language emphasis, domain models and reproducible SQLite suite. **Weaknesses:** authorization, synthetic provenance, weak benchmark methods and thin operations evidence. **Opportunities:** controlled academic datasets, calibrated routing/drift research, privacy-aware lost-person workflow and user-centered accessibility. **Threats:** mistaken official identity or live-status claims, personal-data exposure, unsafe route advice, institutional permission gaps and maintenance of an overbroad feature set. None of these is a generic market forecast; each follows the source and missing evidence above.

## What surprised the reviewer

The route and test surface is broader than a simple mockup; the database models and simulations genuinely run. Yet the most polished pages conceal the weakest authorization. The QR privacy correction removed medical fields but left a guessable official-looking reference. A test suite can pass while preserving account takeover behavior. The benchmark command is honest about six missing metrics while still labeling local harness timings “PASSED.” The image deletion `finally` is thoughtful but cannot guarantee deletion after an OS error. The original Antigravity checkout appears unchanged, while the working branch’s `artifacts/` is tracked despite an ignore rule. These discoveries shift the recommended story from “intelligent operational platform” to “inspectable decision-support research prototype.”

## Human decisions still required

| Decision maker | Question; why it matters | If unanswered |
|---|---|---|
| Supervisor | Which ten outcomes are mandatory for defense, and can negative/unmeasured results be presented? | Acceptance criteria remain ambiguous |
| Project team | Which narrow core workflow will receive the remaining engineering time? | Scope expansion keeps safety gaps open |
| Privacy/legal reviewer | What lawful basis, purposes, retention and subject rights apply to location/medical/incident data? | No personal-data pilot |
| Crowd-safety expert | Are zones, thresholds, graph directions and interventions physically valid? | No safety claim |
| Medical expert | Which vulnerability features and SOS triage rules are clinically appropriate? | No medical-risk claim |
| Religious scholar | Which Fiqh content may be shown and with what authority/provenance? | Assistant remains a non-authoritative demo |
| University ethics process | May users/pilgrims be recruited and under what consent? | No human study |
| Government/institutional partner | Is access to official data, branding, permits or operations authorized? | No official integration or deployment |
| Real users | Can Arabic/English, mobile, low vision and stressful recovery flows be used? | UX/accessibility remain unverified |
| Infrastructure administrator | Can a secure staging PostgreSQL/service with backups, monitoring and secrets be operated? | No reliable pilot |

## Ratings (0–10, not averaged into a false single score)

The “+2 action” column is a concrete path to improving the rating; confidence reflects evidence quality, not optimism.

| Area | Score / confidence | Evidence; main ceiling | +2 action |
|---|---|---|---|
| Problem relevance | 9 / high | Real crowd-safety problem; no user validation | Stakeholder interviews |
| Academic novelty | 5 / medium | Integration more novel than individual algorithms | Publish calibrated comparative study |
| Functional completeness | 5 / high | 15 pages and workflows; many partial | Complete secure core journey |
| Code quality | 4 / high | Runnable suite; views overloaded and unsafe | Service boundaries + review gates |
| Architecture | 6 / medium | Coherent monolith; weak policies | Scoped services/transactions |
| Database design | 5 / medium | Models/migrations; PostgreSQL untested | PG16 plus domain constraints |
| Algorithmic correctness | 4 / medium | Directed graph/linear fit; model assumptions | Ground-truth validation |
| Scientific validity | 2 / high | No outcome datasets | Prospective protocol + raw data |
| Security | 1 / high | Direct source-level account bypasses | Fix critical endpoints + attack suite |
| Privacy | 2 / high | Consent default false; broad disclosure | Full purpose/access/retention controls |
| Reliability | 3 / medium | SQLite suite; no staging/failure exercise | Failure and load testing |
| Safety readiness | 1 / high | No safety case/field validation | Expert hazard assessment |
| Test quality | 5 / high | 75 pass; some assert unsafe behavior | Role/CSRF/concurrency tests |
| Benchmark quality | 3 / high | NOT MEASURED is honest; timings weak | Protocol-driven raw trials |
| User experience | 6 / medium | Rich responsive templates | Usability study and simplification |
| Mobile usability | 4 / low | Responsive CSS; no device study | Device matrix with participants |
| Arabic/RTL quality | 5 / medium | Conditional RTL shell; hardcoded strings | Native bilingual QA |
| Accessibility | 3 / low | Some ARIA and layout; no audit | WCAG keyboard/screen-reader study |
| Documentation | 5 / high | Many files but most are brief | Reproducible detailed runbooks |
| Installation reproducibility | 3 / high | Requirements install worked locally; README thin | Clean checkout scripted install |
| PostgreSQL readiness | 2 / high | Config exists; no PG run | PG16 migration/full suite |
| Deployment readiness | 2 / high | Deploy warnings and no ops topology | Secure staging drill |
| Maintainability | 4 / medium | Modular apps; coupling/UI JS | Refactor workflow services |
| Extensibility | 6 / medium | Monolith boundaries and graph model | Stable APIs and schemas |
| Demonstration readiness | 6 / medium | Synthetic demo feasible | Isolate unsafe routes and label data |
| Defense readiness | 4 / medium | Strong concept; evidence gaps | Close security and measurement narrative |
| Pilot readiness | 1 / high | No permissions, safety/PG validation | Controlled pilot gate package |
| Production readiness | 0 / high | Critical security and no operations proof | Multi-stage validated deployment |
| Research potential | 8 / medium | Routing/drift/forecast testbed | Acquire ethical labeled data |
| Long-term platform potential | 5 / low | Concept broad; partners needed | Narrow pilot and institutional agreement |

Indicative separate scores: academic prototype **6/10**, engineering prototype **3/10**, operational readiness **0/10**. They answer different questions and must not be averaged.

## Final priority lists

**A. Ten best things:** coherent problem; modular Django; domain models; directed graph; drift metric; risk transparency; Arabic/RTL shell; synthetic demonstration; 75 SQLite tests; honest missing-metric markers.

**B. Ten weakest things:** identity bypass; public profile/group lookup; public export; spoofed telemetry; simulation mutation; guessable QR; unvalidated algorithms; no PostgreSQL; no field data; unsupported official-looking UI.

**C. Ten working things to preserve:** models/migrations; seeded zones; map rendering; directed route comparison; drift computation; SOS model; incident queue UI; Arabic base layout; explicit consent default false; retention command.

**D. Ten immediate corrections:** remove demo switch; secure registration; scope profiles; gate lost lookup; authenticate telemetry; gate simulation; gate/sanitize exports; opaque QR; transactional incident state; adversarial tests.

**E. Ten before defense:** complete D; PostgreSQL 16; clean install; raw benchmark protocol; mark all simulations; remove official claims; explain graph limits; Arabic/RTL QA; accessibility audit; honest demo script.

**F. Ten before pilot:** institutional authorization; privacy impact assessment; safety expert sign-off; sensor provenance; calibrated thresholds; staging/monitoring; backup/restore; incident SOP; human study; rollback exercise.

**G. Ten before operations:** all pilot gates; independently validated safety case; security assessment; uptime/latency SLO; on-call team; emergency integration authorization; data protection controls; disaster recovery; field trials; governance ownership.

**H. Five defer:** wallet pass, external LLM, microservices, advanced vision, multi-route optimization.

**I. Five remove or rename:** “official Nusuk” card to local prototype card; “live CCTV” to image-count simulator; “verified SCADA” to synthetic feed; “AI Fiqh authority” to informational rule assistant; “live crowd accuracy” to unvalidated estimate.

**J. Five research directions:** uncertainty-aware indoor location; constrained multi-route allocation; calibrated short-horizon forecasting; privacy-preserving group recovery; human-centered bilingual safety alerts.

**K. Five supervisor questions:** exact acceptance metrics; acceptable negative results; required core workflow; permission for human study; preferred defense claim scope.

**L. Five defensible statements:** Django prototype runs on SQLite; 75 existing tests passed before review changes; directed routing and group-drift code exist; consent model defaults false; six primary metrics remain not measured.

**M. Five prohibited statements:** field validated; official Nusuk/Ministry/SCADA integrated; CCTV person detection deployed; all benchmarks passed; safe for live emergency operations.

## Conclusion

HajjGuard is a good academic project because it turns a consequential local problem into an integrated, testable prototype. Its value lies in the system design and honest research questions, not proven field performance. Security gaps, simulated inputs and missing scientific evidence prevent a stronger claim. The team should stop expanding visible features, secure the core workflows, validate them on PostgreSQL and collect ethical raw evidence. The credible defense sentence is: **“HajjGuard is an Arabic-first Django decision-support prototype that demonstrates crowd, group and incident workflows on local/synthetic data while explicitly identifying the validation required before any real use.”**
