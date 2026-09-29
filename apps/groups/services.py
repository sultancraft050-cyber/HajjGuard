import math
from datetime import timedelta
from django.utils import timezone
from zones.utils import haversine_distance
from zones.models import LocationPing
from groups.models import PilgrimGroup, GroupMembership

class GroupDriftService:
    """
    Monitors family/group cohesion during Tawaf, Sa'i, and Jamarat stoning.
    Identifies:
    1. Member drift > 50 meters from group leader's last known ping.
    2. Member silence > 10 minutes (lack of telemetry / dead battery / network dropout).
    """

    DRIFT_THRESHOLD_METERS = 50.0
    SILENCE_THRESHOLD_SECONDS = 600.0  # 10 minutes

    @classmethod
    def compute_group_metrics(cls, group_or_id):
        data = cls.calculate_group_drift(group_or_id)
        centroid = data.get('centroid') or {}
        return {
            'centroid_lat': centroid.get('lat'),
            'centroid_lng': centroid.get('lng'),
            'dispersion_radius_meters': data.get('dispersion_radius_meters', 0.0),
            'drift_alert': data.get('has_alerts', False),
            'raw_data': data
        }

    @classmethod
    def calculate_group_drift(cls, group_or_id):
        if isinstance(group_or_id, (int, str)):
            group = PilgrimGroup.objects.get(id=group_or_id)
        else:
            group = group_or_id

        now = timezone.now()
        leader_ping = LocationPing.objects.filter(pilgrim=group.leader).order_by('-timestamp').first()

        leader_status = {
            'leader_id': group.leader.id,
            'name': group.leader.user.get_full_name() or group.leader.user.username,
            'has_ping': leader_ping is not None,
            'last_lat': leader_ping.lat if leader_ping else None,
            'last_lng': leader_ping.lng if leader_ping else None,
            'last_ping_time': leader_ping.timestamp if leader_ping else None,
            'minutes_since_ping': round((now - leader_ping.timestamp).total_seconds() / 60.0, 1) if leader_ping else None,
        }

        members = GroupMembership.objects.filter(group=group, is_active=True).select_related('pilgrim', 'pilgrim__user')
        member_results = []
        drifting_count = 0
        silent_count = 0
        safe_count = 0

        for m in members:
            # Skip checking leader against themselves
            if m.pilgrim_id == group.leader_id:
                continue

            mem_ping = LocationPing.objects.filter(pilgrim=m.pilgrim).order_by('-timestamp').first()
            p_name = m.pilgrim.user.get_full_name() or m.pilgrim.user.username

            if not mem_ping:
                silent_count += 1
                member_results.append({
                    'pilgrim_id': m.pilgrim.id,
                    'name': p_name,
                    'status': 'SIGNAL_LOST',
                    'is_drifting': False,
                    'is_silent': True,
                    'distance_meters': None,
                    'last_seen': None,
                    'minutes_since_ping': None,
                    'alert_reason': 'No telemetry ping recorded'
                })
                continue

            silence_secs = (now - mem_ping.timestamp).total_seconds()
            silence_mins = round(silence_secs / 60.0, 1)

            # Check silence threshold (> 10 minutes)
            if silence_secs > cls.SILENCE_THRESHOLD_SECONDS:
                silent_count += 1
                member_results.append({
                    'pilgrim_id': m.pilgrim.id,
                    'name': p_name,
                    'status': 'SIGNAL_LOST',
                    'is_drifting': False,
                    'is_silent': True,
                    'distance_meters': None,
                    'last_seen': mem_ping.timestamp,
                    'minutes_since_ping': silence_mins,
                    'alert_reason': f'No ping received for {silence_mins} mins (> 10m threshold)'
                })
                continue

            # If leader has no ping, we can't calculate distance
            if not leader_ping:
                member_results.append({
                    'pilgrim_id': m.pilgrim.id,
                    'name': p_name,
                    'status': 'LEADER_OFFLINE',
                    'is_drifting': False,
                    'is_silent': False,
                    'distance_meters': None,
                    'last_seen': mem_ping.timestamp,
                    'minutes_since_ping': silence_mins,
                    'alert_reason': 'Leader telemetry unavailable for distance calculation'
                })
                continue

            dist = haversine_distance(leader_ping.lat, leader_ping.lng, mem_ping.lat, mem_ping.lng)
            dist = round(dist, 1)

            if dist > cls.DRIFT_THRESHOLD_METERS:
                drifting_count += 1
                member_results.append({
                    'pilgrim_id': m.pilgrim.id,
                    'name': p_name,
                    'status': 'DRIFTING',
                    'is_drifting': True,
                    'is_silent': False,
                    'distance_meters': dist,
                    'last_seen': mem_ping.timestamp,
                    'minutes_since_ping': silence_mins,
                    'alert_reason': f'Separated by {dist}m from group leader (> 50m safe threshold)'
                })
            else:
                safe_count += 1
                member_results.append({
                    'pilgrim_id': m.pilgrim.id,
                    'name': p_name,
                    'status': 'SAFE',
                    'is_drifting': False,
                    'is_silent': False,
                    'distance_meters': dist,
                    'last_seen': mem_ping.timestamp,
                    'minutes_since_ping': silence_mins,
                    'alert_reason': None
                })

        # Calculate centroid dispersion in metres. This is an RMS distance,
        # not Shannon entropy.
        active_coords = []
        if leader_ping:
            active_coords.append((leader_ping.lat, leader_ping.lng))
        for m in members:
            p_ping = LocationPing.objects.filter(pilgrim=m.pilgrim).order_by('-timestamp').first()
            if p_ping and (now - p_ping.timestamp).total_seconds() <= cls.SILENCE_THRESHOLD_SECONDS:
                active_coords.append((p_ping.lat, p_ping.lng))

        if active_coords:
            centroid_lat = sum(c[0] for c in active_coords) / len(active_coords)
            centroid_lng = sum(c[1] for c in active_coords) / len(active_coords)
            sq_dists = [haversine_distance(centroid_lat, centroid_lng, c[0], c[1]) ** 2 for c in active_coords]
            dispersion_radius_meters = math.sqrt(sum(sq_dists) / len(active_coords))
        else:
            centroid_lat, centroid_lng = None, None
            dispersion_radius_meters = 0.0

        is_group_scattered = (dispersion_radius_meters > 40.0)
        has_alerts = (drifting_count > 0 or silent_count > 0 or is_group_scattered)

        return {
            'group_id': group.id,
            'group_name': group.name,
            'join_code': group.join_code,
            'leader': leader_status,
            'total_monitored_members': len(member_results),
            'safe_count': safe_count,
            'drifting_count': drifting_count,
            'silent_count': silent_count,
            'centroid': {
                'lat': round(centroid_lat, 6) if centroid_lat is not None else None,
                'lng': round(centroid_lng, 6) if centroid_lng is not None else None
            },
            'dispersion_radius_meters': round(dispersion_radius_meters, 1),
            'is_group_scattered': is_group_scattered,
            'has_alerts': has_alerts,
            'members': member_results
        }

