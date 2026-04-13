"""Routing rules API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.routing_rules_service import RoutingRulesService
from vna_main.services.audit_service import AuditService


router = APIRouter(prefix="/routing", tags=["routing"])


class CreateRuleRequest(BaseModel):
    name: str
    target: str
    rule_type: str = "data_type"
    conditions: dict[str, Any] | None = None
    description: str | None = None
    priority: int = 100
    enabled: bool = True


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rule_type: str | None = None
    conditions: dict[str, Any] | None = None
    target: str | None = None
    priority: int | None = None
    enabled: bool | None = None


class ReorderRulesRequest(BaseModel):
    rules: list[dict[str, int]]


class TestRuleRequest(BaseModel):
    conditions: dict[str, Any]
    resource_data: dict[str, Any]


@router.get("/rules")
async def list_rules(
    enabled_only: bool = Query(False),
    rule_type: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    rules = await svc.list_rules(enabled_only=enabled_only, rule_type=rule_type)
    return {"rules": rules, "total": len(rules)}


@router.post("/rules")
async def create_rule(
    request: CreateRuleRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    audit_svc = AuditService(db)
    rule = await svc.create_rule(
        name=request.name,
        target=request.target,
        rule_type=request.rule_type,
        conditions=request.conditions,
        description=request.description,
        priority=request.priority,
        enabled=request.enabled,
    )
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="routing_rule",
        resource_id=str(rule.id),
        details={
            "name": rule.name,
            "target": rule.target,
            "rule_type": rule.rule_type,
            "enabled": rule.enabled
        }
    )
    
    return {
        "id": rule.id,
        "name": rule.name,
        "target": rule.target,
        "priority": rule.priority,
        "enabled": rule.enabled,
    }


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    rule = await svc.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    request: UpdateRuleRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    audit_svc = AuditService(db)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    rule = await svc.update_rule(rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="update",
        resource_type="routing_rule",
        resource_id=str(rule.id),
        details={
            "name": rule.name,
            "target": rule.target,
            "updated_fields": list(updates.keys())
        }
    )
    
    return {
        "id": rule.id,
        "name": rule.name,
        "target": rule.target,
        "priority": rule.priority,
        "enabled": rule.enabled,
    }


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    audit_svc = AuditService(db)
    deleted = await svc.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="routing_rule",
        resource_id=str(rule_id),
        details={}
    )
    
    return {"deleted": True, "rule_id": rule_id}


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    enabled: bool = Query(...),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    success = await svc.toggle_rule(rule_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.commit()
    return {"rule_id": rule_id, "enabled": enabled}


@router.post("/rules/reorder")
async def reorder_rules(
    request: ReorderRulesRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    success = await svc.reorder_rules(request.rules)
    await db.commit()
    return {"reordered": success, "count": len(request.rules)}


@router.post("/evaluate")
async def evaluate_resource(
    resource_data: dict[str, Any],
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    return await svc.evaluate_resource(resource_data)


@router.post("/test")
async def test_rule(
    request: TestRuleRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    return await svc.test_rule(request.conditions, request.resource_data)


@router.get("/types")
async def get_rule_types(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    types = await svc.get_rule_types()
    return {"types": types}


@router.get("/operators")
async def get_operators(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RoutingRulesService(db)
    operators = await svc.get_operators()
    return {"operators": operators}
