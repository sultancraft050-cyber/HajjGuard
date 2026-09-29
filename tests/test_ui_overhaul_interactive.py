import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard
from zones.models import Zone, LocationPing
from safety.models import SosIncident, FieldUnit


class InteractiveUIOverhaulTests(TestCase):
    """
    Comprehensive Test Suite verifying the full UI overhaul to the
    Saudi Unified National Design System (DGA 'كود المنصات' - 'قالب الحج')
    across every single feature and window (17 distinct templates and live APIs).
    """

    def setUp(self):
        self.client = Client()

        # Create demo user and profile
        self.user = User.objects.create_user(
            username="rashid",
            first_name="Rashid",
            last_name="Al-Mansoor",
            email="rashid@hajjguard.sa"
        )
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.profile = PilgrimProfile.objects.create(
            user=self.user,
            role="pilgrim",
            phone="+966551122334",
            age=72,
            gender="M",
            blood_type="O+",
            chronic_condition="HYPERTENSION",
            is_wheelchair_user=True,
            consent_given=True,
            emergency_contact_name="Faisal Al-Mansoor",
            emergency_contact_phone="+966554433221"
        )
        self.client.force_login(self.user)

        # Create campaign and card
        self.campaign = HajjCampaign.objects.create(
            license_no="CAMP-TEST-1447",
            name_ar="شركة وفادة المشاعر الموحدة",
            name_en="Wafada United Hajj Agency",
            country="Saudi Arabia",
            category="VIP",
            assigned_mina_sector="قطاع 3",
            mina_camp_no="مخيم 402",
            leader_name="الشيخ فهد التميمي",
            leader_phone="+966550009988",
            join_code="WAFADA01"
        )
        # Use automatically provisioned NusukCard from signal
        self.card, created = NusukCard.objects.get_or_create(
            pilgrim=self.profile,
            defaults={
                'campaign': self.campaign,
                'tasreeh_no': "TS-1447-992144",
                'border_or_national_id': "1082390192",
                'assigned_jamarat_floor': 2,
                'tent_street_no': "شارع 204"
            }
        )
        if not created:
            self.card.campaign = self.campaign
            self.card.tasreeh_no = "TS-1447-992144"
            self.card.border_or_national_id = "1082390192"
            self.card.assigned_jamarat_floor = 2
            self.card.tent_street_no = "شارع 204"
            self.card.save()

        # Create Core Zones for all holy sites
        self.zone_mataf = Zone.objects.create(
            code="Z-HARAM-MATAF",
            name_ar="صحن المطاف",
            name_en="Mataf Central Basin",
            site_type="HARAM",
            center_lat=21.4225,
            center_lng=39.8262,
            radius_meters=60.0,
            floor_level=0,
            floor_area_sqm=8500.0,
            safe_capacity=18000
        )
        self.zone_jamarat = Zone.objects.create(
            code="Z-JAMARAT-F0",
            name_ar="جسر الجمرات الأرضي",
            name_en="Jamarat Ground Floor",
            site_type="JAMARAT",
            center_lat=21.4198,
            center_lng=39.8715,
            radius_meters=80.0,
            floor_level=0,
            floor_area_sqm=5000.0,
            safe_capacity=10000
        )
        self.zone_mina = Zone.objects.create(
            code="Z-MINA-SEC3",
            name_ar="مخيم منى قطاع 3",
            name_en="Mina Valley Camp Sector 3",
            site_type="MINA",
            center_lat=21.4150,
            center_lng=39.8900,
            radius_meters=150.0,
            floor_level=0,
            floor_area_sqm=12000.0,
            safe_capacity=20000
        )

        # Create Group and Membership for group radar and lookup tests
        from groups.models import PilgrimGroup, GroupMembership
        self.group = PilgrimGroup.objects.create(
            name="Al-Tawheed Hajj Party",
            campaign=self.campaign,
            leader=self.profile,
            join_code="TAWHEED44"
        )
        self.membership = GroupMembership.objects.create(
            pilgrim=self.profile,
            group=self.group,
            role="MEMBER",
            is_active=True
        )

        # Create SOS Incident
        self.incident = SosIncident.objects.create(
            pilgrim=self.profile,
            category="HEAT",
            status="OPEN",
            lat=21.4225,
            lng=39.8262,
            zone=self.zone_mataf,
            called_number="937"
        )

        self.client.force_login(self.user)

    # 1. WINDOW 1: Global Platform Shell (base.html)
    def test_global_shell_dga_standards(self):
        """Verifies that base.html includes the Saudi DGA Government Ribbon and Unified Header."""
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        
        # Check DGA verification ribbon
        self.assertIn("dga-gov-ribbon", content)
        self.assertIn("هيئة الحكومة الرقمية", content)
        self.assertIn("كيف تتحقق؟", content)
        
        # Check Unified Nav Header
        self.assertIn("navbar-dga", content)
        self.assertIn("HajjGuard", content)
        self.assertIn("globalSearchModal", content)
        self.assertIn("globalSosModal", content)
        self.assertIn("dga-footer", content)

    # 2. WINDOW 2: Public Landing Page (home.html)
    def test_public_landing_hajj_template(self):
        """Verifies Figma 'قالب الحج' hero, interactive aerial Haram explorer, and metric cards."""
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # Check Asymmetric Hero & Exact Figma Typography
        self.assertIn("خلق رحلة", content)
        self.assertIn("روحانية خالدة", content)
        self.assertIn("رؤيتنا خلق رحلة روحانية خالدة", content)

        # Check Interactive Aerial Haram Explorer & Photo
        self.assertIn("haram_aerial.jpg", content)
        self.assertIn("haram-photo-viewport", content)
        self.assertIn("hotspot-pin", content)
        self.assertIn("telemetryModal", content)
        self.assertIn("ΔN = (Qin - Qout) × Δt", content)

        # Check 'قسم من نحن' (4 circular mint metric cards)
        self.assertIn("قسم من نحن", content)
        self.assertIn("غير مقاس", content)
        self.assertIn("7", content)

        # Check 'قسم الخدمات' (Standardized service cards)
        self.assertIn("قسم الخدمات", content)
        self.assertIn("بوابة ضيف الرحمن الذكية", content)
        self.assertIn("HajjGuard", content)
        self.assertIn("المساعد الشرعي الذكي", content)

    # 3. WINDOW 3: Pilgrim Smart Portal (pilgrim_portal.html)
    def test_pilgrim_portal_window(self):
        """Verifies Pilgrim Portal citizen dashboard, persona switcher, and live camera HUD."""
        res = self.client.get(reverse('accounts:pilgrim_portal'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("Rashid", content)
        self.assertIn("بطاقة HajjGuard التجريبية", content)
        self.assertIn("cctvCollapse", content)
        self.assertIn("haramCamIframe", content)
        self.assertIn("مراحل رحلة الحج اللحظية", content)

    # 4. WINDOW 4: Digital Smart Nusuk Card (digital_card.html)
    def test_digital_smart_card_window(self):
        """Verifies 3D flip card, Code-128 barcode, scannable QR, and wallet buttons."""
        res = self.client.get(reverse('nusuk:digital_card'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("smartCard", content)
        self.assertIn("flip-card-inner", content)
        self.assertIn("code128-box", content)
        self.assertIn("Apple Wallet", content)
        self.assertIn("Google Wallet", content)

    # 5. WINDOW 5: Live Crowd Map (live_map.html)
    def test_live_map_window(self):
        """Verifies Leaflet map viewport, floating DGA dock, and layer controls."""
        res = self.client.get(reverse('zones:live_map'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("hajj-map", content)
        self.assertIn("map-floating-controls", content)
        self.assertIn("btn-site-pill", content)
        self.assertIn("map-legend", content)

    # 6. WINDOW 6: Smart Guidance & Detour (guidance.html)
    def test_smart_guidance_window(self):
        """Verifies turn-by-turn guidance timeline, congestion relief badges, and detour comparison."""
        res = self.client.get(reverse('zones:guidance'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("timeline-steps", content)
        self.assertIn("كفاءة تخفيف الزحام", content)

    # 7. WINDOW 7: Zone Detail & Telemetry Breakdown (zone_detail.html)
    def test_zone_detail_window(self):
        """Verifies capacity progress bar, sensor array cards, and predictive density."""
        res = self.client.get(reverse('zones:zone_detail', args=['Z-HARAM-MATAF']))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("Z-HARAM-MATAF", content)
        self.assertIn("FIDTM Optical Minaret Sensor", content)
        self.assertIn("progress-bar", content)

    # 8. WINDOW 8: My Group & Spatial Radar (my_group.html)
    def test_my_group_radar_window(self):
        """Verifies centroid dispersion, member roster, and radar map."""
        res = self.client.get(reverse('groups:my_group'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("groupMap", content) or self.assertIn("joinGroupModal", content)
        self.assertIn("رادار", content)

    # 9. WINDOW 9: Lost Pilgrim Rapid Lookup (lost_pilgrim_lookup.html)
    def test_lost_pilgrim_lookup_window(self):
        """Verifies multi-query instant search, demo chips, and verified result cards."""
        res = self.client.get(reverse('groups:lost_pilgrim') + "?q=rashid")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("rashid", content)
        self.assertIn("بيانات هوية الحاج الموثقة", content)
        self.assertIn("المطوف", content)

    # 10. WINDOW 10: Operations Tactical Command (operations_dashboard.html)
    def test_operations_command_dashboard_window(self):
        """Verifies enterprise command console, 7-section precision telemetry, and Makkah clock."""
        res = self.client.get(reverse('safety:operations_dashboard'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("makkah-clock-badge", content)
        self.assertIn("haram-sections-matrix-container", content)
        self.assertIn("btn-sync-haramain", content)
        self.assertIn("incident-tbody", content)

    # 11. WINDOW 11: Dynamic Ranked Risk Board (risk_board.html)
    def test_risk_board_window(self):
        """Verifies sortable risk table, Holy site filter, and CSV export."""
        res = self.client.get(reverse('analytics:risk_board'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("مصفوفة رصد مخاطر التدفق والاختناق", content)
        self.assertIn("تصدير CSV", content)

    # 12. WINDOW 12: Incident Ticket Queue & Dispatch (incident_queue.html)
    def test_incident_queue_window(self):
        """Verifies incident triage table, KPI cards, and dispatch modal."""
        res = self.client.get(reverse('safety:incident_queue'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("قائمة بلاغات واستغاثات الطوارئ", content)
        self.assertIn("dispatchModal", content)

    # 13. WINDOW 13: Defense Routing Benchmark (routing_comparison.html)
    def test_routing_benchmark_window(self):
        """Verifies KSU Section 15 evaluation benchmark tables and choke point reduction."""
        res = self.client.get(reverse('analytics:routing_comparison'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("KSU Benchmark", content) or self.assertIn("معيار التحقق التجريبي", content)
        self.assertIn("KSU Benchmark", content) or self.assertIn("لم يُقَس بعد", content)

    # 14. WINDOW 14: Analytics & Historical Reports (reports.html)
    def test_reports_analytics_window(self):
        """Verifies Chart.js donut chart, summary KPI cards, and export links."""
        res = self.client.get(reverse('analytics:reports'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("categoryChart", content)
        self.assertIn("تصدير الكثافة CSV", content)

    # 15. WINDOW 15: Nusuk AI Copilot Floating Drawer (ai_copilot_drawer.html)
    def test_nusuk_ai_copilot_drawer_component(self):
        """Verifies launcher button, drawer modal, chip prompts, and form submission."""
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("nusukAiLauncher", content)
        self.assertIn("nusukAiDrawer", content)
        self.assertIn("askPromptChip", content)

    # 16. WINDOW 16: Profile & PDPL Privacy (profile.html)
    def test_profile_pdpl_window(self):
        """Verifies profile form, PDPL Article 16 statutory consent, and medical flags."""
        res = self.client.get(reverse('accounts:profile'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("الملف الشخصي وإعدادات الخصوصية", content)
        self.assertIn("PDPL", content)

    # 17. WINDOW 17: User Registration / Auth (register.html)
    def test_registration_window(self):
        """Verifies registration screen layout, validation fields, and PDPL agreement."""
        res = self.client.get(reverse('accounts:register'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("تسجيل ضيف الرحمن", content)
        self.assertIn("consent_given", content)

    # 18. INTERACTIVE APIS: Verify all live interactive endpoints return 200 OK JSON
    def test_interactive_apis(self):
        """Verifies all background telemetry, AI chat, and routing calculation APIs."""
        # 1. Telemetry matrix API
        res = self.client.get(reverse('safety:api_haram_sectional_status'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 'success')

        # 2. Gate surge simulation API
        res = self.client.post(
            reverse('safety:api_simulate_section_gate_flow'),
            data=json.dumps({
                "section_code": "Z-HARAM-MATAF",
                "inflow": 1200,
                "outflow": 600,
                "dt_minutes": 1.0,
                "optical_verify": 12000
            }),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

        # 3. Dynamic route calculation API
        res = self.client.get(reverse('analytics:api_calculate_route') + "?from=Z-MINA-SEC3&to=Z-JAMARAT-F0")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'success')

        # 4. Nusuk AI Chatbot API
        res = self.client.post(
            reverse('nusuk:api_nusuk_ai_chat'),
            data=json.dumps({"question": "نسيت هل طفت 3 أو 4 أشواط؟", "language": "ar"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        ai_data = res.json()
        self.assertIn("answer", ai_data)
        self.assertTrue(len(ai_data["answer"]) > 10)
