# Lipaidox Backend — Database Architecture

> Companion to `docs/ARCHITECTURE.md`. Describes the **current** PostgreSQL schema as
> reflected in the Django models. We remain in the architecture phase — no migrations to
> be authored yet.

## 1. Engine & Configuration

- **PostgreSQL** is the default engine (`django.db.backends.postgresql`). Django 4.2,
  `DEFAULT_AUTO_FIELD = BigAutoField`.
- Three configuration paths in `lipaidox_backend/settings.py:214-250`:
  1. `USE_SQLITE=True` → SQLite `db.sqlite3` (local dev / DB-free tests; cannot build
     Postgres-only column types).
  2. `DATABASE_URL` (managed hosts: Render/Heroku/Fly) → parsed with stdlib `urlparse`,
     `sslmode=require` set by default.
  3. discrete `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` (defaults
     `lipaidox2` / `lipaiduser` / `lipai123` / `localhost:5432`).
- Tenancy root: `lipaidox/models.py::Tenant` (db `tenants`, UUID PK, `domain` unique +
  indexed). Abstract `multitenant/models.py::TenantAwareModel` adds nullable `tenant` FK
  (`on_delete=CASCADE`, `related_name="%(class)s_instances"`).

## 2. Entity Inventory by Domain

All models use `UUIDField(primary_key=True, default=uuid.uuid4)` unless stated; money is
always `DecimalField`; cross-app references are string FKs (`"lipaidox_auth.User"`,
`"lipaidox_creator_profile.CreatorProfile"`, …). Most platform models subclass
`TenantAwareModel`.

### 2.1 Identity / Auth (`lipaidox_auth`, db table `users`)

`User(AbstractUser)` — UUID PK, `tenant` FK, `phone_number`/`phone_country_code`,
`role` (`fan` default / `creator` / `admin`), `status` (default `pending`), `email_verified`,
`phone_verified`, `date_of_birth`, `auth_provider` (default `local`), `google_id`, `apple_id`,
`module`, `profile_title`, `staff_capabilities` (JSON), `is_first_login`.

Partial unique constraints on `User` (per tenant): `unique_phone_per_tenant`,
`unique_google_per_tenant`, `unique_apple_per_tenant` (each conditioned on
`<field>__isnull=False`).

Companion tables:
- `RefreshToken` — `token_hash` unique, `is_active`, `expires_at` (30-day TTL), `last_used_at`.
- `TwoFactorAuth` (O2O) — TOTP `secret` (plaintext — documented codebase precedent), `is_enabled`.
- `BackupCode` (O2O) — `code_hash`, `is_used`.
- `TwoFactorLoginChallenge` — 10-min TTL challenge, hash-only storage.
- `EmailVerification`, `PhoneVerification` — token/OTP + `is_used` + `expires_at`.
- `PasswordResetToken`, `PasswordResetOtp` — `code_hash` (hashed, not plaintext), `attempts`,
  `is_used`, `expires_at`.

### 2.2 Admin & Security

- `lipaidox_admin_panel`: `AdminAccount` (O2O user, `admin_role` incl. superadmin/admin/
  moderator/support/finance, permission flags), `AdminAction` (append-only audit; target
  user/content FKs SET_NULL + `acted_on_entity_id/type`; `state_before/state_after` JSON;
  `reversal_check` constraint: `reversed_at IS NULL OR is_reversible`), `AccountFlag`,
  `PlatformAccount`, `Announcement`, `PlatformPost`, `SystemAlert`, `PlatformSetting`,
  `EmailCampaign`, `Refund`. (`AuditLog` is defined but never migrated — unused.)
- `lipaidox_security`: `SecurityEvent`, `SecuritySettings` (`two_fa_secret` plaintext,
  `backup_codes_hash` ArrayField, risk score 0–1 CheckConstraint), `LoginHistory`,
  `DeviceSession` (unique `(user, device_fingerprint)`), `TwoFAAttempt` (unique `code_hash`,
  rate limit 5/hr). **Not wired into the root GraphQL schema.**

### 2.3 Profiles / Onboarding / KYC

- `CreatorProfile` (db `profiles`) — O2O user; `username` unique, `account_kind`,
  `creator_tier`, `is_verified`, stats.
- `Follow` (unique follower+creator per tenant), `MembershipSubscription` (free tier),
  `Review` + `ReviewHelpful`/`ReviewReport`, `UsernameHistory` (partial unique active per user).
- `CreatorOnboardingStatus` (O2O; `current_step` 8-step enum, `completion_percentage`),
  `OnboardingStepLog` (append-only).
- `KYCStatus` (O2O creator, `overall_status` incl. `ai_processing`/`permanently_rejected`),
  `VerificationDocument` (statuses incl. `ai_passed`/`ai_failed`), `BusinessVerification`,
  `KYCRejectionReason`.
- Content classification: `PlatformCategory` (slug unique), `ContentClassification`
  (O2O creator; primary/secondary category, audience/gender/age/country/interests/professionalism).

### 2.4 Content

`Content` (db `contents`) → `CreatorProfile`; `content_format`, `status`, `media_count`.
Related: `ContentSeries` (self-FK `parent`), `ContentMedia` (`media_type`, `file`,
`like_count`, nullable `archive_artwork_id`/`essential_file_id`/`monetization_file_id`),
`ContentTag`, `ContentAttachment`, `ContentAccessRule`, `ContentComment` (`deleted_at`),
`ContentLike` / `ContentBookmark` / `ContentView` / `ContentReview` / `ContentReport` /
`ContentModerationLog` / `ContentAppeal` (unique per user+content where applicable),
`ContentLicense` (auto `license_key` "LPDX-…"). `MediaProcessor` is service-only (no models).

### 2.5 Monetization / Payment / Wallet

- **`Charge`** (db `charges`, `lipaidox_payment`) — user FK, tenant-aware, `gateway`
  (default `simulated`), `purpose` (wallet_topup/ppv/credits/live_entry/subscription),
  `amount` Decimal(10,2), `currency`, `status` (pending/completed/failed/declined/refunded),
  `method`, `idempotency_key`, `metadata`.
- **`PaymentMethod`** — user FK, `payment_method_type` (mobile_money/card/bank_account/paypal),
  unique `(user, type, identifier…)` per tenant, `deleted_at`. (`bank_account_number_encrypted`
  is plaintext despite the name.)
- **`MobileMoneyProvider`** — unique `(provider_name, country_code)`.
- **`FanWallet`** (`lipaidox_wallet`) — unique `(user, currency)`, `balance >= 0`.
- **`CreatorWallet`** (db `creator_wallets`) — unique `(creator, currency)`
  (`creator_wallets_unique`); `pending_balance`/`available_balance`/`on_hold_balance`,
  lifetime stats, earnings buckets (`earnings_from_ppv/subscriptions/tips/credits/live_streams`),
  6 CheckConstraints (each balance/lifetime ≥ 0).
- **`Transaction`** (db `transactions`) — **master platform ledger**: `fan → User` (SET_NULL),
  `creator → CreatorProfile` (SET_NULL), `transaction_type`, `status`,
  `gross_amount` / `platform_fee_percent` / `platform_fee` / `net_amount`; source UUIDs
  (`ppv_purchase_id`, `subscription_payment_id`, `tip_id`, `credit_purchase_id`, `payout_id`);
  `payment_method` (SET_NULL), `gateway_reference`/`gateway_response` (JSON), `refunded_by →
  AdminAccount`, refund/dispute fields, `ip_address`. Constraint `txn_net_calculation`:
  `net = gross − platform_fee`; `gross > 0`.
- **`WalletTransaction`** (db `wallet_transactions`, append-only) — `wallet` + `creator` FKs,
  `amount`, `balance_before`/`balance_after`, `balance_type`, source UUIDs, 7-day clearing
  fields. Constraint `wallet_txn_balance_consistency`: `balance_after = balance_before + amount`;
  `balance_after >= 0`; `amount != 0`.
- **`PayoutTransaction`** (db `payout_transactions`) — creator + wallet FKs,
  `payment_method` FK **PROTECT**; `tax_withholding_percent`/`tax_withheld_amount`/
  `net_payout_amount`; statuses incl. processing/completed/reversed; `retry_count < 3`;
  reversal fields; admin approval fields. Constraints: `payout_net_calculation`
  (`net = amount − tax_withheld`), tax percent ∈ [0,100], amounts > 0.
- **`WalletClearingJob`** — clearing batch tracking.

### 2.6 Subscriptions / Plans / PPV / Tips / Monetization Settings

- `Subscription` — fan→User, creator→CreatorProfile, `price`, `platform_fee_percent`
  (default 20), `billing_period`, auto-renew flags.
- `SubscriptionPayment` — subscription FK, amount/fee, gateway ref.
- `CreatorPlan` — `tier` unique, feature flags/caps (`None` = unlimited, `0` = not allowed).
- `CreatorPlanSubscription` (O2O creator, credit buckets), `CreatorPlanPayment`,
  `CreatorLiveCreditUsage`, `CreatorPurchasedCredits`.
- `PPVPurchase` — fan/creator/content, `access_type` (one_time/timed), `platform_fee_percent`
  default 15, lock/premium flags.
- `Tip` (db `tips`) — fan/creator/content, `amount`, `platform_fee_percent` default 15.
- `MonetizationSettings` (O2O creator) + `MonetizationPriceHistory` (JSON price history).
- `lms_financial`: `LmsPlan`, `LmsSubscription` (plan FK PROTECT, `stripe_subscription_id`),
  `LmsPayment` (`stripe_payment_intent_id`), `LmsInvoice`, `StudentPaymentMethod`.

### 2.7 Credits & Live Billing (`lipaidox_credits`)

- `CreatorCreditWallet` (Decimal(20,6) buckets: purchased/free_monthly/gifted/reserved;
  balance derived from ledger only), `FanCreditWallet` (integer buckets + CheckConstraints),
  `FanCreditLedger` (append-only), `FanCreditGiftSent` (unique sender+recipient+type+amount).
- `LiveCreditReservation` — wallet FK **PROTECT**, `live_stream` O2O (-> live_streaming),
  status active/settled; constraint `live_resv_one_active_per_creator`.
- `LiveBillingEvent` — `(reservation, sequence)` **unique** → replay-safe heartbeat ledger;
  a single immutable `LIVE_USAGE` row is written on settle.
- `CreditPackage` (`credit_amount > 0`), `CreditPurchase` (`idempotency_key` +
  constraint `credit_purchase_idempotency_unique`), `CreditGift`.
- `FinancialAuditLog` (db `financial_audit_logs`, append-only).

### 2.8 Live Streaming

`LiveStream` (creator, `access_type`, `entry_price`), `LiveStreamEntry`
(unique `(live_stream, fan)`), `LiveStreamChatMessage` (creator flag, soft delete),
`LiveStreamViewer` (watching/left/kicked/banned), `LiveStreamCreditTransaction`
(`gift` FK → credits `FanCreditGiftSent`, `credits_received`, `monetary_value`,
`platform_fee`, `creator_earnings`), `LiveStreamMedia`.

### 2.9 Messaging / Notifications

- `Conversation` (participants, denormalized `last_message_id/preview`), `Message`
  (message_type incl. text/image/video/audio/file/tip/automated/sticker, `reply_to` self-FK,
  read/deleted flags), `MessageAttachment`, `MessageReaction` (unique message+user+emoji),
  `AutoDMRule` (unique (creator, trigger)), `QuickReply`, `ScheduledMessage`, `Broadcast`,
  `StarredMessage` (unique (user, message)), `ConversationReport`.
- `Notification` (user, `entity_type/entity_id` generic deep link), `NotificationPreference`,
  `NotificationDeliveryLog`, `NotificationQueue` (max_attempts 3), `NotificationTemplate`
  (unique (type, channel)), `PushToken`.

### 2.10 Lost & Found + Community (**not tenant-aware**)

- `LostFoundItem`, `ItemImage` (CLIP `embedding` JSON, `ai_class`, confidence),
  `Match` (unique (item_a, item_b, match_type), similarity 0–1), `Vote` (unique (item, user),
  `weight` 0.1–10.0), `Report`, `ProductCache` (unique (product_name, normalized_name)),
  `SearchLog`.
- Community: `CommunityQuestion` (denormalized `score`, composite indexes on
  (category, -created_at) and (-score, -created_at)), `QuestionView` (unique (question, user)),
  `CommunityAnswer` (self-FK `parent` for replies), `CommunityAnswerLike`,
  `QuestionVote` (unique `one_vote_per_user_per_question`), `CommunityPoll`,
  `PollOption`, `CommunityPollVote` (unique `one_vote_per_user_per_poll`, `change_count`),
  `VoteChange` (append-only audit, user SET_NULL).

### 2.11 AI Intelligence & Recommendation

- `ai_intelligence`: `AIMediaIntelligence`, `ContentWatermark`, `AIScanQueue`,
  `AIFingerprintRegistry` (`sha256` unique, `phash`), `CreatorAnalytics`, `ContentAnalytics`,
  `PlatformAnalytics`, `ContentScore`, `FeedRecommendation`, `SuggestedCreator`.
- `recommendation`: `UserInteraction`, `ContentScore`, `FeedRecommendation`,
  `TrendingContent`, `SuggestedCreator`, `UserInterestProfile`, `PromotedContent` (ads).
  > ⚠️ `ContentScore`/`FeedRecommendation`/`SuggestedCreator` exist in **both** apps as
  > distinct tables — a known duplication to normalize in a later phase.
- `feedback`: `AppFeedback` (rating 1–5 CheckConstraint `app_feedback_rating_1_5`).

### 2.12 LMS (summary of notable entities)

- `lms_identity`: `StudentProfile`, `InstructorProfile` (FK → creator-profile `CreatorProfile`,
  SET_NULL, related `lms_instructor`), `CourseReview` (unique (course, student)),
  `WorkExperience`, `EducationRecord`, `Project`, `ExternalCertification`,
  `NotificationPreference`, `PrivacySetting`.
- `lms_content`: `Course` (slug unique, price/discount_price), `CourseCategory` (self-parent),
  `CourseSection`, `Lesson` (unique (course, slug)), `CourseAnnouncement`, `Lab`,
  `LabSubmission`, `LearningPath`, `Recommendation` (unique (student, course)), `Resource`,
  `CourseTag` (unique (course, name)).
- `lms_learning`: `Enrollment` (unique (student, course)), `Note`, `LessonProgress`
  (unique (enrollment, lesson)), `Question`/`Answer`, `Wishlist` (unique (student, course)).
- `lms_community`: `AccountabilityGroup` (+`AccountabilityMember`, `AccountabilityCheckIn`),
  `StudyRoom` (+`Member`, `Channel`, `Message` with `reply_to`).
- `lms_certification`: `SkillBadge` (**`verification_code` unique**), `BadgeEndorsement`
  (unique (badge, endorsed_by)), `AvailableCertification`, `CertificationEnrollment`,
  `Certificate` (**`verification_code` unique**, `blockchain_hash`, `network` default
  "Polygon", `is_public`).
- `lms_skills`: `SkillCategory` (self-parent), `StudentSkill` (unique (student, skill_name)),
  `SkillAssessment`.
- `lms_performance`: `LearningActivityLog`, `LearningStreak` (O2O student),
  `QuizAttempt` (answers JSON), `AssignmentSubmission`.
- `lms_careers`: `JobListing`, `JobApplication` (unique (student, job)), `TalentPoolProfile`.
- `lms_messages`: `Conversation` (unique (course, student, instructor)), `Message`,
  `MessageAttachment`.
- `lms_cohorts`: `Cohort`. `lms_employer`: `EmployerProfile`. `lms_onboarding`:
  `OnboardingProgress` (O2O student, 6 steps).

## 3. Relationship Patterns

1. **String cross-app FK references** resolved by app label (User, CreatorProfile,
   PaymentMethod, AdminAccount, LiveStream, FanCreditGiftSent) — keeps modules decoupled.
2. **O2O profile anchors**: `User↔CreatorProfile`, `User↔KYCStatus`,
   `CreatorProfile↔ContentClassification`, `User↔CreatorOnboardingStatus`.
3. **TenantAwareModel** spreads `tenant` FK on most platform tables; exceptions:
   `lost_found`, several lightweight tables (verification siblings, some LMS tables).
4. **Self-references**: `ContentSeries.parent`, `CourseCategory.parent`,
   `SkillCategory.parent`, `CommunityAnswer.parent`, `Message.reply_to`,
   `StudyRoomMessage.reply_to`.
5. **UUID source-pointer columns** in ledgers instead of FKs (see §6).

## 4. Constraints (database-enforced) — highlights

| Constraint | Meaning |
|---|---|
| `txn_net_calculation` | `net_amount = gross_amount - platform_fee` |
| `payout_net_calculation` | `net_payout_amount = amount - tax_withheld_amount` |
| `wallet_txn_balance_consistency` | `balance_after = balance_before + amount` |
| creator wallet balances | 6 checks: balances & lifetime stats ≥ 0 |
| `reversal_check` (AdminAction) | reversible rows only may be reversed |
| `app_feedback_rating_1_5` | rating between 1 and 5 |
| partial unique (User) | phone / google_id / apple_id unique **per tenant** when non-null |
| `one_vote_per_user_per_*` | QuestionVote / CommunityPollVote / followers, etc. |
| `(reservation, sequence)` unique | LiveBillingEvent replay safety |
| `credit_purchase_idempotency_unique` | no double credit purchases |
| balance ≥ 0 | FanWallet, CreditWallet buckets |

## 5. Indexes

- Every FK, every `unique`/`unique_together`/`UniqueConstraint`, and UUID PKs are indexed
  by Django automatically.
- Explicit/multi-column indexes worth noting: `Tenant.domain` (unique), `Content` search
  fields, `Question` composite `(category, -created_at)` and `(-score, -created_at)`,
  `VoteChange (poll, user, changed_at)`, `Match` similarity lookups, `CourseCategory.parent`,
  `Message` conversation+created, promotion/ads date windows (`PromotedContent`),
  `PushToken` device, notification read-at.
- Review indexes (future focus): composite fan-wallet lookups, `Transaction` (fan, created),
  `WalletTransaction` (wallet, created), credits reservation lookup by live_stream.

## 6. Transaction Strategy

- **Money-movement choke point** — `lipaidox/wallet/services.py`. Every balance-touching
  operation is wrapped in `transaction.atomic()` and rows are locked with
  `select_for_update()` (fan wallet, creator wallet, then reservation in a **fixed lock
  order** to avoid deadlock — `lipaidox/credits/live_billing.py`).
- **Top-up-then-spend** — the gateway only ever credits `FanWallet`
  (`lipaidox/payment/fulfillment.py::fulfill_charge`); feature purchases spend from it via
  `settle()` which row-locks **both** wallets, debits the fan, writes **one**
  `Transaction` row, and adds net earnings to the creator wallet (bucketed by `_EARNING_TYPE`).
- **Exactly-once fulfillment** — `fulfill_charge` is atomic + row-locked and transitions
  `Charge` PENDING → SUCCEEDED exactly once, so concurrent webhook + status polling cannot
  double-credit (webhook always answers 200).
- **Idempotency keys** — NBC charge uses `charge-<charge.id>` (stable UUID created before
  the request); payouts `payout-<txn.id>`; credit purchases use a user-scoped key with a DB
  unique constraint.
- **Append-only ledgers** — never `UPDATE`/`DELETE`; balances derived. Written: one
  `LIVE_USAGE` row per settle, one `WalletTransaction` per earning/payout, one
  `FinancialAuditLog` entry per admin adjustment (ADJUSTMENT with audit).
- **Derived credit billing** — `100 credits = $10 = 15 minutes` → 1 credit per 9 seconds
  (`elapsed ÷ 9`), fixed-point `DECIMAL(20,6)`, config via `LIVE_CREDITS_PER_15_MINUTES` /
  `LIVE_SECONDS_PER_UNIT` / `CREDIT_USD_VALUE`. Engine functions take an explicit
  `now: Optional[datetime] = None` for deterministic tests. A `bill_active_sessions` sweeper
  settles dropped connections up to the last heartbeat.
- **Time injection** — `start_billing`, `heartbeat`, `settle`, `bill_active_sessions`,
  `refresh_monthly_allocation` all accept `now=`.

## 7. Data Integrity Rules

1. Ledger rows must reconcile: `net = gross − fee`, `balance_after = balance_before + amount`,
   non-negative balances everywhere (DB CheckConstraints as backstop).
2. Fan spend is always funded by a prior wallet top-up (no direct provider purchases in
   feature code) — the wallet is the single source of spend.
3. Charge currency == wallet currency (no internal FX on settlement; NBC `NBC_*` FX is
   applied only on the wire and the Charge row keeps its own currency).
4. Payouts require `amount ≥ $50`, `retry_count < 3`, admin approval where flagged, and
   `net = amount − tax_withheld`.
5. Append-only tables never carry mutable business state; state changes emit new rows.

## 8. Known Gaps / Notes

- `lost_found` and some LMS tables bypass `TenantAwareModel` — cross-tenant visibility
  must be handled at query time (or re-scoped).
- `analytics` installed with **no models**; `media_processor` and `discover/` not in
  `INSTALLED_APPS`.
- Duplicated model families (`ai_intelligence` vs `recommendation`; some `lms_*`
  relationships) to normalize.
- `admin_panel.AuditLog` unused — `FinancialAuditLog` is the operative audit trail.
- Stray legacy files in `lipaidox/live_streaming/` (`models.py.bak`, `.deleted`,
  `.deprecated`, `.empty`) should be cleaned up in a later phase.