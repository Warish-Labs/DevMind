"""Parser and validator for in-repo custom review rules (e.g. .devmind/rules.yaml)."""

from __future__ import annotations

import json
import logging

import yaml

from app.core.errors import ValidationError
from app.domain.review.schemas import ReviewRuleCreate, ScopeSelector

logger = logging.getLogger(__name__)


def parse_review_rules_content(content: str, source_type: str = "yaml") -> list[ReviewRuleCreate]:
    """Parse and validate review rules from a YAML or JSON file string.

    Returns a list of validated ReviewRuleCreate instances.
    Raises ValidationError if format is malformed or invalid schema.
    """
    if not content or not content.strip():
        return []

    try:
        if source_type.lower() in ("json", "application/json") or content.strip().startswith("{"):
            raw_data = json.loads(content)
        else:
            raw_data = yaml.safe_load(content)
    except Exception as exc:
        raise ValidationError(
            detail=f"Malformed review rules {source_type.upper()} file: {exc}"
        ) from exc

    if not isinstance(raw_data, dict):
        raise ValidationError(
            detail="Review rules configuration must be a dictionary with a 'rules' list"
        )

    raw_rules = raw_data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValidationError(detail="'rules' key must contain a list of rule definitions")

    parsed_rules: list[ReviewRuleCreate] = []
    for idx, rule_dict in enumerate(raw_rules):
        if not isinstance(rule_dict, dict):
            raise ValidationError(detail=f"Rule item #{idx + 1} must be an object")

        try:
            # Map scope_selector if dictionary provided
            scope_raw = rule_dict.get("scope_selector", {})
            if isinstance(scope_raw, dict):
                scope = ScopeSelector(
                    paths=scope_raw.get("paths", ["**/*"]),
                    languages=scope_raw.get("languages"),
                    ignore=scope_raw.get("ignore"),
                )
            else:
                scope = ScopeSelector()

            rule = ReviewRuleCreate(
                rule_id=str(rule_dict.get("rule_id", f"CUSTOM-{idx + 1}")),
                title=str(rule_dict.get("title", f"Custom Rule {idx + 1}")),
                category=str(rule_dict.get("category", "quality")),
                severity=str(rule_dict.get("severity", "medium")),
                scope_selector=scope,
                check_type=str(rule_dict.get("check_type", "pattern_forbidden")),
                check_config=rule_dict.get("check_config", {}),
                message=str(rule_dict.get("message", "Custom review rule triggered")),
                suggested_fix_template=rule_dict.get("suggested_fix")
                or rule_dict.get("suggested_fix_template"),
                is_enabled=bool(rule_dict.get("is_enabled", True)),
            )
            parsed_rules.append(rule)
        except Exception as exc:
            raise ValidationError(detail=f"Invalid rule definition at index {idx}: {exc}") from exc

    return parsed_rules
