from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any, Literal

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.models import PolicyDefinition, Resource, Rule


Decision = Literal["allow", "deny"]


@dataclass
class Match:
    policy_id: str
    rule_id: str
    effect: Decision
    obligations: list[dict[str, Any]]


def _get_path(value: object, path: str) -> object:
    cur: object = value
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _pattern_match(pattern: str, value: str | None) -> bool:
    if value is None:
        return False
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def _any_pattern_match(patterns: list[str], value: str | None) -> bool:
    if not patterns:
        return True
    return any(_pattern_match(p, value) for p in patterns)


def _evaluate_conditions(conditions: list[dict[str, Any]], facts: dict[str, Any]) -> bool:
    for cond in conditions:
        key = str(cond.get("key", ""))
        op = cond.get("op")
        expected = cond.get("value")

        actual = _get_path(facts, key)

        if op == "exists":
            if actual is None:
                return False
            continue

        if op == "eq":
            if actual != expected:
                return False
            continue

        if op == "ne":
            if actual == expected:
                return False
            continue

        if op == "in":
            if not isinstance(expected, list):
                return False
            if actual not in expected:
                return False
            continue

        if op == "contains":
            if isinstance(actual, str) and isinstance(expected, str):
                if expected not in actual:
                    return False
            elif isinstance(actual, list):
                if expected not in actual:
                    return False
            else:
                return False
            continue

        return False

    return True


def _facts(envelope: Envelope, resource: Resource, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "envelope": envelope.model_dump(),
        "attributes": envelope.attributes,
        "resource": resource.model_dump(),
        "context": context,
    }


def _rule_matches(rule: Rule, action: str, resource: Resource, facts: dict[str, Any]) -> bool:
    if not _any_pattern_match(rule.actions, action):
        return False

    if not _any_pattern_match(rule.resource_types, resource.type):
        return False

    if rule.resource_ids:
        if not _any_pattern_match(rule.resource_ids, resource.id):
            return False

    conds = [c.model_dump() for c in rule.conditions]
    if conds and not _evaluate_conditions(conds, facts):
        return False

    return True


def evaluate_policies(
    *,
    policies: list[PolicyDefinition],
    action: str,
    resource: Resource,
    context: dict[str, Any],
    envelope: Envelope,
) -> tuple[Decision, str | None, Match | None]:
    facts = _facts(envelope, resource, context)

    matched_allow: Match | None = None

    for policy in policies:
        for rule in policy.rules:
            if not _rule_matches(rule, action, resource, facts):
                continue

            m = Match(
                policy_id=policy.id,
                rule_id=rule.id,
                effect=rule.effect,
                obligations=list(rule.obligations),
            )

            if rule.effect == "deny":
                return "deny", "matched_deny_rule", m

            if matched_allow is None:
                matched_allow = m

    if matched_allow is not None:
        return "allow", "matched_allow_rule", matched_allow

    return "deny", "no_matching_policy", None


def explain_policies(
    *,
    policies: list[PolicyDefinition],
    action: str,
    resource: Resource,
    context: dict[str, Any],
    envelope: Envelope,
) -> dict[str, Any]:
    facts = _facts(envelope, resource, context)
    matches: list[dict[str, Any]] = []

    for policy in policies:
        for rule in policy.rules:
            if _rule_matches(rule, action, resource, facts):
                matches.append(
                    {
                        "policy_id": policy.id,
                        "rule_id": rule.id,
                        "effect": rule.effect,
                    }
                )

    decision, reason, match = evaluate_policies(
        policies=policies,
        action=action,
        resource=resource,
        context=context,
        envelope=envelope,
    )

    out: dict[str, Any] = {
        "decision": decision,
        "reason": reason,
        "trace_id": str(uuid.uuid4()),
        "matched_rules": matches,
    }

    if match and match.obligations:
        out["obligations"] = match.obligations

    return out
