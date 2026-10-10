"""Skill 运行时加解密（兼容旧密文 system prompt）。"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def decrypt_text(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("解密失败") from exc


def encrypt_text(plain: str) -> str:
    """对称加密（用于 API Key 等敏感配置落库）。"""
    if plain is None:
        raise ValueError("待加密内容不能为空")
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
