"""
Premium Live billing — 100 credits = $10 = 15 min (one credit per 9 seconds).

Needs a real PostgreSQL database (the schema uses Postgres-only column types), so run
it with the project's schema-isolated runner rather than the stock one:

    ./test.sh db --keepdb
    # or: ./myenv/bin/python manage.py test --settings=lipaidox_backend.test_settings lipaidox.credits.tests

Time is passed in explicitly (`now=`) so a 27-minute stream doesn't take 27 minutes.
"""
from datetime import timedelta
from decimal import Decimal as D

from django.apps import apps as global_apps
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from lipaidox.auth.models import User
from lipaidox.creator_plans.models import CreatorPlan
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.live_streaming.models import LiveStream, LiveStreamStatus

from . import live_billing as lb
from .models import (
    CreatorCreditLedger, CreatorCreditWallet, CreditTransactionType, LiveBillingEvent,
    LiveCreditReservation, ReservationStatus,
)


class MathTests(SimpleTestCase):
    def test_prd_reference_values(self):
        self.assertEqual(lb.credits_for_seconds(900), D("100"))      # 15 min = 100 credits
        self.assertEqual(lb.credits_for_seconds(1620), D("180"))     # 27 min = 180 credits
        self.assertEqual(lb.credits_for_seconds(300), D("33.333333"))  # PRD: 5 min = 33.33
        self.assertEqual(lb.credits_for_seconds(600), D("66.666667"))  # PRD: 10 min = 66.67
        self.assertEqual(lb.seconds_for_credits(1000), 9000)         # 2h 30m
        self.assertEqual(lb.seconds_for_credits(320), 2880)          # 48 minutes
        self.assertEqual(lb.seconds_for_credits(D("0.5")), 4)        # rounds DOWN — never over-promises
        self.assertEqual(lb.usd_for_credits(100), D("10.00"))

    def test_round_trip_is_exact_on_whole_credits(self):
        for credits in (1, 7, 100, 2500):
            self.assertEqual(lb.credits_for_seconds(lb.seconds_for_credits(credits)), D(credits))


class EngineTests(TestCase):
    def setUp(self):
        # Plans are catalog data a deployment may have seeded; these tests state
        # their own plans, so start from none (rolled back with the test).
        CreatorPlan.objects.all().delete()
        self.t0 = timezone.now().replace(microsecond=0)
        self.user = User.objects.create_user(username="cr1", email="cr1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=self.user, username="cr1")
        self.wallet = lb.get_or_create_wallet(self.profile)

    def fund(self, credits, free=0):
        if credits:
            self.wallet.add_purchased_credits(credits)
        if free:
            self.wallet.set_monthly_allocation(free)
        self.wallet.refresh_from_db()

    def go_live(self):
        stream = LiveStream.objects.create(creator=self.profile, title="s")
        stream.status = LiveStreamStatus.LIVE
        stream.started_at = self.t0
        stream.save()
        lb.start_billing(stream, now=self.t0)
        return stream

    def at(self, seconds):
        return self.t0 + timedelta(seconds=seconds)

    def wallet_now(self):
        self.wallet.refresh_from_db()
        return self.wallet

    # ── start ────────────────────────────────────────────────────────────────

    def test_start_reserves_100_and_holds_it(self):
        self.fund(500)
        stream = self.go_live()
        res = stream.credit_reservation
        self.assertEqual(res.credits_reserved, D("100"))
        w = self.wallet_now()
        self.assertEqual(w.reserved_credits, D("100"))
        self.assertEqual(w.total_available_credits, D("500"))   # nothing spent yet
        self.assertEqual(w.spendable_credits, D("400"))         # 100 is held

    def test_start_is_idempotent(self):
        self.fund(500)
        stream = self.go_live()
        again = lb.start_billing(stream, now=self.t0)
        self.assertEqual(again.pk, stream.credit_reservation.pk)
        self.assertEqual(self.wallet_now().reserved_credits, D("100"))

    def test_start_reserves_only_what_exists(self):
        self.fund(40)
        self.assertEqual(self.go_live().credit_reservation.credits_reserved, D("40"))

    def test_start_refused_below_minimum(self):
        self.fund(5)
        stream = LiveStream.objects.create(creator=self.profile, title="s", status=LiveStreamStatus.LIVE, started_at=self.t0)
        with self.assertRaises(lb.BillingError) as ctx:
            lb.start_billing(stream, now=self.t0)
        self.assertEqual(ctx.exception.code, "INSUFFICIENT_CREDITS")
        self.assertEqual(self.wallet_now().reserved_credits, D("0"))

    def test_second_live_at_once_refused(self):
        self.fund(500)
        self.go_live()
        other = LiveStream.objects.create(creator=self.profile, title="b", status=LiveStreamStatus.LIVE, started_at=self.t0)
        with self.assertRaises(lb.BillingError) as ctx:
            lb.start_billing(other, now=self.t0)
        self.assertEqual(ctx.exception.code, "ALREADY_LIVE")

    def test_plan_without_live_is_refused(self):
        CreatorPlan.objects.create(tier="free", name="Free", can_live_stream=False)
        self.fund(500)
        stream = LiveStream.objects.create(creator=self.profile, title="s", status=LiveStreamStatus.LIVE, started_at=self.t0)
        with self.assertRaises(lb.BillingError) as ctx:
            lb.start_billing(stream, now=self.t0)
        self.assertEqual(ctx.exception.code, "PLAN_NO_LIVE")

    # ── the PRD's worked example ─────────────────────────────────────────────

    def test_prd_example_27_minutes_500_credits(self):
        self.fund(500)
        stream = self.go_live()
        # 27 minutes of heartbeats every 10 s: exceeds the 100-credit hold, so it extends.
        for i in range(1, 163):
            snap = lb.heartbeat(stream.id, self.profile, i, now=self.at(i * 10))
        self.assertEqual(snap.credits_consumed, D("180"))
        lb.settle(stream, now=self.at(1620))

        w = self.wallet_now()
        self.assertEqual(w.total_available_credits, D("320"))    # 500 - 180
        self.assertEqual(w.reserved_credits, D("0"))             # hold fully released
        self.assertEqual(lb.seconds_for_credits(w.total_available_credits), 2880)  # 48 min left

        entry = CreatorCreditLedger.objects.get(transaction_type=CreditTransactionType.LIVE_USAGE)
        self.assertEqual(entry.credits_delta, D("-180"))
        self.assertEqual((entry.credits_before, entry.credits_after), (D("500"), D("320")))

        stream.refresh_from_db()
        self.assertEqual(stream.status, LiveStreamStatus.ENDED)
        self.assertEqual(stream.duration_seconds, 1620)
        self.assertEqual(stream.credits_used, D("180"))
        self.assertEqual(stream.end_reason, "creator_ended")

    # ── heartbeat ────────────────────────────────────────────────────────────

    def test_client_cannot_shorten_the_bill(self):
        """Only the server clock counts: a heartbeat sent 'early' bills real elapsed time."""
        self.fund(500)
        stream = self.go_live()
        snap = lb.heartbeat(stream.id, self.profile, 1, now=self.at(900))
        self.assertEqual(snap.credits_consumed, D("100"))

    def test_duplicate_and_replayed_sequences_bill_once(self):
        self.fund(500)
        stream = self.go_live()
        first = lb.heartbeat(stream.id, self.profile, 5, now=self.at(90))
        replay = lb.heartbeat(stream.id, self.profile, 5, now=self.at(400))   # same sequence, later
        older = lb.heartbeat(stream.id, self.profile, 3, now=self.at(500))    # lower sequence
        self.assertEqual(first.credits_consumed, D("10"))
        self.assertEqual(replay.credits_consumed, D("10"))
        self.assertEqual(older.credits_consumed, D("10"))
        self.assertEqual(LiveBillingEvent.objects.count(), 1)

    def test_low_credit_warning_at_five_minutes(self):
        self.fund(40)                                  # 40 credits = 360 s
        stream = self.go_live()
        early = lb.heartbeat(stream.id, self.profile, 1, now=self.at(30))    # 330 s left
        self.assertFalse(early.low_credit)
        late = lb.heartbeat(stream.id, self.profile, 2, now=self.at(120))    # 240 s left
        self.assertTrue(late.low_credit)
        self.assertEqual(late.remaining_seconds, 240)

    def test_exhaustion_ends_stream_and_never_overdraws(self):
        self.fund(30)                                  # 270 s of live time
        stream = self.go_live()
        lb.heartbeat(stream.id, self.profile, 1, now=self.at(200))
        snap = lb.heartbeat(stream.id, self.profile, 2, now=self.at(400))    # past the end
        self.assertTrue(snap.terminated)
        self.assertEqual(snap.end_reason, "credit_exhausted")
        self.assertEqual(snap.credits_consumed, D("30"))                     # capped
        w = self.wallet_now()
        self.assertEqual(w.total_available_credits, D("0"))
        self.assertEqual(w.reserved_credits, D("0"))
        stream.refresh_from_db()
        self.assertEqual(stream.status, LiveStreamStatus.ENDED)
        self.assertEqual(stream.end_reason, "credit_exhausted")
        # A heartbeat after termination is harmless.
        again = lb.heartbeat(stream.id, self.profile, 3, now=self.at(500))
        self.assertTrue(again.terminated)
        self.assertEqual(self.wallet_now().total_available_credits, D("0"))

    # ── settle ───────────────────────────────────────────────────────────────

    def test_settle_releases_unused_hold(self):
        self.fund(500)
        stream = self.go_live()
        lb.heartbeat(stream.id, self.profile, 1, now=self.at(300))           # 33.333333 used
        lb.settle(stream, now=self.at(300))
        res = LiveCreditReservation.objects.get(live_stream=stream)
        self.assertEqual(res.status, ReservationStatus.SETTLED)
        self.assertEqual(res.credits_released, D("100") - D("33.333333"))
        w = self.wallet_now()
        self.assertEqual(w.total_available_credits, D("500") - D("33.333333"))
        self.assertEqual(w.spendable_credits, w.total_available_credits)

    def test_settle_twice_charges_once(self):
        self.fund(500)
        stream = self.go_live()
        lb.settle(stream, now=self.at(900))
        lb.settle(stream, now=self.at(1800))
        self.assertEqual(self.wallet_now().total_available_credits, D("400"))
        self.assertEqual(CreatorCreditLedger.objects.filter(transaction_type="live_usage").count(), 1)

    def test_free_monthly_credits_are_spent_first(self):
        self.fund(100, free=50)
        stream = self.go_live()
        lb.settle(stream, now=self.at(450))                                   # 50 credits
        w = self.wallet_now()
        self.assertEqual(w.free_monthly_credits, D("0"))
        self.assertEqual(w.purchased_credits, D("100"))

    def test_stream_that_never_billed_is_just_ended(self):
        stream = LiveStream.objects.create(creator=self.profile, title="x", status=LiveStreamStatus.LIVE, started_at=self.t0)
        self.assertIsNone(lb.settle(stream, now=self.at(60)))
        stream.refresh_from_db()
        self.assertEqual(stream.status, LiveStreamStatus.ENDED)

    # ── sweeper ──────────────────────────────────────────────────────────────

    def test_sweeper_ends_dropped_connection_billed_to_last_heartbeat(self):
        self.fund(500)
        stream = self.go_live()
        lb.heartbeat(stream.id, self.profile, 1, now=self.at(90))            # 10 credits
        summary = lb.bill_active_sessions(now=self.at(90 + lb.STALE_HEARTBEAT_SECONDS + 30))
        self.assertEqual(summary["ended_lost"], 1)
        stream.refresh_from_db()
        self.assertEqual(stream.end_reason, "connection_lost")
        self.assertEqual(self.wallet_now().total_available_credits, D("490"))  # billed to t=90 only

    def test_sweeper_bills_a_session_that_never_heartbeated(self):
        self.fund(500)
        stream = self.go_live()
        summary = lb.bill_active_sessions(now=self.at(900))
        self.assertEqual(summary["billed"], 1)
        res = LiveCreditReservation.objects.get(live_stream=stream)
        self.assertEqual(res.credits_consumed, D("100"))
        self.assertEqual(res.status, ReservationStatus.ACTIVE)

    # ── ledger & wallet invariants ───────────────────────────────────────────

    def test_ledger_chain_is_unbroken(self):
        self.fund(500, free=20)
        stream = self.go_live()
        lb.settle(stream, now=self.at(450))
        rows = list(CreatorCreditLedger.objects.order_by("created_at"))
        for prev, cur in zip(rows, rows[1:]):
            self.assertEqual(prev.credits_after, cur.credits_before)
        self.assertEqual(rows[-1].credits_after, self.wallet_now().total_available_credits)

    def test_hold_cannot_exceed_balance(self):
        from django.db import IntegrityError, transaction
        self.fund(50)
        self.wallet.reserved_credits = D("51")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.wallet.save()


class RateMigrationTests(TestCase):
    def test_existing_balances_convert_to_prd_rate_with_one_ledger_row(self):
        from importlib import import_module

        user = User.objects.create_user(username="old", email="old@example.com", password="x", role="creator")
        profile = CreatorProfile.objects.create(user=user, username="old")
        wallet = CreatorCreditWallet.objects.create(
            creator=profile, purchased_credits=D("3"), free_monthly_credits=D("1"), total_credits_used=D("2"),
        )
        before = wallet.total_available_credits          # 4 old credits = 60 minutes

        import_module("lipaidox.credits.migrations.0003_convert_balances_to_prd_rate").convert(global_apps, None)

        wallet.refresh_from_db()
        self.assertEqual(wallet.purchased_credits, D("300"))
        self.assertEqual(wallet.free_monthly_credits, D("100"))
        self.assertEqual(wallet.total_credits_used, D("200"))
        self.assertEqual(lb.seconds_for_credits(wallet.total_available_credits), 3600)  # still 60 min
        row = CreatorCreditLedger.objects.get(wallet=wallet)
        self.assertEqual((row.credits_before, row.credits_after, row.credits_delta), (before, D("400"), D("396")))


# ═════════════════════════════════════════════════════════════════════════════
# GraphQL API — transactions, idempotent purchases, admin tools, reports, audit
# ═════════════════════════════════════════════════════════════════════════════

from types import SimpleNamespace as NS  # noqa: E402

from lipaidox_backend.schema import schema  # noqa: E402

from .models import CreditPackage, CreditPurchase, CreditType, FinancialAuditLog  # noqa: E402


def gql(user, query, variables=None):
    """Run a query through the real schema as `user`; returns (data, errors)."""
    request = NS(user=user, META={"REMOTE_ADDR": "10.0.0.7", "HTTP_USER_AGENT": "tests"})
    result = schema.execute_sync(query, variable_values=variables or {}, context_value=NS(request=request))
    return result.data, [str(e) for e in (result.errors or [])]


class ApiTests(TestCase):
    def setUp(self):
        CreatorPlan.objects.all().delete()
        self.t0 = timezone.now().replace(microsecond=0)
        self.user = User.objects.create_user(username="c1", email="c1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=self.user, username="c1")
        self.admin = User.objects.create_user(username="ad", email="ad@example.com", password="x", role="admin")
        self.wallet = lb.get_or_create_wallet(self.profile)
        self.pack = CreditPackage.objects.create(
            name="Starter", credit_type=CreditType.CREATOR_CREDIT, credit_amount=100, price_usd=D("10.00"),
            duration_minutes=15,
        )
        self.pro = CreditPackage.objects.create(
            name="Pro", credit_type=CreditType.CREATOR_CREDIT, credit_amount=1000, price_usd=D("100.00"),
            duration_minutes=150,
        )

    def at(self, s):
        return self.t0 + timedelta(seconds=s)

    def go_live(self):
        stream = LiveStream.objects.create(creator=self.profile, title="s")
        stream.status = LiveStreamStatus.LIVE
        stream.started_at = self.t0
        stream.save()
        lb.start_billing(stream, now=self.t0)
        return stream

    # ── transactions: pagination, filter, ownership ──────────────────────────

    def test_transactions_paginate_filter_and_lookup(self):
        for _ in range(5):
            self.wallet.add_purchased_credits(100)
        self.wallet.set_monthly_allocation(50)
        q = """query($p:Int,$l:Int,$t:String){ myLiveCreditTransactions(page:$p, limit:$l, type:$t){
                 total page pages limit items{ id transactionType creditsDelta creditsAfter } } }"""
        data, errs = gql(self.user, q, {"p": 1, "l": 4})
        self.assertEqual(errs, [])
        page = data["myLiveCreditTransactions"]
        self.assertEqual((page["total"], page["pages"], len(page["items"])), (6, 2, 4))
        data, _ = gql(self.user, q, {"p": 2, "l": 4})
        self.assertEqual(len(data["myLiveCreditTransactions"]["items"]), 2)

        data, _ = gql(self.user, q, {"t": "purchase", "l": 50})
        self.assertEqual(data["myLiveCreditTransactions"]["total"], 5)
        data, _ = gql(self.user, q, {"t": "monthly_allocation", "l": 50})
        self.assertEqual(data["myLiveCreditTransactions"]["total"], 1)

        one_id = page["items"][0]["id"]
        data, _ = gql(self.user, "query($i:ID!){ myLiveCreditTransaction(id:$i){ id creditsDelta } }", {"i": one_id})
        self.assertEqual(data["myLiveCreditTransaction"]["id"], one_id)

        # Another creator can't read it.
        other = User.objects.create_user(username="c2", email="c2@example.com", password="x", role="creator")
        CreatorProfile.objects.create(user=other, username="c2")
        data, _ = gql(other, "query($i:ID!){ myLiveCreditTransaction(id:$i){ id } }", {"i": one_id})
        self.assertIsNone(data["myLiveCreditTransaction"])

    def test_page_size_is_capped(self):
        data, _ = gql(self.user, "{ myLiveCreditTransactions(limit: 100000){ limit } }")
        self.assertEqual(data["myLiveCreditTransactions"]["limit"], 100)

    # ── idempotent purchase ──────────────────────────────────────────────────

    BUY = """mutation($id:ID!,$k:String){ purchaseCreditPack(packageId:$id, idempotencyKey:$k){
              success code message creditBalance } }"""

    def fund_money_wallet(self, usd):
        from lipaidox.wallet.services import credit_fan_wallet
        credit_fan_wallet(self.user, D(usd))

    def test_purchase_with_same_key_credits_and_charges_once(self):
        from lipaidox.wallet.services import get_or_create_fan_wallet
        self.fund_money_wallet("50")
        first, e1 = gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "key-1"})
        again, e2 = gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "key-1"})
        self.assertEqual((e1, e2), ([], []))
        self.assertTrue(first["purchaseCreditPack"]["success"])
        self.assertEqual(again["purchaseCreditPack"]["code"], "OK")
        self.assertEqual(again["purchaseCreditPack"]["message"], "Already processed")
        self.assertEqual(self.wallet_now().total_available_credits, D("100"))          # credited once
        self.assertEqual(get_or_create_fan_wallet(self.user).balance, D("40"))         # charged once
        self.assertEqual(CreditPurchase.objects.filter(user=self.user).count(), 1)

    def test_a_new_key_is_a_new_purchase(self):
        self.fund_money_wallet("50")
        gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "a"})
        gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "b"})
        self.assertEqual(self.wallet_now().total_available_credits, D("200"))

    def test_reusing_a_key_for_another_pack_is_refused(self):
        self.fund_money_wallet("200")
        gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "same"})
        data, _ = gql(self.user, self.BUY, {"id": str(self.pro.id), "k": "same"})
        self.assertEqual(data["purchaseCreditPack"]["code"], "INVALID")
        self.assertEqual(self.wallet_now().total_available_credits, D("100"))          # nothing extra

    def test_insufficient_funds_buys_nothing(self):
        data, _ = gql(self.user, self.BUY, {"id": str(self.pack.id), "k": "poor"})
        self.assertEqual(data["purchaseCreditPack"]["code"], "INSUFFICIENT_FUNDS")
        self.assertEqual(self.wallet_now().total_available_credits, D("0"))

    def wallet_now(self):
        self.wallet.refresh_from_db()
        return self.wallet

    # ── admin: adjustments, permissions, audit ───────────────────────────────

    ADJUST = """mutation($u:ID!,$c:String!,$r:String!,$k:String){
                adminAdjustCreatorCredits(creatorUserId:$u, credits:$c, reason:$r, idempotencyKey:$k){
                  id transactionType creditsDelta creditsAfter } }"""

    def test_adjustment_is_admin_only(self):
        _, errs = gql(self.user, self.ADJUST, {"u": str(self.user.id), "c": "10", "r": "self-serve"})
        self.assertTrue(any("Admin access required" in e for e in errs))
        self.assertEqual(self.wallet_now().total_available_credits, D("0"))

    def test_adjustment_adds_credits_audits_and_is_idempotent(self):
        args = {"u": str(self.user.id), "c": "25.5", "r": "Support goodwill", "k": "adj-1"}
        data, errs = gql(self.admin, self.ADJUST, args)
        self.assertEqual(errs, [])
        self.assertEqual(data["adminAdjustCreatorCredits"]["transactionType"], "adjustment")
        self.assertEqual(self.wallet_now().gifted_credits, D("25.5"))

        again, _ = gql(self.admin, self.ADJUST, args)                                  # retry
        self.assertEqual(again["adminAdjustCreatorCredits"]["id"], data["adminAdjustCreatorCredits"]["id"])
        self.assertEqual(self.wallet_now().gifted_credits, D("25.5"))                   # not doubled

        logs = FinancialAuditLog.objects.filter(action="ADMIN_CREDIT_ADJUSTMENT")
        self.assertEqual(logs.count(), 1)                                              # one action, one row
        row = logs.get()
        self.assertEqual(row.actor_id, self.admin.id)
        self.assertEqual(row.ip_address, "10.0.0.7")
        self.assertEqual(row.new_value["delta"], "25.5")
        self.assertEqual(row.new_value["reason"], "Support goodwill")

    def test_adjustment_rules(self):
        self.wallet.add_purchased_credits(50)
        _, errs = gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "-80", "r": "too much"})
        self.assertTrue(errs)                                                          # can't overdraw
        _, errs = gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "5", "r": "  "})
        self.assertTrue(any("reason" in e.lower() for e in errs))
        _, errs = gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "abc", "r": "x"})
        self.assertTrue(errs)
        data, errs = gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "-20", "r": "clawback"})
        self.assertEqual((errs, data["adminAdjustCreatorCredits"]["creditsDelta"]), ([], -20.0))
        self.assertEqual(self.wallet_now().total_available_credits, D("30"))

    def test_adjustment_cannot_touch_credits_held_for_a_live(self):
        self.wallet.add_purchased_credits(120)
        self.go_live()                                     # holds 100 → 20 spendable
        _, errs = gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "-50", "r": "x"})
        self.assertTrue(errs)
        self.assertEqual(self.wallet_now().total_available_credits, D("120"))

    def test_admin_terminate_bills_and_audits(self):
        self.wallet.add_purchased_credits(500)
        stream = self.go_live()
        lb.heartbeat(stream.id, self.profile, 1, now=self.at(90))
        # settle() reads the wall clock, so pin it to the fake timeline
        real = lb.timezone.now
        lb.timezone.now = lambda: self.at(180)
        try:
            data, errs = gql(self.admin, "mutation($s:ID!){ adminTerminateLive(streamId:$s){ status endReason creditsConsumed } }", {"s": str(stream.id)})
        finally:
            lb.timezone.now = real
        self.assertEqual(errs, [])
        self.assertEqual(data["adminTerminateLive"]["endReason"], "forced_ended")
        self.assertEqual(data["adminTerminateLive"]["creditsConsumed"], 20.0)          # 180 s = 20 credits
        self.assertEqual(FinancialAuditLog.objects.filter(action="LIVE_FORCE_ENDED", entity_id=stream.id).count(), 1)

    def test_package_changes_are_audited(self):
        upd = """mutation($id:ID!){ updateCreditPackage(packageId:$id, input:{ priceUsd: 12.5, isActive: false }){ id } }"""
        _, errs = gql(self.admin, upd, {"id": str(self.pack.id)})
        self.assertEqual(errs, [])
        row = FinancialAuditLog.objects.get(action="CREDIT_PACKAGE_UPDATED")
        self.assertEqual(row.old_value["price_usd"], "10.00")
        self.assertEqual(row.new_value["price_usd"], "12.50")
        self.assertEqual((row.old_value["is_active"], row.new_value["is_active"]), (True, False))

    def test_audit_log_is_readable_by_admins_only(self):
        gql(self.admin, self.ADJUST, {"u": str(self.user.id), "c": "5", "r": "audit me"})
        q = "{ adminFinancialAuditLogs(action:\"ADMIN_CREDIT_ADJUSTMENT\"){ action actorUsername entityType newValue } }"
        data, errs = gql(self.admin, q)
        self.assertEqual(errs, [])
        self.assertEqual(data["adminFinancialAuditLogs"][0]["actorUsername"], "ad")
        _, errs = gql(self.user, q)
        self.assertTrue(any("Admin access required" in e for e in errs))

    # ── admin: monitoring and reports ────────────────────────────────────────

    def test_admin_views_are_admin_only(self):
        for q in ("{ adminLiveDashboard{ activeSessions } }",
                  "{ adminLiveCreditSessions{ liveStreamId } }",
                  "{ adminCreditsReport{ creditsPurchased } }"):
            _, errs = gql(self.user, q)
            self.assertTrue(any("Admin access required" in e for e in errs), q)

    def test_dashboard_and_session_list(self):
        self.wallet.add_purchased_credits(500)
        stream = self.go_live()
        data, errs = gql(self.admin, "{ adminLiveDashboard{ activeSessions creditsPerMinute creditsHeld sessionsToday } }")
        self.assertEqual(errs, [])
        d = data["adminLiveDashboard"]
        self.assertEqual((d["activeSessions"], d["creditsHeld"]), (1, 100.0))
        self.assertAlmostEqual(d["creditsPerMinute"], 6.67, places=2)                  # 100 credits / 15 min

        data, _ = gql(self.admin, "{ adminLiveCreditSessions{ liveStreamId creatorUsername status creditsReserved } }")
        self.assertEqual(data["adminLiveCreditSessions"][0]["creatorUsername"], "c1")
        one, _ = gql(self.admin, "query($s:ID!){ adminLiveCreditSession(streamId:$s){ status title } }", {"s": str(stream.id)})
        self.assertEqual(one["adminLiveCreditSession"]["status"], "active")

    def test_credits_report_matches_the_ledger(self):
        self.wallet.add_purchased_credits(500)
        CreditPurchase.objects.create(
            user=self.user, credit_type=CreditType.CREATOR_CREDIT, package=self.pack, credits_purchased=500,
            total_credits=500, amount_paid=D("50.00"), status="completed", completed_at=timezone.now(),
        )
        self.wallet.set_monthly_allocation(20)
        a = self.go_live()
        lb.settle(a, now=self.at(450))                                                  # 50 credits, creator ended
        # second stream that runs dry
        self.wallet.refresh_from_db()
        self.wallet.take_credits(self.wallet.total_available_credits - D("10"))
        self.wallet.save()
        b = LiveStream.objects.create(creator=self.profile, title="b", status=LiveStreamStatus.LIVE, started_at=self.t0)
        lb.start_billing(b, now=self.t0)
        lb.heartbeat(b.id, self.profile, 1, now=self.at(200))                           # 10 credits = 90 s → exhausted

        data, errs = gql(self.admin, """{ adminCreditsReport{
            creditsPurchased creditsConsumed bonusCreditsIssued purchasesCount purchaseRevenueUsd
            liveSessions averageCreditsPerSession creditExhaustionRate activeSessionsNow creditsHeldNow } }""")
        self.assertEqual(errs, [])
        r = data["adminCreditsReport"]
        self.assertEqual(r["creditsPurchased"], 500.0)
        self.assertEqual(r["bonusCreditsIssued"], 20.0)
        self.assertEqual((r["purchasesCount"], r["purchaseRevenueUsd"]), (1, 50.0))
        self.assertEqual(r["liveSessions"], 2)
        self.assertEqual(r["creditsConsumed"], 60.0)                                    # 50 + 10
        self.assertEqual(r["averageCreditsPerSession"], 30.0)
        self.assertEqual(r["creditExhaustionRate"], 0.5)                                # 1 of 2 ended dry
        self.assertEqual((r["activeSessionsNow"], r["creditsHeldNow"]), (0, 0.0))

    def test_report_can_be_scoped_to_one_creator(self):
        self.wallet.add_purchased_credits(200)
        data, _ = gql(self.admin, "query($u:ID){ adminCreditsReport(creatorUserId:$u){ creditsPurchased } }", {"u": str(self.user.id)})
        self.assertEqual(data["adminCreditsReport"]["creditsPurchased"], 200.0)
        other = User.objects.create_user(username="c9", email="c9@example.com", password="x", role="creator")
        data, _ = gql(self.admin, "query($u:ID){ adminCreditsReport(creatorUserId:$u){ creditsPurchased } }", {"u": str(other.id)})
        self.assertEqual(data["adminCreditsReport"]["creditsPurchased"], 0.0)
