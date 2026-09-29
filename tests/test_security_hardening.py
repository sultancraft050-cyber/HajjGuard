import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import PilgrimProfile, AuditLog
from groups.models import PilgrimGroup, GroupMembership
from nusuk.models import HajjCampaign, NusukCard
from safety.models import SosIncident


class SecurityHardeningTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('secure-pilgrim', password='correct horse battery staple')
        self.profile = PilgrimProfile.objects.create(user=self.user, role='pilgrim', phone='+966500000001')
        self.other_user = User.objects.create_user('other-pilgrim', password='correct horse battery staple')
        self.other = PilgrimProfile.objects.create(user=self.other_user, role='pilgrim', phone='+966500000002')
        self.campaign = HajjCampaign.objects.create(
            license_no='SECURE-CAMP', name_ar='حملة اختبار', name_en='Security Test', country='Saudi Arabia',
            leader_name='Leader', leader_phone='+966500000099', join_code='SECURE1'
        )
        self.card = NusukCard.objects.filter(pilgrim=self.profile).first()
        if self.card is None:
            self.card = NusukCard.objects.create(
                pilgrim=self.profile, campaign=self.campaign, tasreeh_no='TEST-PERMIT-1', border_or_national_id='NATIONAL-1'
            )

    def login(self):
        self.client.force_login(self.user)

    def test_demo_switch_removed_and_anonymous_private_pages_denied(self):
        self.assertEqual(self.client.get('/accounts/demo-switch/secure-pilgrim/').status_code, 404)
        self.assertIn(self.client.get(reverse('accounts:profile')).status_code, (301, 302))
        self.assertIn(self.client.get(reverse('accounts:pilgrim_portal')).status_code, (301, 302))
        self.assertIn(self.client.get(reverse('groups:my_group')).status_code, (301, 302))

    def test_registration_requires_password_consent_and_unique_username(self):
        missing = self.client.post(reverse('accounts:register'), {'username': 'new-user'})
        self.assertEqual(missing.status_code, 400)
        duplicate = self.client.post(reverse('accounts:register'), {
            'username': self.user.username, 'password': 'another correct password', 'consent_given': 'on', 'age': 30
        })
        self.assertEqual(duplicate.status_code, 409)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('correct horse battery staple'))

    def test_profile_is_scoped_to_authenticated_user(self):
        self.login()
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.context['profile'], self.profile)
        self.assertNotContains(response, self.other.phone)

    def test_telemetry_requires_session_and_ignores_identity_substitution(self):
        payload = {'lat': 21.42, 'lng': 39.82, 'pilgrim_id': self.other.id}
        anonymous = self.client.post('/api/telemetry/ping/', data=json.dumps(payload), content_type='application/json')
        self.assertIn(anonymous.status_code, (403, 302))
        self.login()
        response = self.client.post('/api/telemetry/ping/', data=json.dumps(payload), content_type='application/json')
        self.assertIn(response.status_code, (200, 429))
        if response.status_code == 200:
            from zones.models import LocationPing
            self.assertEqual(LocationPing.objects.latest('id').pilgrim, self.profile)

    def test_telemetry_rejects_nonfinite_coordinates_and_bad_timestamp(self):
        self.login()
        for coords in ({'lat': 'NaN', 'lng': 39.8}, {'lat': 'Infinity', 'lng': 39.8}):
            response = self.client.post('/api/telemetry/ping/', data=json.dumps(coords), content_type='application/json')
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/telemetry/ping/', data=json.dumps({'lat': 21.4, 'lng': 39.8, 'timestamp': 'not-a-time'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_browser_state_changes_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post('/api/telemetry/ping/', data=json.dumps({'lat': 21.4, 'lng': 39.8}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_qr_token_is_opaque_and_revocable(self):
        payload = json.loads(self.card.generate_qr_payload())
        self.assertNotIn('tasreeh_no', payload)
        self.assertNotIn('border_or_national_id', payload)
        self.assertGreaterEqual(len(payload['token']), 32)
        from nusuk.services import NusukService
        self.assertTrue(NusukService.parse_qr_payload(json.dumps(payload))[0])
        self.card.is_valid = False
        self.card.save(update_fields=['is_valid'])
        self.assertFalse(NusukService.parse_qr_payload(json.dumps(payload))[0])

    def test_lost_lookup_is_staff_only_and_exact(self):
        self.assertIn(self.client.get('/groups/lost-pilgrim/?q=secure').status_code, (301, 302))
        staff = User.objects.create_superuser('security-admin', 'admin@example.test', 'correct horse battery staple')
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/groups/lost-pilgrim/?q=secure').context['pilgrim'], None)
        self.assertTrue(AuditLog.objects.filter(user=staff, target='LOST_LOOKUP_NOT_FOUND').exists())
        response = self.client.get(f'/groups/lost-pilgrim/?q={self.card.qr_token}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pilgrim'], self.profile)
        self.assertTrue(AuditLog.objects.filter(user=staff).exists())

    def test_sos_routes_number_and_leader_and_deduplicates(self):
        leader_user = User.objects.create_user('group-leader', password='correct horse battery staple')
        leader = PilgrimProfile.objects.create(user=leader_user, role='group_leader', phone='+966500000099')
        group = PilgrimGroup.objects.create(campaign=self.campaign, leader=leader, join_code='GROUP99')
        GroupMembership.objects.create(group=group, pilgrim=self.profile)
        self.login()
        payload = {'category': 'MEDICAL', 'lat': 21.42, 'lng': 39.82, 'called_number': '911'}
        first = self.client.post(reverse('safety:api_trigger_sos'), data=json.dumps(payload), content_type='application/json')
        second = self.client.post(reverse('safety:api_trigger_sos'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['emergency_number'], '997')
        self.assertEqual(first.json()['group_leader_phone'], leader.phone)
        self.assertEqual(SosIncident.objects.filter(pilgrim=self.profile).count(), 1)

    def test_exports_and_simulations_require_staff(self):
        self.assertEqual(self.client.get('/analytics/export/incidents/').status_code, 403)
        self.assertEqual(self.client.post('/analytics/api/trigger-surge/').status_code, 403)
        staff = User.objects.create_superuser('export-admin', 'export@example.test', 'correct horse battery staple')
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/analytics/export/incidents/').status_code, 200)

    def test_assignment_and_resolution_are_staff_only(self):
        self.login()
        response = self.client.post('/safety/api/resolve-incident/', data=json.dumps({'incident_id': 1}), content_type='application/json')
        self.assertIn(response.status_code, (302, 403, 404))
