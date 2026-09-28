import numpy as np
from sklearn.linear_model import LinearRegression

def predict_zone_density_20min(zone_or_records) -> float:
    """
    scikit-learn linear forecasting engine for Hajj crowd density.
    Predicts pedestrian density (people / sqm) 20 minutes ahead.
    
    Robustness guarantees:
    - If fewer than 2 density points exist, falls back cleanly to current density
      without raising ValueError, ZeroDivisionError, or any unhandled exception.
    - Extrapolations are strictly clamped to non-negative floats (y_hat >= 0.0),
      preventing unphysical negative densities.
    """
    if hasattr(zone_or_records, 'density_records'):
        # It's a Zone model instance
        records = list(zone_or_records.density_records.order_by('timestamp')[:12])
    elif isinstance(zone_or_records, (list, tuple)):
        records = list(zone_or_records)
    else:
        return 0.5

    # Edge Case: Fewer than 2 points recorded
    if len(records) < 2:
        if len(records) == 1:
            current_val = getattr(records[0], 'density_per_sqm', None)
            if current_val is None and isinstance(records[0], (int, float)):
                current_val = float(records[0])
            return max(0.0, round(float(current_val or 0.5), 2))
        return 0.5

    # Extract densities
    densities = []
    for r in records:
        if hasattr(r, 'density_per_sqm'):
            densities.append(float(r.density_per_sqm))
        elif isinstance(r, (int, float)):
            densities.append(float(r))
        else:
            densities.append(0.5)

    if len(densities) < 2:
        return max(0.0, round(float(densities[0] if densities else 0.5), 2))

    X = np.arange(len(densities)).reshape(-1, 1)
    y = np.array(densities, dtype=float)

    try:
        model = LinearRegression()
        model.fit(X, y)

        # Predict 4 steps ahead (+20 minutes assuming 5-minute telemetry intervals)
        future_step = np.array([[len(densities) + 4]])
        prediction = model.predict(future_step)[0]

        # Enforce non-negative constraint
        return max(0.0, round(float(prediction), 2))
    except Exception:
        # Fallback to last recorded point if regression fails
        return max(0.0, round(float(densities[-1]), 2))


class PredictiveForecaster:
    """Class wrapper for backward compatibility with analytics.services"""
    @staticmethod
    def forecast_zone(zone):
        return predict_zone_density_20min(zone)


def calculate_prayer_surge_factor(target_dt=None) -> float:
    """
    Computes circadian prayer-time crowd surge coefficient P_surge(t) in [0.0, 1.0]
    using Gaussian dispersion around Makkah Adhan/Iqamah windows (sigma = 20 minutes):
    P_surge(t) = max_k exp(-(t - t_prayer,k)^2 / (2 * sigma^2))
    """
    import math
    from datetime import datetime, time
    from django.utils import timezone

    if target_dt is None:
        target_dt = timezone.now()

    # Canonical prayer minute-of-day offsets in Makkah (UTC+3)
    # Fajr ~ 05:05 (305m), Dhuhr ~ 12:20 (740m), Asr ~ 15:45 (945m), Maghrib ~ 18:35 (1115m), Isha ~ 20:05 (1205m)
    prayer_minutes = [305, 740, 945, 1115, 1205]
    cur_minute = target_dt.hour * 60 + target_dt.minute

    sigma = 20.0  # 20-minute bell curve spread
    max_surge = 0.0

    for p_min in prayer_minutes:
        diff = abs(cur_minute - p_min)
        # Handle day boundary wrap-around
        diff = min(diff, 1440 - diff)
        surge = math.exp(- (diff ** 2) / (2.0 * (sigma ** 2)))
        if surge > max_surge:
            max_surge = surge

    return round(float(max_surge), 3)


def calculate_normalized_congestion_index(
    zone,
    target_dt=None,
    ambient_temp_c: float = 38.0,
    solar_irradiance_w_sqm: float = 800.0,
    rho_max: float = 5.0,
    w_q: float = 0.30,
    w_p: float = 0.35,
    w_h: float = 0.15,
    w_r: float = 0.20
) -> dict:
    """
    Computes Normalized Congestion Index (NCI) in [0.0, 1.0] for a zone:
    NCI(z, t) = clamp(w_q * (Q/C_safe) + w_p * P_surge(t) + w_h * H_solar(t) + w_r * (rho_hat_20m / rho_max), 0.0, 1.0)
    
    Weights default: w_q=0.30, w_p=0.35, w_h=0.15, w_r=0.20 (sum = 1.0).
    """
    from django.utils import timezone
    if target_dt is None:
        target_dt = timezone.now()

    # 1. Nusuk Quota Allocation Ratio: Q(z, t) / C_safe
    from nusuk.models import TafweejSchedule
    active_tafweej = TafweejSchedule.objects.filter(
        target_zone=zone,
        slot_start__lte=target_dt,
        slot_end__gte=target_dt,
        status__in=['SCHEDULED', 'ACTIVE']
    )
    scheduled_quota = sum(s.allocated_pilgrim_count for s in active_tafweej)
    safe_cap = max(1, getattr(zone, 'safe_capacity', 1000))
    quota_ratio = min(1.5, scheduled_quota / safe_cap)

    # 2. Circadian Prayer Surge P_surge(t)
    p_surge = calculate_prayer_surge_factor(target_dt)

    # 3. Solar Radiant Heat Impairment Factor H_solar(t)
    # H_solar(t) = max(0.0, (T_ambient * I_solar - 1200) / 2800)
    heat_product = float(ambient_temp_c) * float(solar_irradiance_w_sqm)
    h_solar = max(0.0, min(1.0, (heat_product - 1200.0) / 2800.0))

    # 4. Trailing Regression Density Ratio
    predicted_rho = predict_zone_density_20min(zone)
    rho_ratio = max(0.0, min(1.5, predicted_rho / max(1.0, rho_max)))

    # Composite Index
    raw_nci = (w_q * quota_ratio) + (w_p * p_surge) + (w_h * h_solar) + (w_r * rho_ratio)
    nci = max(0.0, min(1.0, round(float(raw_nci), 3)))

    # Classification
    if nci >= 0.75:
        level = 'CRITICAL'
        status = 'RED'
    elif nci >= 0.45:
        level = 'ELEVATED'
        status = 'ORANGE'
    else:
        level = 'OPTIMAL'
        status = 'GREEN'

    return {
        'nci': nci,
        'level': level,
        'status': status,
        'components': {
            'quota_ratio': round(quota_ratio, 3),
            'prayer_surge': round(p_surge, 3),
            'solar_heat_factor': round(h_solar, 3),
            'predicted_density_ratio': round(rho_ratio, 3)
        }
    }

