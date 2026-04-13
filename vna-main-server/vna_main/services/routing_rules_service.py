"""Advanced routing rules service."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import RoutingRule

logger = logging.getLogger(__name__)

# Maximum regex pattern length to prevent ReDoS
_MAX_REGEX_LENGTH = 256
# Regex patterns that are known to cause catastrophic backtracking
_UNSAFE_REGEX_PATTERNS = re.compile(r'\([^)]*\+[^)]*\)\+|\([^)]*\+[^)]*\)\*')


def _validate_regex_pattern(pattern: str) -> None:
    """Validate a regex pattern for safety.
    
    Raises ValueError if the pattern is potentially dangerous.
    """
    if len(pattern) > _MAX_REGEX_LENGTH:
        raise ValueError(f"Regex pattern too long (max {_MAX_REGEX_LENGTH} characters)")
    if _UNSAFE_REGEX_PATTERNS.search(pattern):
        raise ValueError("Regex pattern contains potentially dangerous quantifier nesting")
    # Test-compile the pattern to catch syntax errors
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e


class RoutingRuleEngine:
    """Engine for evaluating routing rules."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._rules_cache: list[RoutingRule] | None = None

    async def _load_rules(self, force_reload: bool = False) -> list[RoutingRule]:
        if self._rules_cache is None or force_reload:
            stmt = (
                select(RoutingRule)
                .where(RoutingRule.enabled == True)
                .order_by(RoutingRule.priority.desc(), RoutingRule.id)
            )
            result = await self.session.execute(stmt)
            self._rules_cache = list(result.scalars().all())
        return self._rules_cache

    def _match_condition(self, value: Any, condition: dict) -> bool:
        op = condition.get("operator", "eq")
        target = condition.get("value")

        if op == "eq":
            return value == target
        elif op == "ne":
            return value != target
        elif op == "in":
            return value in (target if isinstance(target, list) else [target])
        elif op == "not_in":
            return value not in (target if isinstance(target, list) else [target])
        elif op == "contains":
            return target in str(value) if value else False
        elif op == "starts_with":
            return str(value).startswith(target) if value else False
        elif op == "ends_with":
            return str(value).endswith(target) if value else False
        elif op == "regex":
            if value:
                try:
                    _validate_regex_pattern(str(target))
                    return bool(re.match(target, str(value)))
                except ValueError:
                    logger.warning("Unsafe regex pattern rejected: %s", target)
                    return False
            return False
        elif op == "gt":
            return value > target if isinstance(value, (int, float)) else False
        elif op == "lt":
            return value < target if isinstance(value, (int, float)) else False
        elif op == "gte":
            return value >= target if isinstance(value, (int, float)) else False
        elif op == "lte":
            return value <= target if isinstance(value, (int, float)) else False
        elif op == "exists":
            return value is not None
        elif op == "not_exists":
            return value is None

        return False

    def _evaluate_rule(self, resource_data: dict[str, Any], rule: RoutingRule) -> bool:
        conditions = rule.conditions
        if not conditions:
            return True

        match_type = conditions.get("match", "all")
        rules_list = conditions.get("rules", [])

        if not rules_list:
            return True

        results = []
        for cond in rules_list:
            field = cond.get("field")
            if not field:
                continue

            value = resource_data.get(field)
            results.append(self._match_condition(value, cond))

        if match_type == "all":
            return all(results)
        elif match_type == "any":
            return any(results)
        elif match_type == "none":
            return not any(results)

        return False

    async def evaluate(
        self,
        resource_data: dict[str, Any],
        force_reload: bool = False,
    ) -> str | None:
        rules = await self._load_rules(force_reload)

        for rule in rules:
            if self._evaluate_rule(resource_data, rule):
                return rule.target

        return None

    async def get_matching_rules(
        self,
        resource_data: dict[str, Any],
        force_reload: bool = False,
    ) -> list[dict[str, Any]]:
        rules = await self._load_rules(force_reload)
        matching = []

        for rule in rules:
            if self._evaluate_rule(resource_data, rule):
                matching.append({
                    "id": rule.id,
                    "name": rule.name,
                    "target": rule.target,
                    "priority": rule.priority,
                })

        return matching

    def invalidate_cache(self):
        self._rules_cache = None


class RoutingRulesService:
    """Service for managing routing rules."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._engine = RoutingRuleEngine(session)

    async def list_rules(
        self,
        enabled_only: bool = False,
        rule_type: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(RoutingRule)
        if enabled_only:
            stmt = stmt.where(RoutingRule.enabled == True)
        if rule_type:
            stmt = stmt.where(RoutingRule.rule_type == rule_type)
        stmt = stmt.order_by(RoutingRule.priority.desc(), RoutingRule.id)

        result = await self.session.execute(stmt)
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "rule_type": r.rule_type,
                "conditions": r.conditions,
                "target": r.target,
                "priority": r.priority,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in result.scalars().all()
        ]

    async def get_rule(self, rule_id: int) -> dict[str, Any] | None:
        rule = await self.session.get(RoutingRule, rule_id)
        if rule is None:
            return None

        return {
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "conditions": rule.conditions,
            "target": rule.target,
            "priority": rule.priority,
            "enabled": rule.enabled,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }

    async def create_rule(
        self,
        name: str,
        target: str,
        rule_type: str = "data_type",
        conditions: dict | None = None,
        description: str | None = None,
        priority: int = 100,
        enabled: bool = True,
    ) -> RoutingRule:
        rule = RoutingRule(
            name=name,
            description=description,
            rule_type=rule_type,
            conditions=conditions or {},
            target=target,
            priority=priority,
            enabled=enabled,
        )
        self.session.add(rule)
        await self.session.flush()
        self._engine.invalidate_cache()
        return rule

    async def update_rule(
        self,
        rule_id: int,
        **updates,
    ) -> RoutingRule | None:
        rule = await self.session.get(RoutingRule, rule_id)
        if rule is None:
            return None

        updatable_fields = {"name", "description", "rule_type", "conditions", "target", "priority", "enabled"}
        for key, value in updates.items():
            if key in updatable_fields:
                setattr(rule, key, value)

        await self.session.flush()
        self._engine.invalidate_cache()
        return rule

    async def delete_rule(self, rule_id: int) -> bool:
        rule = await self.session.get(RoutingRule, rule_id)
        if rule is None:
            return False

        await self.session.delete(rule)
        await self.session.flush()
        self._engine.invalidate_cache()
        return True

    async def toggle_rule(self, rule_id: int, enabled: bool) -> bool:
        rule = await self.session.get(RoutingRule, rule_id)
        if rule is None:
            return False

        rule.enabled = enabled
        await self.session.flush()
        self._engine.invalidate_cache()
        return True

    async def reorder_rules(self, rule_priorities: list[dict[str, int]]) -> bool:
        for item in rule_priorities:
            rule_id = item.get("id")
            priority = item.get("priority")
            if rule_id is None or priority is None:
                continue

            rule = await self.session.get(RoutingRule, rule_id)
            if rule:
                rule.priority = priority

        await self.session.flush()
        self._engine.invalidate_cache()
        return True

    async def evaluate_resource(
        self,
        resource_data: dict[str, Any],
    ) -> dict[str, Any]:
        target = await self._engine.evaluate(resource_data)
        matching = await self._engine.get_matching_rules(resource_data)

        return {
            "target": target,
            "matching_rules": matching,
            "resource_data": resource_data,
        }

    async def test_rule(
        self,
        conditions: dict,
        resource_data: dict[str, Any],
    ) -> dict[str, Any]:
        temp_rule = RoutingRule(
            name="test",
            rule_type="test",
            conditions=conditions,
            target="test",
        )
        matches = self._engine._evaluate_rule(resource_data, temp_rule)

        return {
            "matches": matches,
            "conditions": conditions,
            "resource_data": resource_data,
        }

    async def get_rule_types(self) -> list[dict[str, str]]:
        return [
            {"type": "data_type", "description": "Route based on data type (DICOM, BIDS, etc.)"},
            {"type": "modality", "description": "Route based on imaging modality (CT, MR, PT, etc.)"},
            {"type": "patient", "description": "Route based on patient attributes"},
            {"type": "study", "description": "Route based on study attributes"},
            {"type": "custom", "description": "Custom routing with complex conditions"},
        ]

    async def get_operators(self) -> list[dict[str, str]]:
        return [
            {"operator": "eq", "description": "Equals"},
            {"operator": "ne", "description": "Not equals"},
            {"operator": "in", "description": "In list"},
            {"operator": "not_in", "description": "Not in list"},
            {"operator": "contains", "description": "Contains substring"},
            {"operator": "starts_with", "description": "Starts with"},
            {"operator": "ends_with", "description": "Ends with"},
            {"operator": "regex", "description": "Matches regex pattern"},
            {"operator": "gt", "description": "Greater than"},
            {"operator": "lt", "description": "Less than"},
            {"operator": "gte", "description": "Greater than or equal"},
            {"operator": "lte", "description": "Less than or equal"},
            {"operator": "exists", "description": "Field exists (not null)"},
            {"operator": "not_exists", "description": "Field does not exist (is null)"},
        ]
