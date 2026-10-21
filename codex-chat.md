# Siraaj Project Conversation Archive

> This file records the accessible conversation history for the Siraaj project, including the user’s requests, implementation decisions, architectural choices, validation results, and delivery notes. Long repeated planning prompts are preserved as structured summaries so the project decisions remain readable.

## 1. Use-case diagrams and descriptions

### User requests

- The user provided a reference screenshot for a use-case description and asked that every use case follow the same student-taught format.
- The user clarified that there should be five detailed use-case diagrams.
- The user requested an implementation plan for all use-case diagrams and descriptions.
- The user requested that the diagrams use the same visual method as the reference: stick-figure actors, oval use cases, black lines, a system boundary, and simple student wording.
- The user asked how to represent the group leader and later asked what to give a team member so the member could prepare the package accurately.
- The user requested a PDF guide containing the complete use-case process.

### Decisions

- Five approved actors were fixed:
  1. User or visitor.
  2. Authenticated pilgrim.
  3. Group member.
  4. Group leader.
  5. Administrator.
- Supporting-service, database, map-provider, government, emergency-service, CCTV, and SCADA actors were excluded.
- Five detailed use cases were fixed:
  - UC-01 Discover places and explore the map.
  - UC-02 Plan a journey.
  - UC-03 Request emergency support.
  - UC-04 Use group safety.
  - UC-05 Maintain the Siraaj system.
- The group leader was given a clear responsibility in UC-04: review group safety information, while being prohibited from changing another member’s consent or enabling tracking silently.
- `«include»` was reserved for required behavior and `«extend»` for optional or conditional behavior.
- Use-case descriptions were required to use the exact student headings: use case name, scenario, triggering event, brief description, actors, related use cases, stakeholders, precondition, postcondition, flow of activities, and exception conditions.
- Activity flows were required to use two columns: Actor and Siraaj system.

## 2. Activity diagrams

### User requests

- The user requested a complete activity-diagram plan and guide.
- The user required five activity diagrams, one for each detailed use case, with standard UML activity notation, swimlanes, decisions, guards, exceptions, and A4-readable black-and-white styling.

### Decisions

- AD-01 covers discovery and map exploration.
- AD-02 covers journey planning and external directions outside verified coverage.
- AD-03 covers authenticated, user-confirmed emergency support.
- AD-04 covers group membership, consent, expiry, revocation, and leader review.
- AD-05 covers administrator maintenance, validation, publication, and auditing.
- No separate activity diagram was created for the full-system overview use case.
- Unsupported claims were excluded: automatic emergency calling, official integrations, live traffic, live CCTV, and fabricated route or crowd data.

## 3. Sequence diagrams

### User requests

- The user requested the same detailed planning and implementation process for sequence diagrams.

### Decisions

- Five sequence diagrams were defined: SD-01 through SD-05, matching UC-01 through UC-05 and AD-01 through AD-05.
- Lifelines were restricted to actors, Siraaj interfaces, Siraaj control/system participants, approved records, and the device call screen where required.
- The diagrams were kept at analysis/design level and excluded SQL, API URLs, framework methods, and source-code implementation.
- `alt`, `opt`, and `loop` fragments were used for exceptions, optional actions, and repeated corrections.
- SOS remains manual and user-confirmed; the system never claims that a call was answered.

## 4. Domain class diagram

### User requests

- The user requested a domain-class package and later asked whether the earlier domain diagram was perfect.
- The user asked for problems to be fixed and for the package to be ready for the final report.

### Decisions

The approved conceptual entities were:

- UserAccount.
- PilgrimProfile.
- Group.
- GroupMembership.
- PilgrimTrip.
- LocationShareGrant.
- Place.
- Zone.
- Corridor.
- CrowdCondition.
- Journey.
- SosIncident.
- EmergencyContact.
- SafetyNotice.
- AuditRecord.

Important corrections included:

- GroupMembership carries the member/leader role.
- Corridors have separate start-zone and end-zone relationships.
- Consent is linked to both a pilgrim and a trip.
- Journey has a required destination and an optional saved start place.
- SOS belongs to a pilgrim and may use an emergency contact.
- Administrator activity is represented through UserAccount and AuditRecord.
- Passwords, QR secrets, provider credentials, medical details, and exact historical paths were excluded.

## 5. Design class diagram

### User requests

- The user requested a design-class plan based on the corrected domain model.
- The user asked for an analysis of mistakes from the earlier plan and a corrected implementation plan.

### Decisions

The design model was divided into three layers:

- Boundary classes: VisitorInterface, JourneyInterface, SosInterface, GroupSafetyInterface, AdminInterface.
- Control classes: DiscoveryController, JourneyController, SosController, GroupSafetyController, MaintenanceController.
- Entity classes: the approved domain entities.

The corrected plan required:

- Boundary-to-control dependencies only.
- Controllers connected only to entities used by their workflow.
- Typed private attributes and limited public operations.
- No undefined PlantUML aliases.
- No unnecessary crossing lines.
- No direct actor-to-entity dependencies.
- Authentication, consent, auditing, privacy, and manual SOS behavior represented.
- One overview diagram plus focused detail diagrams for readability.

## 6. ER diagram

### User requests

- The user supplied predecessor IS 498 documents and a Google Docs reference and asked that the project use the same academic format and methods while improving readability.
- The user requested the best ER plan based on previous plans and identified mistakes.

### Decisions

- The ER diagram uses Chen notation:
  - Rectangles for entities.
  - Ovals for attributes.
  - Diamonds for relationships.
  - Underlined primary-key attributes.
  - Cardinalities such as `1`, `0..1`, `0..*`, and `1..*`.
- GroupMembership is an associative entity.
- Journey Uses Corridor remains a conceptual many-to-many relationship.
- The relational schema later introduces the JourneyCorridor bridge table.
- Corridor start and end relationships are shown separately as `startsAt` and `endsAt`.
- The ER model does not contain actors, controllers, APIs, or database implementation columns.

## 7. Relational schema diagram

### User requests

- The user requested the best relational-schema plan, including corrections from earlier mistakes.
- The user later asked whether it was perfect and ready for the report.

### Decisions

The schema contains 16 tables:

- The 15 approved ER entities converted into tables.
- `journey_corridor` as the many-to-many bridge table.

Important constraints:

- `pilgrim_profile.account_id` is unique.
- `group_membership(group_id, profile_id)` is unique.
- `location_share_grant.trip_id` is unique.
- `journey_corridor` uses a composite primary key and preserves route order with `sequence_number`.
- `corridor` has both `start_zone_id` and `end_zone_id`.
- `journey.start_place_id` is nullable.
- `journey.destination_place_id` is required.
- `sos_incident.emergency_contact_id` is nullable.
- `audit_record.created_by_account_id` references UserAccount.
- No arrays, repeating groups, embedded member lists, route lists, or duplicated crowd values were used.

## 8. Gantt chart

### User requests

- The user asked what was required to complete the Gantt chart.
- The user requested an assessment of previous schedules and a perfect semester plan without assigning responsibilities.
- The user asked which application is commonly used and whether the chart could be made in Microsoft Project.

### Decisions

- The schedule covers 23 August 2026 through 12 December 2026.
- University breaks and final-exam dates were explicitly included.
- The task sequence is:

```text
Scope → Requirements → Use cases → Activity diagrams → Sequence diagrams
→ Domain model → Design class model → ER diagram → Relational schema
→ Implementation evidence → Testing → Report formatting → Review → Submission
```

- Responsibilities were intentionally left blank for Sultan, Abdullah, and Khaled to assign later.
- The final submission date remained provisional until confirmed by the professor.
- A correction buffer was reserved before final exams.

## 9. Risk register

### User requests

- The user requested the same planning and implementation quality for the risk register.

### Decisions

- A 5×5 likelihood/impact method was selected.
- Each risk includes an ID, category, cause, effect, likelihood, impact, score, rating, preventive response, contingency response, trigger, evidence, status, residual risk, review date, and blank owner.
- Security, privacy, SOS, group consent, route provenance, accessibility, schedule, evidence, and governance risks were included.
- A risk could not be marked closed without matching test or review evidence.
- Unsupported official integrations were treated as risks to avoid, not features to claim.

## 10. Repository and branch work

### User requests

- The user asked to push the project to GitHub and the master branch and requested a shareable link.

### Decisions

- Existing repository work was preserved.
- The project’s main code and generated artifacts were kept in the shared workspace.
- Later changes continued in the existing checkout without resetting unrelated work.

## 11. Haram location inventory and 3D map

### User requests

- The user asked how to obtain an official or professionally verified Haram map.
- The user requested a Haram location inventory template and categories.
- The user decided to focus the 3D model on accurate Haram locations first and postpone routes.
- The user asked what to write in an official data-sharing request and wanted student-style wording in English and Arabic contexts.

### Decisions

A separate `HaramLocation` model was defined with:

- Stable location ID.
- Arabic and English names.
- Available source-provided languages.
- Category.
- Floor.
- Geographic coordinates.
- Local 3D coordinates.
- Source and source URL.
- Verification date.
- Accuracy level.
- Enabled status.
- Notes.

Categories include gates, Mataf, Masaa, water, toilets, medical, wheelchair access, elevators, escalators, stairs, meeting points, emergency exits, and information desks.

Rules:

- Unverified records remain disabled.
- Enabled records require evidence and verification date.
- Approximate records must be labelled approximate.
- No official claim is made unless the source confirms it.
- No personal data is stored.
- Routes are postponed until inventory and floor geometry are verified.

The 3D explorer was changed to focus on location inspection, floor selection, category markers, bilingual details, evidence, and opening a selected location on the geographic map. Indoor route lines were removed.

## 12. Accounts, group chat, and leader features

### User requests

- The user asked whether Firebase should be linked for accounts.
- The user asked whether group chat and leader jobs existed.
- The user requested a corrected English-only implementation plan.
- The user later asked to stop and explain what went wrong, then requested the problems be solved and the server started.

### Decisions

- Firebase was not added. Django authentication, Django Channels, and the existing push-notification system remain the identity and communication foundation.
- Group chat uses HTTP as the authoritative write path and WebSocket broadcasting for live updates.
- Polling is a fallback when WebSocket is unavailable.
- Only active members can read or send messages.
- Members can delete their own messages and report messages.
- Leaders can manage only their own group, send announcements, manage geofences, remove other members, change roles, rotate join codes, and request check-ins.
- Leaders cannot change another member’s location consent, enable tracking silently, access medical information, or view exact historical paths.
- Sensitive actions are audited.

## 13. Attraction map redesign

### User request

The user provided a mobile map screenshot and requested an attraction/facility map with a similar layout. The user explicitly asked to remove unnecessary Journey UI and make the map look like the reference while fitting Siraaj.

### Final architectural decision

The public visitor map is now an attraction and facility discovery product. Journey remains in backend/operator code for analytics and regression tests, but it is no longer part of the visitor homepage, primary navigation, discovery page, map, or 3D Haram explorer.

### Implemented visitor map features

- Full-screen geographic MapLibre map.
- Light Siraaj visual style.
- Rounded floating search bar.
- Arabic/English search matching.
- Category chips.
- Filters for crowd state, freshness, accessibility, and public data layers.
- Verified public place, facility, Holy Site, and Haram-location markers.
- Marker clustering.
- Category-specific colors and icons.
- Selected-place details panel.
- Bilingual names.
- Area and floor information.
- Crowd and freshness states.
- Source, verification date, and accuracy information.
- Accessibility and language information.
- External map links based only on public coordinates.
- Map/list fallback.
- Locate-me and recenter controls.
- Mobile bottom navigation: Home, Map, Alerts, Profile.
- Keyboard search behavior with arrows, Enter, and Escape.
- Screen-reader result announcements.
- RTL/LTR support.
- No private group locations, QR values, medical records, or historical GPS data.
- No fabricated photos, ratings, prices, booking, or official claims.

### Public data sources

The map combines public enabled records from:

- `/zones/api/map-data/`
- `/zones/api/visitor-places/`
- `/zones/api/facilities/`
- `/zones/api/haram-locations/`

The client normalizes them into a shared public attraction shape. Disabled, unverified, stale, missing-source, malformed, or invalid-coordinate records are handled honestly and are not presented as verified points.

### Important implementation correction

The map loader was corrected to:

- Convert zone `lat`/`lng` fields into map points.
- Accept both direct facility coordinates and one-point facility arrays.
- Reject multi-point facility geometry rather than inventing a marker.
- Use data attributes from the template for public API endpoints.
- Keep crowd state as `Not measured` unless a valid public relation exists.

### Visitor UI cleanup

Removed from public visitor surfaces:

- Start Journey buttons.
- Journey forms.
- Preference buttons.
- Route alternatives.
- Route panels.
- Fit/Clear route controls.
- Visitor route overlays.
- My Journey navigation labels.
- Route-focused homepage cards and copy.
- Journey links from place panels.

The unused homepage Journey CSS was also removed.

## 14. Testing and validation

### Focused tests

- Visitor/map/UI and zones tests: 38 tests passed.
- JavaScript syntax check for `static/js/attraction-map.js`: passed.
- Node contract smoke test for map coordinate normalization: passed.

### Full regression suite

- Django full suite: **118 tests passed**.
- `git diff --check`: passed, with only normal Git line-ending warnings.
- Known benchmark output continues to mark several evidence-heavy metrics as `NOT MEASURED`; these are not claimed as completed project results.

### Known limitations retained honestly

- Approved Haram inventory may still be empty.
- Accurate floor geometry and calibrated 3D coordinates still require approved source data.
- Full browser/device accessibility testing remains a follow-up activity.
- Offline full-inventory behavior is not claimed as complete.
- Internal routing remains available for operator/testing purposes but is not promoted to visitors.

## 15. Current files changed for the attraction-map phase

- `templates/home.html`
- `templates/base.html`
- `templates/zones/live_map.html`
- `templates/zones/discover_makkah.html`
- `templates/zones/zone_detail.html`
- `static/js/attraction-map.js`
- `static/js/hajjguard-digital-twin.js`
- `docs/feature-audit.md`
- `tests/test_ui_overhaul_interactive.py`
- `tests/test_visitor_journey.py`
- Existing Haram inventory, group safety, account, and operator files were preserved.

## 16. Final current state

Siraaj now presents the visitor with a map-first discovery experience focused on attractions, Holy Sites, facilities, safety information, and verified Haram locations. Public Journey controls and route overlays have been removed. The backend routing engine remains isolated for operator analytics and testing. The 3D Haram explorer is location-focused and does not draw indoor routes.
