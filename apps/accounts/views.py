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

