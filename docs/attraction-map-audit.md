# Siraaj 2D Attraction Map Audit

**Audit scope:** public 2D geographic attraction/facility map only. The 3D Haram explorer was explicitly excluded.

**Audit date:** 14 October 2026

**Audited files:**

- `static/js/attraction-map.js`
- `templates/zones/live_map.html`
- `templates/zones/discover_makkah.html`
- `templates/zones/zone_detail.html`
- `templates/home.html`
- `templates/base.html`
- `apps/zones/views.py`
- `apps/zones/models.py`
- `apps/zones/urls.py`

## 1. Executive Summary and Test Results

The public map has a good visitor-focused structure: MapLibre, floating search, category chips, filtering, a details panel, a place-list fallback, RTL text switching, and public-data privacy boundaries are present. The current live database, however, contains no published visitor places, no verified safety facilities, and no approved Haram locations. The only populated public map source is the zone layer in `/zones/api/map-data/`.

The most significant functional issue is that the frontend fetches the zone payload but never adds `data[0].zones` to the normalized `state.items` collection. As a result, the 17 valid public zones returned by the map API are not rendered as visitor map points. The current map therefore has zero rendered entries in the live environment.

### Automated results

| Check | Result | Evidence |
|---|---:|---|
| `tests.test_ui_overhaul_interactive` | Passed | 20 tests in the UI module when run with the map tests |
| `tests.test_visitor_journey` | Passed | 7 tests |
| `apps.zones.tests` | Passed | 11 tests |
| Combined focused map/visitor/zones suite | **38 passed** | Django test output on 14 October 2026 |
| Full Django suite | **118 passed** | Earlier full regression run after the same map implementation |
| `node --check static/js/attraction-map.js` | Passed | Node syntax check |
| Node coordinate-normalization smoke test | Passed | Zone conversion and invalid-NaN rejection |
| `git diff --check` | Passed | Only normal Git line-ending warnings |

The test suite proves regression coverage, but it does not prove that real approved attraction records or accurate Haram coordinates exist. The live data audit below remains the source of truth for that limitation.

## 2. Live Database, API, and Rendered Marker Counts

The audit used Django’s read-only test client with `HTTP_HOST=localhost` and queried the local database without creating or modifying records.

### Database and endpoint counts

| Dataset / endpoint | Database total | Enabled/public database rows | Endpoint rows returned | Accepted by `normalize()` | Dropped by `normalize()` | Rendered in `state.items` |
|---|---:|---:|---:|---:|---:|---:|
| `Zone` / `/zones/api/map-data/` zones | 17 | 17 | 17 | 17 coordinate-valid when tested directly | 0 | **0** |
| `VisitorPlace` / `/zones/api/visitor-places/` | 0 | 0 | 0 | 0 | 0 | 0 |
| `SafetyMapFeature` / `/zones/api/facilities/` | 0 | 0 verified enabled | 0 | 0 | 0 | 0 |
| `HaramLocation` / `/zones/api/haram-locations/` | 0 | 0 | 0 | 0 | 0 | 0 |

The zone endpoint also returned 11 active corridor records. Corridors are not rendered by `attraction-map.js`; the current visitor map only creates point features from visitor places, facilities, and Haram locations.

### Exact API observations

- `/zones/api/map-data/` returned HTTP 200 with 17 zones, 11 corridors, zero facilities, and zero visitor places.
- `/zones/api/visitor-places/` returned HTTP 200 with an empty `places` array.
- `/zones/api/facilities/` returned HTTP 200 with an empty `features` array.
- `/zones/api/haram-locations/` returned HTTP 200 with an empty `haram_locations` array and all 13 category definitions.
- The API correctly returned a privacy note stating that public layers contain no personal identifiers, QR tokens, medical data, or private locations.

### Coordinate and validation counts

- All 17 zone records converted cleanly from `lat`/`lng` to finite latitude/longitude pairs when passed directly through the Node smoke check.
- There were no facility records to classify as direct points, one-point arrays, or rejected multi-point geometry.
- There were no enabled records rejected for missing source, missing verification date, unverified status, or out-of-bounds coordinates because the visitor, facility, and Haram inventories are empty.
- The number of currently rendered `Not measured` attraction markers is zero because no attraction records are rendered. If records are added, `normalize()` assigns `NOT_MEASURED` by default at `static/js/attraction-map.js:61`.

## 3. Confirmed Bugs and Edge Cases

### High priority findings

#### H-01: Zone records are fetched but never rendered

**Evidence:** `static/js/attraction-map.js:109` builds `entries` from `data[1].places`, `data[2].features`, and `data[3].haram_locations`, but excludes `data[0].zones`.

**Impact:** The live API has 17 valid zones, but none become `state.items`, markers, search results, list results, or selected-place details. The Holy Site category therefore has no live source in the current visitor map.

**Recommended fix:** Decide explicitly whether zones are public attraction points. If they are, normalize them from the zone payload and include them in the entries collection. If they are intentionally excluded, remove the unused zone fetch or explain that only dedicated public place records are shown.

#### H-02: Crowd-state mapping cannot match a zone

**Evidence:** `static/js/attraction-map.js:111` searches for `item.rawZone`, but `normalize()` at `static/js/attraction-map.js:53-61` never sets `rawZone`.

**Impact:** No normalized item can match a zone’s `data_freshness` or status. Crowd labels remain `Not measured` for all future place, facility, and Haram records even when a valid public zone relation might exist.

**Recommended fix:** Add an explicit, validated public zone relation to the normalized record, or keep all attraction crowd states as `Not measured` and remove the dead matching code. Do not infer crowd state from geographic proximity.

### Medium priority findings

#### M-01: Arabic and English secondary names are reversed

**Evidence:** `static/js/attraction-map.js:103` assigns `detail-ar.textContent = ar ? item.nameEnglish : item.nameArabic`.

**Impact:** In Arabic mode, the secondary line displays English. In English mode, it displays Arabic. The primary `name()` choice is correct, but the secondary bilingual line is reversed.

**Recommended fix:** Use `ar ? item.nameEnglish : item.nameArabic` only if the element is intentionally labelled as the other language; otherwise make the element label and assignment explicit so Arabic mode shows Arabic as the primary language and English as the secondary language.

#### M-02: Source URLs are accepted by the API but not preserved in the normalized model

**Evidence:** `apps/zones/views.py:87-103` returns `source_url` for visitor places. `static/js/attraction-map.js:53-61` does not copy `source_url` into the normalized item, and `static/js/attraction-map.js:103` renders only the source name.

**Impact:** A visitor cannot inspect the public evidence link even when the source provides one. This weakens traceability and source review.

**Recommended fix:** Preserve a safe `sourceUrl` field and render it as a normal HTTPS link after validating the scheme. Keep it informational and do not expose private credentials.

#### M-03: Basemap failure does not automatically expose the list fallback

**Evidence:** `static/js/attraction-map.js:108` handles the MapLibre `error` event by changing the message only. `fallback()` is called for missing MapLibre, WebGL loss, or initialization exceptions, but not for tile/style errors.

**Impact:** A style/tile failure can leave a blank map with a message while the list fallback remains hidden.

**Recommended fix:** On a terminal MapLibre style/tile failure, call the same fallback path used for library/WebGL failure and expose the reviewed place list.

#### M-04: Coordinate validation accepts `(0,0)` and does not detect swapped coordinates

**Evidence:** `static/js/attraction-map.js:14` checks only numeric range. `apps/zones/models.py:304-312`, `apps/zones/models.py:241-245`, and `apps/zones/models.py:176-186` apply the same range-only approach.

**Impact:** A formally valid but unusable `(0,0)` point can be accepted. A swapped pair can remain numerically valid if both values fall within both allowed ranges. The map does not enforce a Makkah-area plausibility check.

**Recommended fix:** Keep the generic global range validation, then add a source-specific plausibility/review rule or an explicit `accuracy_level`/validation state. Do not silently move or “correct” coordinates.

#### M-05: Cluster expansion API compatibility is uncertain

**Evidence:** `static/js/attraction-map.js:108` uses `await getClusterExpansionZoom(...)`. MapLibre versions differ between callback-style and Promise-style APIs.

**Impact:** A cluster click may fail in the bundled runtime if the installed MapLibre build exposes only a callback API.

**Recommended fix:** Verify the bundled vendor API and use the supported callback/Promise form with a compatibility wrapper.

### Low priority findings

#### L-01: The API computes the Haram empty-state function twice

**Evidence:** `apps/zones/views.py:192-194` calls `published_haram_locations()` for the response and calls it again to select the note.

**Impact:** Extra database work and repeated validation, small at current scale.

**Recommended fix:** Compute once, assign to a local variable, and reuse it.

#### L-02: The details panel is a panel rather than a distinct selected-place bottom card

**Evidence:** `templates/zones/live_map.html:34` contains one details section. Marker selection opens it directly through `select()` at `static/js/attraction-map.js:103`.

**Impact:** The reference-style “selected place card, then details panel” distinction is not fully implemented. The current panel is functional but denser than the requested two-step mobile flow.

**Recommended fix:** Add a compact selected-place card for quick context and retain the expanded details drawer for full evidence and accessibility data.

#### L-03: There is no separate inline search-clear control

**Evidence:** Search is wired at `static/js/attraction-map.js:115`; reset is provided only by `clear-filters` at `static/js/attraction-map.js:123`.

**Impact:** Users can clear the search through the filter panel, but a familiar inline clear affordance is absent.

**Recommended fix:** Add an accessible clear button that appears when the search field contains text and restores the initial result state.

## 4. UI/UX, RTL/LTR, Responsive, and Accessibility Review

### Confirmed strengths

- The map template has explicit container IDs and data attributes at `templates/zones/live_map.html:15-35`.
- Endpoint URLs are available through `data-map-data-url`, `data-visitor-places-url`, `data-facilities-url`, and `data-haram-locations-url` at `templates/zones/live_map.html:30`, with safe hardcoded fallbacks at `static/js/attraction-map.js:109`.
- Search uses a combobox/listbox structure at `templates/zones/live_map.html:16` and generates `role="option"` buttons at `static/js/attraction-map.js:90-95`.
- Arrow key, Enter, and Escape handling is present at `static/js/attraction-map.js:116-117`.
- Result announcements use `role="status"` and `aria-live="polite"` at `templates/zones/live_map.html:27` and are updated at `static/js/attraction-map.js:102-103`.
- Touch targets are generally at least 42–44px through `templates/zones/live_map.html:7-10`.
- Reduced motion is respected at `static/js/attraction-map.js:82` and `templates/zones/live_map.html:11`.
- The mobile bottom navigation exists at `templates/zones/live_map.html:35`, with Map visually selected on the map page.
- The map uses RTL-aware logical properties in the later CSS rules at `templates/zones/live_map.html:9-10`.
- The list fallback uses text labels and buttons, so it does not depend only on marker color.

### Issues and risks

- There is no focus trap inside the details drawer. Escape restores focus to the search field, but keyboard focus can move behind the open panel.
- The search input has `aria-controls` and `aria-expanded`, but no explicit `aria-haspopup="listbox"`; adding it would improve assistive technology consistency.
- The map’s `error` event does not activate the list fallback, as described in M-03.
- `home.html:94` marks the Map item as `active` even when the visitor is on the homepage. This is incorrect active-link highlighting.
- `templates/base.html:358-385` provides the main header links, but the header uses Arabic translation strings and does not expose the same explicit four-item Home/Map/Alerts/Profile visitor navigation as the mobile map navigation.
- The map status, filter drawer, category strip, controls, details panel, and bottom navigation are all layered absolute/positioned elements. The CSS has reasonable z-index values, but a full visual browser pass at mobile and RTL sizes is still required because the live inventory is empty and cannot exercise a selected-place panel.
- The current `Map/list` toggle is implemented as a fallback/list visibility toggle, not a full two-way view switch. MapLibre remains present under the list.
- The “Locate me” handler uses temporary memory only, which is privacy-correct, but it does not warn when the user is outside Makkah. It flies to any valid browser coordinate at `static/js/attraction-map.js:125`.

## 5. Security, XSS, and Privacy Verification

### Positive findings

- `attraction-map.js` does not use `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `eval`, or `document.write` for public data. User/database strings are inserted with `textContent` at `static/js/attraction-map.js:90-95` and `static/js/attraction-map.js:103`.
- The external map URL is built from validated numeric coordinates with `encodeURIComponent` at `static/js/attraction-map.js:103`.
- The external URL has a fixed HTTPS Google Maps origin and `target="_blank" rel="noopener noreferrer"` in `templates/zones/live_map.html:34`.
- The browser location is used temporarily in `static/js/attraction-map.js:125`; no localStorage or sessionStorage write is present in this map script.
- `api_visitor_places()` filters `enabled=True` and calls `full_clean()` before returning rows at `apps/zones/views.py:66-83`.
- `api_safety_features()` filters enabled, verified records and validates each row at `apps/zones/views.py:117-129`.
- `published_haram_locations()` filters enabled records and excludes `UNVERIFIED` rows at `apps/zones/views.py:169-186`.
- API payloads do not return personal group locations, QR values, medical details, or administrator credentials.
- The models require source and verification data before enabled public records are valid: `apps/zones/models.py:187-188`, `apps/zones/models.py:253-261`, and `apps/zones/models.py:313-319`.

### Remaining security/data-quality concerns

- `source_url` is not rendered by the current UI. If it is later added, scheme validation is required before assigning it to `href`.
- Generic coordinate validation does not reject `(0,0)` or implausible but numerically valid swapped pairs.
- `HaramLocation.notes` is intentionally public in `apps/zones/views.py:178-185`; administrators must continue to keep private information out of notes.
- The current map API uses aggregate zone telemetry in `apps/zones/views.py:260-306`. It does not expose pilgrim IDs, but any future normalization of zones must keep aggregate crowd data separate from personal location records.

## 6. Live Demo Risks

1. **Empty public inventory:** the live database contains zero VisitorPlace, SafetyMapFeature, and HaramLocation rows. The map cannot demonstrate attraction markers until approved public records are entered.
2. **Zones not rendered:** 17 valid zones and 11 corridors are returned, but zones are excluded from `state.items`. The demo may appear empty even though the API contains data.
3. **Dropped multi-point facilities:** SafetyMapFeature allows one or more coordinate pairs at `apps/zones/models.py:166`. The frontend intentionally accepts only a direct point or one-point array at `static/js/attraction-map.js:33-42`; route/polygon-like facilities are dropped.
4. **Not measured crowd states:** normalized attractions default to `NOT_MEASURED` at `static/js/attraction-map.js:61`, and the current zone matching code cannot match because `rawZone` is absent.
5. **Stale records:** records older than 90 days are accepted but labelled stale at `static/js/attraction-map.js:58`. They must not be presented as current.
6. **Basemap outage:** MapLibre initialization/WebGL failures show the list fallback, but a style/tile `error` event currently only changes the status message.
7. **External map dependency:** selected-place links open Google Maps. The application does not claim route guidance or live traffic.
8. **Approved Haram coordinates are still missing:** no floor-specific, professionally verified Haram inventory is currently published.

## 7. Prioritized Fix Plan

### Critical

- Resolve H-01 before presenting the map as containing Holy Sites: either render validated zones or explicitly remove the zone source from the public-map contract.
- Populate approved public inventory records only after evidence and second-person review. Do not use synthetic records as verified attractions.

### High

- Resolve H-02 so crowd labels are either correctly related to public records or intentionally remain `Not measured` with dead matching code removed.
- Make tile/style errors activate the reviewed list fallback.
- Fix the reversed bilingual detail line.
- Correct homepage bottom-navigation active state.

### Medium

- Preserve and safely render `source_url` evidence links.
- Add explicit `(0,0)` and source-specific plausibility/review checks while retaining global coordinate validation.
- Verify MapLibre cluster expansion compatibility with the bundled library.
- Add a real two-step selected-card/details interaction if the screenshot reference is a strict acceptance target.
- Add a focus trap or modal semantics for the mobile details drawer.
- Add an outside-Makkah warning for Locate Me.

### Low

- Avoid calling `published_haram_locations()` twice.
- Add an inline search-clear button.
- Improve the header/mobile navigation parity and language labels.
- Run visual browser checks at mobile, tablet, desktop, Arabic RTL, English LTR, reduced-motion, WebGL failure, and tile-failure states.

## Audit Conclusion

The current implementation has a solid privacy-safe visitor-map foundation and passes the automated map/visitor regression tests. It is **not yet ready to claim a complete attraction map** because the live public inventory is empty and the 17 populated zone records are not rendered by the frontend. The most important next action is to resolve the zone-source decision and publish only approved, source-labelled attraction/facility/Haram records. No application code was changed during this audit.


## 8. Post-implementation verification

The approved fix plan was implemented after the original audit. The coordinate guardrail was set to latitude `21.30–21.50` and longitude `39.75–40.10`, based on the exact live and test-fixture ranges. All live Zones and existing coordinate fixtures fall inside these bounds.

### Updated live database/API/rendered marker table

| Dataset | Database total | Enabled/public rows | API rows | Accepted by frontend normalization | Dropped | Rendered entries |
|---|---:|---:|---:|---:|---:|---:|
| Zones / map-data | 17 | 17 | 17 | 17 | 0 | 17 |
| Visitor places | 0 | 0 | 0 | 0 | 0 | 0 |
| Facilities | 0 | 0 verified | 0 | 0 | 0 | 0 |
| Haram locations | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total point entries** | **17** | **17** | **17** | **17** | **0** | **17** |

The API continued to return 11 active corridors. Corridors remain backend/operator data and are not drawn as visitor route overlays.

### Fixes verified

- Zones are now normalized as `HOLY_SITE` records and rendered as public Holy Site markers.
- Zone API records now include a local source label, verification date, and reviewed accuracy state.
- Zone crowd labels use explicit zone status and freshness only.
- `(0,0)`, swapped coordinates, and out-of-region points are rejected by backend and frontend validation.
- `SafetyMapFeature.source_url` was added with migration `zones.0010_safetymapfeature_source_url`.
- Visitor, facility, and Haram source URLs are preserved and safely displayed when public.
- Search clear resets only the query and results; full reset remains on `#clear-filters`.
- MapLibre fallback activates only for terminal style/initialization errors, missing WebGL, or failed initialization. Minor tile errors keep the map available.
- The compact selected-place preview preserves all existing detail IDs and data attributes.
- The bilingual secondary name mapping is corrected.
- The homepage marks Home active; the map page marks Map active.
- Cluster expansion supports callback and Promise MapLibre variants.
- Locate Me reports outside-Makkah coordinates without persisting them.
- The detail drawer has dialog semantics, focus restoration, and keyboard trapping.

### Updated validation

- Full Django suite: **119 tests passed**.
- Focused visitor/map/zones suite: **41 tests passed**.
- `manage.py makemigrations zones --check --dry-run`: no changes detected.
- `node --check static/js/attraction-map.js`: passed.
- Node normalization smoke test: passed for valid zones, `(0,0)`, swapped coordinates, and out-of-region coordinates.
- Live migration `zones.0010_safetymapfeature_source_url`: applied successfully.

### Remaining data limitation

The code now renders the 17 local Zone records, but the live database still has zero approved VisitorPlace, SafetyMapFeature, and HaramLocation records. The map therefore shows Holy Site zone markers while attraction/facility/Haram inventory remains empty until approved source data is entered.
