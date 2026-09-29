import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from zones.models import Zone, DensityRecord

class ZonesLiveMapTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test zone (Jamarat)
        self.zone = Zone.objects.create(
            code='Z-JAMARAT-TEST',
            name_ar='جمرات تجريبي',
            name_en='Jamarat Test',
            site_type='JAMARAT',
            center_lat=21.41980,
            center_lng=39.87150,
            radius_meters=100.0,
            floor_level=2,
            safe_capacity=1000,
            floor_area_sqm=500
        )
        DensityRecord.objects.create(
            zone=self.zone,
            total_people=450,
            density_per_sqm=0.9,
            predicted_density_20m=1.0,
            risk_score=25.0,
            status='GREEN'
        )

        # Create test pilgrim user
        self.user = User.objects.create_user(username='testpilgrim', password='password123')
        self.profile = PilgrimProfile.objects.create(user=self.user, role='pilgrim')
        self.client.force_login(self.user)

    def test_live_map_renders(self):
        response = self.client.get(reverse('zones:live_map'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hajj-map')

    def test_api_zones_status(self):
        response = self.client.get(reverse('zones:api_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['zones'][0]['code'], 'Z-JAMARAT-TEST')

    def test_api_location_ping_matches_zone(self):
        payload = {
            'lat': 21.41982,  # Inside the test zone
            'lng': 39.87152
        }
        response = self.client.post(
            reverse('zones:api_ping'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['zone_code'], 'Z-JAMARAT-TEST')

