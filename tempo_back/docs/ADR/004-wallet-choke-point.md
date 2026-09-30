# ADR-004 — Wallet choke point: top-up-then-spend money movement

- **Status:** Accepted

## Context

Monetization spans gateways, wallets, PPV, tips, subscriptions, credits and live billing.
Naive per-feature money handling invites double-spend bugs, FX mismatches and inconsistent
ledgers.

## Decision

- **Top-up-then-spend:** gateways only ever fund the fan wallet (`credit_fan_wallet`).
  Every purchase spends from the fan wallet via `lipaidox/wallet/services.py::settle`, which
  row-locks both wallets, writes one `Transaction` row, and credits the creator wallet net
  of platform fee.
- **Single choke point:** all balance mutation lives in `wallet/services.py`
  (`settle`, `credit_fan_wallet`, `spend_fan_to_platform`, `credit_creator_from_credits`),
  always `transaction.atomic` + `select_for_update` with fixed lock ordering.
- **Append-only ledgers:** `WalletTransaction`, `LiveBillingEvent`, `FinancialAuditLog`,
  `AdminAction` are insert-only; balances are derived and guarded by DB constraints
  (`balance_after = balance_before + amount`, `net = gross − fee`, non-negative balances).
- **Idempotency:** charges/purchases carry idempotency keys with DB unique backstops;
  webhooks and status polling fulfill exactly once.

## Consequences

- (+) Single place to audit and harden money movement; race-safe fulfillment.
- (+) Ledgers reconcile by construction; tests can assert invariants cheaply.
- (-) Every new monetization feature must route through the choke point — easy to bypass
  during expedited development.
- (-) Wallet row contention is a scalability factor for large-scale tipping/streaming.