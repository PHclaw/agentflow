"""密码强度策略。

注册和修改密码共用同一套规则。原来两处都没有校验 —— 注册接口的
``password: str`` 裸奔，用户设个 "1" 也能建号；改密码补上之后，
如果只有一边校验，就会出现「注册能设弱密码、改了反而被拒」的怪事。
"""
from __future__ import annotations

import re

MIN_LEN = 8
MAX_LEN = 128

#: 常见弱密码。列表不求全，只挡最容易被脚本撞中的那一批。
_COMMON = {
    "password", "passwd", "123456", "1234567", "12345678", "123456789",
    "1234567890", "qwerty", "abc123", "111111", "000000", "iloveyou",
    "admin", "admin123", "root", "letmein", "welcome", "monkey", "dragon",
    "password1", "p@ssw0rd", "qwerty123", "1q2w3e4r", "a123456",
}


def validate_password(password: str) -> str:
    """校验并返回原文（strip 后的）。

    规则刻意保持宽松：只挡「明显不安全的」，不强制大小写+数字+符号组合。
    强制复杂度会让用户写出 ``Password1!`` 这种更好猜的东西，
    而长度本身就是最强的单一指标。
    """
    pwd = (password or "").strip()

    if len(pwd) < MIN_LEN:
        raise ValueError(f"密码至少 {MIN_LEN} 位")
    if len(pwd) > MAX_LEN:
        raise ValueError(f"密码最长 {MAX_LEN} 位")
    if pwd.lower() in _COMMON:
        raise ValueError("这个密码太常见了，换一个")
    if pwd.isdigit():
        raise ValueError("密码不能全是数字")
    if re.fullmatch(r"(.)\1*", pwd):
        raise ValueError("密码不能是同一个字符重复")

    return pwd
