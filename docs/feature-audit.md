# Siraaj Feature Audit

Updated: 14 October 2026

This audit separates implemented code from features that still need approved data, verification, or additional development. A feature is not marked complete only because a screen or model exists.

## Implemented and verified

| Area | Current state | Evidence |
|---|---|---|
| Siraaj branding | Logo, navigation, and homepage branding are present. | `templates/base.html`, `templates/home.html`, `static/images/siraaj-logo-master-transparent.png` |
| Public discovery | Public place and facility APIs, administration, and visitor discovery screens exist. | `apps/zones/views.py`, `apps/zones/models.py`, discovery templates |
| Attraction map | The public map is focused on verified attractions, Holy Sites, facilities, search, category filters, selected-place cards, details, and geographic fallback. Visitor Journey controls and route overlays are removed. | `templates/zones/live_map.html`, `static/js/attraction-map.js` |
| Internal journey planning | The existing journey endpoint and routing engine remain for operator analytics and regression tests; Journey is no longer promoted in the public visitor map or homepage. | `apps/analytics/views.py`, `services/routing.py` |
| Route safety rules | Internal route validation and operator comparison remain covered; public attraction discovery does not draw route lines. | routing services and route tests |
| Haram inventory model | `HaramLocation` supports stable IDs, Arabic/English names, languages, category, floor, geographic coordinates, local 3D position, source, verification date, accuracy, enabled status, and notes. | `apps/zones/models.py`, migration `0009_haramlocation.py` |
| Haram administration | Search, filters, coordinate separation, validation, and approximate-publication warning are present. | `apps/zones/admin.py` |
| Haram public API | Only enabled, non-unverified records are returned; private administrator fields are excluded. | `/zones/api/haram-locations/`, `apps/zones/views.py` |
| Haram explorer UI | Search, category filter, floor selector, bilingual details, evidence display, map handoff, empty state, and WebGL fallback are present. | `templates/home.html`, `static/js/hajjguard-digital-twin.js` |
| Haram-only 3D scope | The current explorer shows Haram geometry only and does not draw indoor route lines. | `static/js/hajjguard-digital-twin.js` |
| Safety and privacy foundations | Existing SOS authentication/manual-call flow, group consent/expiry, QR/offline handling, and related authorization tests remain in the project. | existing safety, groups, and account apps/tests |
| Languages configured | Arabic, English, Urdu, Indonesian, Bengali, Turkish, French, and Malay are configured. | `hajjguard_core/settings.py` |

## Other existing application modules

These modules are present in the repository and have automated coverage, but they must be described honestly in the report.

| Module | Current state | Reporting limit or next check |
|---|---|---|
| Accounts and profiles | Registration, login, profiles, guardian relationships, push subscriptions, and audit logging exist. | Complete browser authorization and translated-content review before claiming production readiness. |
| Group safety | Groups, memberships, trips, consented sharing, live-member visibility, messages, geofences, and ping requests exist. Location markers, drift calculations, freshness, and leader management now use only active consented telemetry. | Real-device location accuracy and drift measurements remain unverified. |
| Emergency support | SOS creation, category-to-number selection, deduplication, incident assignment/resolution, and manual call-intent records exist. | It must remain a user-confirmed handoff; no answered-call or official-gateway claim is supported. |
| Crowd and analytics | Zones, density records, risk board, routing comparison, forecast configuration, exports, and benchmark command exist. | Forecast accuracy, load reduction, battery, offline, and false-alarm metrics are still not measured. |
| PWA/offline card | Service worker, offline emergency card, private local card cache, queued outbox, and push hooks exist. | The service worker caches only the offline shell; full public map/Haram inventory offline behavior is not complete or verified. |
| Nusuk/AI and adapters | Nusuk card models, campaign/schedule screens, AI chat, and adapter/integration status code exist. | These are local or sandbox capabilities unless written authorization and live-provider evidence are available. Do not present them as official integrations. |
| Operator tools | Safety dashboard, incident queue, integration status, weather fallback, and exports exist. | Keep operator screens separate from the visitor product and test export privacy before release. |

## Group chat and leader responsibilities

| Feature | Current evidence | Status |
|---|---|---|
| Join a group | Join-code endpoint creates or reuses an active membership. | Implemented at API level; browser flow still needs end-to-end testing. |
| See the leader and members | The My Group page shows the leader, member list, latest locations, and group map when data is available. | Implemented in the current page. |
| Consent-based location sharing | Sharing requires authentication, active trip membership, explicit consent, expiry, and revocation. | Implemented and tested at API level. |
| Drift and meeting-area alerts | Geofences, enter/exit alerts, stale-location messages, and leader-distance checks exist. | Implemented at service/API level; real-device accuracy is not measured. |
| Group text chat | `GroupMessage`, list/create endpoints, cursor polling, rate limiting, attachments, moderation, Channels broadcast, and a chat panel now exist. | Implemented in the web flow; device notification delivery still needs real-device verification. |
| Leader geofence management | A leader or staff member can create, edit, disable, and review geofences through the protected API and dashboard. | Implemented; location accuracy still depends on real device telemetry. |
| Leader member management | The leader dashboard can review consent freshness, remove members other than the leader, change member roles, and rotate the join code. | Implemented with authorization and audit checks. |
| Leader alerts and notifications | Push, phone-ping requests, group announcements, and group alerts have backend models, endpoints, and dashboard actions. | Implemented at application level; notification delivery and leader inbox behavior need browser and device testing. |

The group chat and leader features therefore exist as backend foundations, but they are not a complete visitor-facing experience. Firebase is not required for this phase; Django Channels plus the existing push system is sufficient.

## Implemented but not complete as a product feature

| Area | What exists | What is still missing |
|---|---|---|
| Haram locations | The schema, API, admin, and interface are ready. | No approved location records are published yet; the API currently returns an empty inventory by design. |
| 3D accuracy | Local `x/y/z` positions can be stored and displayed. | No approved Haram floor plan or calibrated coordinate transform has been loaded, so the geometry remains illustrative. |
| Floor support | Floor selection filters inventory markers. | Separate accurate geometry for each floor has not been built. |
| Category visuals | Categories and labels exist. | Final category icons/legend and visual QA are still needed. |
| Public search | Map and Haram search exist. | Search still needs a complete multi-result, Arabic-aware, accessibility-tested experience across all public datasets. |
| Facilities | Models and API paths exist. | The current environment has no verified facility inventory to demonstrate publicly. |
| Route drawing | Geographic route state and map drawing remain available. | Routes are approximate zone/corridor planning guidance; they are not indoor Haram navigation and are intentionally absent from the 3D explorer. |
| Offline behavior | Emergency/offline card and PWA foundations exist. | The full Haram inventory and basemap are not yet a complete offline package. |
| Language support | Eight language codes are configured. | Translation completeness and layout testing for every language still require review. |
| Data workflow | Manual administrator validation exists and a CSV template is provided. | CSV import, second-person approval, and evidence-review history are not implemented as workflow features. |

## Not implemented and required before claiming completion

1. Obtain an authorized or professionally verified Haram source.
2. Populate and review the inventory for gates, Mataf, Masaa, water, toilets, medical points, accessibility entrances, elevators, escalators, stairs, meeting points, emergency exits, and information desks.
3. Calibrate the local 3D coordinate system against the approved source.
4. Add accurate floor-specific geometry and verify marker placement on each floor.
5. Add a visible category legend and final marker icons.
6. Add approved CSV import only after the source format and review process are agreed.
7. Complete browser tests for published inventory, floor filtering, category filtering, Arabic/RTL, keyboard navigation, screen readers, mobile layout, and WebGL fallback.
8. Complete translation review for all eight configured languages.
9. Decide whether offline Haram inventory is required and, if so, cache only approved public records with freshness labels.
10. Do not implement indoor routes until the location inventory and floor geometry pass verification.

## Explicitly out of scope for this phase

- Indoor turn-by-turn navigation.
- Survey-certified architectural claims.
- Live CCTV, SCADA, live traffic, or automatic emergency calls.
- Government, Nusuk, Nafath, or emergency-gateway integrations without written authorization.
- Personal, group, medical, QR, or historical GPS data in the public Haram inventory.

## Verification evidence

- `manage.py check`: passed.
- Focused zones and UI suite after the latest explorer changes: 31 tests passed.
- Group/PWA suite after the chat and leader work: 19 tests passed.
- Current full Django suite: 118 tests passed.
- API smoke check: HTTP 200; categories are returned and `haram_locations` is currently empty because no approved records have been entered.
- The empty-state browser view was checked on the local development server.

The defense benchmark runner also reports several evidence gaps as `NOT MEASURED`: forecast accuracy, choke-point load reduction, device battery use, offline service-worker fallback, and group-drift false-alarm rate. These must not be presented as achieved metrics until the required labeled data, controlled scenarios, real-device runs, or browser-offline tests exist.

## Completion decision

The software foundation for the Haram location explorer is implemented. The complete visitor feature is **not yet complete** because approved location data, 3D calibration, floor geometry, and full accessibility/language verification are still missing. The next release gate is approved inventory and coordinate calibration, not indoor routing.

