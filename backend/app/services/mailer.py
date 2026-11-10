"""邮件发送服务。

设计取舍：用标准库 ``smtplib`` 而不是 ``aiosmtplib``。

原因是不引入额外依赖 —— SMTP 收发本身是阻塞 IO，直接扔进线程池执行即可，
对「注册发验证码」这种低频场景完全够用。若将来邮件量上来（比如批量通知），
再换成异步库或投递到 Celery 队列。

加密方式按端口自动选：

===========================  ==============================
端口                         行为
===========================  ==============================
465                          SMTP over SSL（直连 TLS）
587 / 25                     STARTTLS（先明文握手再升级）
===========================  ==============================

国内云主机直连 25 端口基本被封，**推荐 465**。
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings
from app.services.verification_copy import PURPOSE_REGISTER, render_email

logger = logging.getLogger(__name__)


class MailNotConfigured(RuntimeError):
    """邮件未配置。

    调用方应据此返回可操作的提示，而不是抛 500 —— 这是部署配置问题，
    不是运行时故障。
    """


def is_configured() -> bool:
    """是否具备发信条件（不看 MAIL_ENABLED 开关）。"""
    return bool(settings.MAIL_HOST and settings.MAIL_USER and settings.MAIL_PASSWORD)


def _build_message(to: str, subject: str, text: str,
                   html: str | None = None) -> EmailMessage:
    sender = settings.MAIL_FROM or settings.MAIL_USER
    msg = EmailMessage()
    msg["From"] = formataddr((settings.MAIL_FROM_NAME, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        # 客户端不支持 HTML 时自动回退到上面的纯文本
        msg.add_alternative(html, subtype="html")
    return msg


def _send_sync(msg: EmailMessage) -> None:
    """阻塞式发送，由调用方放进线程池。"""
    host, port = settings.MAIL_HOST, settings.MAIL_PORT
    timeout = settings.MAIL_TIMEOUT

    if settings.MAIL_USE_SSL:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            smtp.login(settings.MAIL_USER, settings.MAIL_PASSWORD)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        # starttls 前必须先 ehlo，否则 smtplib 会直接报错
        smtp.starttls()
        smtp.ehlo()
        smtp.login(settings.MAIL_USER, settings.MAIL_PASSWORD)
        smtp.send_message(msg)


async def send_mail(to: str, subject: str, text: str,
                    html: str | None = None) -> bool:
    """发送一封邮件。

    Returns:
        True 表示真的投递出去了；False 表示因为 ``MAIL_ENABLED=false``
        被跳过（此时内容会打到日志，方便本地开发直接拿验证码）。
    """
    if not settings.MAIL_ENABLED:
        logger.warning(
            "[MAIL_ENABLED=false] 邮件未发送（仅记录内容）\n  To: %s\n  Subject: %s\n%s",
            to, subject, text,
        )
        return False

    if not is_configured():
        raise MailNotConfigured(
            "邮件服务未配置：请在 .env 中填写 MAIL_HOST / MAIL_USER / MAIL_PASSWORD"
            "（MAIL_PASSWORD 是邮箱授权码，不是登录密码）"
        )

    msg = _build_message(to, subject, text, html)
    await asyncio.to_thread(_send_sync, msg)
    logger.info("验证码邮件已发送 → %s", to)
    return True


# --------------------------------------------------------------------------
# 验证码邮件
# --------------------------------------------------------------------------

async def send_verification_code(
    to: str,
    code: str,
    ttl_seconds: int,
    purpose: str = PURPOSE_REGISTER,
) -> bool:
    """发送验证码邮件。

    文案由 ``verification_copy`` 按用途渲染 —— 注册 / 登录 / 重置密码的措辞不同，
    收件人一眼能分辨这条码是干什么用的。
    """
    minutes = max(1, ttl_seconds // 60)
    # 把收件地址回填到页脚，方便收件人确认这封信是不是发给自己的
    copy = render_email(purpose, code, minutes, recipient=to)
    return await send_mail(
        to=to, subject=copy.subject, text=copy.text, html=copy.html
    )
