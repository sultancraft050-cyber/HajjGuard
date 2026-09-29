# HajjGuard engineering decision log

This log records decisions from the current review without exposing private chain-of-thought. Each entry states evidence, alternatives, consequence and a reconsideration trigger.

| Decision | Evidence and alternatives | Why selected | Consequence / reconsider when |
|---|---|---|---|
| Keep Django modular monolith | Current six apps are runnable; microservices would add network/ops failure | Small team needs inspectability and local transactions | Refactor services first; reconsider when measured load or ownership requires separation |
| Python 3.12 baseline | Fresh 3.12.14 environment installed requirements; inherited environment was incompatible | Matches current reproducible run and dependency wheels | Reconsider after dependency lock and supported 3.13 test |
| PostgreSQL required next, SQLite retained for local tests | SQLite passed; no PostgreSQL 16 run exists | Fast local feedback plus production-like database gate | Do not call DB support verified until PG16 run |
| Prefer circles now, study PostGIS later | Zone model and Haversine are simple and testable; polygon maps unavailable | Avoid invented geometry | Reconsider with authoritative indoor/multilevel geometry |
| Polling/local APIs now, WebSockets later | No measured concurrency requirement | Fewer moving parts for prototype | Reconsider after freshness/latency load evidence |
| Management command for retention now, scheduler later | `prune_location_pings` is executable and tested | Explicit, reviewable deletion | Reconsider for Celery/managed scheduler in staging |
| Django templates now, React later only for measured need | 15 templates provide bilingual server-rendered pages | Keeps accessibility and deploy surface small | Reconsider after user study or interaction complexity |
| Linear forecast is a baseline, not a claim of ML accuracy | `services/prediction.py` works and clamps output; no labeled MAE | Transparent baseline is academically defensible | Reconsider with timestamped labeled series |
| Dijkstra-style directed routing now, A* later | NetworkX graph is small; no validated heuristic | Correct for modeled graph and easy to inspect | Reconsider at measured graph scale with admissible distance |
| One best route now, multi-route later | Demand allocation data absent | Avoids pretending to solve flow assignment | Reconsider with origin/destination demand and capacity labels |
| Local rule-based Fiqh assistant, no external LLM | External API authority/privacy/cost unavailable; local service exists | Deterministic demonstration and no credential dependency | Reconsider only with approved content and scholar review |
| Prototype card, no official integration claim | `get_or_create_demo_card` generates local records; no authority | Safe academic scope | Reconsider only with written institutional API/branding authorization |
| Synthetic sensors/simulation explicitly labeled | CCTV and sectional services generate local values | Allows repeatable demonstrations | Reconsider with provenance and authorized replay/live feed |
| Keep accessibility/localization as core | `base.html` has Arabic/RTL switching and templates are responsive | Directly serves project context | Simplify UI if tests show excess complexity; do not remove Arabic/RTL |
| Treat privacy/security as merge gates | Source review found account takeover, enumeration and public writes | Harm is larger than benefit of more features | Reconsider only after role/attack/retention evidence |
| Treat benchmark `NOT MEASURED` as correct | Current JSON marks six metrics unavailable; historical hardcoded values removed | Honest negative evidence | Replace only from raw reproducible protocol |
| Do not modify application behavior during assessment | User requested documentation-only deliverables | Preserves branch truth for report | Behavior fixes belong in separately reviewed commits |

## Alternatives and ideas considered but not implemented

- **Python 3.13:** available inherited environment was incompatible with installed NumPy; 3.12 was reproducible. Reconsider with a locked, tested dependency set.
- **PostgreSQL instead of SQLite everywhere:** correct pilot target, but unavailable for this review; retain SQLite for fast unit tests and add PG gate.
- **Polygons/PostGIS instead of circular zones:** more accurate but needs authoritative maps and GIS skills; defer until geometry data exists.
- **WebSockets instead of polling:** useful for live freshness but adds connection/state complexity without load evidence.
- **Celery instead of a management command:** appropriate for scheduled retention at scale; explicit command is easier to audit in a prototype.
- **React instead of Django templates:** may improve complex client interactions, but current templates are simpler to test and localize.
- **Pretrained YOLO/crowd models instead of file-size simulation:** required for real vision; would add model, GPU, data and privacy obligations. Keep simulation clearly renamed until then.
- **Advanced forecasting instead of linear regression:** likely better with data, but cannot validate a more complex model without labels; baseline remains transparent.
- **A* instead of Dijkstra:** only useful with a trustworthy heuristic and larger graph.
- **Multi-route allocation instead of one best route:** requires demand/capacity constraints and evaluation.
- **External LLM instead of internal rules:** adds authority, privacy, latency and credentials; not justified for a prototype Fiqh interface.
- **Official card/integration instead of local card:** impossible to claim without authorization and API evidence.
- **Live sensors instead of simulation:** necessary for a pilot but unavailable and institution-dependent.
- **Microservices instead of monolith:** premature; would make consent/incidents and deployment harder to reason about.

## Reconsideration rule

Any feature should be reconsidered only after its data source, authorization, owner, failure mode, test protocol and evidence artifact are named. A polished screen, a passing mocked test or a generated metric is not sufficient evidence to promote a simulated feature to operational status.
