import json
import qrcode
import io
from django.core.files.base import ContentFile
from accounts.models import PilgrimProfile
from nusuk.models import HajjCampaign, NusukCard

class NusukService:
    """
    Nusuk Masar API Service Adapter.
    Simulates the official Ministry of Hajj & Umrah B2B API gateway
    with exact production payload structures.
    """

    @staticmethod
    def generate_nusuk_qr(nusuk_card):
        """
        Generates a high-resolution QR code PNG containing the official Nusuk card payload
        """
        payload = nusuk_card.generate_qr_payload()
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#0d5c3a", back_color="white") # Official Saudi Green
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        file_name = f"nusuk_{nusuk_card.tasreeh_no}.png"
        nusuk_card.qr_code_image.save(file_name, ContentFile(buffer.getvalue()), save=False)

    @staticmethod
    def parse_qr_payload(qr_text):
        """
        Parses and validates a scanned QR code text payload
        """
        try:
            data = json.loads(qr_text)
            if data.get("type") == "NUSUK_SMART_CARD" and data.get("token"):
                card = NusukCard.objects.filter(qr_token=data["token"], is_valid=True).first()
                if card:
                    return True, data
                return False, "QR token is unknown or revoked"
            return False, "Not a valid Nusuk Smart Card QR code"
        except Exception as e:
            return False, f"Failed to parse QR data: {str(e)}"
