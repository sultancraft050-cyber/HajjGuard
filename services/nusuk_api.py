import json
import logging
import requests
from typing import Dict, Any, Tuple
from django.conf import settings
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard

logger = logging.getLogger(__name__)

class NusukApiAdapter:
    """
    Adapter for the Ministry of Hajj & Umrah B2B Nusuk Masar API.
    
    Modes:
    1. Sandbox Mode (default): High-fidelity simulation returning complete demographic,
       camp sector, tent number, and Tafweej slot payload.
    2. Live Gateway Mode: Sends authenticated HTTPS requests with strict 5-second timeout
       and resilient handling of 5xx, 4xx, and network connection drops.
    """

    TIMEOUT_SECONDS = 5.0

    @classmethod
    def is_sandbox(cls) -> bool:
        return getattr(settings, 'NUSUK_USE_SANDBOX', True)

    @classmethod
    def get_api_url(cls) -> str:
        return getattr(settings, 'NUSUK_API_BASE_URL', 'https://api.nusuk.sa/v1/masar/pilgrims')

    @classmethod
    def get_api_key(cls) -> str:
        return getattr(settings, 'NUSUK_API_KEY', 'SANDBOX_MOCK_KEY_1448')

    @classmethod
    def query_pilgrim_permit(cls, identifier: str) -> Dict[str, Any]:
        """
        Queries official permit status by tasreeh number or border/national ID.
        """
        identifier = str(identifier).strip()

        if cls.is_sandbox():
            return cls._query_sandbox(identifier)
        return cls._query_live(identifier)

    @classmethod
    def _query_sandbox(cls, identifier: str) -> Dict[str, Any]:
        """
        High-fidelity mock sandbox providing realistic Saudi Hajj Ministry data.
        """
        # Built-in mock dataset
        mock_registry = {
            "1082390192": {
                "tasreeh_no": "TASREEH-1448-9901",
                "border_or_national_id": "1082390192",
                "is_valid": True,
                "demographics": {
                    "first_name": "Rashid",
                    "last_name": "Al-Hashimi",
                    "nationality": "Saudi",
                    "gender": "M",
                    "age": 72,
                    "blood_type": "O+",
                    "chronic_condition": "CARDIAC",
                    "is_wheelchair_user": True,
                    "phone": "+966501234567",
                    "emergency_contact_name": "Dr. Salman (Son)",
                    "emergency_contact_phone": "+966509876543"
                },
                "campaign": {
                    "license_no": "CAMP-SA-1448-08",
                    "name_en": "Al-Nukhba VIP Pilgrimage Services",
                    "name_ar": "شركة النخبة لحجاج الداخل المتميزة",
                    "country": "Saudi Arabia",
                    "category": "PREMIUM",
                    "leader_name": "Sheikh Mansour Al-Zahrani",
                    "leader_phone": "+966551122334"
                },
                "camp": {
                    "assigned_mina_sector": "Sector 3 (Royal Protocol / Jamarat Proximity)",
                    "mina_camp_no": "Camp 44-A",
                    "tent_number": "Tent 12-B",
                    "makkah_hotel": "Clock Royal Towers Makkah (Fairmont)"
                },
                "tafweej": {
                    "tafweej_jamarat_slot": "10 Dhul-Hijjah 09:00 - 10:00 AM",
                    "assigned_jamarat_floor": 2
                }
            },
            "2981023812": {
                "tasreeh_no": "TASREEH-1448-3341",
                "border_or_national_id": "2981023812",
                "is_valid": True,
                "demographics": {
                    "first_name": "Fatima",
                    "last_name": "Noor",
                    "nationality": "Egyptian",
                    "gender": "F",
                    "age": 32,
                    "blood_type": "A+",
                    "chronic_condition": "NONE",
                    "is_wheelchair_user": False,
                    "phone": "+201012345678",
                    "emergency_contact_name": "Tariq Noor (Spouse)",
                    "emergency_contact_phone": "+201098765432"
                },
                "campaign": {
                    "license_no": "CAMP-EG-1448-22",
                    "name_en": "Misr Al-Khair International Hajj Delegation",
                    "name_ar": "حملة مصر الخير لضيوف الرحمن الدولية",
                    "country": "Egypt",
                    "category": "STANDARD",
                    "leader_name": "Ustadh Ahmed El-Sayed",
                    "leader_phone": "+966509988776"
                },
                "camp": {
                    "assigned_mina_sector": "Sector 7 (Central Mina Valley)",
                    "mina_camp_no": "Camp 102",
                    "tent_number": "Tent 45-C",
                    "makkah_hotel": "Makkah Grand Coral Hotel"
                },
                "tafweej": {
                    "tafweej_jamarat_slot": "10 Dhul-Hijjah 02:00 - 03:00 PM",
                    "assigned_jamarat_floor": 3
                }
            }
        }

        # Check by national ID or tasreeh
        for record in mock_registry.values():
            if record["border_or_national_id"] == identifier or record["tasreeh_no"] == identifier:
                return {
                    "success": True,
                    "data": record,
                    "source": "SANDBOX_MOCK",
                    "error": None
                }

        # Dynamic fallback record for testing arbitrary border IDs
        return {
            "success": True,
            "data": {
                "tasreeh_no": f"TASREEH-1448-{identifier[-4:] if len(identifier) >= 4 else '1000'}",
                "border_or_national_id": identifier,
                "is_valid": True,
                "demographics": {
                    "first_name": "Verified",
                    "last_name": "Pilgrim",
                    "nationality": "International",
                    "gender": "M",
                    "age": 40,
                    "blood_type": "B+",
                    "chronic_condition": "NONE",
                    "is_wheelchair_user": False,
                    "phone": "+966500000000",
                    "emergency_contact_name": "Emergency Care",
                    "emergency_contact_phone": "+966500000001"
                },
                "campaign": {
                    "license_no": "CAMP-INTL-1448-99",
                    "name_en": "Standard International Hajj Services",
                    "name_ar": "حملة ضيوف الرحمن الدولية",
                    "country": "International",
                    "category": "STANDARD",
                    "leader_name": "Hajj Guide Officer",
                    "leader_phone": "+966500000002"
                },
                "camp": {
                    "assigned_mina_sector": "Sector 4",
                    "mina_camp_no": "Camp 55",
                    "tent_number": "Tent 10",
                    "makkah_hotel": "Holy Sites Hotel"
                },
                "tafweej": {
                    "tafweej_jamarat_slot": "10 Dhul-Hijjah 11:00 - 12:00 PM",
                    "assigned_jamarat_floor": 1
                }
            },
            "source": "SANDBOX_SYNTHETIC",
            "error": None
        }

    @classmethod
    def _query_live(cls, identifier: str) -> Dict[str, Any]:
        """
        Sends HTTPS request to official Nusuk gateway with 5s timeout and error handling.
        """
        url = f"{cls.get_api_url()}/{identifier}/"
        headers = {
            "Authorization": f"Bearer {cls.get_api_key()}",
            "Accept": "application/json",
            "User-Agent": "HajjGuard-OS/2.0"
        }

        try:
            response = requests.get(url, headers=headers, timeout=cls.TIMEOUT_SECONDS)

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "source": "LIVE_NUSUK_GATEWAY",
                    "error": None
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "data": None,
                    "source": "LIVE_NUSUK_GATEWAY",
                    "error_code": "NOT_FOUND",
                    "error": f"No valid permit found in Nusuk database for ID {identifier}."
                }
            elif 500 <= response.status_code < 600:
                logger.error(f"Nusuk upstream server error {response.status_code} on {identifier}")
                return {
                    "success": False,
                    "data": None,
                    "source": "LIVE_NUSUK_GATEWAY",
                    "error_code": "UPSTREAM_5XX",
                    "error": "Ministry of Hajj upstream server temporarily unavailable. Please retry."
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "source": "LIVE_NUSUK_GATEWAY",
                    "error_code": f"HTTP_{response.status_code}",
                    "error": f"Unexpected response from Nusuk gateway: HTTP {response.status_code}"
                }
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout querying Nusuk API for {identifier} after {cls.TIMEOUT_SECONDS}s")
            return {
                "success": False,
                "data": None,
                "source": "LIVE_NUSUK_GATEWAY",
                "error_code": "TIMEOUT",
                "error": f"Nusuk API connection timed out after {cls.TIMEOUT_SECONDS}s. Operating in offline contingency mode."
            }
        except requests.exceptions.RequestException as exc:
            logger.error(f"Network error querying Nusuk API: {exc}")
            return {
                "success": False,
                "data": None,
                "source": "LIVE_NUSUK_GATEWAY",
                "error_code": "NETWORK_ERROR",
                "error": f"Network communication error with Nusuk gateway: {str(exc)}"
            }

    @classmethod
    def sync_pilgrim_data(cls, user: User, permit_identifier: str) -> Tuple[bool, str]:
        """
        Fetches official Nusuk data and syncs to PilgrimProfile, HajjCampaign, and NusukCard.
        """
        res = cls.query_pilgrim_permit(permit_identifier)
        if not res["success"]:
            return False, res.get("error", "Unknown Nusuk sync failure")

        data = res["data"]
        demo = data["demographics"]
        camp_info = data["campaign"]
        taf = data["tafweej"]

        # 1. Update/Create PilgrimProfile
        profile, _ = PilgrimProfile.objects.get_or_create(user=user)
        user.first_name = demo.get("first_name", user.first_name)
        user.last_name = demo.get("last_name", user.last_name)
        user.save()

        profile.age = demo.get("age", profile.age)
        profile.gender = demo.get("gender", profile.gender)
        profile.blood_type = demo.get("blood_type", profile.blood_type)
        profile.chronic_condition = demo.get("chronic_condition", profile.chronic_condition)
        profile.is_wheelchair_user = demo.get("is_wheelchair_user", profile.is_wheelchair_user)
        profile.phone = demo.get("phone", profile.phone)
        profile.emergency_contact_name = demo.get("emergency_contact_name", profile.emergency_contact_name)
        profile.emergency_contact_phone = demo.get("emergency_contact_phone", profile.emergency_contact_phone)
        profile.save()

        # 2. Update/Create Campaign
        campaign, _ = HajjCampaign.objects.get_or_create(
            license_no=camp_info["license_no"],
            defaults={
                "name_ar": camp_info.get("name_ar", camp_info["name_en"]),
                "name_en": camp_info["name_en"],
                "country": camp_info.get("country", "Saudi Arabia"),
                "category": camp_info.get("category", "STANDARD"),
                "assigned_mina_sector": data["camp"].get("assigned_mina_sector", "Sector 3"),
                "mina_camp_no": data["camp"].get("mina_camp_no", "Camp 44"),
                "makkah_hotel": data["camp"].get("makkah_hotel", ""),
                "leader_name": camp_info.get("leader_name", "Campaign Leader"),
                "leader_phone": camp_info.get("leader_phone", "+966500000000"),
                "join_code": camp_info["license_no"][-6:]
            }
        )

        # 3. Update/Create NusukCard
        card, created = NusukCard.objects.get_or_create(
            pilgrim=profile,
            defaults={
                "campaign": campaign,
                "tasreeh_no": data["tasreeh_no"],
                "border_or_national_id": data["border_or_national_id"],
                "tafweej_jamarat_slot": taf.get("tafweej_jamarat_slot", "10 Dhul-Hijjah"),
                "assigned_jamarat_floor": taf.get("assigned_jamarat_floor", 2),
                "is_valid": data.get("is_valid", True)
            }
        )
        if not created:
            card.campaign = campaign
            card.tasreeh_no = data["tasreeh_no"]
            card.border_or_national_id = data["border_or_national_id"]
            card.tafweej_jamarat_slot = taf.get("tafweej_jamarat_slot", card.tafweej_jamarat_slot)
            card.assigned_jamarat_floor = taf.get("assigned_jamarat_floor", card.assigned_jamarat_floor)
            card.is_valid = data.get("is_valid", card.is_valid)
            card.generate_qr_payload()
            card.save()

        from nusuk.services import NusukService
        NusukService.generate_nusuk_qr(card)
        card.save()

        return True, f"Successfully synced official Nusuk permit {card.tasreeh_no}"
