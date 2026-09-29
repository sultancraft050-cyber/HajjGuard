import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard
from nusuk.services import NusukService

logger = logging.getLogger(__name__)

@receiver(post_save, sender=PilgrimProfile)
def auto_provision_nusuk_card(sender, instance, created, **kwargs):
    """
    Automated Smart Card Provisioning:
    Whenever a pilgrim profile is created (or missing a smart card),
    automatically provisions a simulated HajjGuard card with a unique reference,
    camp allocation, and cryptographic QR payload.
    """
    if instance.role != 'pilgrim':
        return

    # Check if NusukCard already exists
    if hasattr(instance, 'nusuk_card') and instance.nusuk_card is not None:
        return
    if NusukCard.objects.filter(pilgrim=instance).exists():
        return

    # Find or create a local demo campaign. This is not an official integration.
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

    tasreeh_no = f"TASREEH-1447-{instance.user.id:04d}"
    national_id = f"10{instance.user.id:08d}"

    card = NusukCard(
        pilgrim=instance,
        campaign=campaign,
        tasreeh_no=tasreeh_no,
        border_or_national_id=national_id,
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
    except Exception as e:
        logger.warning(f"Could not generate PNG for QR: {e}")
        
    card.save()
    logger.info(f"Auto-provisioned simulated HajjGuard card {tasreeh_no} for user {instance.user.username}")
