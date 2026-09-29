from django.core.management.base import BaseCommand
from services.haramain_adapter import HaramainLiveAdapter

class Command(BaseCommand):
    help = "Refreshes local synthetic crowd density and Tawaf demonstration values"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Refreshing local synthetic Haramain demonstration values..."))
        res = HaramainLiveAdapter.sync_to_database()

        if res["success"]:
            self.stdout.write(self.style.SUCCESS(f"Updated {res['synced_sectors']} local synthetic sectors."))
            for r in res.get("records", []):
                self.stdout.write(f" -> Zone: {r['zone_code']} | Live Headcount: {r['headcount']} | Lap Time: {r['expected_minutes']} mins | Status: {r['status']}")
        else:
            self.stdout.write(self.style.ERROR(f"Sync failed: {res.get('error')}"))
