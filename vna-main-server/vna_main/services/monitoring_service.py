"""Monitoring and metrics service."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from vna_main.models.database import (
    ResourceIndex,
    PatientMapping,
    Label,
    WebhookSubscription,
    SyncEvent,
)

logger = logging.getLogger(__name__)

_MAX_METRIC_SAMPLES = 1000


@dataclass
class MetricValue:
    name: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class HealthStatus:
    component: str
    status: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsService:
    """Service for collecting and exposing metrics."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._metrics: dict[str, list[MetricValue]] = defaultdict(list)
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None):
        key = f"{name}:{labels}" if labels else name
        self._counters[key] += value
        entries = self._metrics[name]
        entries.append(MetricValue(
            name=name,
            value=self._counters[key],
            labels=labels or {},
        ))
        if len(entries) > _MAX_METRIC_SAMPLES:
            entries[:] = entries[-_MAX_METRIC_SAMPLES:]
    
    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None):
        key = f"{name}:{labels}" if labels else name
        self._gauges[key] = value
        entries = self._metrics[name]
        entries.append(MetricValue(
            name=name,
            value=value,
            labels=labels or {},
        ))
        if len(entries) > _MAX_METRIC_SAMPLES:
            entries[:] = entries[-_MAX_METRIC_SAMPLES:]
    
    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None):
        key = f"{name}:{labels}" if labels else name
        hist_entries = self._histograms[key]
        hist_entries.append(value)
        if len(hist_entries) > _MAX_METRIC_SAMPLES:
            hist_entries[:] = hist_entries[-_MAX_METRIC_SAMPLES:]
        entries = self._metrics[name]
        entries.append(MetricValue(
            name=name,
            value=value,
            labels=labels or {},
        ))
        if len(entries) > _MAX_METRIC_SAMPLES:
            entries[:] = entries[-_MAX_METRIC_SAMPLES:]
    
    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = f"{name}:{labels}" if labels else name
        return self._counters.get(key, 0.0)
    
    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = f"{name}:{labels}" if labels else name
        return self._gauges.get(key, 0.0)
    
    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float]:
        key = f"{name}:{labels}" if labels else name
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        total = sum(sorted_values)
        
        return {
            "count": count,
            "sum": total,
            "avg": total / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(count * 0.5)] if count > 0 else 0,
            "p90": sorted_values[int(count * 0.9)] if count > 0 else 0,
            "p99": sorted_values[int(count * 0.99)] if count > 0 else 0,
        }
    
    async def collect_database_metrics(self) -> dict[str, Any]:
        resource_count = await self.session.execute(select(func.count()).select_from(ResourceIndex))
        patient_count = await self.session.execute(select(func.count()).select_from(PatientMapping))
        label_count = await self.session.execute(select(func.count()).select_from(Label))
        webhook_count = await self.session.execute(select(func.count()).select_from(WebhookSubscription))
        pending_sync = await self.session.execute(
            select(func.count()).select_from(SyncEvent).where(SyncEvent.processed == False)
        )
        
        metrics = {
            "resources_total": resource_count.scalar() or 0,
            "patients_total": patient_count.scalar() or 0,
            "labels_total": label_count.scalar() or 0,
            "webhooks_total": webhook_count.scalar() or 0,
            "sync_events_pending": pending_sync.scalar() or 0,
        }
        
        for name, value in metrics.items():
            self.set_gauge(f"vna_{name}", value)
        
        return metrics
    
    def export_prometheus_format(self) -> str:
        lines = []
        
        for key, value in self._counters.items():
            name = key.split(":")[0] if ":" in key else key
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        for key, value in self._gauges.items():
            name = key.split(":")[0] if ":" in key else key
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        for key, values in self._histograms.items():
            name = key.split(":")[0] if ":" in key else key
            stats = self.get_histogram_stats(name)
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_sum {stats['sum']}")
        
        return "\n".join(lines)


class HealthCheckService:
    """Service for health checks and alerting."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._last_checks: dict[str, HealthStatus] = {}
    
    async def check_database(self) -> HealthStatus:
        try:
            start = time.time()
            await self.session.execute(select(1))
            latency = (time.time() - start) * 1000
            
            status = HealthStatus(
                component="database",
                status="healthy",
                message="Database connection OK",
                details={"latency_ms": round(latency, 2)},
            )
        except (SQLAlchemyError, RuntimeError) as e:
            logger.error("Database health check failed: %s", e, exc_info=True)
            status = HealthStatus(
                component="database",
                status="unhealthy",
                message=str(e),
            )
        
        self._last_checks["database"] = status
        return status
    
    async def check_resources(self) -> HealthStatus:
        try:
            result = await self.session.execute(select(func.count()).select_from(ResourceIndex))
            count = result.scalar() or 0
            
            status = HealthStatus(
                component="resources",
                status="healthy",
                message=f"{count} resources indexed",
                details={"count": count},
            )
        except SQLAlchemyError as e:
            logger.error("Resources health check failed: %s", e, exc_info=True)
            status = HealthStatus(
                component="resources",
                status="unhealthy",
                message=str(e),
            )
        
        self._last_checks["resources"] = status
        return status
    
    async def check_sync_queue(self) -> HealthStatus:
        try:
            result = await self.session.execute(
                select(func.count()).select_from(SyncEvent).where(SyncEvent.processed == False)
            )
            pending = result.scalar() or 0
            
            if pending > 1000:
                status = HealthStatus(
                    component="sync_queue",
                    status="degraded",
                    message=f"High pending sync events: {pending}",
                    details={"pending_count": pending},
                )
            else:
                status = HealthStatus(
                    component="sync_queue",
                    status="healthy",
                    message=f"{pending} pending sync events",
                    details={"pending_count": pending},
                )
        except SQLAlchemyError as e:
            logger.error("Sync queue health check failed: %s", e, exc_info=True)
            status = HealthStatus(
                component="sync_queue",
                status="unhealthy",
                message=str(e),
            )
        
        self._last_checks["sync_queue"] = status
        return status
    
    async def check_webhooks(self) -> HealthStatus:
        try:
            result = await self.session.execute(
                select(func.count()).select_from(WebhookSubscription).where(WebhookSubscription.enabled == True)
            )
            active = result.scalar() or 0
            
            status = HealthStatus(
                component="webhooks",
                status="healthy",
                message=f"{active} active webhook subscriptions",
                details={"active_count": active},
            )
        except SQLAlchemyError as e:
            logger.error("Webhooks health check failed: %s", e, exc_info=True)
            status = HealthStatus(
                component="webhooks",
                status="unhealthy",
                message=str(e),
            )
        
        self._last_checks["webhooks"] = status
        return status
    
    async def run_all_checks(self) -> dict[str, Any]:
        checks = await asyncio.gather(
            self.check_database(),
            self.check_resources(),
            self.check_sync_queue(),
            self.check_webhooks(),
        )
        
        all_healthy = all(c.status == "healthy" for c in checks)
        any_unhealthy = any(c.status == "unhealthy" for c in checks)
        
        overall_status = "healthy"
        if any_unhealthy:
            overall_status = "unhealthy"
        elif any(c.status == "degraded" for c in checks):
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": [
                {
                    "component": c.component,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in checks
            ],
        }
    
    def get_last_check(self, component: str) -> HealthStatus | None:
        return self._last_checks.get(component)


class AlertRule:
    """Alert rule definition."""
    
    def __init__(
        self,
        name: str,
        condition: str,
        threshold: float,
        comparison: str = "gt",
        duration_seconds: int = 60,
        severity: str = "warning",
        message_template: str | None = None,
    ):
        self.name = name
        self.condition = condition
        self.threshold = threshold
        self.comparison = comparison
        self.duration_seconds = duration_seconds
        self.severity = severity
        self.message_template = message_template or f"Alert: {name} triggered"
    
    def evaluate(self, value: float) -> bool:
        if self.comparison == "gt":
            return value > self.threshold
        elif self.comparison == "lt":
            return value < self.threshold
        elif self.comparison == "eq":
            return value == self.threshold
        elif self.comparison == "ne":
            return value != self.threshold
        return False


class AlertingService:
    """Service for alert management."""
    
    DEFAULT_RULES = [
        AlertRule(
            name="high_pending_sync_events",
            condition="sync_events_pending",
            threshold=1000,
            comparison="gt",
            severity="warning",
            message_template="High number of pending sync events: {value}",
        ),
        AlertRule(
            name="database_latency_high",
            condition="database_latency_ms",
            threshold=500,
            comparison="gt",
            severity="warning",
            message_template="Database latency is high: {value}ms",
        ),
        AlertRule(
            name="no_resources_indexed",
            condition="resources_total",
            threshold=0,
            comparison="eq",
            severity="info",
            message_template="No resources indexed in the system",
        ),
    ]
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._rules: list[AlertRule] = list(self.DEFAULT_RULES)
        self._alert_state: dict[str, dict[str, Any]] = {}
    
    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)
    
    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False
    
    async def evaluate_rules(self, metrics: dict[str, float]) -> list[dict[str, Any]]:
        alerts = []
        
        for rule in self._rules:
            metric_name = rule.condition
            value = metrics.get(metric_name, 0)
            
            triggered = rule.evaluate(value)
            state_key = rule.name
            
            if triggered:
                if state_key not in self._alert_state:
                    self._alert_state[state_key] = {
                        "triggered_at": datetime.now(timezone.utc),
                        "firings": 0,
                    }
                
                self._alert_state[state_key]["firings"] += 1
                
                if self._alert_state[state_key]["firings"] == 1:
                    alerts.append({
                        "rule": rule.name,
                        "status": "firing",
                        "severity": rule.severity,
                        "message": rule.message_template.format(value=value),
                        "value": value,
                        "threshold": rule.threshold,
                        "triggered_at": self._alert_state[state_key]["triggered_at"].isoformat(),
                    })
            else:
                if state_key in self._alert_state:
                    del self._alert_state[state_key]
        
        return alerts
    
    def get_active_alerts(self) -> list[dict[str, Any]]:
        return [
            {
                "rule": name,
                "triggered_at": state["triggered_at"].isoformat(),
                "firings": state["firings"],
            }
            for name, state in self._alert_state.items()
        ]
