from django.core.management.base import BaseCommand
from services.haramain_adapter import HaramainLiveAdapter

class Command(BaseCommand):
    help = "Syncs real-world live crowd density and Tawaf duration from the official Saudi Two Holy Mosques Authority API"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Connecting to official Saudi Haramain SCADA API (trasul.gph.gov.sa)..."))
        res = HaramainLiveAdapter.sync_to_database()

        if res["success"]:
            self.stdout.write(self.style.SUCCESS(f"Successfully synced {res['synced_sectors']} Holy Mosque sectors from live Saudi SCADA!"))
            for r in res.get("records", []):
                self.stdout.write(f" -> Zone: {r['zone_code']} | Live Headcount: {r['headcount']} | Lap Time: {r['expected_minutes']} mins | Status: {r['status']}")
        else:
            self.stdout.write(self.style.ERROR(f"Sync failed: {res.get('error')}"))
