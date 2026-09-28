from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from .models import PilgrimProfile
from nusuk.models import NusukCard
from safety.models import EmergencyContact

def pilgrim_portal(request):
    """
    Renders the tactile, accessible mobile-friendly Pilgrim Portal.
    Defaults to 'rashid' demo pilgrim if not authenticated.
    """
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        profile = PilgrimProfile.objects.filter(user__username='rashid').first()
        if not profile:
            profile = PilgrimProfile.objects.filter(role='pilgrim').first()

    nusuk_card = NusukCard.objects.filter(pilgrim=profile).first()
    emergency_numbers = EmergencyContact.objects.all()[:4]

    # Hajj Day-by-Day Ritual Timeline
    rituals = [
        {
            'day': 8,
            'title_en': 'Day 8: Tarwiyah (Mina)',
            'title_ar': 'يوم التروية - المبيت بمنى',
            'status': 'completed',
            'desc_en': 'Pray Dhuhr, Asr, Maghrib, Isha, and Fajr shortened in Mina tents.',
            'desc_ar': 'الصلاة بمنى قصراً بدون جمع والمبيت حتى فجر يوم عرفة.',
            'audio_text': 'Labbayk Allahumma Labbayk, Labbayka La Shareeka Laka Labbayk.'
        },
        {
            'day': 9,
            'title_en': 'Day 9: The Day of Arafat',
            'title_ar': 'يوم عرفة - الوقوف والمغفرة',
            'status': 'active',
            'desc_en': 'Stand at Arafat from Dhuhr until Sunset in supplication, then proceed to Muzdalifah.',
            'desc_ar': 'أعظم أركان الحج: الوقوف بعرفة حتى غروب الشمس ثم النفرة لمزدلفة.',
            'audio_text': 'La ilaha illa Allah wahdahu la shareeka lah, lahul mulk wa lahul hamd.'
        },
        {
            'day': 10,
            'title_en': 'Day 10: Eid & Jamarat Al-Aqaba',
            'title_ar': 'يوم النحر - رمي جمرة العقبة وطواف الإفاضة',
            'status': 'upcoming',
            'desc_en': 'Stone the large pillar (7 pebbles), sacrifice, shave/cut hair, and perform Tawaf Al-Ifadah.',
            'desc_ar': 'رمي الجمرة الكبرى بسبع حصيات، الحلق أو التقصير، وطواف الإفاضة.',
            'audio_text': 'Allahu Akbar, Allahu Akbar, La ilaha illa Allah.'
        },
        {
            'day': 11,
            'title_en': 'Days 11-13: Days of Tashreeq',
            'title_ar': 'أيام التشريق - رمي الجمرات الثلاث',
            'status': 'upcoming',
            'desc_en': 'Stay in Mina and stone all three Jamarat after Dhuhr each day.',
            'desc_ar': 'المبيت بمنى ورمي الجمرات الصغرى والوسطى والكبرى.',
            'audio_text': 'Bismillahi Allahu Akbar Raghman lish-Shaytan.'
        },
    ]

    all_demo_pilgrims = PilgrimProfile.objects.filter(role='pilgrim')

    return render(request, 'accounts/pilgrim_portal.html', {
        'profile': profile,
        'card': nusuk_card,
        'emergency_numbers': emergency_numbers,
        'rituals': rituals,
        'demo_pilgrims': all_demo_pilgrims,
    })

def demo_switch_user(request, username):
    """
    Helper for test examiners to seamlessly switch profiles 
    (e.g., Uncle Rashid vs Fatima Noor vs Operator)
    """
    user = get_object_or_404(User, username=username)
    login(request, user)
    
    if user.profile.role == 'operator':
        return redirect('safety:operations_dashboard')
    return redirect('accounts:pilgrim_portal')


def register_view(request):
    """
    KSU Specification Section 7.1 (Screen 1) & Section 16 (PDPL):
    Register and login: Form, language choice, age band, mobility status, consent agreement.
    """
    from django.utils import timezone
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        language = request.POST.get('language', 'ar')
        nationality = request.POST.get('nationality', 'Saudi Arabia')
        age = int(request.POST.get('age', 35))
        gender = request.POST.get('gender', 'M')
        is_wheelchair = request.POST.get('is_wheelchair_user') == 'on'
        chronic = request.POST.get('chronic_condition', 'NONE')
        blood_type = request.POST.get('blood_type', 'O+')
        em_name = request.POST.get('emergency_contact_name', '').strip()
        em_phone = request.POST.get('emergency_contact_phone', '').strip()
        consent = request.POST.get('consent_given') == 'on'

        if not username:
            username = f"pilgrim_{phone[-4:] if len(phone)>=4 else timezone.now().strftime('%M%S')}"

        user, created = User.objects.get_or_create(username=username, defaults={
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
        })
        if not created and not hasattr(user, 'profile'):
            user.first_name = first_name
            user.last_name = last_name
            user.save()

        profile, p_created = PilgrimProfile.objects.update_or_create(user=user, defaults={
            'role': 'pilgrim',
            'phone': phone,
            'language': language,
            'nationality': nationality,
            'age': age,
            'gender': gender,
            'is_wheelchair_user': is_wheelchair,
            'chronic_condition': chronic,
            'blood_type': blood_type,
            'emergency_contact_name': em_name,
            'emergency_contact_phone': em_phone,
            'consent_given': consent,
            'consent_timestamp': timezone.now(),
        })

        login(request, user)
        return redirect('accounts:pilgrim_portal')

    return render(request, 'accounts/register.html', {
        'chronic_choices': PilgrimProfile.CHRONIC_CHOICES,
        'language_choices': PilgrimProfile.LANGUAGE_CHOICES,
    })


def profile_view(request):
    """
    KSU Specification Section 7.1 (Screen 9) & Section 16:
    Profile: Edit details, language, consent settings.
    """
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        profile = PilgrimProfile.objects.filter(role='pilgrim').first()

    if request.method == 'POST':
        profile.language = request.POST.get('language', profile.language)
        profile.phone = request.POST.get('phone', profile.phone)
        profile.age = int(request.POST.get('age', profile.age))
        profile.is_wheelchair_user = request.POST.get('is_wheelchair_user') == 'on'
        profile.chronic_condition = request.POST.get('chronic_condition', profile.chronic_condition)
        profile.emergency_contact_name = request.POST.get('emergency_contact_name', profile.emergency_contact_name)
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', profile.emergency_contact_phone)
        profile.consent_given = request.POST.get('consent_given') == 'on'
        profile.save()
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'chronic_choices': PilgrimProfile.CHRONIC_CHOICES,
        'language_choices': PilgrimProfile.LANGUAGE_CHOICES,
    })


