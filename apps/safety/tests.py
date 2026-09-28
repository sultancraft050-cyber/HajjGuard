import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard
from safety.models import SosIncident, EmergencyContact
from zones.models import Zone, DensityRecord
from tests.test_system_integrity import HajjGuardSystemIntegrityTests

class SafetyAndPortalTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create test campaign
        self.campaign = HajjCampaign.objects.create(
            license_no='CAMP-TEST-99',
            name_ar='حملة تجريبية',
            name_en='Test Campaign',
            country='Saudi Arabia',
            assigned_mina_sector='Sector 3',
            mina_camp_no='Camp 44',
            leader_name='Sheikh Ahmad',
            leader_phone='+966551122334',
            join_code='TEST-1'
        )

        # Create test user and pilgrim profile
        self.user = User.objects.create_user(username='testpilgrim2', password='password123')
        self.profile = PilgrimProfile.objects.create(
            user=self.user,
            role='pilgrim',
            age=70,
            blood_type='O+',
            is_wheelchair_user=True,
            chronic_condition='CARDIAC'
        )
        self.card = NusukCard.objects.create(
            pilgrim=self.profile,
            campaign=self.campaign,
            tasreeh_no='TAS-TEST-001',
            border_or_national_id='1082390192',
            is_valid=True
        )

    def test_pilgrim_portal_renders(self):
        response = self.client.get(reverse('accounts:pilgrim_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OFFICIAL NUSUK CARD')

    def test_operations_dashboard_renders(self):
        response = self.client.get(reverse('safety:operations_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Central Operations Command Center')

    def test_api_trigger_sos(self):
        payload = {
            'category': 'MEDICAL',
            'called_number': '997',
            'lat': 21.41980,
            'lng': 39.87150
        }
        response = self.client.post(
            reverse('safety:api_trigger_sos'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(SosIncident.objects.filter(id=data['incident_id']).exists())

    def test_api_lookup_lost_pilgrim(self):
        response = self.client.get(reverse('safety:api_lookup_pilgrim') + '?q=1082390192')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'found')
        self.assertEqual(data['campaign']['leader_phone'], '+966551122334')
        self.assertIn('Sector 3', data['campaign']['mina_tent'])

