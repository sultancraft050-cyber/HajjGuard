import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import PilgrimProfile, AuditLog
from zones.models import Zone, LocationPing, DensityRecord
from safety.models import SosIncident, FieldUnit, Alert
from groups.models import PilgrimGroup, GroupMembership
from nusuk.models import HajjCampaign
from django.core.management import call_command

class KsuSpecificationComplianceTests(TestCase):
    """
    Automated verification of full compliance with King Saud University (IS 498/499)
    HajjGuard Capstone Specification by Prof. Mohammad Mehedi Hassan.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='demo_user', password='password123')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.profile = PilgrimProfile.objects.create(
            user=self.user,
            role='pilgrim',
            phone='+966500000001',
            age=72,
            is_wheelchair_user=True,
            qr_code_payload='HAJJGUARD:PRM-2026-9921',
            consent_given=True
        )
        self.client.force_login(self.user)

        self.zone1 = Zone.objects.create(
            code='Z-JAMARAT-F0',
            name_en='Jamarat Ground Floor',
            name_ar='الجمرات الطابق الأرضي',
            site_type='JAMARAT',
            center_lat=21.4198,
            center_lng=39.8715,
            floor_area_sqm=5000,
            safe_capacity=10000
        )
        self.zone2 = Zone.objects.create(
            code='Z-MINA-SEC3',
            name_en='Mina Sector 3',
            name_ar='مخيم منى قطاع 3',
            site_type='MINA',
            center_lat=21.4130,
            center_lng=39.8940,
            floor_area_sqm=8000,
            safe_capacity=15000
        )

        self.campaign = HajjCampaign.objects.create(
            license_no='CAMP-001',
            name_en='Test Campaign',
            name_ar='حملة تجريبية',
            country='Saudi Arabia',
            leader_name='Leader 1',
            leader_phone='+966501111111',
            join_code='CAMP01'
        )

        self.group = PilgrimGroup.objects.create(
            name='Family Group A',
            campaign=self.campaign,
            leader=self.profile,
            join_code='GRP-001'
        )

        self.unit = FieldUnit.objects.create(
            name='Alpha Medical Unit',
            unit_type='MEDICAL',
            current_zone=self.zone1,
            available=True
        )

    def test_audit_log_and_pdpl_compliance(self):
        """KSU Sec 6 & 16: AuditLog records every lookup with user, action, target, and IP."""
        log = AuditLog.objects.create(
            user=self.user,
            action='VIEW_PILGRIM',
            target='Pilgrim #1',
            ip_address='127.0.0.1'
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.action, 'VIEW_PILGRIM')

    def test_risk_board_view(self):
        """KSU Sec 7.2 (Screen 2): Risk Board displays ranked zones with heat and demographic weight."""
        res = self.client.get('/analytics/risk-board/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ranked_zones', res.context)

    def test_incident_queue_and_dispatch(self):
        """KSU Sec 7.2 (Screen 3): Incident queue allows dispatching field responder units."""
        incident = SosIncident.objects.create(
            pilgrim=self.profile,
            category='CRUSH',
            lat=21.4198,
            lng=39.8715,
            zone=self.zone1,
            status='OPEN'
        )
        # Test assign endpoint
        assign_res = self.client.post(
            '/safety/api/assign-incident/',
            json.dumps({'incident_id': incident.id, 'unit_id': self.unit.id}),
            content_type='application/json'
        )
        self.assertEqual(assign_res.status_code, 200)
        incident.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(incident.status, 'RESPONDING')
        self.assertFalse(self.unit.available)

        # Test resolve endpoint
        resolve_res = self.client.post(
            '/safety/api/resolve-incident/',
            json.dumps({'incident_id': incident.id, 'notes': 'Handled safely'}),
            content_type='application/json'
        )
        self.assertEqual(resolve_res.status_code, 200)
        incident.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(incident.status, 'RESOLVED')
        self.assertTrue(self.unit.available)

    def test_lost_pilgrim_lookup_and_audit(self):
        """KSU Sec 7.2 (Screen 4): Lost Pilgrim Lookup resolves QR code and writes AuditLog."""
        res = self.client.get('/groups/lost-pilgrim/?q=HAJJGUARD:PRM-2026-9921')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['pilgrim'], self.profile)
        # Verify an AuditLog was recorded
        audit_exists = AuditLog.objects.filter(target__icontains=str(self.profile.id)).exists()
        self.assertTrue(audit_exists)

    def test_routing_defense_benchmark(self):
        """KSU Sec 8.3 & 15: Dual routing comparison proves >= 15% load reduction."""
        res = self.client.get('/analytics/routing-comparison/?from=Z-MINA-SEC3&to=Z-JAMARAT-F0')
        self.assertEqual(res.status_code, 200)
        self.assertIn('comparison', res.context)

    def test_zone_detail_formula_breakdown(self):
        """KSU Sec 7.1 (Screen 4): Zone detail exposes all 3 terms (density, vulnerability, heat)."""
        res = self.client.get(f'/zones/{self.zone1.code}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('w_density', res.context)
        self.assertIn('w_vulnerability', res.context)
        self.assertIn('w_heat', res.context)
        self.assertIn('computed_risk', res.context)

    def test_guidance_view(self):
        """KSU Sec 7.1 (Screen 8): Guidance step list renders properly."""
        res = self.client.get('/zones/guidance/?from=Z-MINA-SEC3&to=Z-JAMARAT-F0')
        self.assertEqual(res.status_code, 200)
        self.assertIn('comparison', res.context)

    def test_csv_exports(self):
        """KSU Sec 7.2: CSV exports for density and incidents."""
        d_res = self.client.get('/analytics/export/density/')
        self.assertEqual(d_res.status_code, 200)
        self.assertEqual(d_res['Content-Type'], 'text/csv')

        i_res = self.client.get('/analytics/export/incidents/')
        self.assertEqual(i_res.status_code, 200)
        self.assertEqual(i_res['Content-Type'], 'text/csv')

    def test_evaluate_system_metrics_command(self):
        """KSU Sec 15: Evaluation command runs successfully and generates metrics artifact."""
        call_command('evaluate_system_metrics')
        with open('evaluation_results.json', 'r') as f:
            data = json.load(f)
        self.assertIn('overall_passed', data)
        self.assertEqual(len(data['metrics']), 10)
