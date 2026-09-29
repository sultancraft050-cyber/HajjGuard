# Architecture

HajjGuard is a Django modular monolith. `accounts` handles profiles and audit logs; `zones` stores spatial telemetry and density; `groups` handles group membership and drift; `safety` handles SOS and operations; `analytics` handles risk, reports, routing and evaluation; `nusuk` contains local simulated card workflows. `services/` contains algorithm and adapter modules.
