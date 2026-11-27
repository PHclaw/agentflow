"""安全的数学表达式求值。

**为什么需要它**：LLM 通过 function-calling 传进来的 ``expression``
本质上是「攻击者可控的字符串」——提示注入能诱导模型调用计算器，
而模型以为自己只是在做数学题，这比让它直接拒绝安全策略容易得多。

因此这里**不做字符白名单**（白名单挡不住 ``9**9**9**9`` 这种 CPU 耗尽，
也容易被新的语法绕过），而是用 AST 只放行数学运算本身：

- 只允许数字常量与 + - * / // % ** 及正负号
- 禁止属性访问、下标、调用、推导式、lambda —— ``__import__`` 之类
  在语法树层面就不存在，而不是靠运行时拦截
- 限制指数大小、数字位数、节点数量，避免算力被一条表达式打满

调用方拿到 ``SafeMathError`` 就当作「表达式非法」处理。
"""
import ast
import math
import operator
from typing import Any, Union

__all__ = ["SafeMathError", "safe_eval_math"]


class SafeMathError(ValueError):
    """表达式不被允许，或计算过程越界。"""


#: 二元运算符白名单
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

#: 一元运算符白名单（正负号）
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

#: 单个数字最多多少位，防止构造超大整数拖慢后续运算
_MAX_INT_DIGITS = 30
#: 幂的指数上限，防止 9**9**9 这类把 CPU 打满
_MAX_EXPONENT = 1000
#: 表达式里最多多少个 AST 节点
_MAX_NODES = 120
#: 原始字符串长度上限
_MAX_LENGTH = 500


def _check_number(value: Any) -> Union[int, float]:
    if isinstance(value, bool):
        # bool 是 int 的子类，单独拦掉，避免 True/False 被当数字
        raise SafeMathError("布尔值不是合法数字")
    if isinstance(value, int):
        if abs(value) >= 10 ** _MAX_INT_DIGITS:
            raise SafeMathError("数字过大")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            # inf / nan 传回给 LLM 只会让它继续拿这个「数」算下去，
            # 不如在源头当成非法表达式
            raise SafeMathError("结果不是有限数")
        return value
    raise SafeMathError(f"不支持的数字类型: {type(value).__name__}")


def _eval_node(node: ast.AST) -> Union[int, float]:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        return _check_number(node.value)

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        func = _BINOPS.get(op_type)
        if func is None:
            raise SafeMathError("不支持的运算符")
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        # 幂运算单独限流：底数与指数都要可控
        if op_type is ast.Pow:
            if not isinstance(right, (int, float)) or abs(right) > _MAX_EXPONENT:
                raise SafeMathError("指数过大")
            if isinstance(left, int) and isinstance(right, int):
                # 估算结果位数，避免 10**500 这种把内存吃掉
                if left not in (0, 1, -1) and right > 0:
                    if len(str(abs(left))) * right > _MAX_INT_DIGITS:
                        raise SafeMathError("计算结果过大")
            elif left == 0 and right < 0:
                raise SafeMathError("零不能取负幂")
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise SafeMathError("除数不能为 0")

        # 底层算术异常必须收敛成 SafeMathError，否则调用方拿到的异常类型
        # 不一致（0**-1 抛 ZeroDivisionError，10**309.0 抛 OverflowError），
        # 「非法表达式」这个契约就破了。
        try:
            result = func(left, right)
        except (ZeroDivisionError, OverflowError, ValueError) as exc:
            raise SafeMathError(f"计算失败: {exc}") from exc
        return _check_number(result)

    if isinstance(node, ast.UnaryOp):
        func = _UNARYOPS.get(type(node.op))
        if func is None:
            raise SafeMathError("不支持的一元运算符")
        return _check_number(func(_eval_node(node.operand)))

    # 其余全部拒绝：Call / Attribute / Subscript / Name / Lambda /
    # ListComp / JoinedStr(f-string) 等等
    raise SafeMathError(f"不允许的表达式成分: {type(node).__name__}")


def safe_eval_math(expression: str) -> Union[int, float]:
    """只对数学表达式求值，任何越界语法都会抛 ``SafeMathError``。

    >>> safe_eval_math("2 + 3 * 4")
    14
    >>> safe_eval_math("__import__('os').getcwd()")
    Traceback (most recent call last):
    SafeMathError: 不允许的表达式成分: Call
    """
    if not isinstance(expression, str):
        raise SafeMathError("表达式必须是字符串")

    expr = expression.strip()
    if not expr:
        raise SafeMathError("表达式为空")
    if len(expr) > _MAX_LENGTH:
        raise SafeMathError("表达式过长")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise SafeMathError(f"表达式语法错误: {exc.msg}") from exc

    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        raise SafeMathError("表达式过于复杂")

    return _eval_node(tree)
