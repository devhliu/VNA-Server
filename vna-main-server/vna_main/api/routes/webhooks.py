"""Webhook API - subscribe to events and manage deliveries."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
import ipaddress
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.webhook_service import WebhookDelivery, WebhookService
from vna_main.services.audit_service import AuditService
from vna_common.responses import PaginatedResponse

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class CreateWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    events: list[str]
    description: str | None = None
    secret: str | None = None
    enabled: bool = True

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL to prevent SSRF attacks by blocking private/internal IPs."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(v)
            hostname = parsed.hostname
            if hostname:
                # Check for localhost
                if hostname.lower() in ('localhost', 'localhost.localdomain'):
                    raise ValueError('URL cannot point to localhost')
                # Check for private IP ranges
                try:
                    ip = ipaddress.ip_address(hostname)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        raise ValueError('URL cannot point to private/internal IP address')
                except ValueError:
                    # Not an IP address, could be hostname - continue validation
                    pass
                # Additional checks for common internal hostnames
                internal_hosts = [
                    'internal', 'intranet', 'private', 'local', 'corp',
                    'internal.api', 'api.internal', 'service.consul',
                    'metadata.google.internal', 'metadata', 'kubernetes',
                    'kubernetes.default.svc', 'etcd', 'redis', 'mysql',
                    'postgres', 'mongodb', 'elasticsearch'
                ]
                if any(host in hostname.lower() for host in internal_hosts):
                    raise ValueError('URL cannot point to internal hostname')
            return v
        except Exception:
            # If URL parsing fails, let the URL validation handle it
            return v


class UpdateWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    description: str | None = None
    enabled: bool | None = None

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Validate URL to prevent SSRF attacks by blocking private/internal IPs."""
        if v is None:
            return v
        try:
            from urllib.parse import urlparse
            parsed = urlparse(v)
            hostname = parsed.hostname
            if hostname:
                # Check for localhost
                if hostname.lower() in ('localhost', 'localhost.localdomain'):
                    raise ValueError('URL cannot point to localhost')
                # Check for private IP ranges
                try:
                    ip = ipaddress.ip_address(hostname)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        raise ValueError('URL cannot point to private/internal IP address')
                except ValueError:
                    # Not an IP address, could be hostname - continue validation
                    pass
                # Additional checks for common internal hostnames
                internal_hosts = [
                    'internal', 'intranet', 'private', 'local', 'corp',
                    'internal.api', 'api.internal', 'service.consul',
                    'metadata.google.internal', 'metadata', 'kubernetes',
                    'kubernetes.default.svc', 'etcd', 'redis', 'mysql',
                    'postgres', 'mongodb', 'elasticsearch'
                ]
                if any(host in hostname.lower() for host in internal_hosts):
                    raise ValueError('URL cannot point to internal hostname')
            return v
        except Exception:
            # If URL parsing fails, let the URL validation handle it
            return v


@router.post("")
async def create_webhook(
    req: CreateWebhookRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = WebhookService(db)
    audit_svc = AuditService(db)
    sub = await svc.create_subscription(
        url=req.url,
        events=req.events,
        secret=req.secret,
        description=req.description,
        enabled=req.enabled,
    )
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="webhook",
        resource_id=str(sub.id),
        details={"url": sub.url, "events": sub.events, "enabled": sub.enabled}
    )
    
    return {
        "id": sub.id,
        "url": sub.url,
        "events": sub.events,
        "description": sub.description,
        "enabled": sub.enabled,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


@router.get("", response_model=PaginatedResponse[dict])
async def list_webhooks(
    event: str | None = None,
    enabled: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = WebhookService(db)
    subs, total = await svc.list_subscriptions(event=event, enabled=enabled, offset=offset, limit=limit)
    return PaginatedResponse(
        items=[
            {
                "id": s.id,
                "url": s.url,
                "events": s.events,
                "description": s.description,
                "enabled": s.enabled,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ],
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/stats")
async def webhook_stats(db: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    svc = WebhookService(db)
    return await svc.get_subscription_stats()


@router.get("/{sub_id}")
async def get_webhook(
    sub_id: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = WebhookService(db)
    sub = await svc.get_subscription(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {
        "id": sub.id,
        "url": sub.url,
        "events": sub.events,
        "description": sub.description,
        "enabled": sub.enabled,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


@router.patch("/{sub_id}")
async def update_webhook(
    sub_id: int,
    req: UpdateWebhookRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = WebhookService(db)
    audit_svc = AuditService(db)
    sub = await svc.update_subscription(
        sub_id,
        url=req.url,
        events=req.events,
        secret=req.secret,
        description=req.description,
        enabled=req.enabled,
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="update",
        resource_type="webhook",
        resource_id=str(sub.id),
        details={"url": sub.url, "events": sub.events, "enabled": sub.enabled}
    )
    
    return {
        "id": sub.id,
        "url": sub.url,
        "events": sub.events,
        "description": sub.description,
        "enabled": sub.enabled,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }


@router.delete("/{sub_id}")
async def delete_webhook(
    sub_id: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    svc = WebhookService(db)
    audit_svc = AuditService(db)
    deleted = await svc.delete_subscription(sub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="webhook",
        resource_id=str(sub_id),
        details={}
    )
    
    return {"deleted": str(sub_id)}


@router.get("/{sub_id}/deliveries")
async def get_deliveries(
    sub_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = WebhookDelivery(db)
    logs = await svc.get_delivery_logs(subscription_id=sub_id, limit=limit)
    return {
        "items": [
            {
                "id": log.id,
                "subscription_id": log.subscription_id,
                "event_type": log.event_type,
                "delivery_id": log.delivery_id,
                "response_status": log.response_status,
                "success": log.success,
                "error": log.error,
                "attempt_count": log.attempt_count,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }
