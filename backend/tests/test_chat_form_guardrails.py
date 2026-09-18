from backend.app.core.form_flow import (
    apply_calculated_fields, apply_flow_rules, get_missing_fields, is_valid_next_question,
)
from backend.app.rag.agent import is_auto_fill_field
from backend.app.core.form_flow import prepend_group_introduction


def test_cluster_introduction_precedes_first_question_and_is_not_repeated():
    intro = "Vui lòng cung cấp thông tin người sử dụng đất dưới đây:"
    fields = [
        {"key": "recipient"},
        {"key": "name", "section_id": "owner", "question_group": intro},
        {"key": "address", "section_id": "owner", "question_group": intro},
    ]
    reply, seen = prepend_group_introduction(fields, "recipient", "Nơi nhận?", [])
    assert reply == "Nơi nhận?" and seen == []
    reply, seen = prepend_group_introduction(fields, "name", "Họ và tên?", seen)
    assert reply == intro + "\n\nHọ và tên?"
    reply, seen = prepend_group_introduction(fields, "address", "Địa chỉ?", seen)
    assert reply == "Địa chỉ?" and seen == ["owner"]
    reply, _ = prepend_group_introduction(fields, "name", "Họ và tên?", seen)
    assert reply == "Họ và tên?"


def test_cluster_intro_does_not_duplicate_or_replace_condition_question():
    fields = [{"key": "name", "section_id": "owner", "question_group": "Thông tin:"}]
    reply, seen = prepend_group_introduction(fields, "name", "Thông tin:\nTên?", [])
    assert reply.count("Thông tin:") == 1 and seen == ["owner"]
    fields[0]["condition_group_id"] = "owner"
    reply, seen = prepend_group_introduction(fields, "name", "Tên?", [])
    assert reply == "Tên?" and seen == []


def test_introduction_once_per_cluster_across_saved_chat_turns():
    import json
    fields = [
        {"key": "name", "name": "Name", "section_id": "owner", "question_group": "Owner information:"},
        {"key": "address", "name": "Address", "section_id": "owner", "question_group": "Owner information:"},
        {"key": "land", "name": "Land", "section_id": "land", "question_group": "Land information:"},
    ]
    state = {}
    for key, expected in [
        ("name", "Owner information:\n\nQuestion?"),
        ("address", "Question?"),
        ("address", "Question?"),
        ("land", "Land information:\n\nQuestion?"),
        ("name", "Question?"),
    ]:
        introduced = state.get("introduced_groups", [])
        state = apply_flow_rules(fields, {}, state)
        reply, state["introduced_groups"] = prepend_group_introduction(
            fields, key, "Question?", introduced,
        )
        assert reply == expected
        state = json.loads(json.dumps(state))
    assert state["introduced_groups"] == ["owner", "land"]


def test_chat_rejects_later_missing_question():
    fields = [{"key": "first"}, {"key": "later"}]
    assert is_valid_next_question(fields, fields[0], "first", {})
    assert not is_valid_next_question(fields, fields[0], "later", {})


def test_chat_accepts_selected_alternative_but_rejects_skipped_or_filled():
    fields = [
        {"key": "tax", "require_one_of_group": "identity"},
        {"key": "citizen", "require_one_of_group": "identity"},
    ]
    assert is_valid_next_question(fields, fields[0], "citizen", {})
    assert not is_valid_next_question(fields, fields[0], "citizen", {"citizen": "__SKIPPED__"})
    assert not is_valid_next_question(fields, fields[0], "citizen", {"citizen": "123"})


def test_formula_is_computed_and_never_asked():
    fields = [
        {"key": "amount", "display_order": 100, "value_source": "user_input"},
        {"key": "tax", "value_source": "formula", "calculation_formula": "[1] * 0.02"},
    ]
    data = {"amount": "1000000"}
    apply_flow_rules(fields, data)
    apply_calculated_fields(fields, data)
    assert data["tax"] == "20000"
    assert is_auto_fill_field(fields[1])
    assert not get_missing_fields([f for f in fields if not is_auto_fill_field(f)], data)
    data["amount"] = "2000000"
    apply_calculated_fields(fields, data)
    assert data["tax"] == "40000"


def test_inactive_invalid_field_does_not_block_completion():
    fields = [
        {"key": "parent", "name": "Parent"},
        {"key": "child", "name": "Child", "depends_on": {"field": "parent", "value": False}},
    ]
    data = {"parent": "yes"}
    apply_flow_rules(fields, data)
    missing_keys = {f["key"] for f in get_missing_fields(fields, data)}
    invalid = [key for key in ["child"] if key in missing_keys]
    assert data["child"] == "__SKIPPED__"
    assert not missing_keys and not invalid
