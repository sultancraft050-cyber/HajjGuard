import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard
from services.fiqh_ai import NusukFiqhAI

class NusukSmartCardAndAITests(TestCase):
    """
    Automated verification for:
    1. Digital 'Nusuk Card' (Smart ID) automated provisioning, barcode, and QR integrity.
    2. Nusuk AI Fiqh & Ritual Copilot Islamic jurisprudence engine and live crowd integration.
    """

    def setUp(self):
        self.client = Client()
        self.campaign = HajjCampaign.objects.create(
            license_no="CAMP-TEST-2026",
            name_en="Al-Rajhi Hajj Pilgrims",
            name_ar="مؤسسة الراجحي لخدمة الحجاج",
            country="Saudi Arabia",
            assigned_mina_sector="Sector 3",
            mina_camp_no="Camp 44",
            leader_name="Sheikh Abdullah",
            leader_phone="+966501112233",
            quota=1000,
            join_code="RAJHI-T"
        )
        self.user = User.objects.create_user(username='hajj_pilgrim_1', password='password123', first_name='Tariq', last_name='Zahrani')

    def test_auto_provision_nusuk_card_on_pilgrim_creation(self):
        """Test 1: Auto-provisioning signal creates a valid NusukCard on PilgrimProfile creation."""
        profile = PilgrimProfile.objects.create(
            user=self.user,
            role='pilgrim',
            phone='+966501234567',
            age=68,
            is_wheelchair_user=True,
            chronic_condition='CARDIAC',
            blood_type='A+'
        )

        card = NusukCard.objects.filter(pilgrim=profile).first()
        self.assertIsNotNone(card, "NusukCard must be automatically provisioned via signal")
        self.assertTrue(card.tasreeh_no.startswith("TASREEH-1447-"))
        self.assertTrue(card.is_valid)
        self.assertIn("NUSUK_SMART_CARD", card.qr_payload)
        self.assertTrue(len(card.get_barcode_code()) > 0)

    def test_nusuk_card_barcode_and_qr_integrity(self):
        """Test 2: Verifies QR payload structure and Code128 laser barcode generation."""
        profile = PilgrimProfile.objects.create(
            user=self.user,
            role='pilgrim',
            blood_type='B+'
        )
        card = profile.nusuk_card
        payload = json.loads(card.qr_payload)
        
        self.assertEqual(payload['type'], 'NUSUK_SMART_CARD')
        self.assertEqual(payload['version'], '2.0-2026')
        self.assertIn('tasreeh_no', payload)
        self.assertIn('camp', payload)
        self.assertIn('barcode', payload)
        self.assertEqual(payload['blood_type'], 'B+')

    def test_digital_card_view_http_200(self):
        """Test 3: GET /nusuk/card/ renders the 3D flip smart card with HTTP 200."""
        self.client.force_login(self.user)
        # Create profile to trigger card
        PilgrimProfile.objects.create(user=self.user, role='pilgrim')

        response = self.client.get('/nusuk/card/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Digital Nusuk Smart Card")
        self.assertContains(response, "AUTHORIZED PILGRIM")
        self.assertContains(response, "flipCard")

    def test_api_card_details_http_200(self):
        """Test 4: GET /nusuk/card/api/ returns structured JSON card details."""
        self.client.force_login(self.user)
        PilgrimProfile.objects.create(user=self.user, role='pilgrim')

        response = self.client.get('/nusuk/card/api/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('tasreeh_no', data['card'])
        self.assertIn('barcode', data['card'])
        self.assertIn('blood_type', data['card'])

    def test_fiqh_ai_tawaf_doubt_ruling(self):
        """Test 5: Fiqh AI resolves doubt in Tawaf rounds by building on certainty (lesser number)."""
        res = NusukFiqhAI.answer_query(
            question="شككت في عدد أشواط الطواف هل طفت ثلاثة أم أربعة؟",
            language='ar'
        )
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['category'], 'TAWAF_DOUBT')
        self.assertIn("البناء على اليقين", res['answer'])
        self.assertIn("وزارة الحج والعمرة", res['source'])

    def test_fiqh_ai_proxy_jamarat_stoning(self):
        """Test 6: Fiqh AI validates proxy stoning concession (Tawkīl) for sick and elderly."""
        res = NusukFiqhAI.answer_query(
            question="هل يجوز التوكيل في رمي الجمرات لمريض أو عاجز؟",
            language='ar'
        )
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['category'], 'JAMARAT_PROXY')
        self.assertIn("يجوز التوكيل في رمي الجمرات", res['answer'])

    def test_fiqh_ai_live_crowd_telemetry_integration(self):
        """Test 7: Fiqh AI dynamically queries HaramSectionalEngine when asked about crowd."""
        res = NusukFiqhAI.answer_query(
            question="هل صحن المطاف مزدحم الآن؟",
            language='ar'
        )
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['category'], 'LIVE_CROWD_TELEMETRY')
        self.assertIn("صحن المطاف", res['answer'])
        self.assertIn("HaramSectionalEngine", res['engine'])

    def test_api_nusuk_ai_chat_endpoint(self):
        """Test 8: POST /nusuk/api/ai/chat/ processes query and returns JSON ruling."""
        payload = {
            'question': 'قصصت شعري قبل ذبح الهدي يوم النحر فما الحكم؟',
            'language': 'ar'
        }
        response = self.client.post(
            '/nusuk/api/ai/chat/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['category'], 'DAY10_ORDER')
        self.assertIn("افعل ولا حرج", data['answer'])
