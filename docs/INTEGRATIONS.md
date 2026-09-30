# HajjGuard integration status

HajjGuard currently runs with local sandbox adapters. No Ministry, Nusuk, Nafath, Civil Defense, emergency gateway, SCADA, CCTV, or wallet provider is enabled in production.

| Provider | Current state | Evidence required before enablement |
| --- | --- | --- |
| External identity / Nafath | Disabled | Written authorization, provider specification, sandbox credentials, approved scopes |
| Pilgrimage / Nusuk / Ministry | Sandbox | Read-only contract, permitted fields, privacy approval, test records |
| SCADA / CCTV telemetry | Simulation | Signed feed contract, source provenance, retention and privacy approval |
| Emergency incident gateway | Disabled | Provider API, incident ownership, acknowledgement contract, outage procedure |
| Apple / Google wallet | Disabled | Pass-format approval, signing credentials, branding approval |

The pilgrim SOS flow creates a local incident and shows the selected emergency number. The pilgrim must press a second confirmation control before HajjGuard opens the phone's native `tel:` dialer. HajjGuard records the call handoff request; it cannot verify whether the call was answered.

Live connectors must be enabled one provider at a time through sandbox, staging, and production configurations. Secrets belong in the deployment secret manager. They must never appear in source code, templates, QR payloads, logs, or benchmark artifacts.
