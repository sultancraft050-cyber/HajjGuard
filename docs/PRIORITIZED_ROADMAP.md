# HajjGuard prioritized roadmap

This roadmap orders correctness and evidence before feature expansion. Effort: XS <1 day, S 1–3 days, M 4 days–2 weeks, L 2–6 weeks, XL >6 weeks or external organization.

## Stage 0 — before branch merge

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk if skipped |
|---|---|---|---|---|
| P0 | Remove passwordless demo switch and secure registration | Django developer; none; M | Existing users cannot be impersonated; password and consent tests pass | Account takeover |
| P0 | Enforce owner/staff scope for profile, portal, group and lost lookup | Developer + privacy reviewer; P0 auth; M | Anonymous/other-user/field-role tests deny or minimize | Personal/location disclosure |
| P0 | Authenticate telemetry; reject nonfinite/out-of-range/stale identity substitution | Developer; auth policy; M | Attack tests and rate-limit evidence | Spoofed safety data |
| P0 | Gate/sanitize CSV and JSON exports; remove formula injection | Developer + privacy reviewer; M | Role, CSRF, cell-escaping and audit tests | Bulk disclosure |
| P0 | Gate simulation and incident state transitions | Developer; permission matrix; M | Unauthorized, duplicate, race and object-ID tests | Wrong crowd/dispatch state |
| P0 | Opaque revocable QR token | Developer; migration design; M | Random token, revocation, exact lookup tests | Enumeration/replay |
| P0 | Run full suite on PostgreSQL 16 and SQLite; test baseline-to-head migrations | Infra admin; PostgreSQL; M | Logs, schema and test artifacts | Merge portability unknown |
| P0 | Fix unsupported official/live wording | Team; none; S | Claim scan and demo review show prototype/simulation labels | Misrepresentation |

## Stage 1 — before supervisor demonstration

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk |
|---|---|---|---|---|
| P1 | Complete clean-install README/runbook | Developer; Stage 0; S | New checkout from remote installs and runs | Demo failure |
| P1 | Browser route and RTL/LTR matrix | UX tester/native reviewer; staging; M | Screenshots/defect log for every standalone page | False UI confidence |
| P1 | Accessibility keyboard/screen-reader/contrast pass | Accessibility tester; templates; M | WCAG findings and fixes | Exclusion and defense criticism |
| P1 | Rebuild benchmark harness with raw inputs and uncertainty | Researcher; datasets; L | Versioned scenario hash, raw trials, protocol | Unsupported metrics |
| P1 | Narrow the live/demo boundary | Supervisor/team; P0; XS | Demo runbook cannot reach unsafe endpoints | Accidental disclosure |

## Stage 2 — before final defense

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk |
|---|---|---|---|---|
| P1 | Label source, freshness and synthetic/live state in every telemetry view | Developer/researcher; data contract; M | UI and API provenance fields | Misread simulation |
| P1 | Validate forecast, routing and drift with held-out/labeled data | Researcher + crowd-safety expert; data approval; L | MAE/confidence, route scenario and false-alarm report | Weak academic claims |
| P1 | Complete threat model, privacy impact and retention matrix | Privacy/legal reviewer; Stage 0; L | Signed review and deletion/audit evidence | No defensible personal-data story |
| P1 | Present negative results and alternatives | Supervisor/team; reports; S | Defense slides cite raw evidence | Overclaiming |

## Stage 3 — after defense academic enhancement

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk |
|---|---|---|---|---|
| P2 | Timestamp-aware forecasting and calibrated risk | Researcher; labeled data; L | Prospective evaluation | Invalid predictions |
| P2 | Indoor/multilevel geometry or PostGIS study | GIS developer; validated maps; L | Geometry and uncertainty tests | Unsafe routes |
| P2 | Privacy-preserving lost-person recovery study | Security/privacy researcher; ethics; L | Threat/utility comparison | Re-identification |
| P2 | Human-centered Arabic/English usability study | UX team; ethics; L | Task success and error report | Poor adoption |

## Stage 4 — controlled pilot preparation

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk |
|---|---|---|---|---|
| P2 | Authorized sensor/data sandbox | Institution/data provider; XL | Contract, provenance, replay set | Illegal/unreliable data |
| P2 | Secure PostgreSQL staging, backups, monitoring and secrets | Infra admin; Stage 0; L | Restore, load and incident drill | Data loss/outage |
| P2 | Human operator SOP and fail-safe gate | Safety expert/institution; L | Tabletop and rollback exercise | Harmful automation |
| P2 | Pilot ethics, privacy and medical/religious review | Review boards; XL | Approvals and participant protocol | Unacceptable study |

## Stage 5 — future operational platform

| Priority | Work / reason | Dependency, owner, effort | Acceptance evidence | Risk |
|---|---|---|---|---|
| P3 | Independent security assessment and red team | Security team; pilot build; L | Remediated findings | Persistent compromise |
| P3 | Prospective safety case and field validation | Institution/domain experts; XL | Signed hazards, controls, outcomes | Unsafe deployment |
| P3 | Scale telemetry/image processing only when measured bottlenecks exist | Platform team; L/XL | Load/SLO evidence | Premature complexity |

## Best next ten tasks

1. Remove demo identity switching.
2. Require real registration password and unchecked consent.
3. Add route/role/object authorization matrix.
4. Protect profile, group, lost lookup and telemetry.
5. Gate/sanitize exports and simulation APIs.
6. Make incident transitions transactional and idempotent.
7. Replace QR identifiers with random revocable tokens.
8. Add adversarial regression suite.
9. Run genuine PostgreSQL 16 plus baseline migration upgrade.
10. Rewrite README and claim scan.

## Best next 30 days

Finish Stage 0, obtain PostgreSQL service, produce clean-install and browser/RTL evidence, and agree with the supervisor on the ten-metric acceptance protocol. Freeze new feature work until these gates pass.

## Best next semester

Run an ethical labeled-data study for drift/forecast/routing, involve crowd-safety, accessibility, medical and religious reviewers, and publish an uncertainty-aware evaluation rather than a feature-count narrative.

## Best research direction

Privacy-preserving, uncertainty-aware group recovery and congestion routing for multilingual pilgrims: compare opaque-token recovery and alert policies under synthetic and ethically collected trajectories with calibrated false-alarm and utility measures.

## Best future architecture

A secure Django core with explicit policy/services and PostgreSQL/PostGIS, a measured telemetry ingestion worker, a separate image-processing queue only if needed, and a human-gated operator API. Keep accounts, consent, groups and incidents transactionally close until scale evidence proves otherwise.
