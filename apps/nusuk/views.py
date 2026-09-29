import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from accounts.models import PilgrimProfile, AuditLog
from nusuk.models import NusukCard, HajjCampaign
from nusuk.services import NusukService
from services.fiqh_ai import NusukFiqhAI

def get_or_create_demo_card(user):
    """Retrieves or provisions a NusukCard for user."""
    profile = getattr(user, 'profile', None) if user.is_authenticated else None
    if profile:
        card = NusukCard.objects.filter(pilgrim=profile).first()
        if not card:
            campaign = HajjCampaign.objects.first()
            if not campaign:
                campaign = HajjCampaign.objects.create(
                    license_no="CAMP-SA-2026",
                    name_en="Al-Rajhi Pilgrim Hospitality",
                    name_ar="مؤسسة الراجحي لخدمة ضيوف الرحمن",
                    country="Saudi Arabia",
                    assigned_mina_sector="Sector 3 (Al-Muaisem)",
                    mina_camp_no="Camp 44",
                    leader_name="Sheikh Abdullah Al-Ghamdi",
                    leader_phone="+966501112233",
                    quota=3000,
                    join_code="RAJHI-1"
                )
            card = NusukCard.objects.create(
                pilgrim=profile,
                campaign=campaign,
                tasreeh_no=f"TASREEH-1447-{profile.user.id:04d}",
                border_or_national_id=f"10{profile.user.id:08d}",
                tafweej_jamarat_slot="10 Dhul-Hijjah 08:30 - 09:30",
                assigned_jamarat_floor=2,
                tent_street_no="Street 204",
                makkah_hotel_name="Swissotel Al Maqam Makkah",
                is_valid=True
            )
            card.get_barcode_code()
            card.generate_qr_payload()
            try:
                NusukService.generate_nusuk_qr(card)
            except Exception:
                pass
            card.save()
        return card
    return None


@login_required(login_url='/accounts/login/')
def digital_card_view(request):
    """
    Renders the local simulated HajjGuard card interface.
    Features Apple/Google Wallet 3D flip styling, holographic chip, Code-128 laser barcode,
    scannable QR code, and offline printable pass simulation.
    """
    card = get_or_create_demo_card(request.user)
    
    # Audit log entry for PDPL compliance if viewing record
    if request.user.is_authenticated and card:
        AuditLog.objects.create(
            user=request.user,
            action='VIEW_PILGRIM',
            target=f"Digital Nusuk Card #{card.tasreeh_no}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    context = {
        'card': card,
        'profile': card.pilgrim if card else None,
        'barcode_code': card.get_barcode_code() if card else 'NSK890192',
        'active_menu': 'nusuk_card'
    }
    return render(request, 'nusuk/digital_card.html', context)


@login_required(login_url='/accounts/login/')
@require_GET
def api_card_details(request):
    """Returns the minimum card data needed by the authenticated owner."""
    card = get_or_create_demo_card(request.user)
    if not card:
        return JsonResponse({'status': 'error', 'message': 'No card found'}, status=404)
        
    return JsonResponse({
        'status': 'success',
        'card': {
            'tasreeh_no': card.tasreeh_no,
            'campaign': card.campaign.name_en,
            'campaign_ar': card.campaign.name_ar,
            'camp': f"{card.campaign.assigned_mina_sector} - {card.campaign.mina_camp_no}",
            'tent_street_no': card.tent_street_no,
            'makkah_hotel': card.makkah_hotel_name,
            'assigned_jamarat_floor': card.assigned_jamarat_floor,
            'tafweej_slot': card.tafweej_jamarat_slot,
            'barcode': card.get_barcode_code(),
            'qr_image_url': card.qr_code_image.url if card.qr_code_image else None,
            'is_valid': card.is_valid
        }
    })


@login_required(login_url='/accounts/login/')
@require_POST
def api_nusuk_ai_chat(request):
    """
    Nusuk AI Fiqh & Ritual Copilot API endpoint.
    Handles inquiries regarding Islamic jurisprudence, rituals, concessions, and live crowd status.
    """
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        language = data.get('language', 'ar')
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid payload: {str(e)}'}, status=400)

    if not question:
        return JsonResponse({'status': 'error', 'message': 'Question cannot be empty'}, status=400)

    profile = getattr(request.user, 'profile', None) if request.user.is_authenticated else None

    # Get authoritative guidance
    result = NusukFiqhAI.answer_query(
        question=question,
        user_profile=profile,
        language=language
    )

    return JsonResponse(result)
