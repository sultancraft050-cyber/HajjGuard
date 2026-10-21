# Siraaj language audit

## Current supported languages

The active visitor language selector supports Arabic (`ar`) and English (`en`). Other languages are not advertised until their interface translations are complete.

## Verified bilingual surfaces

- Homepage navigation, visitor copy, Haram explorer, 3D explorer labels, and mobile language switch.
- Attraction map search, categories, filters, status messages, details, fallback states, and mobile navigation.
- Discovery page and public place details.
- Zone detail labels and measurement units.
- Group page header, chat, member status, management labels, and browser-generated messages.
- Registration, profile/privacy settings, and the pilgrim portal.
- Risk board and analytics reports.
- Shared navigation, footer, search palette, and emergency dialog.
- Nusuk assistant launcher, prompts, placeholder, and request language.

## Map language behavior

- Siraaj controls use the active Arabic or English locale.
- Place names prefer the selected language, then fall back to English or Arabic.
- MapLibre symbol layers request `name:ar` for Arabic and `name:en` for English when the tile data provides those properties.
- The map never invents translated place names when the source does not provide them.

## Verification

- Django system check passes.
- JavaScript syntax checks pass for the attraction map and Haram digital twin.
- Visitor/UI/PWA tests pass.
- Full Django suite: 119 tests passed in the final full run.

## Current boundary

All public visitor, map, account, group, PWA, safety-status, and guidance surfaces now use Arabic/English locale branches. Remaining Arabic text in source files is an Arabic branch, user-provided data, brand metadata, or a compatibility comment retained for an existing regression hook. The operator telemetry dashboard still contains a small set of English-only internal labels because it is an English-facing staff tool; it does not appear in the visitor site or map.

## Browser verification

- English map: search, category filtering, place selection, details drawer, external-map link, and list fallback verified.
- Arabic map: RTL direction, Arabic search, Arabic categories, Arabic place details, mobile language switch, and localized MapLibre controls verified.
- Language persistence: Arabic remained active when navigating home and returning to the map.
- Responsive check: mobile viewport verified with the compact language switch and bottom navigation; desktop layout rules remain in the responsive stylesheet and are covered by the UI regression suite.
