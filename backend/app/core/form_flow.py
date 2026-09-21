"""Deterministic form-question flow shared by the chat API and the AI prompt.

The AI may phrase questions and extract answers, but it must not decide whether a
form group is complete or whether a dependent field is applicable.
"""
from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, Iterable, List, MutableMapping, Tuple


SKIPPED = "__SKIPPED__"
_TRUE_VALUES = {"có", "co", "yes", "true", "1", "x", "☑", "đúng", "rồi", "được", "ok"}
_FALSE_VALUES = {"không", "khong", "no", "false", "0", "☐", "sai", "chưa", "ko", "bỏ qua", "bo qua", "không có", "khong co"}
_LABEL_RE = re.compile(r"\[(\d+(?:\.\d+)*)\]")
_FORMULA_REF_RE = re.compile(r"\[([^\[\]]+)\]")


def is_real_value(value: Any) -> bool:
    return value not in (None, "", SKIPPED)


def _decimal_value(value: Any) -> Decimal:
    """Parse common Vietnamese currency/number input without guessing text."""
    if isinstance(value, bool) or value in (None, "", SKIPPED):
        raise InvalidOperation
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    raw = str(value).strip().replace(" ", "")
    if not re.fullmatch(r"[-+]?\d[\d.,]*", raw):
        raise InvalidOperation
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1 or ("." in raw and len(raw.rsplit(".", 1)[1]) == 3):
        raw = raw.replace(".", "")
    elif raw.count(",") > 1 or ("," in raw and len(raw.rsplit(",", 1)[1]) == 3):
        raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    return Decimal(raw)


def _eval_decimal_expression(expression: str) -> Decimal:
    """Evaluate arithmetic only; names, calls and every other AST node are rejected."""
    operators = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
    }

    def visit(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError("Công thức chỉ được dùng số và các phép +, -, *, /, ().")

    return visit(ast.parse(expression, mode="eval"))


def apply_calculated_fields(fields: Iterable[Dict[str, Any]], data: MutableMapping[str, Any]) -> None:
    """Resolve formula fields in display order when all referenced inputs exist."""
    ordered = order_fields(fields)
    references: Dict[str, Dict[str, Any]] = {}
    for field in ordered:
        key = str(field.get("key", ""))
        name = str(field.get("name", ""))
        if key:
            references[key] = field
        if name:
            references[name] = field
        label = _label_order(name)
        if label:
            references[".".join(str(part) for part in label)] = field
        raw_order = field.get("display_order")
        if isinstance(raw_order, int) and raw_order > 0 and raw_order % 100 == 0:
            references[str(raw_order // 100)] = field

    for field in ordered:
        if field.get("value_source") != "formula":
            continue
        target = str(field.get("key", ""))
        formula = str(field.get("calculation_formula") or "").strip()
        if not target or not formula:
            continue
        missing = False

        def replace_reference(match: re.Match[str]) -> str:
            nonlocal missing
            ref = match.group(1).strip()
            source = references.get(ref)
            value = data.get(source.get("key", "")) if source else None
            try:
                return str(_decimal_value(value))
            except (InvalidOperation, ValueError):
                missing = True
                return "0"

        expression = _FORMULA_REF_RE.sub(replace_reference, formula)
        if missing or _FORMULA_REF_RE.search(expression):
            data.pop(target, None)
            continue
        try:
            result = _eval_decimal_expression(expression)
            if not result.is_finite():
                raise ValueError("Kết quả không hữu hạn")
            integral = result == result.to_integral_value()
            data[target] = str(result.quantize(Decimal("1"))) if integral else format(result.normalize(), "f")
        except (ArithmeticError, InvalidOperation, SyntaxError, ValueError):
            data.pop(target, None)


def is_false_value(value: Any) -> bool:
    return value == SKIPPED or (isinstance(value, str) and value.strip().lower() in _FALSE_VALUES)


def _label_order(name: str) -> Tuple[int, ...] | None:
    match = _LABEL_RE.search(name or "")
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def order_fields(fields: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return fields in the Admin/PDF order.

    New visual forms persist ``display_order``. Older forms retain their existing
    JSON-array order unless their labels explicitly contain a numeric [n] prefix.
    Virtual condition fields (section_condition_*) are dynamically anchored right
    before their first member field if their stored display_order is unconfigured or <= 10.
    """
    field_list = list(fields)

    # Determine the minimum display_order of physical fields belonging to each section
    member_min_orders: Dict[str, int] = {}
    for index, f in enumerate(field_list):
        if not f.get("is_virtual"):
            raw_order = f.get("display_order")
            try:
                ord_val = int(raw_order) if raw_order is not None else None
            except (TypeError, ValueError):
                ord_val = None
            if ord_val is None:
                ord_val = (index + 1) * 100
            sec_id = f.get("section_id") or f.get("alternative_group_id") or f.get("condition_group_id")
            dep = f.get("depends_on")
            dep_key = dep.get("field") if isinstance(dep, dict) else None
            derived = f.get("derived_from")
            derived_key = derived.get("field") if isinstance(derived, dict) else None
            if sec_id:
                member_min_orders[str(sec_id)] = min(member_min_orders.get(str(sec_id), 999999), ord_val)
            if dep_key:
                member_min_orders[str(dep_key)] = min(member_min_orders.get(str(dep_key), 999999), ord_val)
            if derived_key:
                member_min_orders[str(derived_key)] = min(member_min_orders.get(str(derived_key), 999999), ord_val)

    decorated = []
    for index, field in enumerate(field_list):
        raw_order = field.get("display_order")
        try:
            display_order = int(raw_order) if raw_order is not None else None
        except (TypeError, ValueError):
            display_order = None

        key_str = str(field.get("key", ""))
        is_virt = field.get("is_virtual") or key_str.startswith("section_condition_")
        if is_virt:
            sec_id = key_str.replace("section_condition_", "")
            target_order = member_min_orders.get(sec_id) or member_min_orders.get(key_str)
            if target_order is not None:
                display_order = target_order - 1
            elif display_order is None or display_order < 100:
                display_order = 9999
        elif display_order is None:
            display_order = (index + 1) * 100

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

    # Resolve output-only fields from an earlier answer. These fields represent
    # physical marks on the PDF and must never become extra questions. Members
    # may be far apart in PDF order; resolving them does not affect fields in
    # between.
    for field in ordered:
        derived_from = field.get("derived_from")
        key = field.get("key")
        if not key or not isinstance(derived_from, dict) or not derived_from.get("field"):
            continue
        parent_ref = str(derived_from["field"])
        parent = field_by_name.get(parent_ref) or next(
            (candidate for candidate in field_by_name.values() if str(candidate.get("key", "")) == parent_ref),
            None,
        )
        if not parent:
            continue
        parent_value = data.get(parent.get("key", ""))
        if parent_value in (None, "", SKIPPED):
            data.pop(key, None)
            continue
        expected = derived_from.get("value", True)
        if isinstance(expected, bool):
            matches = (not is_false_value(parent_value)) if expected else is_false_value(parent_value)
        else:
            matches = str(parent_value).strip().casefold() == str(expected).strip().casefold()
        data[key] = "có" if matches else "không"

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
    for f in ordered:
        if f.get("key"):
            field_by_name[str(f.get("key"))] = f
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
        if field.get("derived_from"):
            continue
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


def get_one_of_members(
    fields: Iterable[Dict[str, Any]],
    field_or_key: Dict[str, Any] | str,
) -> List[Dict[str, Any]]:
    """Return the alternatives belonging to the same legacy one-of group.

    Newer forms have a virtual ``choice`` lead field. Older saved forms only
    carry ``require_one_of_group`` on each alternative. Chat uses this helper
    to give both schemas the same two-step UX: choose an alternative, then
    provide its value.
    """
    ordered = order_fields(fields)
    if isinstance(field_or_key, dict):
        target = field_or_key
    else:
        target = next(
            (field for field in ordered if str(field.get("key", "")) == str(field_or_key)),
            None,
        )
    if not target or not target.get("require_one_of_group"):
        return []
    group = str(target["require_one_of_group"])
    return [field for field in ordered if str(field.get("require_one_of_group") or "") == group]


def build_one_of_choice_question(members: Iterable[Dict[str, Any]]) -> str:
    """Build the canonical, user-facing question for a legacy one-of group."""
    names = []
    for field in members:
        name = str(field.get("name") or field.get("key") or "").strip()
        # Labels such as "[15]" are useful for PDF ordering, not conversation.
        name = _LABEL_RE.sub("", name, count=1).strip(" .:-")
        names.append(name)
    names = [name for name in names if name]
    if not names:
        return "Bạn cần khai báo một trong các thông tin của nhóm này. Bạn muốn cung cấp thông tin nào?"
    if len(names) == 1:
        choices = names[0]
    elif len(names) == 2:
        choices = f"{names[0]} hoặc {names[1]}"
    else:
        choices = f"{', '.join(names[:-1])} hoặc {names[-1]}"
    return f"Bạn cần khai báo một trong các thông tin sau: {choices}. Bạn muốn cung cấp thông tin nào?"


def is_valid_one_of_next_field(
    fields: Iterable[Dict[str, Any]],
    representative: Dict[str, Any] | None,
    candidate_key: str | None,
) -> bool:
    """Allow the AI to move from a group representative to a chosen member."""
    if not representative or not candidate_key:
        return False
    return any(
        str(member.get("key", "")) == str(candidate_key)
        for member in get_one_of_members(fields, representative)
    )


def is_valid_next_question(fields, next_field, candidate_key, data) -> bool:
    """Enforce question order while allowing an unanswered active alternative."""
    if not next_field or not candidate_key:
        return False
    if candidate_key == next_field.get("key"):
        return True
    return (is_valid_one_of_next_field(fields, next_field, candidate_key)
            and data.get(candidate_key) in (None, ""))


def prepend_group_introduction(fields, candidate_key, reply, introduced_groups):
    """Show a configured cluster introduction once, before its first question."""
    introduced = list(introduced_groups or [])
    field = next((f for f in fields if f.get("key") == candidate_key), None)
    if not field or field.get("condition_group_id") or field.get("alternative_group_id"):
        return reply, introduced
    group = field.get("section_id")
    introduction = str(field.get("question_group") or "").strip()
    if not group or not introduction or str(group) in introduced:
        return reply, introduced
    # The backend owns the introduction; avoid doubling it if an older agent
    # happens to include the exact configured text already.
    if introduction not in reply:
        reply = f"{introduction}\n\n{reply}"
    introduced.append(str(group))
    return reply, introduced
