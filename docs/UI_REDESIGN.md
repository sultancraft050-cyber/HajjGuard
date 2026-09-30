# HajjGuard UI redesign

## Design philosophy

The landing experience is organized around one decision: help a pilgrim understand a place before moving through it. The page uses a calm white and soft green visual system, large readable type, a single exploration surface, and a persistent emergency action. It is a HajjGuard safety experience rather than a travel booking page or a dense operations dashboard.

## Main components

- **Exploration hero:** a large illustrative aerial Haram view with selectable zone markers, rotation controls, and a clear Simulation Mode label. It is not a live camera feed.
- **Zone information panel:** shows the selected zone, current status, density, prediction, risk, and links to the full map and guidance screens.
- **Intelligence cards:** explain the three user benefits: Predict, Guide, and Protect.
- **Journey planner:** lets the user choose a start, destination, and priority such as less crowded, cooler, or accessible.
- **Emergency action:** keeps SOS access visible from the top navigation.
- **Honesty labels:** local, synthetic, and unavailable data are identified in the interface.

## User journeys

1. A visitor explores a Holy Site zone and opens its summary.
2. A pilgrim starts a journey and opens the full map or guidance page.
3. A pilgrim chooses a route priority before moving.
4. A pilgrim uses the persistent SOS action when help is needed.
5. An operator continues to use the dedicated operations screens for incident and zone work.

## Technical choices

The first screen remains a server-rendered Django page and uses the existing sectional telemetry JSON. The explorer uses a repository-hosted illustrative aerial image with lightweight HTML, CSS, and JavaScript overlays, so it works without a new build system, external 3D runtime, or paid map service. Selecting a marker reads the existing zone record; it does not create a separate frontend data source. The full geographic map remains available on the live-map route.

## Accessibility and responsive behavior

Zone markers and controls are keyboard-focusable buttons with accessible names. The layout collapses to one column on phones, keeps the SOS control visible, and honors reduced-motion preferences. Color is paired with text status so crowd meaning does not depend on color alone.

## Future extensions

The digital twin can later be replaced with an authorized 3D or terrain provider without changing the zone panel contract. A future implementation can add verified facilities, time recommendations, and route alternatives when those measurements are available. No official provider, live CCTV feed, or automatic emergency calling is implied by this interface.
