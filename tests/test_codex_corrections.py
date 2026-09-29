import json
from django.contrib.auth.models import User
from django.test import TestCase, Client

from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard


class CodexCorrectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='privacy-test')
        self.profile = PilgrimProfile.objects.create(user=self.user, role='pilgrim')
        self.campaign = HajjCampaign.objects.create(
            license_no='TEST-CODEX-1', name_ar='اختبار', name_en='Test',
            country='Saudi Arabia', leader_name='Leader', leader_phone='000',
            join_code='CODEX1'
        )

    def test_consent_is_opt_in(self):
        self.assertFalse(self.profile.consent_given)
        self.assertIsNone(self.profile.consent_timestamp)

    def test_qr_payload_contains_no_sensitive_profile_fields(self):
        card = NusukCard.objects.get(pilgrim=self.profile)
        payload = json.loads(card.qr_payload)
        self.assertEqual(payload['type'], 'NUSUK_SMART_CARD')
        self.assertIn('token', payload)
        self.assertGreaterEqual(len(payload['token']), 32)
        for forbidden in ('pilgrim_id', 'name', 'nationality', 'blood_type', 'leader_phone', 'emergency_pin'):
            self.assertNotIn(forbidden, payload)

    def test_card_api_requires_authentication(self):
        response = Client().get('/nusuk/card/api/')
        self.assertIn(response.status_code, (301, 302))

    def test_benchmark_artifact_does_not_assert_success(self):
        with open('evaluation_results.json', encoding='utf-8') as handle:
            result = json.load(handle)
        self.assertFalse(result['overall_passed'])
        self.assertFalse(result['overall_passed'])
        self.assertTrue(any('NOT MEASURED' in metric.get('measured', '') for metric in result['metrics']) or result.get('status') == 'not_generated')
