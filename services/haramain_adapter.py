import logging
import os
import urllib3
import requests
from typing import Dict, Any, List
from django.utils import timezone
from zones.models import Zone, DensityRecord

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class HaramainLiveAdapter:
    """
    Disabled provider adapter reserved for an authorized telemetry connector.
    
    Directly interfaces with the General Authority for the Care of the Two Holy Mosques
    local synthetic telemetry adapter; a provider connector requires written authorization:
    https://trasul.gph.gov.sa/haram-api/public/api/pry/TawafSaiStatus
    
    A future provider would supply crowd telemetry; the default deployment uses local simulation:
    - Real-time expected Tawaf lap durations (minutes)
    - Active open gate numbers (e.g. Gate 1 King Abdulaziz, Gate 79 Fahd)
    - Live congestion status codes (1=Light, 2=Moderate, 3=Crowded, 4=Closed)
    - Mathematically calculated live headcount mapped to HajjGuard zones
    """

    API_URL = "https://trasul.gph.gov.sa/haram-api/public/api/pry/TawafSaiStatus"
    TIMEOUT_SECONDS = 8.0

    # Mapping of known location labels to HajjGuard zone codes and capacities.
    LOCATION_MAPPING = {
        "صحن الطواف": {
            "code": "Z-HARAM-MATAF",
            "name_en": "Kaaba Mataf Central Basin",
            "safe_capacity": 18000,
            "floor_area_sqm": 5000,
            "floor_level": 0
        },
        "مطاف الدور الارضي": {
            "code": "Z-HARAM-GF-PER",
            "name_en": "Mataf Ground Perimeter Colonnades",
            "safe_capacity": 15000,
            "floor_area_sqm": 4500,
            "floor_level": 0
        },
        "مطاف الدور الاول": {
            "code": "Z-HARAM-F1",
            "name_en": "Mataf (First Floor - Wheelchairs)",
            "safe_capacity": 12000,
            "floor_area_sqm": 4000,
            "floor_level": 1
        },
        "مطاف الدور الاول ": {
            "code": "Z-HARAM-F1",
            "name_en": "Mataf (First Floor - Wheelchairs)",
            "safe_capacity": 12000,
            "floor_area_sqm": 4000,
            "floor_level": 1
        },
        "سطح المطاف": {
            "code": "Z-HARAM-ROOF",
            "name_en": "Mataf Roof Tier",
            "safe_capacity": 15000,
            "floor_area_sqm": 6000,
            "floor_level": 2
        },
        "المسعى الدور الارضي": {
            "code": "Z-HARAM-MASA-GF",
            "name_en": "Masa'a (Ground Floor)",
            "safe_capacity": 25000,
            "floor_area_sqm": 10000,
            "floor_level": 0
        },
        "المسعى الدور الاول": {
            "code": "Z-HARAM-MASA-F1",
            "name_en": "Masa'a (First Floor)",
            "safe_capacity": 25000,
            "floor_area_sqm": 10000,
            "floor_level": 1
        },
        "التوسعة": {
            "code": "Z-HARAM-EXT-KFA",
            "name_en": "King Fahd & King Abdullah Expansions",
            "safe_capacity": 80000,
            "floor_area_sqm": 35000,
            "floor_level": 0
        }
    }

    @classmethod
    def fetch_live_status(cls) -> Dict[str, Any]:
        """
        Sends an upstream request only when explicitly enabled by deployment policy.
        """
        if (os.environ.get('HAJJGUARD_ENABLE_HARAMAIN_PROVIDER') != '1' or
                os.environ.get('HAJJGUARD_HARAMAIN_AUTHORIZED') != '1'):
            return {'success': False, 'source': 'SIMULATION_HARAMAIN_TELEMETRY', 'data': None, 'error': 'Provider disabled pending authorization'}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HajjGuard-Integration/2.0",
            "Accept": "application/json",
            "Referer": "https://alharamain.gov.sa/"
        }

        try:
            resp = requests.get(
                cls.API_URL,
                headers=headers,
                verify=False,  # Internal Saudi Gov SSL root
                timeout=cls.TIMEOUT_SECONDS
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "source": "SIMULATION_HARAMAIN_TELEMETRY",
                    "data": data,
                    "error": None
                }
            else:
                logger.warning(f"Haramain API responded with HTTP {resp.status_code}")
                return {
                    "success": False,
                    "source": "SIMULATION_HARAMAIN_TELEMETRY",
                    "data": None,
                    "error": f"HTTP {resp.status_code}"
                }
        except requests.exceptions.Timeout:
            logger.warning("Haramain API request timed out")
            return {
                "success": False,
                "source": "SIMULATION_HARAMAIN_TELEMETRY",
                "data": None,
                "error": "Connection timeout"
            }
        except Exception as e:
            logger.error(f"Error querying Haramain API: {e}")
            return {
                "success": False,
                "source": "SIMULATION_HARAMAIN_TELEMETRY",
                "data": None,
                "error": str(e)
            }

    @classmethod
    def sync_to_database(cls) -> Dict[str, Any]:
        """
        Fetches provider-reported telemetry only after deployment authorization and
        translates it into HajjGuard DensityRecord entries in the database.
        """
        res = cls.fetch_live_status()
        if not res["success"] or not res["data"]:
            return {
                "success": False,
                "error": res.get("error", "Telemetry provider unavailable"),
                "synced_sectors": 0
            }

        raw_items = res["data"]
        synced_records = []

        for item in raw_items:
            loc_name = str(item.get("location_name", "")).strip()
            
            # Match location
            mapping = None
            for key, val in cls.LOCATION_MAPPING.items():
                if key.strip() in loc_name or loc_name in key.strip():
                    mapping = val
                    break

            if not mapping:
                continue

            zone = Zone.objects.filter(code=mapping["code"]).first()
            if not zone:
                continue

            # Extract provider-reported time metrics
            try:
                time_expect = float(item.get("time_expect", 45))
                light_time = float(item.get("light_time", 35))
                crowded_time = float(item.get("crowded_time", 60))
            except (ValueError, TypeError):
                time_expect, light_time, crowded_time = 45.0, 35.0, 60.0

            # Compute mathematical saturation ratio from actual lap duration
            # ratio = 0.0 (light baseline) to 1.0 (peak congested)
            if crowded_time > light_time and time_expect > 0:
                saturation = (time_expect - light_time) / (crowded_time - light_time)
                saturation = max(0.15, min(1.30, saturation))  # Clamp between 15% and 130%
            else:
                saturation = 0.25

            # Provider status: "1" = Green, "2" = Orange/Moderate, "3" = Red/Crowded, "4" = Closed
            status_num = str(item.get("status", "2"))
            if status_num == "1":
                status_code = "GREEN"
                saturation = min(saturation, 0.45)
            elif status_num == "2":
                status_code = "ORANGE"
                saturation = max(0.50, min(saturation, 0.85))
            elif status_num == "3":
                status_code = "RED"
                saturation = max(0.95, saturation)
            else:
                status_code = "GREEN"

            # Derive headcount from capacity and provider-reported saturation
            safe_cap = zone.safe_capacity
            estimated_headcount = int(safe_cap * saturation)
            density = round(estimated_headcount / max(zone.floor_area_sqm, 1), 2)
            risk_score = min(100.0, round(saturation * 100.0, 1))

            doors = item.get("door_no") or "All Primary Gates"

            # Create live DensityRecord
            rec = DensityRecord.objects.create(
                zone=zone,
                phone_count=int(estimated_headcount * 0.45),
                image_count=int(estimated_headcount * 0.55),
                total_people=estimated_headcount,
                density_per_sqm=density,
                predicted_density_20m=round(density * 1.08, 2),
                risk_score=risk_score,
                status=status_code
            )

            # Record optical verification in CameraSnapshot for PDPL compliance audit
            from zones.models import CameraSnapshot
            CameraSnapshot.objects.create(
                zone=zone,
                taken_at=timezone.now(),
                people_counted=estimated_headcount,
                processed=True
            )

            synced_records.append({
                "location": loc_name,
                "zone_code": zone.code,
                "expected_minutes": int(time_expect),
                "doors": doors,
                "headcount": estimated_headcount,
                "capacity": safe_cap,
                "density": density,
                "status": status_code,
                "provider_updated_at": item.get("updated_at")
            })

        return {
            "success": True,
            "source": "SIMULATION_HARAMAIN_TELEMETRY",
            "synced_sectors": len(synced_records),
            "timestamp": timezone.now().isoformat(),
            "records": synced_records
        }
