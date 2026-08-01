from django.apps import AppConfig

class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lipaidox.wallet'
    label = 'lipaidox_wallet'
    verbose_name = 'Wallet & Payouts'
