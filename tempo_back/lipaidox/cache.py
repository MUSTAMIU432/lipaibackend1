"""
Central cache service — the one place that talks to Django's cache.

PostgreSQL is the source of truth; everything here is a disposable copy with a
TTL. Resolvers use the cache-aside helpers below instead of calling
``cache.get``/``cache.set`` themselves, so key naming, TTLs and invalidation
stay in one file.

Keys
----
Every key is ``<namespace>:v<version>:<parts…>`` (Django adds the global
``CACHE_KEY_PREFIX``). Bumping a namespace's version orphans every key under
it at once — e.g. one ``CreditPackage`` edit invalidates all the
``creditPackages(creditType, target, isActive)`` argument combinations without
having to enumerate them. Orphaned keys simply expire.

Only public, non-sensitive read models belong here: catalogs and aggregate
counts. Never cache tokens, passwords, OTPs, balances or anything private.

Values
------
The Redis cache uses a JSON serializer (no pickle), so cached values must be
JSON-safe. ``get_or_set_models`` stores model rows through Django's JSON
serializer and rebuilds real instances (Decimal, datetime, UUID intact) on a
hit, so existing ``Type.from_model(...)`` code works unchanged.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, List, Optional, Type

from django.core import serializers
from django.core.cache import cache
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

# TTLs (seconds). Short enough that a missed invalidation (a bulk `.update()`
# that skips signals) heals itself quickly.
TTL_CATALOG = 600
TTL_AGGREGATE = 300

# Namespaces
NS_CREDIT_PACKAGES = "catalog:credit_packages"
NS_CATEGORIES = "catalog:categories"
NS_MOBILE_MONEY_PROVIDERS = "catalog:mobile_money_providers"
NS_REVIEW_SUMMARY = "reviews:summary"

_VERSION_TTL = 60 * 60 * 24 * 30


def _version(namespace: str) -> int:
    v = cache.get(f"{namespace}:version")
    if v is None:
        v = 1
        cache.add(f"{namespace}:version", v, _VERSION_TTL)
    return int(v)


def make_key(namespace: str, *parts: Any) -> str:
    """``namespace:v<n>:part1:part2`` — parts are str()-ed, None becomes ``-``."""
    rendered = ":".join("-" if p is None else str(p) for p in parts)
    return f"{namespace}:v{_version(namespace)}" + (f":{rendered}" if rendered else "")


def get_cached(namespace: str, *parts: Any) -> Any:
    return cache.get(make_key(namespace, *parts))


def set_cached(namespace: str, *parts: Any, value: Any, ttl: int) -> None:
    cache.set(make_key(namespace, *parts), value, ttl)


def delete_cached(namespace: str, *parts: Any) -> None:
    cache.delete(make_key(namespace, *parts))


def invalidate_namespace(namespace: str) -> None:
    """Orphan every key in ``namespace`` by bumping its version."""
    key = f"{namespace}:version"
    try:
        cache.incr(key)
    except ValueError:  # key missing (evicted or never set)
        cache.set(key, 2, _VERSION_TTL)


def invalidate_on_commit(namespace: str, *parts: Any) -> None:
    """
    Drop a key (or, with no parts, the whole namespace) once the current
    transaction commits. Invalidating before commit would let a concurrent
    reader re-cache the old rows in the gap; outside a transaction this runs
    immediately.
    """
    if parts:
        transaction.on_commit(lambda: delete_cached(namespace, *parts))
    else:
        transaction.on_commit(lambda: invalidate_namespace(namespace))


def get_or_set(namespace: str, *parts: Any, ttl: int, loader: Callable[[], Any]) -> Any:
    """Cache-aside for JSON-safe values (dicts, lists, numbers, strings)."""
    key = make_key(namespace, *parts)
    hit = cache.get(key)
    if hit is not None:
        return hit
    value = loader()
    cache.set(key, value, ttl)
    return value


def get_or_set_models(
    namespace: str, *parts: Any, ttl: int, loader: Callable[[], Iterable[models.Model]]
) -> List[models.Model]:
    """
    Cache-aside for a list of model instances. The rows are stored as Django's
    JSON serialization and rebuilt as unsaved-but-populated instances on a hit;
    don't call ``.save()`` on what this returns.
    """
    key = make_key(namespace, *parts)
    raw = cache.get(key)
    if raw is not None:
        try:
            return [d.object for d in serializers.deserialize("json", raw, ignorenonexistent=True)]
        except Exception:  # schema changed under an old entry — treat as a miss
            logger.warning("cache: discarding undecodable entry %s", key, exc_info=True)
    rows = list(loader())
    cache.set(key, serializers.serialize("json", rows), ttl)
    return rows


def invalidate_namespace_on_change(model: Type[models.Model], namespace: str) -> None:
    """
    Bump ``namespace`` whenever ``model`` is saved or deleted. Used for catalog
    tables edited from Django admin, seed commands and bulk tooling, which have
    no service layer to hang explicit invalidation on.
    """
    def _handler(sender, **kwargs):
        invalidate_on_commit(namespace)

    uid = f"cache-invalidate:{model._meta.label}:{namespace}"
    post_save.connect(_handler, sender=model, weak=False, dispatch_uid=uid + ":save")
    post_delete.connect(_handler, sender=model, weak=False, dispatch_uid=uid + ":delete")


def register_catalog_invalidation() -> None:
    """Called once from ``LipaidoxConfig.ready()``."""
    from lipaidox.content_classification.models import PlatformCategory
    from lipaidox.credits.models import CreditPackage
    from lipaidox.payment.models import MobileMoneyProvider

    invalidate_namespace_on_change(CreditPackage, NS_CREDIT_PACKAGES)
    invalidate_namespace_on_change(PlatformCategory, NS_CATEGORIES)
    invalidate_namespace_on_change(MobileMoneyProvider, NS_MOBILE_MONEY_PROVIDERS)


def cache_health() -> Optional[str]:
    """None when a set/get round-trip works, else a short error (no URLs/secrets)."""
    probe = make_key("health", "probe")
    try:
        cache.set(probe, "ok", 10)
        if cache.get(probe) != "ok":
            return "cache round-trip returned nothing"
        return None
    except Exception as exc:
        return type(exc).__name__
