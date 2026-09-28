from zones.models import Zone, Corridor, DensityRecord, LocationPing
from accounts.models import PilgrimProfile

# Re-export core algorithms from modular services package
from services.routing import RoutingEngine
from services.prediction import PredictiveForecaster, predict_zone_density_20min
from services.cctv import CctvPersonCounter, process_cctv_image_secure

class CrowdSimulator:
    """
    Simulates crowd movements, surges, and resets.
    """

    @staticmethod
    def trigger_jamarat_morning_surge():
        """
        Simulates morning stoning rush by surging 34,500 pilgrims into Jamarat Ground Floor (Z-JAMARAT-F0),
        crossing its 30,000 capacity limit into critical RED congestion.
        """
        jamarat_f0 = Zone.objects.filter(code='Z-JAMARAT-F0').first()
        if not jamarat_f0:
            return False

        # Set to congested RED (115% capacity)
        DensityRecord.objects.create(
            zone=jamarat_f0,
            phone_count=18000,
            image_count=16500,
            total_people=34500,
            density_per_sqm=2.88,
            predicted_density_20m=3.50,
            risk_score=88.5,
            status='RED'
        )

        # Set Jamarat 3rd floor as clear bypass option (30% capacity)
        jamarat_f3 = Zone.objects.filter(code='Z-JAMARAT-F3').first()
        if jamarat_f3:
            DensityRecord.objects.create(
                zone=jamarat_f3,
                phone_count=5000,
                image_count=4000,
                total_people=9000,
                density_per_sqm=0.75,
                predicted_density_20m=0.85,
                risk_score=22.0,
                status='GREEN'
            )

        return True

    @staticmethod
    def reset_all_zones_normal():
        """
        Resets Holy Sites and Haram to their authentic real-world state:
        - Haram zones: Synced live from official Saudi SCADA (active Umrah season).
        - Holy Sites (Mina, Jamarat, Muzdalifah, Arafat): Set to 0 (Off-Season / Closed outside of 8-13 Dhul-Hijjah).
        """
        from services.haramain_adapter import HaramainLiveAdapter
        try:
            HaramainLiveAdapter.sync_to_database()
        except Exception:
            pass

        # Outside of Hajj season, holy sites are dormant / off-season (0 headcount)
        for zone in Zone.objects.exclude(site_type='HARAM'):
            DensityRecord.objects.create(
                zone=zone,
                phone_count=0,
                image_count=0,
                total_people=0,
                density_per_sqm=0.0,
                predicted_density_20m=0.0,
                risk_score=0.0,
                status='DORMANT'
            )
        return True
