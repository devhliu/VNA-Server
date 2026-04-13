"""Webhooks API - Event subscription management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Webhook
from bids_server.models.schemas import WebhookCreate, WebhookResponse

router = APIRouter(prefix="/bidsweb/v1/webhooks", tags=["Webhooks"])


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List all registered webhooks."""
    result = await db.execute(
        select(Webhook).order_by(Webhook.created_at.desc())
    )
    return [WebhookResponse.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    req: WebhookCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a webhook for event notifications.
    
    Available events:
    - resource.created, resource.updated, resource.deleted
    - label.updated
    - annotation.created
    - task.completed, task.failed
    - * (all events)
    """
    webhook = Webhook(
        name=req.name,
        url=req.url,
        events=req.events,
        secret=req.secret,
        filters=req.filters,
    )
    db.add(webhook)
    await db.flush()
    return WebhookResponse.model_validate(webhook)


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    result = await db.execute(select(Webhook).where(Webhook.webhook_id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(404, f"Webhook {webhook_id} not found")
    await db.delete(webhook)
    await db.flush()
    return {"deleted": True, "webhook_id": webhook_id}
