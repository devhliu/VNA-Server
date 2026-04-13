"""Monitoring and metrics API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.monitoring_service import (
    MetricsService,
    HealthCheckService,
    AlertingService,
    AlertRule,
)


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def get_health(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = HealthCheckService(db)
    return await svc.run_all_checks()


@router.get("/health/{component}")
async def get_component_health(
    component: str,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = HealthCheckService(db)
    
    check_map = {
        "database": svc.check_database,
        "resources": svc.check_resources,
        "sync_queue": svc.check_sync_queue,
        "webhooks": svc.check_webhooks,
    }
    
    if component not in check_map:
        return {"error": f"Unknown component: {component}"}
    
    status = await check_map[component]()
    return {
        "component": status.component,
        "status": status.status,
        "message": status.message,
        "details": status.details,
        "timestamp": status.timestamp.isoformat(),
    }


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    metrics_svc = MetricsService(db)
    db_metrics = await metrics_svc.collect_database_metrics()
    
    return {
        "database": db_metrics,
        "counters": {
            k.split(":")[0]: v 
            for k, v in metrics_svc._counters.items()
        },
        "gauges": {
            k.split(":")[0]: v 
            for k, v in metrics_svc._gauges.items()
        },
    }


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    db: AsyncSession = Depends(get_session),
) -> str:
    metrics_svc = MetricsService(db)
    await metrics_svc.collect_database_metrics()
    return metrics_svc.export_prometheus_format()


@router.get("/alerts")
async def get_alerts(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    metrics_svc = MetricsService(db)
    alerting_svc = AlertingService(db)
    
    metrics = await metrics_svc.collect_database_metrics()
    alerts = await alerting_svc.evaluate_rules(metrics)
    
    return {
        "active_alerts": alerting_svc.get_active_alerts(),
        "new_firing": alerts,
        "rules": [
            {
                "name": r.name,
                "condition": r.condition,
                "threshold": r.threshold,
                "comparison": r.comparison,
                "severity": r.severity,
            }
            for r in alerting_svc._rules
        ],
    }


@router.post("/alerts/rules")
async def add_alert_rule(
    name: str = Query(...),
    condition: str = Query(...),
    threshold: float = Query(...),
    comparison: str = Query("gt"),
    severity: str = Query("warning"),
    message_template: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    alerting_svc = AlertingService(db)
    
    rule = AlertRule(
        name=name,
        condition=condition,
        threshold=threshold,
        comparison=comparison,
        severity=severity,
        message_template=message_template,
    )
    alerting_svc.add_rule(rule)
    
    return {
        "added": True,
        "rule": {
            "name": rule.name,
            "condition": rule.condition,
            "threshold": rule.threshold,
            "comparison": rule.comparison,
            "severity": rule.severity,
        },
    }


@router.delete("/alerts/rules/{name}")
async def remove_alert_rule(
    name: str,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    alerting_svc = AlertingService(db)
    removed = alerting_svc.remove_rule(name)
    return {"removed": removed, "rule_name": name}


@router.get("/status")
async def get_system_status(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    health_svc = HealthCheckService(db)
    metrics_svc = MetricsService(db)
    alerting_svc = AlertingService(db)
    
    health = await health_svc.run_all_checks()
    metrics = await metrics_svc.collect_database_metrics()
    alerts = await alerting_svc.evaluate_rules(metrics)
    
    return {
        "health": health,
        "metrics": metrics,
        "alerts": {
            "active": alerting_svc.get_active_alerts(),
            "firing": alerts,
        },
    }
