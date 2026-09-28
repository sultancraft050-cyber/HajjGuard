from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import PilgrimProfile
from zones.models import Zone, Corridor, DensityRecord
from nusuk.models import HajjCampaign, NusukCard
from nusuk.services import NusukService
from safety.models import EmergencyContact

class Command(BaseCommand):
    help = 'Seeds HajjGuard with authentic holy sites zones, corridors, emergency hotlines, and sample campaigns/pilgrims'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting HajjGuard database seeding...'))

        # 1. EMERGENCY CONTACTS (Official Saudi Hajj Numbers)
        emergency_data = [
            {
                'number': '911',
                'name_ar': 'العمليات الأمنية الموحدة (طوارئ مكة)',
                'name_en': 'Unified Security Operations (Makkah 911)',
                'service_type': 'UNIFIED',
                'description_ar': 'الشرطة، أمن الطرق، والمرور لجميع الحالات الأمنية الطارئة',
                'description_en': 'Police, traffic, and general public security emergencies',
                'badge_color': '#dc3545',
                'icon_name': 'bi-shield-shaded',
                'sort_order': 1
            },
            {
                'number': '997',
                'name_ar': 'الهلال الأحمر السعودي (إسعاف وطوارئ طبية)',
                'name_en': 'Saudi Red Crescent (Medical & Ambulance)',
                'service_type': 'AMBULANCE',
                'description_ar': 'الإسعاف والإنقاذ الطبي للحالات الحرجة والإغماء وضربات الشمس',
                'description_en': 'Critical medical emergencies, fainting, heat stroke, cardiac events',
                'badge_color': '#e63946',
                'icon_name': 'bi-heart-pulse-fill',
                'sort_order': 2
            },
            {
                'number': '998',
                'name_ar': 'الدفاع المدني السعودي',
                'name_en': 'Civil Defense (Fire & Rescue)',
                'service_type': 'CIVIL_DEFENSE',
                'description_ar': 'حرائق، تدافعات، وحوادث الإنقاذ والسلامة العامة',
                'description_en': 'Fire hazards, structural collapse, crowd crush emergencies',
                'badge_color': '#f77f00',
                'icon_name': 'bi-fire',
                'sort_order': 3
            },
            {
                'number': '1966',
                'name_ar': 'مركز رعاية المستفيدين - وزارة الحج والعمرة',
                'name_en': 'Ministry of Hajj Pilgrim Care Center',
                'service_type': 'HAJJ_CARE',
                'description_ar': 'الإرشاد والتائهين، الشكاوى، والاستفسارات التنظيمية',
                'description_en': 'Lost pilgrim guidance, complaints, and general Hajj assistance',
                'badge_color': '#0d5c3a',
                'icon_name': 'bi-building-fill-check',
                'sort_order': 4
            },
            {
                'number': '937',
                'name_ar': 'مركز الاستشارات الطبية - وزارة الصحة',
                'name_en': 'Ministry of Health Medical Consultations',
                'service_type': 'HEALTH_ADVICE',
                'description_ar': 'استشارات طبية وإرشاد لأقرب المراكز الصحية والمستشفيات في المشاعر',
                'description_en': 'Immediate doctor consultation and directions to nearest field hospitals',
                'badge_color': '#028090',
                'icon_name': 'bi-hospital-fill',
                'sort_order': 5
            },
        ]

        for item in emergency_data:
            EmergencyContact.objects.update_or_create(
                number=item['number'],
                defaults=item
            )
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(emergency_data)} official Saudi emergency hotlines.'))

        # 2. HOLY SITES ZONES (Accurate GPS coordinates & capacities)
        zones_data = [
            # 7 Official Architectural Sections of Masjid Al-Haram
            {
                'code': 'Z-HARAM-MATAF',
                'name_ar': 'صحن المطاف الأوسط (الكعبة المشرفة)',
                'name_en': 'Kaaba Mataf Central Basin',
                'site_type': 'HARAM',
                'center_lat': 21.42250,
                'center_lng': 39.82620,
                'radius_meters': 45.0,
                'floor_level': 0,
                'safe_capacity': 18000,
                'floor_area_sqm': 5000,
            },
            {
                'code': 'Z-HARAM-GF-PER',
                'name_ar': 'أروقة المطاف الأرضي المحيطة',
                'name_en': 'Mataf Ground Perimeter Colonnades',
                'site_type': 'HARAM',
                'center_lat': 21.42250,
                'center_lng': 39.82620,
                'radius_meters': 65.0,
                'floor_level': 0,
                'safe_capacity': 15000,
                'floor_area_sqm': 4500,
            },
            {
                'code': 'Z-HARAM-F1',
                'name_ar': 'مطاف الدور الأول المعلق (العربات والمشاة)',
                'name_en': 'Mataf First Floor (Rounds/Wheelchairs)',
                'site_type': 'HARAM',
                'center_lat': 21.42250,
                'center_lng': 39.82620,
                'radius_meters': 75.0,
                'floor_level': 1,
                'safe_capacity': 12000,
                'floor_area_sqm': 4000,
            },
            {
                'code': 'Z-HARAM-ROOF',
                'name_ar': 'سطح المطاف المفتوح',
                'name_en': 'Mataf Roof Tier',
                'site_type': 'HARAM',
                'center_lat': 21.42250,
                'center_lng': 39.82620,
                'radius_meters': 85.0,
                'floor_level': 2,
                'safe_capacity': 15000,
                'floor_area_sqm': 6000,
            },
            {
                'code': 'Z-HARAM-MASA-GF',
                'name_ar': 'المسعى - الدور الأرضي (الصفا والمروة)',
                'name_en': "Masa'a Ground Floor (Safa & Marwah)",
                'site_type': 'HARAM',
                'center_lat': 21.42360,
                'center_lng': 39.82770,
                'radius_meters': 110.0,
                'floor_level': 0,
                'safe_capacity': 25000,
                'floor_area_sqm': 10000,
            },
            {
                'code': 'Z-HARAM-MASA-F1',
                'name_ar': 'المسعى - الدور الأول العلوي',
                'name_en': "Masa'a First Floor",
                'site_type': 'HARAM',
                'center_lat': 21.42360,
                'center_lng': 39.82770,
                'radius_meters': 110.0,
                'floor_level': 1,
                'safe_capacity': 25000,
                'floor_area_sqm': 10000,
            },
            {
                'code': 'Z-HARAM-EXT-KFA',
                'name_ar': 'توسعة الملك فهد والملك عبد الله',
                'name_en': 'King Fahd & King Abdullah Expansions',
                'site_type': 'HARAM',
                'center_lat': 21.42180,
                'center_lng': 39.82480,
                'radius_meters': 140.0,
                'floor_level': 0,
                'safe_capacity': 80000,
                'floor_area_sqm': 35000,
            },
            {
                'code': 'Z-HARAM-MASA',
                'name_ar': 'المسعى العام (الصفا والمروة)',
                'name_en': "Masa'a General Gallery",
                'site_type': 'HARAM',
                'center_lat': 21.42360,
                'center_lng': 39.82770,
                'radius_meters': 120.0,
                'floor_level': 0,
                'safe_capacity': 25000,
                'floor_area_sqm': 10000,
            },
            # Jamarat Complex (Stoning bridge multi-floors)
            {
                'code': 'Z-JAMARAT-F0',
                'name_ar': 'منشأة الجمرات - الدور الأرضي',
                'name_en': 'Jamarat Bridge (Ground Level)',
                'site_type': 'JAMARAT',
                'center_lat': 21.41980,
                'center_lng': 39.87150,
                'radius_meters': 90.0,
                'floor_level': 0,
                'safe_capacity': 30000,
                'floor_area_sqm': 12000,
            },
            {
                'code': 'Z-JAMARAT-F1',
                'name_ar': 'منشأة الجمرات - الدور الأول',
                'name_en': 'Jamarat Bridge (First Floor)',
                'site_type': 'JAMARAT',
                'center_lat': 21.41980,
                'center_lng': 39.87150,
                'radius_meters': 90.0,
                'floor_level': 1,
                'safe_capacity': 30000,
                'floor_area_sqm': 12000,
            },
            {
                'code': 'Z-JAMARAT-F2',
                'name_ar': 'منشأة الجمرات - الدور الثاني',
                'name_en': 'Jamarat Bridge (Second Floor)',
                'site_type': 'JAMARAT',
                'center_lat': 21.41980,
                'center_lng': 39.87150,
                'radius_meters': 90.0,
                'floor_level': 2,
                'safe_capacity': 30000,
                'floor_area_sqm': 12000,
            },
            {
                'code': 'Z-JAMARAT-F3',
                'name_ar': 'منشأة الجمرات - الدور الثالث',
                'name_en': 'Jamarat Bridge (Third Floor)',
                'site_type': 'JAMARAT',
                'center_lat': 21.41980,
                'center_lng': 39.87150,
                'radius_meters': 90.0,
                'floor_level': 3,
                'safe_capacity': 30000,
                'floor_area_sqm': 12000,
            },
            # Mina Camps (Tent sectors)
            {
                'code': 'Z-MINA-SEC1',
                'name_ar': 'مشعر منى - مخيمات قطاع 1 (جنوب شرق آسيا)',
                'name_en': 'Mina Tents - Sector 1 (SE Asia)',
                'site_type': 'MINA',
                'center_lat': 21.41400,
                'center_lng': 39.89700,
                'radius_meters': 180.0,
                'floor_level': 0,
                'safe_capacity': 45000,
                'floor_area_sqm': 50000,
            },
            {
                'code': 'Z-MINA-SEC2',
                'name_ar': 'مشعر منى - مخيمات قطاع 2 (جنوب آسيا)',
                'name_en': 'Mina Tents - Sector 2 (South Asia)',
                'site_type': 'MINA',
                'center_lat': 21.41550,
                'center_lng': 39.89400,
                'radius_meters': 180.0,
                'floor_level': 0,
                'safe_capacity': 45000,
                'floor_area_sqm': 50000,
            },
            {
                'code': 'Z-MINA-SEC3',
                'name_ar': 'مشعر منى - مخيمات قطاع 3 (حجاج الداخل والدول العربية)',
                'name_en': 'Mina Tents - Sector 3 (Domestic & Arab)',
                'site_type': 'MINA',
                'center_lat': 21.41700,
                'center_lng': 39.89100,
                'radius_meters': 180.0,
                'floor_level': 0,
                'safe_capacity': 45000,
                'floor_area_sqm': 50000,
            },
            # Muzdalifah & Arafat
            {
                'code': 'Z-MUZDALIFAH',
                'name_ar': 'مشعر مزدلفة (المبيت وجمع الحصى)',
                'name_en': 'Muzdalifah Open Plains',
                'site_type': 'MUZDALIFAH',
                'center_lat': 21.39100,
                'center_lng': 39.90700,
                'radius_meters': 350.0,
                'floor_level': 0,
                'safe_capacity': 150000,
                'floor_area_sqm': 200000,
            },
            {
                'code': 'Z-ARAFAT-JBL',
                'name_ar': 'مشعر عرفات - جبل الرحمة والمسجد',
                'name_en': 'Arafat - Mount of Mercy',
                'site_type': 'ARAFAT',
                'center_lat': 21.35480,
                'center_lng': 39.98400,
                'radius_meters': 250.0,
                'floor_level': 0,
                'safe_capacity': 80000,
                'floor_area_sqm': 100000,
            },
        ]

        zone_instances = {}
        for z in zones_data:
            zone_obj, _ = Zone.objects.update_or_create(code=z['code'], defaults=z)
            zone_instances[z['code']] = zone_obj

            # Create initial normal density record if none exists
            if not DensityRecord.objects.filter(zone=zone_obj).exists():
                DensityRecord.objects.create(
                    zone=zone_obj,
                    phone_count=150,
                    image_count=200,
                    total_people=350,
                    density_per_sqm=0.35,
                    predicted_density_20m=0.40,
                    risk_score=15.0,
                    status='GREEN'
                )
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(zones_data)} accurate Holy Sites zones.'))

        # 3. CORRIDORS (Pedestrian paths between camps & Jamarat / Haram)
        corridors_data = [
            # From Mina Sector 3 to Jamarat Floors
            {
                'from': 'Z-MINA-SEC3',
                'to': 'Z-JAMARAT-F0',
                'name_ar': 'طريق الملك فهد الرئيسي المشاة (للدور الأرضي)',
                'name_en': 'King Fahd Main Pedestrian Way (to Ground Floor)',
                'base_walking_minutes': 25.0,
                'width_meters': 20.0,
            },
            {
                'from': 'Z-MINA-SEC3',
                'to': 'Z-JAMARAT-F2',
                'name_ar': 'طريق الجوهرة المشاة (للدور الثاني)',
                'name_en': 'Al-Jawharah Pedestrian Street (to 2nd Floor)',
                'base_walking_minutes': 22.0,
                'width_meters': 18.0,
            },
            {
                'from': 'Z-MINA-SEC3',
                'to': 'Z-JAMARAT-F3',
                'name_ar': 'نفق المعيصم للمشاة (للدور الثالث - مسار التفافي آمن)',
                'name_en': 'Al-Muaisem Pedestrian Tunnel (to 3rd Floor - Bypass)',
                'base_walking_minutes': 20.0,
                'width_meters': 22.0,
            },
            # Haram Inter-Tier & Inter-Section Corridors
            {
                'from': 'Z-HARAM-GF-PER',
                'to': 'Z-HARAM-MATAF',
                'name_ar': 'بوابات النزول من الأروقة إلى صحن المطاف',
                'name_en': 'Colonnade Descent Portals to Mataf Basin',
                'base_walking_minutes': 2.0,
                'width_meters': 18.0,
            },
            {
                'from': 'Z-HARAM-GF-PER',
                'to': 'Z-HARAM-F1',
                'name_ar': 'منحدرات وسلالم الصعود للدور الأول (مسار العربات البديل)',
                'name_en': 'Ascent Ramps to 1st Floor (Wheelchair Alternate Route)',
                'base_walking_minutes': 4.0,
                'width_meters': 12.0,
            },
            {
                'from': 'Z-HARAM-F1',
                'to': 'Z-HARAM-ROOF',
                'name_ar': 'الجسور والسلالم الكهربائية إلى سطح المطاف',
                'name_en': 'Escalators & Skybridges to Mataf Roof Tier',
                'base_walking_minutes': 5.0,
                'width_meters': 14.0,
            },
            {
                'from': 'Z-HARAM-MATAF',
                'to': 'Z-HARAM-MASA-GF',
                'name_ar': 'الممر الأرضي المباشر إلى الصفا (المسعى الأرضي)',
                'name_en': 'Direct Ground Corridor to Safa (Masaa Level 0)',
                'base_walking_minutes': 3.0,
                'width_meters': 20.0,
            },
            {
                'from': 'Z-HARAM-F1',
                'to': 'Z-HARAM-MASA-F1',
                'name_ar': 'الجسر المعلق من مطاف الدور الأول إلى مسعى الدور الأول',
                'name_en': 'Level 1 Elevated Skybridge to Upper Masaa',
                'base_walking_minutes': 4.0,
                'width_meters': 16.0,
            },
            {
                'from': 'Z-HARAM-EXT-KFA',
                'to': 'Z-HARAM-GF-PER',
                'name_ar': 'مداخل توسعة الملك فهد والملك عبد الله إلى أروقة المطاف',
                'name_en': 'King Fahd Expansion Gates to Mataf Colonnades',
                'base_walking_minutes': 5.0,
                'width_meters': 30.0,
            },
            {
                'from': 'Z-HARAM-MATAF',
                'to': 'Z-HARAM-MASA',
                'name_ar': 'الممر المباشر من المطاف إلى الصفا (المسعى العام)',
                'name_en': 'Direct Corridor Mataf to Safa (General)',
                'base_walking_minutes': 5.0,
                'width_meters': 15.0,
            },
            {
                'from': 'Z-JAMARAT-F0',
                'to': 'Z-HARAM-MATAF',
                'name_ar': 'أنفاق محبس الجن للمشاة باتجاه الحرم المكي',
                'name_en': 'Mahbas Al-Jinn Pedestrian Tunnels to Grand Mosque',
                'base_walking_minutes': 55.0,
                'width_meters': 25.0,
            },
        ]

        for c in corridors_data:
            from_z = zone_instances.get(c['from'])
            to_z = zone_instances.get(c['to'])
            if from_z and to_z:
                Corridor.objects.update_or_create(
                    from_zone=from_z,
                    to_zone=to_z,
                    defaults={
                        'name_ar': c['name_ar'],
                        'name_en': c['name_en'],
                        'base_walking_minutes': c['base_walking_minutes'],
                        'width_meters': c['width_meters'],
                        'is_active': True,
                    }
                )
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(corridors_data)} key corridor connections.'))

        # 4. VERIFIED HAJJ CAMPAIGNS
        campaigns_data = [
            {
                'license_no': 'CAMP-DOM-001',
                'name_ar': 'شركة الراجحي لخدمات حجاج الداخل',
                'name_en': 'Al-Rajhi Domestic Hajj Services',
                'country': 'Saudi Arabia (Domestic)',
                'category': 'PREMIUM',
                'assigned_mina_sector': 'Sector 3',
                'mina_camp_no': 'Camp 44',
                'makkah_hotel': 'Abraj Al-Bait, Royal Clock Tower',
                'leader_name': 'الشيخ طارق المنصور (Sheikh Tariq)',
                'leader_phone': '+966551234567',
                'quota': 2500,
                'join_code': 'RAJHI-1',
            },
            {
                'license_no': 'CAMP-SA-202',
                'name_ar': 'شركة مطوفي حجاج جنوب آسيا (البراق)',
                'name_en': 'Al-Buraq South Asia Tawafa (Pakistan/India)',
                'country': 'Pakistan / South Asia',
                'category': 'STANDARD',
                'assigned_mina_sector': 'Sector 2',
                'mina_camp_no': 'Camp 18',
                'makkah_hotel': 'Makkah Al-Aziziyah Grand Hotel',
                'leader_name': 'مولانا محبوب الهدى (Moulana Mahboob)',
                'leader_phone': '+966509876543',
                'quota': 4000,
                'join_code': 'BURAQ-7',
            },
            {
                'license_no': 'CAMP-SEA-303',
                'name_ar': 'شركة حجاج جنوب شرق آسيا (نوسانتارا)',
                'name_en': 'Nusantara Tawafa Group (Indonesia/Malaysia)',
                'country': 'Indonesia / Southeast Asia',
                'category': 'STANDARD',
                'assigned_mina_sector': 'Sector 1',
                'mina_camp_no': 'Camp 5',
                'makkah_hotel': 'Swissotel Al Maqam Makkah',
                'leader_name': 'Haji Budi Santoso',
                'leader_phone': '+966567788990',
                'quota': 5000,
                'join_code': 'NUSAN-9',
            },
        ]

        campaign_objs = {}
        for camp in campaigns_data:
            camp_obj, _ = HajjCampaign.objects.update_or_create(
                license_no=camp['license_no'],
                defaults=camp
            )
            campaign_objs[camp['join_code']] = camp_obj
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(campaigns_data)} verified Hajj campaigns.'))

        # 5. PILGRIM PROFILES & NUSUK SMART CARDS
        # User 1: Control Room Operator
        op_user, _ = User.objects.get_or_create(username='operator', defaults={'first_name': 'Hajj Command', 'last_name': 'Officer'})
        op_user.set_password('admin123')
        op_user.is_staff = True
        op_user.save()
        PilgrimProfile.objects.update_or_create(
            user=op_user,
            defaults={'role': 'operator', 'language': 'ar', 'phone': '+966500000000'}
        )

        # User 2: "Uncle Rashid" (Elderly Pilgrim with Cardiac condition)
        rashid_user, _ = User.objects.get_or_create(username='rashid', defaults={'first_name': 'Rashid', 'last_name': 'Al-Ansari'})
        rashid_user.set_password('pass123')
        rashid_user.save()
        rashid_prof, _ = PilgrimProfile.objects.update_or_create(
            user=rashid_user,
            defaults={
                'role': 'pilgrim',
                'language': 'ar',
                'phone': '+966501112233',
                'age': 72,
                'gender': 'M',
                'is_wheelchair_user': True,
                'chronic_condition': 'CARDIAC',
                'blood_type': 'O+',
                'emergency_contact_name': 'ابنه المهندس فيصل (Son Faisal)',
                'emergency_contact_phone': '+966554433221'
            }
        )
        card1, _ = NusukCard.objects.update_or_create(
            pilgrim=rashid_prof,
            defaults={
                'campaign': campaign_objs['RAJHI-1'],
                'tasreeh_no': 'TASREEH-1448-9901',
                'border_or_national_id': '1082390192',
                'tafweej_jamarat_slot': '10 Dhul-Hijjah 08:30 - 09:30',
                'assigned_jamarat_floor': 2,
                'is_valid': True
            }
        )
        NusukService.generate_nusuk_qr(card1)
        card1.save()

        # User 3: "Fatima Noor" (Young adult pilgrim from Southeast Asia)
        fatima_user, _ = User.objects.get_or_create(username='fatima', defaults={'first_name': 'Fatima', 'last_name': 'Noor'})
        fatima_user.set_password('pass123')
        fatima_user.save()
        fatima_prof, _ = PilgrimProfile.objects.update_or_create(
            user=fatima_user,
            defaults={
                'role': 'pilgrim',
                'language': 'id',
                'phone': '+628123456789',
                'age': 32,
                'gender': 'F',
                'is_wheelchair_user': False,
                'chronic_condition': 'NONE',
                'blood_type': 'A+',
                'emergency_contact_name': 'Suami: Ahmad (Husband)',
                'emergency_contact_phone': '+628198765432'
            }
        )
        card2, _ = NusukCard.objects.update_or_create(
            pilgrim=fatima_prof,
            defaults={
                'campaign': campaign_objs['NUSAN-9'],
                'tasreeh_no': 'TASREEH-1448-3341',
                'border_or_national_id': 'B88492019',
                'tafweej_jamarat_slot': '10 Dhul-Hijjah 10:00 - 11:00',
                'assigned_jamarat_floor': 1,
                'is_valid': True
            }
        )
        NusukService.generate_nusuk_qr(card2)
        card2.save()

        self.stdout.write(self.style.SUCCESS('Successfully generated Pilgrim profiles, accounts, and authentic Nusuk QR Cards.'))
        self.stdout.write(self.style.SUCCESS('HajjGuard Seeding Completed Successfully! [READY]'))
