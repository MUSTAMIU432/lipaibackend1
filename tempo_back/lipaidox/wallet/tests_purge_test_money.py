"""
purge_test_money: test-only fans lose their unbacked balance and purchases,
creators lose the earnings those purchases paid them, real-money fans are
left alone.

    ./test.sh db lipaidox.wallet.tests_purge_test_money
"""
from decimal import Decimal as D
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from lipaidox.auth.models import User
from lipaidox.content.models import Content
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.payment.models import Charge, ChargePurpose, ChargeStatus
from lipaidox.ppv.models import PPVPurchase
from lipaidox.wallet.models import CreatorWallet, FanWallet, Transaction, TransactionType
from lipaidox.wallet.services import credit_fan_wallet, settle


class PurgeTestMoneyTests(TestCase):
    def setUp(self):
        creator_user = User.objects.create_user(username="cre", email="cre@example.com", password="x", role="creator")
        self.creator = CreatorProfile.objects.create(user=creator_user, username="cre")
        self.content = Content.objects.create(creator=self.creator, title="Advanced tech project", status="published")

        self.fan = User.objects.create_user(username="fan", email="fan@example.com", password="x", role="fan")
        credit_fan_wallet(self.fan, D("197.38"))  # test money: no real charge behind it
        self.buy(self.fan, D("9.99"))

        self.real = User.objects.create_user(username="real", email="real@example.com", password="x", role="fan")
        Charge.objects.create(user=self.real, gateway="nbc", amount=D("20"), purpose=ChargePurpose.WALLET_TOPUP, status=ChargeStatus.SUCCEEDED)
        credit_fan_wallet(self.real, D("20"))

    def buy(self, user, amount):
        purchase = PPVPurchase(fan=user, content=self.content, creator=self.creator, amount_paid=amount, currency="USD",
                               platform_fee_percent=D("15"))
        purchase.calculate_fees()
        purchase.save()
        settle(fan_user=user, creator_profile=self.creator, gross=amount, fee_percent=D("15"),
               tx_type=TransactionType.PPV_PURCHASE, description="PPV unlock", ppv_purchase_id=purchase.id)
        Content.objects.filter(pk=self.content.pk).update(purchase_count=1, total_revenue=amount)

    def run_cmd(self, *args):
        out = StringIO()
        call_command("purge_test_money", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        out = self.run_cmd()
        self.assertIn("Would remove: 1 wallet(s)", out)
        self.assertEqual(FanWallet.objects.get(user=self.fan).balance, D("187.39"))
        self.assertTrue(PPVPurchase.objects.filter(fan=self.fan).exists())

    def test_apply_removes_test_money_and_reverses_creator(self):
        creator_before = CreatorWallet.objects.get(creator=self.creator)
        self.assertGreater(creator_before.pending_balance, 0)

        self.run_cmd("--apply")

        w = FanWallet.objects.get(user=self.fan)
        self.assertEqual((w.balance, w.lifetime_topup, w.lifetime_spent), (0, 0, 0))
        self.assertFalse(PPVPurchase.objects.filter(fan=self.fan).exists())
        self.assertFalse(Transaction.objects.filter(fan=self.fan).exists())
        cw = CreatorWallet.objects.get(creator=self.creator)
        self.assertEqual(cw.pending_balance, 0)
        self.assertEqual(cw.lifetime_earnings, 0)
        self.assertEqual(cw.earnings_from_ppv, 0)
        self.content.refresh_from_db()
        self.assertEqual(self.content.purchase_count, 0)

    def test_real_money_fan_is_skipped(self):
        out = self.run_cmd("--apply")
        self.assertIn("Skipped real", out)
        self.assertEqual(FanWallet.objects.get(user=self.real).balance, D("20"))
