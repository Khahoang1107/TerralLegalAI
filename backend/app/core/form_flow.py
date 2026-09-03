"""Deterministic form-question flow shared by the chat API and the AI prompt.

The AI may phrase questions and extract answers, but it must not decide whether a
form group is complete or whether a dependent field is applicable.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, MutableMapping, Tuple


SKIPPED = "__SKIPPED__"
_TRUE_VALUES = {"có", "co", "yes", "true", "1", "x", "☑", "đúng", "rồi", "được", "ok"}
_FALSE_VALUES = {"không", "khong", "no", "false", "0", "☐", "sai", "chưa", "ko", "bỏ qua", "bo qua", "không có", "khong co"}
_LABEL_RE = re.compile(r"\[(\d+(?:\.\d+)*)\]")


def is_real_value(value: Any) -> bool:
    return value not in (None, "", SKIPPED)


def is_false_value(value: Any) -> bool:
    return value == SKIPPED or (isinstance(value, str) and value.strip().lower() in _FALSE_VALUES)


def _label_order(name: str) -> Tuple[int, ...] | None:
    match = _LABEL_RE.search(name or "")
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def order_fields(fields: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return fields in the Admin/PDF order.

    New visual forms persist ``display_order``. Older forms retain their existing
    JSON-array order unless their labels explicitly contain a numeric [n] prefix.
    """
    decorated = []
    for index, field in enumerate(fields):
        raw_order = field.get("display_order")
        try:
            display_order = int(raw_order) if raw_order is not None else None
        except (TypeError, ValueError):
            display_order = None
        label_order = _label_order(str(field.get("name", "")))
        # Do not make an unlabelled old field jump ahead of the stored Admin order.
        key = (0, display_order, index) if display_order is not None else ((1, label_order, index) if label_order else (2, (), index))
        decorated.append((key, field))
    return [field for _, field in sorted(decorated, key=lambda item: item[0])]


def _dependency_is_active(field: Dict[str, Any], field_by_name: Dict[str, Dict[str, Any]], data: Dict[str, Any]) -> bool | None:
    """True/False when a dependency can be evaluated; None when parent is absent."""
    depends_on = field.get("depends_on") or field.get("group_depends_on")
    if not isinstance(depends_on, dict) or not depends_on.get("field"):
        return True
    parent_ref = str(depends_on["field"])
    parent = field_by_name.get(parent_ref) or next(
        (candidate for candidate in field_by_name.values() if str(candidate.get("key", "")) == parent_ref),
        None,
    )
    if not parent:
        return True  # Invalid Admin reference must not silently hide required data.
    value = data.get(parent.get("key", ""))
    if value in (None, ""):
        return None
    expected = depends_on.get("value", True)
    if isinstance(expected, bool):
        actual = not is_false_value(value) if expected else is_false_value(value)
        return actual
    return str(value).strip().casefold() == str(expected).strip().casefold()


def _legacy_label_dependency_active(field: Dict[str, Any], fields: Iterable[Dict[str, Any]], data: Dict[str, Any]) -> bool | None:
    """Compatibility for old forms where [20.1] follows boolean [20].

    New forms should always use ``depends_on`` from Admin.  This fallback is
    deliberately limited to boolean parents so ordinary numbered sections are
    never treated as branches.
    """
    if field.get("depends_on"):
        return True
    label = _label_order(str(field.get("name", "")))
    if not label or len(label) < 2:
        return True
    parent_number = (label[0],)
    for parent in fields:
        if _label_order(str(parent.get("name", ""))) == parent_number and parent.get("type") == "boolean":
            value = data.get(parent.get("key", ""))
            if value in (None, ""):
                return None
            return not is_false_value(value)
    return True


def apply_flow_rules(
    fields: Iterable[Dict[str, Any]],
    data: MutableMapping[str, Any],
    flow_state: Dict[str, Any] | None = None,
) -> Dict[str, List[str]]:
    """Apply reversible branch/group skips and return their provenance.

    Only skips created by this function are reopened when a parent answer changes.
    A user's explicit ``__SKIPPED__`` remains an explicit answer.
    """
    ordered = order_fields(fields)
    field_by_name = {str(f.get("name", "")): f for f in ordered}
    state = flow_state or {}
    branch_skipped = set(state.get("branch_skipped_keys", []))
    group_skipped = set(state.get("group_skipped_keys", []))

    # Re-evaluate dependencies until parent/child cascades settle.
    changed = True
    while changed:
        changed = False
        for field in ordered:
            key = field.get("key")
            if not key:
                continue
            active = _dependency_is_active(field, field_by_name, data)
            if active is True:
                active = _legacy_label_dependency_active(field, ordered, data)
            if active is False:
                if data.get(key) != SKIPPED:
                    data[key] = SKIPPED
                    changed = True
                    branch_skipped.add(key)
                # Preserve provenance only if this engine (or one-of handling)
                # created the old skip. An explicit user skip must stay explicit
                # if the parent later becomes active again.
                elif key in branch_skipped or key in group_skipped:
                    branch_skipped.add(key)
            elif active is True and key in branch_skipped:
                if data.get(key) == SKIPPED:
                    data.pop(key, None)
                    changed = True
                branch_skipped.discard(key)
            elif key in branch_skipped and is_real_value(data.get(key)):
                branch_skipped.discard(key)

    # A valid answer to one member fulfils exactly one "one-of" group.
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for field in ordered:
        group = field.get("require_one_of_group")
        if group:
            groups.setdefault(str(group), []).append(field)
    for members in groups.values():
        fulfilled = any(is_real_value(data.get(member.get("key", ""))) for member in members)
        if fulfilled:
            for member in members:
                key = member.get("key")
                if key and not is_real_value(data.get(key)):
                    data[key] = SKIPPED
                    group_skipped.add(key)
        else:
            # Reopen only values the engine skipped; user skips must remain visible
            # so get_missing_fields can ask the group again.
            for member in members:
                key = member.get("key")
                if key in group_skipped:
                    if data.get(key) == SKIPPED:
                        data.pop(key, None)
                    group_skipped.discard(key)

    return {
        "branch_skipped_keys": sorted(branch_skipped),
        "group_skipped_keys": sorted(group_skipped),
    }


def get_missing_fields(fields: Iterable[Dict[str, Any]], data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the deterministic next questions, including an unmet one-of group."""
    ordered = order_fields(fields)
    field_by_name = {str(f.get("name", "")): f for f in ordered}
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for field in ordered:
        if field.get("require_one_of_group"):
            groups.setdefault(str(field["require_one_of_group"]), []).append(field)

    unmet_representatives: Dict[str, str] = {}
    for group, members in groups.items():
        if not any(is_real_value(data.get(member.get("key", ""))) for member in members):
            candidate = next((m for m in members if data.get(m.get("key", "")) != SKIPPED), members[0])
            unmet_representatives[group] = candidate.get("key", "")

    missing: List[Dict[str, Any]] = []
    for field in ordered:
        key = field.get("key", "")
        group = field.get("require_one_of_group")
        if group:
            if unmet_representatives.get(str(group)) == key:
                missing.append(field)
            continue
        if is_real_value(data.get(key)) or data.get(key) == SKIPPED:
            continue
        # A child waits for a missing parent; a false parent was already skipped.
        active = _dependency_is_active(field, field_by_name, data)
        if active is True:
            active = _legacy_label_dependency_active(field, ordered, data)
        if active is None:
            continue
        missing.append(field)
    return missing
