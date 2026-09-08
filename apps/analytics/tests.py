from django.test import TestCase, Client
from django.urls import reverse
from zones.models import Zone, Corridor, DensityRecord
from analytics.services import RoutingEngine, CrowdSimulator, PredictiveForecaster

class AnalyticsAndRoutingTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create origin zone (Mina Camp Sector 3)
        self.mina_sec3 = Zone.objects.create(
            code='Z-MINA-SEC3',
            name_ar='مشعر منى قطاع 3',
            name_en='Mina Sector 3',
            site_type='MINA',
            center_lat=21.41700,
            center_lng=39.89100,
            safe_capacity=45000,
            floor_area_sqm=50000
        )

        # Create destination zone 1: Jamarat Ground Level
        self.jamarat_f0 = Zone.objects.create(
            code='Z-JAMARAT-F0',
            name_ar='الجمرات الدور الأرضي',
            name_en='Jamarat Ground Floor',
            site_type='JAMARAT',
            center_lat=21.41980,
            center_lng=39.87150,
            safe_capacity=30000,
            floor_area_sqm=12000
        )

        # Create destination zone 2: Jamarat 3rd Floor (Bypass option)
        self.jamarat_f3 = Zone.objects.create(
            code='Z-JAMARAT-F3',
            name_ar='الجمرات الدور الثالث',
            name_en='Jamarat 3rd Floor',
            site_type='JAMARAT',
            center_lat=21.41980,
            center_lng=39.87150,
            safe_capacity=30000,
            floor_area_sqm=12000
        )

        # Create Corridor 1: King Fahd Way (Direct to Ground Level, 25 mins)
        self.corridor_f0 = Corridor.objects.create(
            from_zone=self.mina_sec3,
            to_zone=self.jamarat_f0,
            name_ar='طريق الملك فهد',
            name_en='King Fahd Way',
            base_walking_minutes=25.0
        )

        # Create Corridor 2: Al-Muaisem Tunnel (Bypass to 3rd Floor, 20 mins)
        self.corridor_f3 = Corridor.objects.create(
            from_zone=self.mina_sec3,
            to_zone=self.jamarat_f3,
            name_ar='نفق المعيصم',
            name_en='Al-Muaisem Tunnel',
            base_walking_minutes=20.0
        )

        # Initial normal densities
        DensityRecord.objects.create(
            zone=self.jamarat_f0,
            total_people=7500,
            density_per_sqm=0.62,
            predicted_density_20m=0.70,
            status='GREEN'
        )
        DensityRecord.objects.create(
            zone=self.jamarat_f3,
            total_people=6000,
            density_per_sqm=0.50,
            predicted_density_20m=0.55,
            status='GREEN'
        )

    def test_api_trigger_surge_and_reset(self):
        # Trigger surge
        res = self.client.post(reverse('analytics:api_trigger_surge'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['new_status'], 'RED')

        # Check DB state
        rec = self.jamarat_f0.density_records.first()
        self.assertEqual(rec.status, 'RED')
        self.assertGreater(rec.total_people, self.jamarat_f0.safe_capacity)

        # Reset crowd
        res_reset = self.client.post(reverse('analytics:api_reset_crowd'))
        self.assertEqual(res_reset.status_code, 200)
        rec_after = self.jamarat_f0.density_records.first()
        self.assertEqual(rec_after.status, 'GREEN')

    def test_predictive_forecaster(self):
        forecast = PredictiveForecaster.forecast_zone(self.jamarat_f0)
        self.assertIsInstance(forecast, float)
        self.assertGreaterEqual(forecast, 0.0)

    def test_routing_engine_comparison(self):
        # When Jamarat F0 is surged to RED
        CrowdSimulator.trigger_jamarat_morning_surge()
        comparison = RoutingEngine.get_route_comparison('Z-MINA-SEC3', 'Z-JAMARAT-F0')
        self.assertTrue(comparison['target_is_congested'])
        self.assertIn('baseline', comparison)
        self.assertIn('congestion_aware', comparison)

