import logging
import urllib.request
import json
from datetime import datetime
import zoneinfo

logger = logging.getLogger(__name__)

MAKKAH_TZ = zoneinfo.ZoneInfo("Asia/Riyadh")

# In-memory cache to prevent excessive API calls
_weather_cache = {
    'timestamp': None,
    'data': None
}
CACHE_TTL_SECONDS = 600  # 10 minutes

def get_live_makkah_weather() -> dict:
    """
    Fetches real-time live meteorological telemetry for Al-Masjid Al-Haram, Makkah
    Coordinates: 21.4225 N, 39.8262 E (Kaaba Basin)
    Timezone: Asia/Riyadh (UTC+3)
    """
    global _weather_cache
    now_makkah = datetime.now(MAKKAH_TZ)

    # Check cache freshness
    if _weather_cache['timestamp'] and _weather_cache['data']:
        elapsed = (datetime.now() - _weather_cache['timestamp']).total_seconds()
        if elapsed < CACHE_TTL_SECONDS:
            data = dict(_weather_cache['data'])
            data['makkah_time_12'] = now_makkah.strftime('%I:%M:%S %p')
            data['makkah_time_hm'] = now_makkah.strftime('%I:%M %p')
            data['makkah_date'] = now_makkah.strftime('%d %B %Y')
            return data

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=21.4225&longitude=39.8262"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,surface_pressure"
        "&timezone=Asia%2FRiyadh"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HajjGuard-WeatherService/2.0'})
        with urllib.request.urlopen(req, timeout=4.0) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            curr = res_json.get('current', {})

            temp_c = round(float(curr.get('temperature_2m', 34.0)), 1)
            feels_like_c = round(float(curr.get('apparent_temperature', temp_c)), 1)
            humidity_pct = int(curr.get('relative_humidity_2m', 45))
            is_day = int(curr.get('is_day', 0))
            pressure_hpa = round(float(curr.get('surface_pressure', 980.0)), 1)

            payload = {
                'success': True,
                'temperature': round(temp_c),
                'temperature_exact': temp_c,
                'feels_like': round(feels_like_c),
                'feels_like_exact': feels_like_c,
                'humidity': humidity_pct,
                'is_day': is_day,
                'pressure_hpa': pressure_hpa,
                'timezone': 'AST (UTC+3)',
                'makkah_time_12': now_makkah.strftime('%I:%M:%S %p'),
                'makkah_time_hm': now_makkah.strftime('%I:%M %p'),
                'makkah_time_24': now_makkah.strftime('%H:%M'),
                'makkah_date': now_makkah.strftime('%d %B %Y'),
                'condition_ar': 'أجواء ليلية معتدلة' if not is_day else 'أجواء حارة مشمسة',
                'condition_en': 'Clear Night Sky' if not is_day else 'Hot Sunny Day',
            }

            _weather_cache['timestamp'] = datetime.now()
            _weather_cache['data'] = payload
            return payload

    except Exception as err:
        logger.warning(f"Live Makkah weather API unavailable, applying astronomical fallback: {err}")
        # Dynamic diurnal fallback based on actual Makkah hour
        hour = now_makkah.hour
        # Diurnal curve for Makkah in September: low ~32-34C at 05:00, peak ~41-43C at 14:00
        if 0 <= hour < 7:
            fb_temp = 33.5
        elif 7 <= hour < 11:
            fb_temp = 37.0
        elif 11 <= hour < 17:
            fb_temp = 42.0
        elif 17 <= hour < 21:
            fb_temp = 38.0
        else:
            fb_temp = 34.5

        return {
            'success': False,
            'temperature': round(fb_temp),
            'temperature_exact': fb_temp,
            'feels_like': round(fb_temp + 2.0),
            'feels_like_exact': fb_temp + 2.0,
            'humidity': 45 if hour < 7 else 30,
            'is_day': 1 if (6 <= hour <= 18) else 0,
            'pressure_hpa': 980.0,
            'timezone': 'AST (UTC+3)',
            'makkah_time_12': now_makkah.strftime('%I:%M:%S %p'),
            'makkah_time_hm': now_makkah.strftime('%I:%M %p'),
            'makkah_time_24': now_makkah.strftime('%H:%M'),
            'makkah_date': now_makkah.strftime('%d %B %Y'),
            'condition_ar': 'أجواء ليلية معتدلة' if (hour < 6 or hour > 18) else 'أجواء نهارية',
            'condition_en': 'Clear Night Sky' if (hour < 6 or hour > 18) else 'Sunny Day',
        }
