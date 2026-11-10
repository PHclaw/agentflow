"""
测试提示词工具（app/services/prompt_utils.py）
"""
import pytest

from app.services.prompt_utils import (
    align_variables_to_template,
    build_executable_user,
    expand_variable_combinations,
    extract_system_from_spec_md,
    extract_variables,
    looks_like_spec_md,
    primary_variable,
    render_template,
)


class TestExtractVariables:
    def test_extracts_unique_names_in_order(self):
        assert extract_variables("你好 {{name}}，{{ name }} 和 {{age}}") == ["name", "age"]

    def test_ignores_invalid_identifiers(self):
        assert extract_variables("{{1bad}} {{ok}}") == ["ok"]

    def test_handles_empty(self):
        assert extract_variables("") == []
        assert extract_variables(None) == []


class TestRenderTemplate:
    def test_replaces_known_variables(self):
        assert render_template("你好 {{name}}", {"name": "小明"}) == "你好 小明"

    def test_keeps_unknown_placeholder(self):
        assert render_template("你好 {{name}}", {}) == "你好 {{name}}"

    def test_handles_none_template(self):
        assert render_template(None, {"a": 1}) == ""


class TestAlignVariables:
    def test_fills_placeholder_from_common_key(self):
        aligned = align_variables_to_template("问题：{{question}}", {"input": "退款流程"})

        assert aligned["question"] == "退款流程"

    def test_keeps_explicit_value(self):
        aligned = align_variables_to_template("问题：{{question}}", {"question": "A", "input": "B"})

        assert aligned["question"] == "A"

    def test_single_placeholder_falls_back_to_any_value(self):
        aligned = align_variables_to_template("分析 {{topic}}", {"whatever": "销售额"})

        assert aligned["topic"] == "销售额"

    def test_no_placeholders_returns_normalized_values(self):
        assert align_variables_to_template("无占位符", {"a": None}) == {"a": ""}


class TestBuildExecutableUser:
    def test_renders_variable_into_template(self):
        assert build_executable_user("问题：{{question}}", {"question": "如何退款"}) == "问题：如何退款"

    def test_appends_value_when_not_rendered(self):
        result = build_executable_user("请回答", {"input": "销售额是多少"})

        assert "请回答" in result
        assert "销售额是多少" in result

    def test_defaults_to_input_placeholder(self):
        assert build_executable_user("", {"input": "你好"}) == "你好"

    def test_multiple_values_are_listed(self):
        result = build_executable_user("固定文本", {"a": "一", "b": "二"})

        assert "a: 一" in result and "b: 二" in result


class TestSpecMd:
    def test_extracts_system_block(self):
        md = "# 某 Skill\n\n### System\n\n```text\n你是一个助手\n```\n\n## 调用 Prompt\n"
        assert extract_system_from_spec_md(md) == "你是一个助手"

    def test_returns_empty_without_system_block(self):
        assert extract_system_from_spec_md("# 普通文档") == ""

    def test_looks_like_spec_md(self):
        assert looks_like_spec_md("# Skill\n\n## Executable Spec") is True
        assert looks_like_spec_md("随便一段文本") is False
        assert looks_like_spec_md(None) is False


class TestVariableCombinations:
    def test_empty_returns_single_execution(self):
        assert expand_variable_combinations(None) == [{}]

    def test_cartesian_product(self):
        combos = expand_variable_combinations({"input": ["a", "b"], "lang": ["zh"]})

        assert combos == [
            {"input": "a", "lang": "zh"},
            {"input": "b", "lang": "zh"},
        ]

    def test_empty_list_becomes_empty_string(self):
        assert expand_variable_combinations({"input": []}) == [{"input": ""}]


class TestPrimaryVariable:
    def test_returns_first_pair(self):
        assert primary_variable({"a": "1", "b": "2"}) == ("a", "1")

    def test_empty_map(self):
        assert primary_variable({}) == ("", "")
        assert primary_variable(None) == ("", "")
