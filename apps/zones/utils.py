import math
from typing import Optional

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees).
    
    Resilient against:
    - Identical coordinates (returns 0.0 without precision loss)
    - Extreme lat/lon boundary conditions
    - Floating-point domain errors in sqrt(1 - a)
    """
    # Quick return for identical coordinates
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    # Ensure valid coordinate bounds
    lat1 = max(-90.0, min(90.0, float(lat1)))
    lat2 = max(-90.0, min(90.0, float(lat2)))
    lon1 = max(-180.0, min(180.0, float(lon1)))
    lon2 = max(-180.0, min(180.0, float(lon2)))

    R = 6371000.0  # Earth mean radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    sin_half_dphi = math.sin(delta_phi / 2.0)
    sin_half_dlambda = math.sin(delta_lambda / 2.0)

    a = (sin_half_dphi * sin_half_dphi) + \
        math.cos(phi1) * math.cos(phi2) * (sin_half_dlambda * sin_half_dlambda)

    # Clamp 'a' strictly to [0.0, 1.0] to eliminate floating-point crashes
    a = max(0.0, min(1.0, a))
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    return R * c

def haversine_distance_3d(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    alt1: float = 0.0, alt2: float = 0.0,
    floor1: int = 0, floor2: int = 0,
    vertical_gamma: float = 3.5,
    floor_penalty_meters: float = 45.0
) -> float:
    """
    Computes 3D spatial distance incorporating altitude differential and vertical floor penalties:
    D_3D = sqrt(D_horizontal^2 + (gamma * delta_h)^2) + omega_floor * |delta_Floor|
    
    Parameters:
    - gamma (default 3.5): Physiological walking impedance multiplier on ramps/stairs.
    - omega_floor (default 45.0m): Fixed equivalent pedestrian cost for vertical transitions (escalator/stairway queues).
    """
    d_horiz = haversine_distance(lat1, lon1, lat2, lon2)
    delta_h = abs(float(alt2 or 0.0) - float(alt1 or 0.0))
    floor_diff = abs(int(floor2 or 0) - int(floor1 or 0))

    d_3d = math.sqrt((d_horiz * d_horiz) + ((vertical_gamma * delta_h) ** 2))
    return round(d_3d + (floor_penalty_meters * floor_diff), 2)

def altitude_from_barometric_pressure(
    pressure_hpa: float,
    baseline_pressure_hpa: float = 1013.25,
    temp_c: float = 35.0
) -> float:
    """
    Computes relative altitude above ground baseline using the hypsometric barometric equation:
    delta_h = (R_specific * T_kelvin / g) * ln(P_baseline / P_device)
    
    Returns altitude in meters rounded to 2 decimal places. Clamped to realistic thresholds.
    """
    if pressure_hpa <= 0 or baseline_pressure_hpa <= 0:
        return 0.0

    R_specific = 287.058  # Gas constant for dry air in J/(kg*K)
    g = 9.80665          # Gravitational acceleration in m/s^2
    t_kelvin = max(250.0, min(350.0, temp_c + 273.15))

    delta_h = (R_specific * t_kelvin / g) * math.log(baseline_pressure_hpa / pressure_hpa)
    # Clamp between -50m and +300m for holy sites terrain
    return max(-50.0, min(300.0, round(delta_h, 2)))

def determine_zone_for_point(lat: float, lng: float, floor_level: Optional[int] = None, max_search_radius: float = 500.0):
    """
    Determines the correct Zone for a given GPS coordinate point.
    Multi-level / floor_level aware:
    - In overlapping architectural complexes (e.g. Jamarat Ground, Level 1, Level 2, Level 3; Mataf Ground vs Level 1),
      if floor_level is provided, filters for that specific floor.
    - If inside multiple zones, chooses the one with the matching floor_level, or closest center.
    - If outside all zone radii, assigns to closest zone within max_search_radius (default 500m), else None.
    """
    from zones.models import Zone

    all_zones = list(Zone.objects.all())
    if not all_zones:
        return None

    containing_zones = []
    closest_zone = None
    min_dist = float('inf')

    for z in all_zones:
        dist = haversine_distance(z.center_lat, z.center_lng, lat, lng)
        if dist < min_dist:
            min_dist = dist
            closest_zone = z
        if dist <= z.radius_meters:
            containing_zones.append((z, dist))

    if containing_zones:
        # If floor_level was specified, filter by floor_level
        if floor_level is not None:
            floor_matches = [z for (z, d) in containing_zones if z.floor_level == floor_level]
            if floor_matches:
                return floor_matches[0]

        # Otherwise pick the zone whose center is closest to the pilgrim
        containing_zones.sort(key=lambda x: x[1])
        return containing_zones[0][0]

    # Outside radius: assign to closest if within tolerance (e.g. 500m)
    if min_dist <= max_search_radius:
        # If floor_level specified, check if another zone with that floor is close
        if floor_level is not None:
            floor_zones = [z for z in all_zones if z.floor_level == floor_level]
            if floor_zones:
                floor_zones.sort(key=lambda z: haversine_distance(z.center_lat, z.center_lng, lat, lng))
                best_floor_zone = floor_zones[0]
                if haversine_distance(best_floor_zone.center_lat, best_floor_zone.center_lng, lat, lng) <= max_search_radius:
                    return best_floor_zone
        return closest_zone

    return None
