from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict

placeholder_pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_.\-]+)\s*\}\}")


def get_value(context: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


def resolve_placeholders(value: Any, context: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item, context) for item in value]
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            path = match.group(1)
            resolved = get_value(context, path)
            return str(resolved)

        return placeholder_pattern.sub(replace, value)
    return value


def merge_context(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    merged.update(updates)
    return merged
