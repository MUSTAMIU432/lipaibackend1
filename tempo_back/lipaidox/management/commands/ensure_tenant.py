from django.core.management.base import BaseCommand

from lipaidox.tenant_setup import configured_tenant, ensure_tenant


class Command(BaseCommand):
    help = "Create the app's tenant (DEFAULT_TENANT_ID / _NAME / _DOMAIN) if it does not exist."

    def handle(self, *args, **options):
        tenant, created = ensure_tenant()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Already present'}: {tenant.id} ({tenant.name}, {tenant.domain})"
            )
        )
        if str(tenant.id) != str(configured_tenant()["id"]):
            self.stderr.write("Tenant id mismatch with configuration.")
