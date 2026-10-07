import json
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from zones.models import Corridor, DensityRecord, VisitorPlace, Zone


class VisitorJourneyTests(TestCase):
    def setUp(self):
        self.origin = Zone.objects.create(
            code='Z-ORIGIN-VISITOR', name_ar='البداية', name_en='Visitor origin',
            site_type='HARAM', center_lat=21.4225, center_lng=39.8262,
            radius_meters=60, floor_level=0, safe_capacity=1000, floor_area_sqm=500,
        )
        self.destination = Zone.objects.create(
            code='Z-DEST-VISITOR', name_ar='الوجهة', name_en='Visitor destination',
            site_type='JAMARAT', center_lat=21.4198, center_lng=39.8715,
            radius_meters=60, floor_level=0, safe_capacity=1000, floor_area_sqm=500,
        )
        Corridor.objects.create(
            name_ar='ممر', name_en='Visitor corridor', from_zone=self.origin,
            to_zone=self.destination, base_walking_minutes=12, width_meters=10,
        )

    def test_public_discovery_page_requires_no_login(self):
        response = self.client.get(reverse('zones:discover_makkah'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Discover Makkah')
        self.assertContains(response, 'Start a journey')
        self.assertContains(response, 'verify before visiting')

    def test_enabled_places_are_source_labelled_and_filtered(self):
        place = VisitorPlace.objects.create(
            name_ar='موقع', name_en='Accessible place', category='VISIT',
            description='Planning description', area='Central Makkah',
            coordinates=[21.4225, 39.8262], accessibility={'wheelchair': True},
            source='Venue website', verification_date=date.today(), enabled=True,
        )
        VisitorPlace.objects.create(
            name_ar='مخفي', name_en='Disabled place', category='VISIT',
            description='Hidden', source='Source', verification_date=date.today(), enabled=False,
        )
        response = self.client.get(reverse('zones:api_visitor_places'), {'category': 'visit', 'accessible': '1'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([row['id'] for row in payload['places']], [place.id])
        self.assertEqual(payload['places'][0]['provenance'], 'admin_curated')
        self.assertNotIn('Disabled place', response.content.decode())

    def test_enabled_place_requires_source_and_verification(self):
        place = VisitorPlace(
            name_ar='موقع', name_en='Invalid', category='VISIT', description='x', enabled=True,
        )
        with self.assertRaises(ValidationError):
            place.full_clean()

    def test_invalid_coordinates_are_rejected(self):
        place = VisitorPlace(
            name_ar='موقع', name_en='Invalid', category='VISIT', description='x',
            coordinates=[float('nan'), 39.8], source='Source', verification_date=date.today(), enabled=True,
        )
        with self.assertRaises(ValidationError):
            place.full_clean()

    def test_stale_place_is_explicitly_labelled(self):
        place = VisitorPlace.objects.create(
            name_ar='قديم', name_en='Older place', category='VISIT', description='x',
            coordinates=[21.42, 39.82], source='Source', verification_date=date.today() - timedelta(days=91), enabled=True,
        )
        payload = self.client.get(reverse('zones:api_visitor_places')).json()
        self.assertTrue(next(row for row in payload['places'] if row['id'] == place.id)['stale'])

    def test_journey_reuses_route_engine_and_honest_missing_data(self):
        response = self.client.get(reverse('analytics:api_calculate_route'), {
            'from': self.origin.code, 'to': self.destination.code, 'preference': 'less_crowded',
        })
        self.assertEqual(response.status_code, 200)
        journey = response.json()['route_comparison']['journey']
        self.assertEqual(journey['preference'], 'less_crowded')
        self.assertIsNone(journey['crowd'])
        self.assertIn('Not measured', journey['best_departure_label'])

    def test_journey_translates_record_status_for_visitors(self):
        DensityRecord.objects.create(
            zone=self.destination, total_people=850, density_per_sqm=1.7,
            predicted_density_20m=2.1, risk_score=62, status='ORANGE',
        )
        response = self.client.get(reverse('analytics:api_calculate_route'), {
            'from': self.origin.code, 'to': self.destination.code, 'preference': 'fastest',
        })
        self.assertEqual(response.json()['route_comparison']['journey']['crowd'], 'Busy')
