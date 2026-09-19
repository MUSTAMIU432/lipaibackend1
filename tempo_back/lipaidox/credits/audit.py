"""Write to the financial audit trail from a GraphQL resolver."""
from typing import Optional

from .models import FinancialAuditLog


def _client_ip(request) -> Optional[str]:
    meta = getattr(request, "META", {}) or {}
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else meta.get("REMOTE_ADDR")
    return ip or None


def record_audit(info, action: str, entity_type: str, entity_id=None, old=None, new=None) -> FinancialAuditLog:
    """Append one row. `info` is the resolver's Info (for actor, IP and user agent)."""
    request = info.context.request
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    meta = getattr(request, "META", {}) or {}
    return FinancialAuditLog.objects.create(
        actor=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old or {},
        new_value=new or {},
        ip_address=_client_ip(request),
        user_agent=(meta.get("HTTP_USER_AGENT") or "")[:500],
    )
