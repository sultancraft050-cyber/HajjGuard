from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import PilgrimProfile
from nusuk.models import NusukCard
from safety.models import EmergencyContact

@login_required(login_url='/accounts/login/')
def pilgrim_portal(request):
    """
    Renders the tactile, accessible mobile-friendly Pilgrim Portal.
    Defaults to 'rashid' demo pilgrim if not authenticated.
    """
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return HttpResponse('A pilgrim profile is required.', status=404)

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

    return render(request, 'accounts/pilgrim_portal.html', {
        'profile': profile,
        'card': nusuk_card,
        'emergency_numbers': emergency_numbers,
        'rituals': rituals,
        'demo_pilgrims': (),
    })

def register_view(request):
    """
    KSU Specification Section 7.1 (Screen 1) & Section 16 (PDPL):
    Register and login: Form, language choice, age band, mobility status, consent agreement.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        language = request.POST.get('language', 'ar')
        nationality = request.POST.get('nationality', 'Saudi Arabia')
        try:
            age = int(request.POST.get('age', 35))
        except (TypeError, ValueError):
            return HttpResponse('Invalid age.', status=400)
        gender = request.POST.get('gender', 'M')
        is_wheelchair = request.POST.get('is_wheelchair_user') == 'on'
        chronic = request.POST.get('chronic_condition', 'NONE')
        blood_type = request.POST.get('blood_type', 'O+')
        em_name = request.POST.get('emergency_contact_name', '').strip()
        em_phone = request.POST.get('emergency_contact_phone', '').strip()
        consent = request.POST.get('consent_given') == 'on'
        password = request.POST.get('password', '')

        if not username or len(password) < 12 or not consent:
            return HttpResponse('Username, a password of at least 12 characters, and explicit consent are required.', status=400)
        if not 5 <= age <= 110:
            return HttpResponse('Age must be between 5 and 110.', status=400)
        if User.objects.filter(username=username).exists():
            return HttpResponse('Username is already registered.', status=409)

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password,
                first_name=first_name, last_name=last_name, email=email)
            PilgrimProfile.objects.create(user=user, role='pilgrim', phone=phone,
                language=language, nationality=nationality, age=age, gender=gender,
                is_wheelchair_user=is_wheelchair, chronic_condition=chronic,
                blood_type=blood_type, emergency_contact_name=em_name,
                emergency_contact_phone=em_phone, consent_given=True,
                consent_timestamp=timezone.now())

        login(request, user)
        return redirect('accounts:pilgrim_portal')

    return render(request, 'accounts/register.html', {
        'chronic_choices': PilgrimProfile.CHRONIC_CHOICES,
        'language_choices': PilgrimProfile.LANGUAGE_CHOICES,
    })


@login_required(login_url='/accounts/login/')
def profile_view(request):
    """
    KSU Specification Section 7.1 (Screen 9) & Section 16:
    Profile: Edit details, language, consent settings.
    """
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return HttpResponse('A pilgrim profile is required.', status=404)

    if request.method == 'POST':
        profile.language = request.POST.get('language', profile.language)
        profile.phone = request.POST.get('phone', profile.phone)
        try:
            profile.age = int(request.POST.get('age', profile.age))
        except (TypeError, ValueError):
            return HttpResponse('Invalid age.', status=400)
        if not 5 <= profile.age <= 110:
            return HttpResponse('Age must be between 5 and 110.', status=400)
        profile.is_wheelchair_user = request.POST.get('is_wheelchair_user') == 'on'
        profile.chronic_condition = request.POST.get('chronic_condition', profile.chronic_condition)
        profile.emergency_contact_name = request.POST.get('emergency_contact_name', profile.emergency_contact_name)
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', profile.emergency_contact_phone)
        profile.consent_given = request.POST.get('consent_given') == 'on'
        profile.consent_timestamp = timezone.now() if profile.consent_given else None
        profile.save()
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'chronic_choices': PilgrimProfile.CHRONIC_CHOICES,
        'language_choices': PilgrimProfile.LANGUAGE_CHOICES,
    })


