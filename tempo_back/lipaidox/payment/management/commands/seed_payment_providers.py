from django.core.management.base import BaseCommand
from lipaidox.payment.models import MobileMoneyProvider

class Command(BaseCommand):
    help = 'Seeds mobile money providers'

    def handle(self, *args, **kwargs):
        providers = [
            ('M-Pesa', 'Kenya',        'KE', '+254'),
            ('M-Pesa', 'Tanzania',     'TZ', '+255'),
            ('M-Pesa', 'Mozambique',   'MZ', '+258'),
            ('MTN MoMo', 'Ghana',      'GH', '+233'),
            ('Vodafone Cash', 'Egypt', 'EG', '+20'),
        ]

        for name, country, code, dial in providers:
            provider, created = MobileMoneyProvider.objects.get_or_create(
                provider_name=name,
                country_code=code,
                defaults={'country_name': country, 'dial_code': dial}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created provider: {name} ({country})'))
            else:
                self.stdout.write(self.style.WARNING(f'Provider already exists: {name} ({country})'))

        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
