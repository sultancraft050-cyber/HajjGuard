import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from zones.models import Zone, DensityRecord, Corridor

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
        from tests.phase_a_helpers import consented_trip
        consented_trip(self.profile)
        self.client.force_login(self.user)

    def test_live_map_renders(self):
        response = self.client.get(reverse('zones:live_map'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hajj-map')
        self.assertContains(response, 'watchPosition')
        self.assertContains(response, 'X-CSRFToken')
        self.assertNotContains(response, 'Demo GPS')

    def test_api_zones_status(self):
        response = self.client.get(reverse('zones:api_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['zones'][0]['code'], 'Z-JAMARAT-TEST')
        self.assertIn('data_freshness', data['zones'][0])
        self.assertIn('corridors', data)

    def test_api_status_exposes_active_corridor_geometry(self):
        destination = Zone.objects.create(
            code='Z-HARAM-TEST', name_ar='حرم تجريبي', name_en='Haram Test',
            site_type='HARAM', center_lat=21.4225, center_lng=39.8262,
            radius_meters=100, safe_capacity=1000, floor_area_sqm=500,
        )
        corridor = Corridor.objects.create(
            name_ar='ممر تجريبي', name_en='Test corridor', from_zone=self.zone,
            to_zone=destination, base_walking_minutes=8, width_meters=12,
        )
        response = self.client.get(reverse('zones:api_status'))
        item = next(c for c in response.json()['corridors'] if c['id'] == corridor.id)
        self.assertEqual(item['coordinates'], [[self.zone.center_lat, self.zone.center_lng], [destination.center_lat, destination.center_lng]])
        self.assertEqual(item['status'], 'open')

    def test_public_map_data_has_only_public_layers(self):
        response = self.client.get(reverse('zones:api_map_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('zones', data)
        self.assertIn('corridors', data)
        self.assertIn('facilities', data)
        self.assertIn('places', data)
        self.assertNotIn('pilgrim_id', response.content.decode())
        self.assertNotIn('qr_token', response.content.decode())

    def test_routes_endpoint_returns_corridor_overlay(self):
        response = self.client.get(reverse('zones:api_routes'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('corridors', response.json())

    def test_api_location_ping_matches_zone(self):
        payload = {
            'lat': 21.41982,  # Inside the test zone
            'lng': 39.87152,
            'accuracy_meters': 8.5,
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
        self.assertEqual(self.profile.pings.get(id=data['ping_id']).accuracy_meters, 8.5)

    def test_api_location_ping_rejects_invalid_accuracy(self):
        response = self.client.post(
            reverse('zones:api_ping'),
            data=json.dumps({'lat': 21.41982, 'lng': 39.87152, 'accuracy_meters': 'NaN'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

