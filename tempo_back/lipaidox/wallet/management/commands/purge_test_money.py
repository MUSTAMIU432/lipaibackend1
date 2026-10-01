"""
Remove test money — wallet credit that no real payment ever backed.

Before NBC went live, top-ups ran through the `simulated` gateway (or were
credited directly), so fans hold balances and purchases that never cost
anyone anything. This removes them:

    python manage.py purge_test_money            # dry run: lists what would go
    python manage.py purge_test_money --apply    # does it

A fan is "test-only" when they have no successful charge on a real gateway
(anything but `simulated`). Fans with real money are never touched — they're
listed for a manual look instead. For each test-only fan:

  * every purchase they made is reversed on the creator side (pending, then
    available balance, and the earnings totals `settle` added);
  * PPV unlocks are deleted (the content re-locks) and the content's
    purchase count / revenue corrected;
  * their ledger rows and simulated charges are deleted;
  * the wallet goes to 0 / 0 / 0.

Other purchase kinds (subscriptions, credits, tips, live entry) get their
money reversed too, but what they bought is listed rather than guessed at.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from lipaidox.payment.models import Charge, ChargeStatus
from lipaidox.wallet.models import CreatorWallet, FanWallet, Transaction, TransactionType

ZERO = Decimal("0")

_EARNINGS_FIELD = {
    TransactionType.PPV_PURCHASE: "earnings_from_ppv",
    TransactionType.SUBSCRIPTION: "earnings_from_subscriptions",
    TransactionType.TIP: "earnings_from_tips",
    TransactionType.CREDIT_PURCHASE: "earnings_from_credits",
    TransactionType.LIVE_ENTRY: "earnings_from_live_streams",
}


def _has_real_money(user) -> bool:
    return Charge.objects.filter(user=user, status=ChargeStatus.SUCCEEDED).exclude(gateway="simulated").exists()


def _reverse_creator_side(txn: Transaction) -> str | None:
    """Takes the purchase's net share back out of the creator's wallet. Returns a warning, if any."""
    if txn.creator_id is None or not txn.net_amount:
        return None
    wallet = CreatorWallet.objects.select_for_update().filter(creator_id=txn.creator_id, currency=txn.currency).first()
    if wallet is None:
        return None
    net = Decimal(txn.net_amount)
    from_pending = min(net, wallet.pending_balance)
    from_available = min(net - from_pending, wallet.available_balance)
    wallet.pending_balance -= from_pending
    wallet.available_balance -= from_available
    wallet.lifetime_earnings = max(ZERO, wallet.lifetime_earnings - net)
    field = _EARNINGS_FIELD.get(txn.transaction_type)
    if field:
        setattr(wallet, field, max(ZERO, getattr(wallet, field) - net))
    wallet.save()
    shortfall = net - from_pending - from_available
    if shortfall > 0:
        return f"creator wallet {wallet.pk} was short {shortfall} (already paid out?) — check by hand"
    return None


class Command(BaseCommand):
    help = "Remove wallet money and purchases that no real payment backed (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually delete. Without it, only report.")

    def handle(self, *args, apply=False, **options):
        from lipaidox.ppv.models import PPVPurchase

        mode = "APPLYING" if apply else "DRY RUN — nothing will change (add --apply)"
        self.stdout.write(self.style.WARNING(mode))

        wallets = FanWallet.objects.select_related("user").filter(
            user__isnull=False
        ).exclude(balance=0, lifetime_topup=0, lifetime_spent=0)
        test_fans, skipped = [], []
        for w in wallets:
            (skipped if _has_real_money(w.user) else test_fans).append(w)

        totals = {"wallets": 0, "balance": ZERO, "purchases": 0, "ppv_unlocks": 0, "charges": 0}
        warnings: list[str] = []

        for w in test_fans:
            user = w.user
            txns = list(Transaction.objects.filter(fan=user))
            charges = Charge.objects.filter(user=user, gateway="simulated")
            ppv_ids = [t.ppv_purchase_id for t in txns if t.ppv_purchase_id]
            self.stdout.write(
                f"• {user.username}: balance {w.balance}, topped up {w.lifetime_topup}, "
                f"{len(txns)} purchase(s), {charges.count()} simulated charge(s)"
            )
            for t in txns:
                self.stdout.write(f"    - {t.transaction_type} {t.gross_amount} {t.currency}: {t.description or ''}")
                if t.transaction_type not in (TransactionType.PPV_PURCHASE,):
                    warnings.append(
                        f"{user.username}: {t.transaction_type} {t.gross_amount} reversed, but what it bought "
                        f"(id {t.subscription_payment_id or t.credit_purchase_id or t.tip_id or '—'}) was left in place"
                    )

            totals["wallets"] += 1
            totals["balance"] += w.balance
            totals["purchases"] += len(txns)
            totals["ppv_unlocks"] += len(ppv_ids)
            totals["charges"] += charges.count()
            if not apply:
                continue

            with transaction.atomic():
                for t in txns:
                    warn = _reverse_creator_side(t)
                    if warn:
                        warnings.append(f"{user.username}: {warn}")
                for p in PPVPurchase.objects.filter(id__in=ppv_ids).select_related("content"):
                    content = p.content
                    if content is not None:
                        type(content).objects.filter(pk=content.pk).update(
                            purchase_count=F("purchase_count") - 1,
                            total_revenue=F("total_revenue") - p.amount_paid,
                        )
                    p.delete()
                Transaction.objects.filter(id__in=[t.id for t in txns]).delete()
                charges.delete()
                FanWallet.objects.filter(pk=w.pk).update(balance=0, lifetime_topup=0, lifetime_spent=0)

        self.stdout.write("")
        self.stdout.write(
            f"{'Removed' if apply else 'Would remove'}: {totals['wallets']} wallet(s) holding {totals['balance']}, "
            f"{totals['purchases']} purchase(s) ({totals['ppv_unlocks']} PPV unlock(s)), "
            f"{totals['charges']} simulated charge(s)."
        )
        for w in skipped:
            self.stdout.write(self.style.NOTICE(f"Skipped {w.user.username}: has real payments (balance {w.balance}) — review by hand."))
        for msg in warnings:
            self.stdout.write(self.style.WARNING(f"! {msg}"))
