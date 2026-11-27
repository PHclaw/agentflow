"""安全数学求值的回归测试。

背景：``tools_memory._calculator_tool`` 曾经直接 ``eval(expression)``，
而 expression 来自 LLM 的 function-calling 参数——提示注入可以诱导模型
「以为自己在做数学题」从而调用它，一条 ``__import__('os').system(...)``
就是后端进程的任意代码执行。这里锁住修复，防止有人把 eval 改回去。

Found by /qa on 2026-11-26
"""
import pytest

from app.core.safe_math import SafeMathError, safe_eval_math
from app.integrations.tools_memory import tool_manager


class TestSafeEvalMath:
    """正常数学表达式必须继续可用。"""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("2 + 3 * 4", 14),
            ("(1 + 2) / 3", 1.0),
            ("10 % 3", 1),
            ("2**10", 1024),
            ("-5 + 2", -3),
            ("7 // 2", 3),
            ("1.5 * 2", 3.0),
            ("  8 - 3  ", 5),
        ],
    )
    def test_normal_arithmetic(self, expr, expected):
        assert safe_eval_math(expr) == expected

    @pytest.mark.parametrize(
        "payload",
        [
            # 任意代码执行
            "__import__('os').getcwd()",
            "__import__('subprocess').check_output(['echo','x'])",
            "open('pwned','w').write('x')",
            "exec('1+1')",
            "eval('1+1')",
            # 沙箱逃逸经典链
            "().__class__.__bases__[0].__subclasses__()",
            "[c for c in ().__class__.__mro__]",
            "lambda: 1",
            # 算力耗尽
            "9**9**9**9",
            "10**100",
            "2**1001",
            "2**1e6",
            # 报告者建议的沙箱逃逸变体（__mro__ 而非 __bases__）
            "().__class__.__mro__[1].__subclasses__()",
            "[c for c in ().__class__.__mro__]",
            # 边界：算术异常必须收敛成 SafeMathError，而不是穿透
            "0**-1",
            "0.0**-1",
            "10**309.0",
            # 非有限结果
            "1e300 * 1e300",
            # 未定义名字
            "a + b",
            # 边界
            "",
            "   ",
            "1/0",
            "1" * 600,
        ],
    )
    def test_attack_payloads_rejected(self, payload):
        with pytest.raises(SafeMathError):
            safe_eval_math(payload)

    def test_bool_not_treated_as_number(self):
        # True/False 是 int 子类，不能借道当数字用
        with pytest.raises(SafeMathError):
            safe_eval_math("True + 1")


class TestCalculatorTool:
    """真实调用链：LLM 通过 function-calling 走到这个 handler。"""

    def test_legit_calculation(self):
        assert tool_manager._calculator_tool("2 + 3 * 4") == 14.0

    @pytest.mark.parametrize(
        "payload",
        [
            "__import__('os').getcwd()",
            "__import__('os').environ",
            "open('pwned','w')",
            "9**9**9**9",
            # 边界算术异常不能穿透契约
            "0**-1",
            "10**309.0",
            "().__class__.__mro__[1].__subclasses__()",
        ],
    )
    def test_malicious_expression_returns_zero(self, payload):
        # 契约：非法表达式返回 0.0，不抛异常、不执行
        assert tool_manager._calculator_tool(payload) == 0.0

    @pytest.mark.asyncio
    async def test_execute_via_tool_manager(self):
        res = await tool_manager.execute(tool_name="calculator", expression="2+2")
        assert res["success"] is True
        assert res["result"] == 4.0

    @pytest.mark.asyncio
    async def test_execute_blocks_injection(self):
        res = await tool_manager.execute(
            tool_name="calculator", expression="__import__('os').getcwd()"
        )
        # 不允许把工作目录之类的信息带出去
        assert res["success"] is True
        assert res["result"] == 0.0
