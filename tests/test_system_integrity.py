import os
import json
import tempfile
from datetime import datetime, timezone as dt_timezone, timedelta
from unittest.mock import patch, MagicMock

import requests
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import IntegrityError

from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard
from zones.models import Zone, Corridor, LocationPing, DensityRecord
from zones.utils import haversine_distance, determine_zone_for_point, haversine_distance_3d, altitude_from_barometric_pressure
from groups.models import PilgrimGroup, GroupMembership
from groups.services import GroupDriftService
from safety.models import SosIncident
from services.prediction import (
    predict_zone_density_20min,
    calculate_normalized_congestion_index,
    calculate_prayer_surge_factor
)
from services.routing import RoutingEngine
from services.cctv import CctvPersonCounter
from services.nusuk_api import NusukApiAdapter


class HajjGuardSystemIntegrityTests(TestCase):
    """
    End-to-End System Integrity and Robustness Test Suite for HajjGuard.
    Covers all 5 core stages of operational safety, algorithms, security, and data integrity.
    """

    def setUp(self):
        self.client = Client()

        # Base User & Profile for testing
        self.user = User.objects.create_user(
            username="test_pilgrim",
            first_name="Ahmad",
            last_name="Al-Ghamdi",
            email="ahmad@hajjguard.sa"
        )
        self.profile = PilgrimProfile.objects.create(
            user=self.user,
            role="pilgrim",
            phone="+966551234567",
            age=45,
            gender="M",
            blood_type="O+",
            chronic_condition="NONE",
            emergency_contact_name="Faisal Al-Ghamdi",
            emergency_contact_phone="+966559876543"
        )

        # Base Campaign
        self.campaign = HajjCampaign.objects.create(
            license_no="CAMP-TEST-1448-01",
            name_ar="حملة الاختبار الرسمية",
            name_en="Official Test Campaign",
            country="Saudi Arabia",
            category="STANDARD",
            assigned_mina_sector="Sector 3",
            mina_camp_no="Camp 12",
            leader_name="Sheikh Abdullah",
            leader_phone="+966550001122",
            join_code="TEST01"
        )

        # Base Zones
        self.zone_jamarat_f0 = Zone.objects.create(
            code="TEST-JAM-F0",
            name_ar="الجمرات الطابق الأرضي",
            name_en="Jamarat Ground Floor",
            site_type="JAMARAT",
            center_lat=21.4198,
            center_lng=39.8715,
            radius_meters=80.0,
            floor_level=0,
            floor_area_sqm=5000.0,
            safe_capacity=10000
        )
        self.zone_jamarat_f2 = Zone.objects.create(
            code="TEST-JAM-F2",
            name_ar="الجمرات الطابق الثاني",
            name_en="Jamarat Second Floor",
            site_type="JAMARAT",
            center_lat=21.4198,
            center_lng=39.8715,
            radius_meters=80.0,
            floor_level=2,
            floor_area_sqm=5000.0,
            safe_capacity=10000
        )
        self.zone_mina_camp = Zone.objects.create(
            code="TEST-MINA-SEC3",
            name_ar="مخيم منى قطاع 3",
            name_en="Mina Sector 3 Camps",
            site_type="MINA",
            center_lat=21.4150,
            center_lng=39.8800,
            radius_meters=150.0,
            floor_level=0,
            floor_area_sqm=12000.0,
            safe_capacity=15000
        )

    # =========================================================================
    # STAGE 1 & 3: Nusuk Sync Workflow & API Adapter Resilience
    # =========================================================================

    def test_nusuk_sandbox_sync_workflow(self):
        """
        Verifies the complete Nusuk sync pipeline:
        Query mock sandbox -> update PilgrimProfile -> create/link Campaign -> issue NusukCard & QR.
        """
        sync_user = User.objects.create_user(username="sync_test_user")
        success, message = NusukApiAdapter.sync_pilgrim_data(sync_user, "1082390192")

        self.assertTrue(success, f"Nusuk sync failed with message: {message}")
        
        # Verify Profile updated with demographics
        profile = PilgrimProfile.objects.get(user=sync_user)
        self.assertEqual(profile.age, 72)
        self.assertEqual(profile.chronic_condition, "CARDIAC")
        self.assertTrue(profile.is_wheelchair_user)
        self.assertTrue(profile.is_vulnerable())
        self.assertEqual(sync_user.first_name, "Rashid")
        self.assertEqual(sync_user.last_name, "Al-Hashimi")

        # Verify Campaign linked
        card = NusukCard.objects.get(pilgrim=profile)
        self.assertEqual(card.border_or_national_id, "1082390192")
        self.assertEqual(card.tasreeh_no, "TASREEH-1448-9901")
        self.assertEqual(card.campaign.license_no, "CAMP-SA-1448-08")
        self.assertEqual(card.assigned_jamarat_floor, 2)
        self.assertTrue(card.is_valid)

        # Verify QR payload is populated and valid JSON
        self.assertTrue(bool(card.qr_payload))
        qr_data = json.loads(card.qr_payload)
        self.assertEqual(qr_data["type"], "NUSUK_SMART_CARD")
        self.assertEqual(qr_data["tasreeh_no"], "TASREEH-1448-9901")
        self.assertTrue(qr_data["is_vulnerable"])

    def test_nusuk_live_gateway_resilience_and_timeouts(self):
        """
        Tests live Nusuk gateway error handling:
        Catches timeouts, 5xx server errors, and returns clean structured error dictionaries.
        """
        with patch.object(NusukApiAdapter, 'is_sandbox', return_value=False):
            # 1. Test timeout handling
            with patch('requests.get', side_effect=requests.exceptions.Timeout("Connection timeout")):
                res = NusukApiAdapter.query_pilgrim_permit("9999999999")
                self.assertFalse(res["success"])
                self.assertEqual(res["error_code"], "TIMEOUT")
                self.assertIn("offline contingency", res["error"])

            # 2. Test 503 upstream error handling
            mock_503 = MagicMock()
            mock_503.status_code = 503
            with patch('requests.get', return_value=mock_503):
                res = NusukApiAdapter.query_pilgrim_permit("9999999999")
                self.assertFalse(res["success"])
                self.assertEqual(res["error_code"], "UPSTREAM_5XX")
                self.assertIn("upstream server temporarily unavailable", res["error"])

    # =========================================================================
    # STAGE 1 & 2: Group Management, Collision Resilience & Drift Tracking
    # =========================================================================

    def test_group_creation_and_join_code_generation(self):
        """
        Tests creation of PilgrimGroup, ensuring join code generation is automatic,
        non-empty, uppercase, and indexed.
        """
        group = PilgrimGroup.objects.create(
            name="Al-Ghamdi Family",
            campaign=self.campaign,
            leader=self.profile
        )
        self.assertIsNotNone(group.join_code)
        self.assertGreaterEqual(len(group.join_code), 4)
        self.assertEqual(group.join_code, group.join_code.upper())

    def test_group_join_code_collision_retry_and_auto_expansion(self):
        """
        Verifies that when join codes collide, the retry loop regenerates and
        expands the code length after max attempts without entering an infinite loop.
        """
        # Pre-seed existing code
        existing_code = "AAAA"
        PilgrimGroup.objects.create(
            name="Existing Group",
            campaign=self.campaign,
            leader=self.profile,
            join_code=existing_code
        )

        mock_candidates = ["AAAA"] * 6 + ["BBBBB"]
        call_count = [0]

        def fake_token_hex(num_bytes):
            idx = min(call_count[0], len(mock_candidates) - 1)
            call_count[0] += 1
            return mock_candidates[idx]

        with patch('secrets.token_hex', side_effect=fake_token_hex):
            # max_attempts=5 -> after 5 collisions of "AAAA", attempts expand length and returns "BBBBB"
            code = PilgrimGroup.generate_join_code(length=4, max_attempts=5)
            self.assertEqual(code, "BBBBB")

    def test_group_membership_unique_constraint(self):
        """
        Ensures a pilgrim cannot be added to the same group multiple times.
        """
        group = PilgrimGroup.objects.create(
            name="Unique Test Group",
            campaign=self.campaign,
            leader=self.profile
        )
        GroupMembership.objects.create(group=group, pilgrim=self.profile, role="MEMBER")
        
        with self.assertRaises(IntegrityError):
            GroupMembership.objects.create(group=group, pilgrim=self.profile, role="DEPUTY")

    def test_group_drift_service_metrics(self):
        """
        Tests GroupDriftService:
        1. Member separated > 50m triggers 'DRIFTING'.
        2. Member with no ping for > 10m triggers 'SIGNAL_LOST'.
        3. Member close to leader is marked 'SAFE'.
        """
        # Create leader and 3 members
        leader_profile = self.profile
        user_safe = User.objects.create_user("safe_user")
        profile_safe = PilgrimProfile.objects.create(user=user_safe, role="pilgrim")

        user_drift = User.objects.create_user("drift_user")
        profile_drift = PilgrimProfile.objects.create(user=user_drift, role="pilgrim")

        user_silent = User.objects.create_user("silent_user")
        profile_silent = PilgrimProfile.objects.create(user=user_silent, role="pilgrim")

        group = PilgrimGroup.objects.create(
            name="Tawaf Group",
            campaign=self.campaign,
            leader=leader_profile
        )
        GroupMembership.objects.create(group=group, pilgrim=profile_safe, role="MEMBER")
        GroupMembership.objects.create(group=group, pilgrim=profile_drift, role="MEMBER")
        GroupMembership.objects.create(group=group, pilgrim=profile_silent, role="MEMBER")

        now = timezone.now()

        # Leader ping at Kaaba center
        LocationPing.objects.create(pilgrim=leader_profile, lat=21.42250, lng=39.82620, timestamp=now)

        # Safe member 10 meters away (~0.00009 deg)
        LocationPing.objects.create(pilgrim=profile_safe, lat=21.42255, lng=39.82620, timestamp=now)

        # Drifting member 120 meters away (~0.0011 deg north)
        LocationPing.objects.create(pilgrim=profile_drift, lat=21.42360, lng=39.82620, timestamp=now)

        # Silent member with ping 15 minutes ago (> 10m threshold)
        LocationPing.objects.create(
            pilgrim=profile_silent,
            lat=21.42250,
            lng=39.82620,
            timestamp=now - timedelta(minutes=15)
        )

        res = GroupDriftService.calculate_group_drift(group)

        self.assertEqual(res["total_monitored_members"], 3)
        self.assertEqual(res["safe_count"], 1)
        self.assertEqual(res["drifting_count"], 1)
        self.assertEqual(res["silent_count"], 1)
        self.assertTrue(res["has_alerts"])

        # Check member statuses
        statuses = {m["name"]: m["status"] for m in res["members"]}
        self.assertEqual(statuses["safe_user"], "SAFE")
        self.assertEqual(statuses["drift_user"], "DRIFTING")
        self.assertEqual(statuses["silent_user"], "SIGNAL_LOST")

    # =========================================================================
    # STAGE 2: Mathematical Safety & Predictive Forecasting
    # =========================================================================

    def test_haversine_formula_floating_point_safety(self):
        """
        Tests haversine_distance corner cases:
        1. Identical coordinates return 0.0 immediately.
        2. Clamping ensures math.sqrt(1 - a) never crashes with ValueError on float rounding.
        """
        # Identical points
        dist_zero = haversine_distance(21.4225, 39.8262, 21.4225, 39.8262)
        self.assertEqual(dist_zero, 0.0)

        # Normal distance test (Mina to Jamarat ~1.0 km)
        dist = haversine_distance(21.4150, 39.8800, 21.4198, 39.8715)
        self.assertGreater(dist, 900.0)
        self.assertLess(dist, 1300.0)

    def test_predictive_crowd_density_fallbacks_and_safety(self):
        """
        Tests predict_zone_density_20min:
        - Graceful fallback for 0 or 1 records (no ValueError / ZeroDivisionError).
        - Non-negative clamping for declining trends.
        - Correct positive extrapolation for rising trends.
        """
        # 1. Edge Case: 0 records
        pred_empty = predict_zone_density_20min([])
        self.assertEqual(pred_empty, 0.5)

        # 2. Edge Case: 1 record
        pred_single = predict_zone_density_20min([1.8])
        self.assertEqual(pred_single, 1.8)

        # 3. Upward trend: [1.0, 1.3, 1.6, 1.9, 2.2]
        pred_upward = predict_zone_density_20min([1.0, 1.3, 1.6, 1.9, 2.2])
        self.assertGreater(pred_upward, 2.2)

        # 4. Sharply falling trend clamped at >= 0.0
        pred_downward = predict_zone_density_20min([3.0, 2.0, 1.0, 0.2])
        self.assertGreaterEqual(pred_downward, 0.0)

    # =========================================================================
    # STAGE 2: Dynamic Routing Engine (NetworkX DiGraph & Disconnected Fallback)
    # =========================================================================

    def test_routing_engine_dynamic_congestion_reroute(self):
        """
        Tests NetworkX DiGraph dynamic rerouting:
        When a direct corridor's destination zone is congested (RED), the engine
        applies an exponential penalty and routes via an alternate bypass corridor.
        """
        # Create 3 zones: Start, Congested Mid, Detour Mid, Target
        z_start = Zone.objects.create(code="Z-START", name_ar="البداية", name_en="Start", site_type="MINA", center_lat=21.41, center_lng=39.87, safe_capacity=1000)
        z_congested = Zone.objects.create(code="Z-CONGESTED", name_ar="ممر مزدحم", name_en="Congested Path", site_type="JAMARAT", center_lat=21.42, center_lng=39.87, safe_capacity=500)
        z_clear = Zone.objects.create(code="Z-CLEAR", name_ar="ممر بديل", name_en="Clear Path", site_type="JAMARAT", center_lat=21.42, center_lng=39.88, safe_capacity=5000)
        z_target = Zone.objects.create(code="Z-TARGET", name_ar="الهدف", name_en="Target", site_type="JAMARAT", center_lat=21.43, center_lng=39.87, safe_capacity=5000)

        # Create corridors:
        # Path 1 (Shortest direct baseline): Start -> Congested -> Target (base time: 5 + 5 = 10 mins)
        Corridor.objects.create(from_zone=z_start, to_zone=z_congested, name_en="Direct 1", name_ar="مباشر 1", base_walking_minutes=5.0)
        Corridor.objects.create(from_zone=z_congested, to_zone=z_target, name_en="Direct 2", name_ar="مباشر 2", base_walking_minutes=5.0)

        # Path 2 (Slightly longer bypass): Start -> Clear -> Target (base time: 8 + 6 = 14 mins)
        Corridor.objects.create(from_zone=z_start, to_zone=z_clear, name_en="Bypass 1", name_ar="بديل 1", base_walking_minutes=8.0)
        Corridor.objects.create(from_zone=z_clear, to_zone=z_target, name_en="Bypass 2", name_ar="بديل 2", base_walking_minutes=6.0)

        # Mark z_congested as heavily congested (120% capacity -> RED)
        DensityRecord.objects.create(zone=z_congested, total_people=600, density_per_sqm=4.5, status="RED", risk_score=85.0)

        # Mark z_clear as normal (10% capacity -> GREEN)
        DensityRecord.objects.create(zone=z_clear, total_people=200, density_per_sqm=0.5, status="GREEN", risk_score=10.0)

        # Compare baseline vs congestion-aware routing
        comparison = RoutingEngine.get_route_comparison("Z-START", "Z-TARGET")

        self.assertEqual(comparison["baseline"]["path"], ["Z-START", "Z-CONGESTED", "Z-TARGET"])
        self.assertEqual(comparison["congestion_aware"]["path"], ["Z-START", "Z-CLEAR", "Z-TARGET"])
        self.assertTrue(comparison["is_rerouted"])

    def test_routing_engine_disconnected_fallback(self):
        """
        Verifies that when two zones have no valid corridor path, find_path_safe
        returns a structured fallback result with straight-line estimate without throwing NetworkXNoPath.
        """
        z_isolated = Zone.objects.create(
            code="Z-ISOLATED",
            name_ar="معزول",
            name_en="Isolated Zone",
            site_type="ARAFAT",
            center_lat=21.35,
            center_lng=39.98,
            safe_capacity=1000
        )
        G = RoutingEngine.build_graph(congestion_penalty=True)
        res = RoutingEngine.find_path_safe(G, "TEST-MINA-SEC3", "Z-ISOLATED")

        self.assertFalse(res["is_connected"])
        self.assertIsNotNone(res["estimated_minutes"])
        self.assertIn("TEST-MINA-SEC3", res["path"])
        self.assertIn("Z-ISOLATED", res["path"])

    # =========================================================================
    # STAGE 2: CCTV Video Processing & Saudi PDPL Deletion Guarantee
    # =========================================================================

    def test_cctv_image_deletion_on_success(self):
        """
        Verifies that surveillance frames processed for headcount are deleted
        immediately in the finally: block to comply with Saudi Personal Data Protection Law.
        """
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
            tf.write(b"SIMULATED_CCTV_IMAGE_DATA_123456789")
            temp_path = tf.name

        self.assertTrue(os.path.exists(temp_path))

        res = CctvPersonCounter.process_frame(temp_path, zone_code="TEST-JAM-F0")
        self.assertTrue(res["success"])
        self.assertGreater(res["headcount"], 0)

        # Verify image was purged from storage
        self.assertFalse(os.path.exists(temp_path), "PDPL Violation: CCTV frame was not unlinked on success!")

    def test_cctv_image_deletion_on_exception(self):
        """
        Verifies that even if the vision inference model throws an unhandled exception,
        the CCTV frame is STILL deleted in the finally: block.
        """
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
            tf.write(b"SIMULATED_CCTV_CRASH_IMAGE_DATA")
            temp_path = tf.name

        self.assertTrue(os.path.exists(temp_path))

        with patch('os.path.getsize', side_effect=RuntimeError("Simulated GPU inference crash")):
            res = CctvPersonCounter.process_frame(temp_path, zone_code="TEST-JAM-F0")
            self.assertFalse(res["success"])
            self.assertIn("Simulated GPU inference crash", res["error"])

        # Verify image was purged despite the runtime crash
        self.assertFalse(os.path.exists(temp_path), "PDPL Violation: CCTV frame was not unlinked on exception!")

    # =========================================================================
    # STAGE 3: SOS Incident Lifecycle & Queue Management
    # =========================================================================

    def test_sos_incident_trigger_and_resolution_lifecycle(self):
        """
        Tests end-to-end SOS emergency workflow:
        1. Pilgrim triggers SOS via API -> Incident created in OPEN status.
        2. Operations dashboard lists active incident.
        3. Dispatcher marks resolved -> Status updated to RESOLVED with timestamp.
        4. Dashboard active incidents counter decrements.
        """
        # 1. Trigger SOS
        payload = {
            "category": "HEAT",
            "lat": 21.4198,
            "lng": 39.8715,
            "called_number": "997"
        }
        res = self.client.post(
            "/safety/api/trigger-sos/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        incident_id = data["incident_id"]

        # Verify DB entry
        incident = SosIncident.objects.get(id=incident_id)
        self.assertEqual(incident.category, "HEAT")
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.zone, self.zone_jamarat_f0)

        # 2. Check operations dashboard
        dash_res = self.client.get("/safety/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        self.assertGreaterEqual(dash_res.context["active_incidents_count"], 1)

        # 3. Resolve Incident
        resolve_res = self.client.post(f"/safety/api/resolve/{incident_id}/")
        self.assertEqual(resolve_res.status_code, 200)

        incident.refresh_from_db()
        self.assertEqual(incident.status, "RESOLVED")
        self.assertIsNotNone(incident.resolved_at)

    # =========================================================================
    # STAGE 3: Telemetry Ingestion Hardening, Anti-Spoofing & Throttling
    # =========================================================================

    def test_telemetry_ping_valid_ingestion_and_zone_resolution(self):
        """
        Tests valid mobile telemetry ping:
        Resolves correct zone, floor level, and records LocationPing.
        """
        payload = {
            "lat": 21.4198,
            "lng": 39.8715,
            "floor_level": 2,
            "altitude": 32.5,
            "pilgrim_id": self.profile.user.username
        }
        res = self.client.post(
            "/api/telemetry/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["zone_code"], "TEST-JAM-F2")  # Multi-level floor 2 prioritized
        self.assertEqual(data["floor_level"], 2)

    def test_telemetry_ping_coordinate_bounds_validation(self):
        """
        Ensures coordinates outside [-90..90, -180..180] are rejected with HTTP 400.
        """
        payload = {
            "lat": 121.4198,  # Invalid latitude
            "lng": 39.8715
        }
        res = self.client.post(
            "/api/telemetry/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("out of physical bounds", res.json()["message"])

    def test_telemetry_ping_anti_spoofing_future_timestamp(self):
        """
        Rejects telemetry pings with timestamps set more than 60 seconds into the future.
        """
        future_ts = (datetime.now(dt_timezone.utc) + timedelta(minutes=5)).isoformat()
        payload = {
            "lat": 21.4198,
            "lng": 39.8715,
            "timestamp": future_ts
        }
        res = self.client.post(
            "/api/telemetry/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Spoofed telemetry timestamp", res.json()["message"])

    def test_telemetry_ping_rate_limiting_429(self):
        """
        Enforces 3-second minimum throttle between mobile telemetry pings.
        Second ping sent immediately returns HTTP 429.
        """
        # Create a dedicated pilgrim to avoid collision with other tests
        throttle_user = User.objects.create_user("throttle_pilgrim")
        throttle_profile = PilgrimProfile.objects.create(user=throttle_user, role="pilgrim")

        payload = {
            "lat": 21.4150,
            "lng": 39.8800,
            "pilgrim_id": throttle_user.username
        }

        # First ping -> 200 OK
        res1 = self.client.post(
            "/api/telemetry/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res1.status_code, 200)

        # Immediate second ping -> 429 Too Many Requests
        res2 = self.client.post(
            "/api/telemetry/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res2.status_code, 429)
        data = res2.json()
        self.assertEqual(data["status"], "throttled")
        self.assertIn("Rate limit exceeded", data["message"])

    # =========================================================================
    # STAGE 6: Real-World Saudi Haramain SCADA Ingestion
    # =========================================================================

    def test_haramain_live_adapter_sync(self):
        """
        Tests the real-world Haramain authority SCADA ingestion adapter.
        Verifies live data extraction, expected lap times, and density record updates.
        """
        from services.haramain_adapter import HaramainLiveAdapter

        mock_payload = [
            {
                "id": 1,
                "location_name": "صحن الطواف",
                "time_expect": "45",
                "light_time": "35",
                "crowded_time": "60",
                "status": "2",
                "door_no": "1 -3 -5 -19 - 40 - 79",
                "updated_at": "2026-09-20T13:03:51.000000Z"
            }
        ]

        with patch.object(HaramainLiveAdapter, 'fetch_live_status', return_value={"success": True, "data": mock_payload}):
            # Set up test zone matching code
            Zone.objects.get_or_create(
                code="Z-HARAM-MATAF",
                defaults={
                    "name_ar": "صحن المطاف",
                    "name_en": "Kaaba Mataf",
                    "safe_capacity": 18000,
                    "floor_area_sqm": 5000,
                    "center_lat": 21.4225,
                    "center_lng": 39.8262
                }
            )
            res = HaramainLiveAdapter.sync_to_database()
            self.assertTrue(res["success"])
            self.assertGreaterEqual(res["synced_sectors"], 1)

            # Verify DensityRecord created
            rec = DensityRecord.objects.filter(zone__code="Z-HARAM-MATAF").first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.status, "ORANGE")
            self.assertGreater(rec.total_people, 5000)

    def test_haramain_live_sync_api_endpoint(self):
        """
        Tests the POST /safety/api/sync-haramain/ endpoint.
        """
        from services.haramain_adapter import HaramainLiveAdapter
        with patch.object(HaramainLiveAdapter, 'sync_to_database', return_value={"success": True, "synced_sectors": 6}):
            res = self.client.post("/safety/api/sync-haramain/")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["synced_sectors"], 6)

    def test_3d_spatial_distance_and_barometric_altitude(self):
        """
        Tests 3D spatial distance weighting and barometric altitude calculation.
        """
        d_horiz = haversine_distance(21.4198, 39.8715, 21.4200, 39.8720)
        
        # Test 3D with 9 meters elevation difference (Floor 0 to Floor 2)
        d_3d = haversine_distance_3d(
            21.4198, 39.8715, 21.4200, 39.8720,
            alt1=0.0, alt2=9.0, floor1=0, floor2=2
        )
        # Should be strictly greater due to (gamma * delta_h) and (omega_floor * 2)
        self.assertGreater(d_3d, d_horiz + 80.0)

        # Test barometric hypsometric formula
        alt_ground = altitude_from_barometric_pressure(1013.25, baseline_pressure_hpa=1013.25)
        self.assertEqual(alt_ground, 0.0)

        # Level 2 drop of 1.2 hPa
        alt_upper = altitude_from_barometric_pressure(1012.05, baseline_pressure_hpa=1013.25)
        self.assertGreater(alt_upper, 9.0)
        self.assertLess(alt_upper, 12.0)

    def test_normalized_congestion_index_composite_function(self):
        """
        Tests the Normalized Congestion Index (NCI) formulation.
        """
        DensityRecord.objects.create(
            zone=self.zone_jamarat_f0,
            total_people=8500,
            density_per_sqm=1.7,
            predicted_density_20m=2.1,
            status='ORANGE'
        )
        res = calculate_normalized_congestion_index(
            self.zone_jamarat_f0,
            ambient_temp_c=42.0,
            solar_irradiance_w_sqm=950.0
        )
        self.assertIn('nci', res)
        self.assertIn('level', res)
        self.assertIn('status', res)
        self.assertGreaterEqual(res['nci'], 0.0)
        self.assertLessEqual(res['nci'], 1.0)
        self.assertIn(res['status'], ['GREEN', 'ORANGE', 'RED'])

        # Test prayer surge calculation
        dhuhr_time = datetime(2026, 9, 21, 12, 20, tzinfo=dt_timezone.utc)
        surge_at_prayer = calculate_prayer_surge_factor(dhuhr_time)
        self.assertGreaterEqual(surge_at_prayer, 0.95)

        night_time = datetime(2026, 9, 21, 2, 30, tzinfo=dt_timezone.utc)
        surge_at_night = calculate_prayer_surge_factor(night_time)
        self.assertLess(surge_at_night, 0.10)

    def test_viscous_shockwave_dampened_routing_and_stochastic_logit(self):
        """
        Tests viscous shockwave dampening edge weights and stochastic logit multi-path choice.
        """
        G = RoutingEngine.build_graph(congestion_penalty=True)
        self.assertIn("TEST-JAM-F0", G)
        self.assertIn("TEST-JAM-F2", G)

        # Check stochastic multi-path logit assignment
        paths = RoutingEngine.find_k_shortest_paths_stochastic(G, "TEST-JAM-F0", "TEST-MINA-SEC3", k=3)
        self.assertIsInstance(paths, list)
        if paths:
            total_prob = sum(p['assignment_probability'] for p in paths)
            self.assertAlmostEqual(total_prob, 1.0, places=1)
            for p in paths:
                self.assertIn('cost_minutes', p)
                self.assertIn('assignment_probability', p)

    def test_group_drift_dispersion_centroid_and_entropy(self):
        """
        Tests group spatial centroid and cohesion entropy calculations in GroupDriftService.
        """
        group = PilgrimGroup.objects.create(
            name="Al-Noor Family",
            campaign=self.campaign,
            leader=self.profile,
            join_code="NOOR44"
        )
        member_user = User.objects.create_user(username="member_noor", first_name="Fatima")
        member_profile = PilgrimProfile.objects.create(user=member_user, role="pilgrim")
        GroupMembership.objects.create(group=group, pilgrim=member_profile, role="MEMBER")

        LocationPing.objects.create(
            pilgrim=self.profile,
            lat=21.4150,
            lng=39.8800,
            zone=self.zone_mina_camp
        )
        LocationPing.objects.create(
            pilgrim=member_profile,
            lat=21.4152,
            lng=39.8802,
            zone=self.zone_mina_camp
        )

        res = GroupDriftService.calculate_group_drift(group)
        self.assertIn('centroid', res)
        self.assertIn('dispersion_radius_meters', res)
        self.assertIn('is_group_scattered', res)
        self.assertIsNotNone(res['centroid']['lat'])
        self.assertIsNotNone(res['centroid']['lng'])
        self.assertGreater(res['dispersion_radius_meters'], 0.0)
        self.assertFalse(res['is_group_scattered'])

    def test_adaptive_telemetry_engine_and_backoff(self):
        """
        Tests adaptive telemetry envelope with dynamic interval, jitter, and barometric altitude.
        """
        payload = {
            "lat": 21.4198,
            "lng": 39.8715,
            "pressure_hpa": 1011.5,
            "pilgrim_id": self.profile.id
        }
        res = self.client.post(
            "/zones/api/ping/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("adaptive_telemetry", data)
        self.assertIn("recommended_interval_seconds", data["adaptive_telemetry"])
        self.assertIn("jitter_pct", data["adaptive_telemetry"])
        self.assertEqual(data["adaptive_telemetry"]["jitter_pct"], 20.0)

    def test_adversarial_sos_flooding_defense_and_plausibility(self):
        """
        Tests rate-limiting / deduplication of repeated SOS pings and spatial plausibility.
        """
        payload1 = {
            "category": "MEDICAL",
            "lat": 21.4198,
            "lng": 39.8715,
            "battery_level": 4,
            "called_number": "997"
        }
        res1 = self.client.post("/safety/api/trigger-sos/", data=json.dumps(payload1), content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["status"], "success")
        incident_id = data1["incident_id"]

        inc = SosIncident.objects.get(id=incident_id)
        self.assertIn("LAST-GASP", inc.notes)

        payload2 = {
            "category": "MEDICAL",
            "lat": 21.4202,
            "lng": 39.8718,
            "battery_level": 3,
            "called_number": "997"
        }
        res2 = self.client.post("/safety/api/trigger-sos/", data=json.dumps(payload2), content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "updated")
        self.assertEqual(data2["incident_id"], incident_id)

        count = SosIncident.objects.filter(pilgrim=self.profile, status='OPEN').count()
        self.assertEqual(count, 1)

