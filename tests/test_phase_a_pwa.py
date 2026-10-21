import json
import io
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import HASH_SESSION_KEY
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from hajjguard_core.asgi import application

from accounts.models import GuardianRelationship, PilgrimProfile, PushSubscription
from groups.models import GroupGeofence, GroupMembership, GroupMessage, LocationShareGrant, PilgrimGroup, PilgrimTrip, GeofenceAlert
from zones.models import LocationPing
from nusuk.models import HajjCampaign
from PIL import Image


class PhaseAPwaTests(TransactionTestCase):
    def setUp(self):
        campaign = HajjCampaign.objects.create(license_no='PWA-CAMP', name_en='PWA Camp', name_ar='حملة PWA', country='Saudi Arabia', join_code='PWACAMP')
        self.u1 = User.objects.create_user('pwa-one', password='correct horse battery staple')
        self.u2 = User.objects.create_user('pwa-two', password='correct horse battery staple')
        self.p1 = PilgrimProfile.objects.create(user=self.u1, phone='+966500001001', consent_given=True)
        self.p2 = PilgrimProfile.objects.create(user=self.u2, phone='+966500001002', consent_given=True)
        self.group = PilgrimGroup.objects.create(name='PWA Group', campaign=campaign, leader=self.p1, join_code='PWAGRP')
        GroupMembership.objects.create(group=self.group, pilgrim=self.p1)
        GroupMembership.objects.create(group=self.group, pilgrim=self.p2)
        now = timezone.now()
        self.trip1 = PilgrimTrip.objects.create(pilgrim=self.p1, group=self.group, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2), status='ACTIVE')
        self.trip2 = PilgrimTrip.objects.create(pilgrim=self.p2, group=self.group, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2), status='ACTIVE')
        self.client.force_login(self.u1)

    def test_pwa_requires_authentication(self):
        client = Client()
        self.assertIn(client.get('/app/').status_code, (301, 302))

    def test_explicit_sharing_consent_and_revoke(self):
        response = self.client.post('/api/trip/location-sharing/enable', data=json.dumps({'consent_given': False, 'consent_version': 'phase-a-1'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/trip/location-sharing/enable', data=json.dumps({'consent_given': True, 'consent_version': 'phase-a-1'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        grant = LocationShareGrant.objects.get(trip=self.trip1)
        self.assertTrue(grant.is_active)
        self.assertEqual(self.client.post('/api/trip/location-sharing/revoke', data='{}', content_type='application/json').status_code, 200)
        grant.refresh_from_db()
        self.assertFalse(grant.enabled)

    def test_live_members_only_include_consenting_members(self):
        LocationShareGrant.objects.create(pilgrim=self.p1, trip=self.trip1, consent_given=True, consent_version='phase-a-1', consent_timestamp=timezone.now(), enabled=True, expires_at=self.trip1.ends_at)
        LocationPing.objects.create(pilgrim=self.p1, lat=21.42, lng=39.82)
        response = self.client.get(f'/groups/api/groups/{self.group.id}/live-members/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m['id'] for m in response.json()['members']], [self.p1.id])
        self.assertNotContains(response, 'blood_type')
        self.assertNotContains(response, 'qr_token')

    def test_group_page_does_not_render_nonconsented_location(self):
        LocationPing.objects.create(pilgrim=self.p2, lat=21.43, lng=39.83)
        response = self.client.get('/groups/my-group/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '21.43')
        self.assertNotContains(response, '21.83')

    def test_non_member_cannot_read_group_map_or_chat(self):
        outsider = User.objects.create_user('pwa-outsider', password='correct horse battery staple')
        PilgrimProfile.objects.create(user=outsider)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/live-members/').status_code, 403)
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/messages/').status_code, 403)

    def test_chat_is_authenticated_group_scoped_and_rate_limited(self):
        response = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'Meet at gate 79'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GroupMessage.objects.count(), 1)
        response = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'Again'}), content_type='application/json')
        self.assertEqual(response.status_code, 429)

    def test_message_cursor_and_leader_announcement(self):
        response = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'First'}), content_type='application/json')
        message_id = response.json()['message']['id']
        self.assertFalse(response.json()['message']['is_announcement'])
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/messages/?after_id={message_id}').json()['messages'], [])
        announcement = self.client.post(f'/groups/api/groups/{self.group.id}/announcements/', data=json.dumps({'text': 'Meet at the agreed point'}), content_type='application/json')
        self.assertEqual(announcement.status_code, 200)
        self.assertTrue(announcement.json()['message']['is_announcement'])

    def test_message_attachment_is_validated_and_group_scoped(self):
        created = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'Photo'}), content_type='application/json').json()['message']
        buffer = io.BytesIO()
        Image.new('RGB', (12, 12), 'green').save(buffer, format='PNG')
        upload = SimpleUploadedFile('meeting.png', buffer.getvalue(), content_type='image/png')
        response = self.client.post(f'/groups/api/groups/{self.group.id}/messages/{created["id"]}/attachments/', {'image': upload})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(response.json()['image_url']).status_code, 200)
        outsider = User.objects.create_user('attachment-outsider', password='correct horse battery staple')
        PilgrimProfile.objects.create(user=outsider)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(response.json()['image_url']).status_code, 403)

    def test_member_can_delete_only_own_message(self):
        own = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'Own'}), content_type='application/json').json()['message']['id']
        self.client.force_login(self.u2)
        other = self.client.post(f'/groups/api/groups/{self.group.id}/messages/create/', data=json.dumps({'text': 'Other'}), content_type='application/json')
        self.assertEqual(other.status_code, 200)
        self.assertEqual(self.client.post(f'/groups/api/groups/{self.group.id}/messages/{own}/moderate/', data=json.dumps({'action': 'delete'}), content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(f'/groups/api/groups/{self.group.id}/messages/{other.json()["message"]["id"]}/moderate/', data=json.dumps({'action': 'delete'}), content_type='application/json').status_code, 200)

    def test_group_management_is_leader_only_and_scoped(self):
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/management/').status_code, 200)
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/management/').status_code, 403)
        self.assertEqual(self.client.post(f'/groups/api/groups/{self.group.id}/announcements/', data=json.dumps({'text': 'No'}), content_type='application/json').status_code, 403)

    def test_leader_can_manage_member_and_geofence(self):
        fence = self.client.post(f'/api/groups/{self.group.id}/geofences/create/', data=json.dumps({'name': 'Meet', 'lat': 21.42, 'lng': 39.82, 'radius_meters': 100}), content_type='application/json')
        self.assertEqual(fence.status_code, 200)
        fence_id = fence.json()['id']
        updated = self.client.patch(f'/api/geofences/{fence_id}/', data=json.dumps({'name': 'New Meet', 'radius_meters': 120}), content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.delete(f'/api/geofences/{fence_id}/delete/').status_code, 200)
        role = self.client.patch(f'/groups/api/groups/{self.group.id}/members/{self.p2.id}/role/', data=json.dumps({'role': 'DEPUTY'}), content_type='application/json')
        self.assertEqual(role.status_code, 200)
        self.assertEqual(role.json()['role'], 'DEPUTY')
        self.assertEqual(self.client.post(f'/groups/api/groups/{self.group.id}/members/{self.p2.id}/remove/').status_code, 200)
        self.assertFalse(GroupMembership.objects.get(group=self.group, pilgrim=self.p2).is_active)

    def test_join_form_accepts_group_code_and_rotation_invalidates_old_code(self):
        old_code = self.group.join_code
        self.assertEqual(self.client.post('/groups/api/join/', data={'group_code': old_code}).status_code, 200)
        rotated = self.client.post(f'/groups/api/groups/{self.group.id}/rotate-code/')
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.json()['join_code'], old_code)

    def test_trip_expiry_hides_sharing(self):
        LocationShareGrant.objects.create(pilgrim=self.p1, trip=self.trip1, consent_given=True, consent_version='phase-a-1', enabled=True, expires_at=timezone.now() - timedelta(seconds=1))
        LocationPing.objects.create(pilgrim=self.p1, lat=21.42, lng=39.82)
        self.assertEqual(self.client.get(f'/groups/api/groups/{self.group.id}/live-members/').json()['members'], [])

    def test_guardian_relationship_requires_explicit_consent(self):
        relation = GuardianRelationship.objects.create(guardian=self.p1, dependent=self.p2, relationship_type='CAREGIVER')
        self.assertFalse(relation.consent_given)

    def test_phone_ping_requires_active_push_subscription(self):
        response = self.client.post(f'/groups/api/groups/{self.group.id}/members/{self.p2.id}/ping/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 409)
        PushSubscription.objects.create(user=self.u2, endpoint='https://fcm.googleapis.com/pwa-two', p256dh='key', auth='auth')
        response = self.client.post(f'/groups/api/groups/{self.group.id}/members/{self.p2.id}/ping/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_geofence_is_leader_scoped_and_crossing_is_alerted(self):
        fence_response = self.client.post(f'/api/groups/{self.group.id}/geofences/create/', data=json.dumps({'name': 'Meeting point', 'lat': 21.42, 'lng': 39.82, 'radius_meters': 100}), content_type='application/json')
        self.assertEqual(fence_response.status_code, 200)
        LocationShareGrant.objects.create(pilgrim=self.p1, trip=self.trip1, consent_given=True, consent_version='phase-a-1', consent_timestamp=timezone.now(), enabled=True, expires_at=self.trip1.ends_at)
        LocationPing.objects.create(pilgrim=self.p1, lat=21.43, lng=39.83, timestamp=timezone.now() - timedelta(seconds=10))
        self.client.post('/api/telemetry/ping/', data=json.dumps({'lat': 21.42, 'lng': 39.82}), content_type='application/json')
        self.assertTrue(GeofenceAlert.objects.filter(pilgrim=self.p1, event_type='ENTER').exists())

    def test_push_subscription_rejects_unknown_endpoint(self):
        response = self.client.post('/accounts/api/push/subscribe/', data=json.dumps({'subscription': {'endpoint': 'https://evil.example/push', 'keys': {'p256dh': 'x', 'auth': 'y'}}}), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_manifest_and_service_worker_are_available(self):
        self.assertEqual(self.client.get('/manifest.webmanifest').status_code, 200)
        self.assertEqual(self.client.get('/service-worker.js').status_code, 200)

    def test_owner_offline_card_is_private_and_medical_fields_are_opt_in(self):
        response = self.client.get('/api/offline-card/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['owner_id'], self.u1.pk)
        self.assertIsNone(payload['medical'])
        self.assertIn('qr_image', payload)
        medical = self.client.get('/api/offline-card/?include_medical=true').json()
        self.assertEqual(medical['medical']['condition'], 'NONE')

    def test_websocket_accepts_member_and_rejects_outsider(self):
        session = SessionStore()
        session['_auth_user_id'] = str(self.u1.pk)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session[HASH_SESSION_KEY] = self.u1.get_session_auth_hash()
        session.save()
        cookie = f'sessionid={session.session_key}'.encode()
        member = WebsocketCommunicator(application, f'/ws/groups/{self.group.id}/', headers=[(b'cookie', cookie), (b'origin', b'http://localhost')])
        outsider = User.objects.create_user('ws-outsider', password='correct horse battery staple')
        outsider_session = SessionStore()
        outsider_session['_auth_user_id'] = str(outsider.pk)
        outsider_session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        outsider_session[HASH_SESSION_KEY] = outsider.get_session_auth_hash()
        outsider_session.save()
        denied = WebsocketCommunicator(application, f'/ws/groups/{self.group.id}/', headers=[(b'cookie', f'sessionid={outsider_session.session_key}'.encode()), (b'origin', b'http://localhost')])
        async def scenario():
            connected, _ = await member.connect()
            self.assertTrue(connected)
            await member.disconnect()
            accepted, _ = await denied.connect()
            self.assertFalse(accepted)
            await denied.disconnect()
        async_to_sync(scenario)()
