from django.core.management.base import BaseCommand
from market_place.models import TicketVendor


class Command(BaseCommand):
    help = 'Synchronize vendor verification status fields'

    def handle(self, *args, **kwargs):
        vendors = TicketVendor.objects.all()
        updated_count = 0
        
        for vendor in vendors:
            old_status = vendor.verification_status
            
            # Sync based on is_verified
            if vendor.is_verified:
                vendor.verification_status = 'approved'
            elif vendor.rejection_reason:
                vendor.verification_status = 'rejected'
                vendor.is_verified = False
            else:
                vendor.verification_status = 'pending'
                vendor.is_verified = False
            
            if old_status != vendor.verification_status:
                vendor.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated {vendor.brand_name}: {old_status} → {vendor.verification_status}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully synchronized {updated_count} vendor(s)'
            )
        )