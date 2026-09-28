import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import PilgrimProfile
from zones.models import Zone, LocationPing, DensityRecord
from safety.models import Alert
from groups.models import PilgrimGroup, GroupMembership
from nusuk.models import HajjCampaign

class Command(BaseCommand):
    help = 'Simulates 500 fake pilgrims moving across holy sites with optional --surge flag (KSU Section 9)'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=500, help='Number of pilgrims to simulate (default: 500)')
        parser.add_argument('--surge', action='store_true', help='Trigger sudden surge into a choke point (creates RED zone)')
        parser.add_argument('--choke', type=str, default='Z-JAMARAT-F0', help='Target choke point zone for surge (default: Z-JAMARAT-F0)')

    def handle(self, *args, **options):
        count = options['count']
        surge = options['surge']
        choke_code = options['choke']

        self.stdout.write(self.style.NOTICE(f"Initializing pilgrim simulation: {count} pilgrims (Surge: {surge})..."))

        zones = list(Zone.objects.all())
        if not zones:
            self.stdout.write(self.style.ERROR("No zones found! Run 'python manage.py seed_hajjguard' first."))
            return

        choke_zone = Zone.objects.filter(code=choke_code).first() or zones[0]

        # Ensure campaign exists
        campaign, _ = HajjCampaign.objects.get_or_create(
            license_no='CAMP-KSA-9921',
            defaults={
                'name_en': 'Al-Ansar VIP Hajj Campaign',
                'name_ar': 'حملة الأنصار لحجاج الداخل',
                'country': 'Saudi Arabia',
                'category': 'PREMIUM',
                'assigned_mina_sector': 'Sector 3',
                'mina_camp_no': 'Camp 44',
                'makkah_hotel': 'Al-Aziziyah Towers',
                'leader_name': 'Sheikh Abdullah Al-Ghamdi',
                'leader_phone': '+966 50 123 4567',
                'join_code': 'ANSAR2026',
            }
        )

        now = timezone.now()

        # Ensure a designated leader pilgrim exists
        leader_user, _ = User.objects.get_or_create(
            username='campaign_leader',
            defaults={
                'first_name': 'Sheikh Abdullah',
                'last_name': 'Al-Ghamdi',
                'email': 'leader@ansar.org'
            }
        )
        leader_profile, _ = PilgrimProfile.objects.get_or_create(
            user=leader_user,
            defaults={
                'role': 'leader',
                'phone': '+966501234567',
                'language': 'ar',
                'nationality': 'Saudi Arabia',
                'age': 48,
                'gender': 'M',
                'blood_type': 'O+',
                'qr_code_payload': 'HAJJGUARD:PRM-LEADER-01',
                'consent_given': True,
                'consent_timestamp': now
            }
        )

        # Ensure demo campaign group exists
        demo_group, _ = PilgrimGroup.objects.get_or_create(
            join_code='GRP-MINA1',
            defaults={
                'name': 'Al-Ansar Campaign - Family Group A',
                'campaign': campaign,
                'leader': leader_profile,
            }
        )

        created_users = 0
        updated_pings = 0

        # Generate / Retrieve pilgrims
        nationalities = ['Saudi Arabia', 'Egypt', 'Pakistan', 'Indonesia', 'Nigeria', 'Turkey', 'Algeria', 'United Kingdom']
        
        for i in range(1, count + 1):
            username = f"sim_pilgrim_{i:04d}"
            user, u_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': f"Pilgrim_{i}",
                    'last_name': f"Haji",
                    'email': f"{username}@hajjguard.org"
                }
            )

            # Age distribution: 20% seniors (>=65)
            is_senior = (i % 5 == 0)
            age = random.randint(65, 82) if is_senior else random.randint(22, 60)
            is_wheelchair = (i % 15 == 0)
            chronic = 'HYPERTENSION' if (i % 8 == 0) else ('DIABETES' if (i % 10 == 0) else 'NONE')

            profile, p_created = PilgrimProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'pilgrim',
                    'phone': f"+96650{i:07d}",
                    'language': 'ar' if (i % 2 == 0) else 'en',
                    'nationality': random.choice(nationalities),
                    'age': age,
                    'gender': 'M' if (i % 3 != 0) else 'F',
                    'blood_type': random.choice(['O+', 'A+', 'B+', 'AB+']),
                    'is_wheelchair_user': is_wheelchair,
                    'chronic_condition': chronic,
                    'qr_code_payload': f"HAJJGUARD:PRM-2026-{i:04d}",
                    'consent_given': True,
                    'consent_timestamp': now
                }
            )
            if u_created:
                created_users += 1

            # Put first 25 pilgrims into demo group
            if i <= 25:
                GroupMembership.objects.get_or_create(
                    group=demo_group,
                    pilgrim=profile,
                    defaults={
                        'role': 'DEPUTY' if i == 1 else 'MEMBER',
                        'is_active': True
                    }
                )

            # Decide zone: If surge is active, 75% go to choke_zone
            if surge and random.random() < 0.75:
                target_zone = choke_zone
            else:
                target_zone = random.choice(zones)

            # Small jitter around zone center
            lat_jitter = random.uniform(-0.0006, 0.0006)
            lng_jitter = random.uniform(-0.0006, 0.0006)
            p_lat = target_zone.center_lat + lat_jitter
            p_lng = target_zone.center_lng + lng_jitter

            # Create LocationPing
            LocationPing.objects.create(
                pilgrim=profile,
                zone=target_zone,
                lat=p_lat,
                lng=p_lng,
                timestamp=now
            )
            updated_pings += 1

        # Recompute Density Records for all zones
        self.stdout.write(self.style.NOTICE("Recomputing zone density and risk metrics..."))
        window_15m = now - timezone.timedelta(minutes=15)

        for z in zones:
            active_pings = LocationPing.objects.filter(zone=z, timestamp__gte=window_15m).count()
            headcount = max(active_pings, 50)
            density = round(headcount / max(z.floor_area_sqm, 1), 2)
            predicted_20m = round(density * (1.35 if surge and z == choke_zone else 1.05), 2)

            status_code, color_code, label = z.get_status(headcount)
            risk = round(min(100.0, (headcount / max(z.safe_capacity, 1)) * 100.0), 1)

            DensityRecord.objects.create(
                zone=z,
                timestamp=now,
                phone_count=active_pings,
                image_count=int(active_pings * 0.9),
                total_people=headcount,
                density_per_sqm=density,
                predicted_density_20m=predicted_20m,
                risk_score=risk,
                status=status_code
            )

        if surge:
            latest_rec = choke_zone.density_records.first()
            density_val = latest_rec.density_per_sqm if latest_rec else 4.2
            Alert.objects.create(
                zone=choke_zone,
                alert_type='CROWD_SURGE',
                severity='CRITICAL',
                message_en=f"CRITICAL SURGE DETECTED: Density reached {density_val} p/m² at {choke_zone.name_en}. Mandatory detour active.",
                message_ar=f"تحذير تدافع وازدحام حرج: الكثافة بلغت {density_val} فرد/م² في {choke_zone.name_ar}. تم تفعيل التحويل الإجباري."
            )
            self.stdout.write(self.style.WARNING(f"SURGE ACTIVATED: Zone {choke_zone.code} forced into CRITICAL RED state."))

        self.stdout.write(self.style.SUCCESS(
            f"Simulation complete: {count} pilgrims processed, {updated_pings} pings recorded across {len(zones)} zones."
        ))
