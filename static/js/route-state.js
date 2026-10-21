(function (global) {
  'use strict';
  const STORAGE_KEY = 'siraaj.route.v1';
  const VERSION = 1;
  const MAX_AGE_MS = 30 * 60 * 1000;

  function finiteCoordinate(point) {
    return Array.isArray(point) && point.length === 2 &&
      Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])) &&
      Number(point[0]) >= -90 && Number(point[0]) <= 90 &&
      Number(point[1]) >= -180 && Number(point[1]) <= 180;
  }

  function normalizeRoute(route) {
    if (!route || route.is_connected !== true || !Array.isArray(route.path) || route.path.length < 2 ||
        !Array.isArray(route.coordinates) || route.coordinates.length < 2 ||
        route.path.length !== route.coordinates.length || route.coordinates.some((point) => !finiteCoordinate(point))) return null;
    const path = route.path.map(String);
    if (path.some((code, index) => !code || (index > 0 && code === path[index - 1]))) return null;
    return {
      path,
      coordinates: route.coordinates.map((point) => [Number(point[0]), Number(point[1])]),
      is_connected: true,
      estimated_minutes: Number.isFinite(Number(route.estimated_minutes)) ? Number(route.estimated_minutes) : null,
      preference: route.preference || null,
      notes: Array.isArray(route.notes) ? route.notes.map(String) : [],
      provenance: route.provenance || 'local_corridor_records',
      coverage: route.coverage || 'verified_walking',
      geometry_quality: route.geometry_quality || 'zone_corridor_planning',
      route_data_version: route.route_data_version || 'v1',
    };
  }

  function normalize(state) {
    if (!state || state.version !== VERSION) return null;
    const alternatives = {};
    Object.entries(state.alternatives || {}).forEach(([key, value]) => {
      const normalized = normalizeRoute(value);
      if (normalized) alternatives[key] = normalized;
    });
    const selectedRoute = normalizeRoute(state.selectedRoute);
    const externalDirectionsUrl = typeof state.externalDirectionsUrl === 'string' && state.externalDirectionsUrl.startsWith('https://www.google.com/maps/dir/') ? state.externalDirectionsUrl : null;
    if (!selectedRoute && Object.keys(alternatives).length === 0 && !(state.routeStatus === 'external_directions' && externalDirectionsUrl)) return null;
    return {
      version: VERSION,
      selectedPreference: state.selectedPreference || selectedRoute?.preference || Object.keys(alternatives)[0] || null,
      selectedRoute: selectedRoute || alternatives[state.selectedPreference] || null,
      alternatives,
      originZone: state.originZone ? String(state.originZone) : null,
      destinationZone: state.destinationZone ? String(state.destinationZone) : null,
      routeStatus: state.routeStatus || 'available',
      coverage: state.coverage || selectedRoute?.coverage || 'verified_walking',
      geometryQuality: state.geometryQuality || selectedRoute?.geometry_quality || 'zone_corridor_planning',
      provenance: state.provenance || selectedRoute?.provenance || 'local_corridor_records',
      freshness: state.freshness || null,
      generatedAt: state.generatedAt || new Date().toISOString(),
      externalDirectionsUrl,
      destinationCoordinates: Array.isArray(state.destinationCoordinates) && finiteCoordinate(state.destinationCoordinates) ? state.destinationCoordinates.map(Number) : null,
    };
  }

  function publish(state, persist = true) {
    const normalized = normalize(state);
    if (!normalized) { clear(false); return null; }
    if (persist) {
      try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(normalized)); } catch (_) { /* storage is optional */ }
    }
    document.dispatchEvent(new CustomEvent('hajjguard:route-updated', { detail: normalized }));
    return normalized;
  }

  function read() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const state = normalize(JSON.parse(raw));
      if (!state || Date.now() - Date.parse(state.generatedAt) > MAX_AGE_MS) { sessionStorage.removeItem(STORAGE_KEY); return null; }
      return state;
    } catch (_) { try { sessionStorage.removeItem(STORAGE_KEY); } catch (__) {} return null; }
  }

  function clear(dispatch = true) {
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (_) { /* storage is optional */ }
    if (dispatch) document.dispatchEvent(new CustomEvent('hajjguard:route-updated', { detail: null }));
  }

  global.SiraajRouteState = { VERSION, normalizeRoute, normalize, publish, read, clear };
})(window);
