import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from zones.models import Zone, Corridor, DensityRecord, CameraSnapshot
from safety.models import Alert
from services.sectional_telemetry import HaramSectionalEngine
from services.routing import RoutingEngine


class SectionalHeadcountTests(TestCase):
    """
    Automated test suite verifying the 7-Section Precision Headcount Architecture
    and Sectional Gate Balance & 3D Spatial Telemetry for Al-Masjid Al-Haram.
    
    Verifies:
    1. Architectural section specifications (Mataf L0/Perimeter/F1/Roof, Masa'a L0/F1, Expansion).
    2. Conservation of Crowd Flow continuity equation: ΔN = (Inflow - Outflow) * Δt.
    3. Optical Point-Regression (FIDTM) auto-calibration when discrepancy > 5%.
    4. Closed-loop Choke Point Divert Trigger at critical density (>= 3.5 p/m²).
    5. Multi-tier detour routing away from congested Mataf floor to upper levels.
    6. Sectional API endpoints (/safety/api/haram-sectional-status/ and simulation).
    7. Saudi PDPL Article 16 compliance (non-biometric telemetry records).
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='telemetry_admin', password='password123')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        from accounts.models import PilgrimProfile
        PilgrimProfile.objects.create(user=self.user, role='operator')

        # Seed all 7 physical sections
        self.sections = {}
        for code, meta in HaramSectionalEngine.SECTIONS_METADATA.items():
            zone, _ = Zone.objects.get_or_create(
                code=code,
                defaults={
                    'name_en': meta['name_en'],
                    'name_ar': meta['name_ar'],
                    'site_type': 'HARAM',
                    'center_lat': 21.42250,
                    'center_lng': 39.82620,
                    'safe_capacity': meta['safe_capacity'],
                    'floor_area_sqm': meta['floor_area_sqm'],
                    'floor_level': meta['floor_level'],
                }
            )
            self.sections[code] = zone

        # Create inter-tier corridors for routing verification
        self.c1 = Corridor.objects.create(
            name_en="Colonnade to Mataf Basin Ramp",
            name_ar="منحدر الرواق إلى صحن المطاف",
            from_zone=self.sections['Z-HARAM-GF-PER'],
            to_zone=self.sections['Z-HARAM-MATAF'],
            base_walking_minutes=2.0,
            width_meters=8.0,
            is_active=True
        )
        self.c2 = Corridor.objects.create(
            name_en="Colonnade to First Floor Escalator",
            name_ar="سلالم الرواق إلى الدور الأول",
            from_zone=self.sections['Z-HARAM-GF-PER'],
            to_zone=self.sections['Z-HARAM-F1'],
            base_walking_minutes=3.0,
            width_meters=6.0,
            is_active=True
        )
        self.c3 = Corridor.objects.create(
            name_en="First Floor to Roof Skybridge",
            name_ar="جسر الدور الأول إلى السطح",
            from_zone=self.sections['Z-HARAM-F1'],
            to_zone=self.sections['Z-HARAM-ROOF'],
            base_walking_minutes=4.0,
            width_meters=7.0,
            is_active=True
        )

    def test_all_seven_haram_sections_metadata(self):
        """Test 1: Verify all 7 Haram architectural sections are registered with exact capacities & areas."""
        expected_sections = [
            'Z-HARAM-MATAF',
            'Z-HARAM-GF-PER',
            'Z-HARAM-F1',
            'Z-HARAM-ROOF',
            'Z-HARAM-MASA-GF',
            'Z-HARAM-MASA-F1',
            'Z-HARAM-EXT-KFA'
        ]
        self.assertEqual(len(HaramSectionalEngine.SECTIONS_METADATA), 7)
        for code in expected_sections:
            self.assertIn(code, self.sections)
            zone = self.sections[code]
            meta = HaramSectionalEngine.SECTIONS_METADATA[code]
            self.assertEqual(zone.site_type, 'HARAM')
            self.assertEqual(zone.safe_capacity, meta['safe_capacity'])
            self.assertEqual(zone.floor_area_sqm, meta['floor_area_sqm'])
            self.assertEqual(zone.floor_level, meta['floor_level'])

    def test_conservation_of_crowd_flow_positive_net(self):
        """Test 2a: Test Conservation of Flow with net inflow: ΔN = (Inflow - Outflow) * Δt."""
        zone = self.sections['Z-HARAM-MATAF']
        now = timezone.now()
        DensityRecord.objects.create(
            zone=zone,
            timestamp=now,
            phone_count=2100,
            image_count=2900,
            total_people=5000,
            density_per_sqm=1.0,
            status='GREEN'
        )

        # Inflow = 1,200/min, Outflow = 800/min, Net = +400/min, Δt = 2.0 min => ΔN = +800
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=1200,
            outflow_per_min=800,
            dt_minutes=2.0
        )

        expected_count = 5000 + 800
        self.assertEqual(res['headcount'], expected_count)
        self.assertEqual(res['net_flow_per_min'], 400)
        expected_density = round(expected_count / zone.floor_area_sqm, 2)
        self.assertEqual(res['density_sqm'], expected_density)
        self.assertFalse(res['calibration_applied'])

    def test_conservation_of_crowd_flow_negative_net(self):
        """Test 2b: Test Conservation of Flow with net outflow reducing headcount."""
        zone = self.sections['Z-HARAM-MATAF']
        now = timezone.now()
        DensityRecord.objects.create(
            zone=zone,
            timestamp=now,
            phone_count=3000,
            image_count=4000,
            total_people=7000,
            density_per_sqm=1.4,
            status='GREEN'
        )

        # Inflow = 600/min, Outflow = 1,100/min, Net = -500/min, Δt = 1.0 min => ΔN = -500
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=600,
            outflow_per_min=1100,
            dt_minutes=1.0
        )

        expected_count = 7000 - 500
        self.assertEqual(res['headcount'], expected_count)
        self.assertEqual(res['net_flow_per_min'], -500)

    def test_optical_discrepancy_calibration_triggered(self):
        """Test 3a: Discrepancy > 5% triggers auto-calibration to optical ground truth."""
        zone = self.sections['Z-HARAM-MATAF']
        now = timezone.now()
        DensityRecord.objects.create(
            zone=zone,
            timestamp=now,
            phone_count=4000,
            image_count=6000,
            total_people=10000,
            density_per_sqm=2.0,
            status='ORANGE'
        )

        # Inflow 1000, Outflow 1000 => Integrated = 10000
        # Optical FIDTM ground truth = 11,500 (Discrepancy = 15% > 5%)
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=1000,
            outflow_per_min=1000,
            dt_minutes=1.0,
            optical_verify_count=11500
        )

        self.assertTrue(res['calibration_applied'])
        self.assertEqual(res['headcount'], 11500)
        self.assertEqual(res['discrepancy_pct'], 15.0)

    def test_optical_discrepancy_calibration_not_triggered_when_within_tolerance(self):
        """Test 3b: Discrepancy <= 5% preserves integrated gate count without forced calibration."""
        zone = self.sections['Z-HARAM-MATAF']
        now = timezone.now()
        DensityRecord.objects.create(
            zone=zone,
            timestamp=now,
            phone_count=4000,
            image_count=6000,
            total_people=10000,
            density_per_sqm=2.0,
            status='ORANGE'
        )

        # Integrated = 10000. Optical = 10200 (Discrepancy = 2.0% <= 5%)
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=1000,
            outflow_per_min=1000,
            dt_minutes=1.0,
            optical_verify_count=10200
        )

        self.assertFalse(res['calibration_applied'])
        self.assertEqual(res['headcount'], 10000)
        self.assertEqual(res['discrepancy_pct'], 2.0)

    def test_choke_point_divert_trigger_at_3_5_density(self):
        """Test 4: Density >= 3.5 p/m² triggers RED status, divert flag, and high severity Alert."""
        zone = self.sections['Z-HARAM-MATAF']
        now = timezone.now()
        # Area = 5,000 sqm. Headcount = 17,500 => Density = 3.5 p/m²
        DensityRecord.objects.create(
            zone=zone,
            timestamp=now,
            phone_count=7000,
            image_count=10000,
            total_people=17000,
            density_per_sqm=3.4,
            status='ORANGE'
        )

        # Inflow 1500, Outflow 1000, dt=1 => Count = 17,500 (Density 3.5 p/m²)
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=1500,
            outflow_per_min=1000,
            dt_minutes=1.0
        )

        self.assertEqual(res['status_code'], 'RED')
        self.assertTrue(res['divert_active'])
        self.assertGreaterEqual(res['density_sqm'], 3.5)

        # Check Alert creation
        alert = Alert.objects.filter(zone=zone, severity='HIGH', alert_type='CROWD_SURGE').first()
        self.assertIsNotNone(alert)
        self.assertIn("Multi-tier diversion activated", alert.message_en)

    def test_multi_tier_routing_rerouting_to_upper_tier(self):
        """Test 5: Congestion-aware routing diverts pilgrims to Level 1 when Mataf Basin is RED."""
        mataf = self.sections['Z-HARAM-MATAF']
        f1 = self.sections['Z-HARAM-F1']
        now = timezone.now()

        # Mark Mataf as RED (3.6 p/m²)
        DensityRecord.objects.create(
            zone=mataf,
            timestamp=now,
            total_people=18000,
            density_per_sqm=3.6,
            status='RED'
        )

        # Mark First Floor as GREEN (1.0 p/m²)
        DensityRecord.objects.create(
            zone=f1,
            timestamp=now,
            total_people=4000,
            density_per_sqm=1.0,
            status='GREEN'
        )

        route_comp = RoutingEngine.get_route_comparison(
            from_zone_code='Z-HARAM-GF-PER',
            to_zone_code='Z-HARAM-MATAF'
        )

        self.assertTrue(route_comp['is_rerouted'])
        self.assertTrue(route_comp['target_is_congested'])
        self.assertIn('Z-HARAM-F1', route_comp['congestion_aware']['path'])

    def test_api_haram_sectional_status_matrix(self):
        """Test 6a: GET /safety/api/haram-sectional-status/ returns 200 with all 7 sections."""
        response = self.client.get('/safety/api/haram-sectional-status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['total_sections'], 7)
        self.assertIn('not measured', data['accuracy_rating'])
        
        section_codes = [s['code'] for s in data['sections']]
        self.assertEqual(len(section_codes), 7)
        for code in HaramSectionalEngine.SECTIONS_METADATA.keys():
            self.assertIn(code, section_codes)

        # Verify attributes on first section
        first = data['sections'][0]
        self.assertIn('headcount', first)
        self.assertIn('safe_capacity', first)
        self.assertIn('density_sqm', first)
        self.assertIn('inflow_per_min', first)
        self.assertIn('outflow_per_min', first)
        self.assertIn('accuracy_badge', first)

    def test_api_simulate_section_gate_flow(self):
        """Test 6b: POST /safety/api/simulate-section-gate-flow/ executes flow balance integration."""
        payload = {
            'section_code': 'Z-HARAM-MATAF',
            'inflow': 1500,
            'outflow': 900,
            'dt_minutes': 1.0,
            'optical_verify': 12000
        }
        response = self.client.post(
            '/safety/api/simulate-section-gate-flow/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'success')
        res_data = data['data']
        self.assertEqual(res_data['section_code'], 'Z-HARAM-MATAF')
        self.assertIn('headcount', res_data)
        self.assertIn('density_sqm', res_data)
        self.assertIn('status_code', res_data)

    def test_pdpl_compliance_non_biometric_data(self):
        """Test 7: Verify telemetry and snapshots store only statistical counts, adhering to PDPL Article 16."""
        res = HaramSectionalEngine.compute_conservation_of_flow(
            section_code='Z-HARAM-MATAF',
            inflow_per_min=1000,
            outflow_per_min=900,
            dt_minutes=1.0
        )

        rec = DensityRecord.objects.filter(zone=self.sections['Z-HARAM-MATAF']).first()
        self.assertIsNotNone(rec)
        # Verify aggregate statistical fields only
        self.assertIsInstance(rec.total_people, int)
        self.assertIsInstance(rec.phone_count, int)
        self.assertIsInstance(rec.image_count, int)

        snapshot = CameraSnapshot.objects.filter(zone=self.sections['Z-HARAM-MATAF']).first()
        self.assertIsNotNone(snapshot)
        self.assertIsInstance(snapshot.people_counted, int)
        # Ensure no biometric vector or face bounding box attributes exist on model
        self.assertFalse(hasattr(snapshot, 'face_vector'))
        self.assertFalse(hasattr(snapshot, 'biometric_id'))
