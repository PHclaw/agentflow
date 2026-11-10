"""验证码文案。

按「用途 × 渠道」组织：

- **用途**决定措辞（注册 / 登录 / 重置密码），用户一眼能看出这条码是干什么用的
- **渠道**决定长度约束：邮件可以写全，短信必须极简

两条硬约束（有测试守着）：

1. 短信单条上限 **70 字**（中文）。超出会拆条计费，还可能被运营商截断，
   把有效期或安全提示切掉。
2. 短信签名必须用 ``【】`` 且**置顶** —— 国内运营商要求签名在前，
   且签名需提前向服务商报备。

邮件侧刻意保持朴素排版：营销感重的 HTML 更容易被判垃圾邮件。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.config import settings
from app.services.verification import (
    PURPOSE_LOGIN,
    PURPOSE_PASSWORD_RESET,
    PURPOSE_REGISTER,
)

#: 短信单条字符上限（中文按 1 字计）
SMS_MAX_CHARS = 70

__all__ = [
    "SMS_MAX_CHARS",
    "MailCopy",
    "PURPOSE_LOGIN",
    "PURPOSE_PASSWORD_RESET",
    "PURPOSE_REGISTER",
    "render_email",
    "render_sms",
    "spec_for",
]


@dataclass(frozen=True)
class PurposeSpec:
    """一种验证码用途的措辞规格。"""

    #: 邮件主题中「验证码」前面的限定词
    subject: str
    #: 正文里「您正在___」的动作短语
    action: str
    #: 短信安全提示。短信没有空位另起一行，敏感用途要把「非本人操作」并进来。
    sms_tail: str
    #: 邮件安全提示。邮件另有一句「如非本人操作」收尾，这里不重复它，
    #: 否则重置密码那封会出现两次「非本人操作」。
    mail_tail: str


SPECS: dict[str, PurposeSpec] = {
    PURPOSE_REGISTER: PurposeSpec(
        subject="注册验证码",
        action="注册账号",
        sms_tail="请勿泄露给他人",
        mail_tail="请勿泄露给他人",
    ),
    PURPOSE_LOGIN: PurposeSpec(
        subject="登录验证码",
        action="登录账号",
        sms_tail="请勿泄露给他人",
        mail_tail="请勿泄露给他人",
    ),
    PURPOSE_PASSWORD_RESET: PurposeSpec(
        subject="重置密码验证码",
        action="重置密码",
        # 短信里必须自己带上「非本人操作」，否则这条最敏感的提示会丢
        sms_tail="请勿泄露，非本人操作请忽略",
        mail_tail="请勿泄露给他人",
    ),
}

#: 未登记的用途走这个兜底，避免新增 purpose 时直接抛错
DEFAULT_SPEC = PurposeSpec(
    subject="验证码",
    action="完成身份验证",
    sms_tail="请勿泄露给他人",
    mail_tail="请勿泄露给他人",
)


def spec_for(purpose: str) -> PurposeSpec:
    return SPECS.get(purpose, DEFAULT_SPEC)


def brand() -> str:
    """展示品牌名。

    SMS 场景下这个名字必须与服务商已报备的签名一致，
    否则会被网关拦截 —— 如与 MAIL_FROM_NAME 不同，改成读专门的 SMS_SIGNATURE。
    """
    return settings.MAIL_FROM_NAME or "AgentFlow"


def purpose_label(purpose: str) -> str:
    """给日志用，不参与文案。"""
    return spec_for(purpose).subject.replace("验证码", "") or "验证"


# --------------------------------------------------------------------------
# 短信
# --------------------------------------------------------------------------


def render_sms(purpose: str, code: str, minutes: int) -> str:
    """渲染短信文案。

    结构：``【签名】您正在{动作}，验证码 {码}，{N} 分钟内有效。{安全提示}。``

    顺序按「先说要干什么 → 再给码 → 再讲时效与安全」排，
    用户扫一眼就够 —— 这是短信场景唯一重要的可读性目标。
    """
    spec = spec_for(purpose)
    return (
        f"【{brand()}】您正在{spec.action}，"
        f"验证码 {code}，{minutes} 分钟内有效。"
        f"{spec.sms_tail}。"
    )


# --------------------------------------------------------------------------
# 邮件
# --------------------------------------------------------------------------

# 配色直接对齐 frontend/tailwind.config.js 的 neutral / accent 色阶。
# 刻意不拆成配置项：只改主色而浅色调不动，邮件反而会和产品脱节。
#
# 唯一保留的非中性色是「安全提示」的琥珀 —— 它不是品牌色而是语义色，
# 承担的是「这行字需要先看」这个信息。前端要的是克制，邮件里这种预警
# 反而应该跳出来。
NEUTRAL_50 = "#FAFAFA"        # neutral-50 · 页面底
NEUTRAL_500 = "#737373"       # neutral-500 · 次要文字
NEUTRAL_600 = "#525252"       # neutral-600 · 正文
NEUTRAL_900 = "#171717"       # neutral-900 · 标题 / 验证码
ACCENT_50 = "#EEF2FF"         # accent-50 · 验证码底
ACCENT_100 = "#E0E7FF"        # accent-100 · 页脚底
ACCENT_200 = "#C7D2FE"        # accent-200 · 描边
ACCENT_600 = "#4F46E5"        # accent-600 · 用途标签
WARN_BG = "#FDF5EC"
WARN_LINE = "#CE7033"
WARN_TEXT = "#8A4A22"

# 品牌标识的两色。与 frontend/src/components/layout/Logo.tsx 同源。
#
# 注意：邮件页头是**浅底**。标识里的藏青画在靛蓝底上会糊成一片 ——
# 这不是配色偏好问题，是深色画在深色上看不见。
LOGO_NAVY = "#091B4D"
LOGO_CYAN = "#00BFEF"

# 系统字体栈。不用 Web Font：QQ 邮箱、Outlook、网易系都会直接丢弃 @font-face，
# 加载失败时的回退字形反而更难看。
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
        "'Hiragino Sans GB','Microsoft YaHei',Roboto,Helvetica,Arial,sans-serif")

# 渐进增强：支持媒体查询的客户端（Gmail App / Apple Mail / iOS）走这里收窄留白，
# 不支持的（Outlook 桌面版）忽略整段，按下面的表格宽度原样渲染。
STYLE_BLOCK = """<style>
  body{margin:0;padding:0;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}
  table{border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt}
  img{border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic}
  a{text-decoration:none}
  @media only screen and (max-width:620px){
    .wrap{width:100%!important}
    .px{padding-left:20px!important;padding-right:20px!important}
    .code{font-size:32px!important;letter-spacing:8px!important;text-indent:8px!important}
    .h1{font-size:19px!important}
    .hide-sm{display:none!important}
  }
</style>"""


@dataclass(frozen=True)
class MailCopy:
    subject: str
    text: str
    html: str


def _logo_url() -> str:
    """品牌标识图片的绝对地址；拿不到就返回空串。

    邮件里引图只有这一种可靠方式，理由见 ``PUBLIC_BASE_URL`` 的注释：
    内联 SVG 和 base64 都会被客户端丢弃/屏蔽，必须是 http/https。
    """
    if settings.MAIL_LOGO_URL:
        return settings.MAIL_LOGO_URL
    base = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if base:
        return f"{base}/static/brand/af-mark@2x.png"
    return ""


def _logo_lockup(name: str) -> str:
    """页头标识：单字标 + 品牌名。图片不可用时整体退化成双色字标。

    为什么不留「色块 + 首字母」那条老路：那只是因为当时没有标识图，
    拿个字母凑数。换成正式标识后它就成了四不像 —— 既不像标志，
    也不像文字，图一被拦就露馅。

    图片被拦时退化成**双色字标**而不是纯文字：它是唯一不依赖图片
    还能保住品牌识别的形式（藏青 + 青蓝的双色关系本身就是标识的一部分）。
    """
    url = _logo_url()
    is_default_brand = (name or "").strip().lower() == "agentflow"

    if not url:
        # 没有可用图片。此时不能既画字标又写品牌名，否则会显示成
        # 「agentflow AgentFlow」。所以字标本身就承担品牌名的角色。
        body = (
            f'<span style="color:{LOGO_NAVY}">agent</span>'
            f'<span style="color:{LOGO_CYAN}">flow</span>'
            if is_default_brand
            else f'<span style="color:{LOGO_NAVY}">{name}</span>'
        )
        return (
            f'<span style="font-family:{FONT};font-size:18px;font-weight:700;'
            f'letter-spacing:-0.02em;line-height:24px;'
            f'mso-line-height-rule:exactly">{body}</span>'
        )

    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="30" valign="middle" style="width:30px">'
        f'<img src="{url}" width="30" height="22" alt="{name}"'
        ' style="display:block;width:30px;height:22px;border:0"></td>'
        f'<td valign="middle" style="padding-left:10px;font-family:{FONT};'
        f'font-size:17px;font-weight:700;letter-spacing:-0.02em;color:{LOGO_NAVY};'
        f'line-height:22px;mso-line-height-rule:exactly">{name}</td>'
        '</tr></table>'
    )


def render_email(purpose: str, code: str, minutes: int,
                 recipient: str = "") -> MailCopy:
    """渲染验证码邮件（主题 / 纯文本 / HTML）。

    排版约束（决定了下面为什么全用 table 而不是 div/flex）：

    - Outlook 桌面版用 Word 排版引擎，**不支持 flex / grid**
    - 大量客户端会剥掉 ``<head>`` 里的 ``<style>``，所以关键样式一律内联
    - 图片默认不加载，验证码必须是**可选中复制的真实文字**，不能做成图

    纯文本版不能省：一部分客户端（企业邮箱、终端）只显示纯文本，
    HTML 被拦时它往往是唯一送达的部分。
    """
    spec = spec_for(purpose)
    name = brand()
    site = settings.MAIL_FROM.split("@")[-1] if "@" in settings.MAIL_FROM else name

    subject = f"【{name}】{spec.subject}（{minutes} 分钟内有效）"

    text = (
        f"您正在{spec.action}，验证码为：\n\n"
        f"    {code}\n\n"
        f"验证码 {minutes} 分钟内有效，且仅可使用一次。{spec.mail_tail}。\n"
        f"如非本人操作，忽略本邮件即可。\n\n"
        f"—— {name}\n"
        f"（此邮件由系统自动发出，请勿直接回复）\n"
    )

    # 收件箱列表里跟随主题显示的那行预览文字。它同时是 HTML 里的隐藏段落，
    # 不写的话客户端会抓正文里的随机片段当摘要。
    preheader = f"您的{spec.subject}是 {code}，{minutes} 分钟内有效，请勿泄露给他人。"

    sent_to = (
        f"发送至 <span style=\"color:{NEUTRAL_600}\">{recipient}</span>。"
        if recipient else ""
    )

    html = "".join([
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        # 关掉 iOS 邮箱自动放大字号，否则放大的正文会把版式撑坏
        '<meta name="x-apple-disable-message-reformatting">',
        # 显式声明「只支持浅色」：不声明的话 Gmail / Outlook 的深色模式
        # 会按自己的算法反色，墨绿底和琥珀提示框很容易被翻成脏色
        '<meta name="color-scheme" content="light">',
        '<meta name="supported-color-schemes" content="light">',
        f"<title>{subject}</title>",
        STYLE_BLOCK,
        # Outlook 不认自定义字体栈，退到 Arial 避免中文用衬线体
        "<!--[if mso]><style>body,table,td,p,div,span{font-family:Arial,'Microsoft YaHei',sans-serif!important}</style><![endif]-->",
        "</head>",
        f'<body style="margin:0;padding:0;background:{NEUTRAL_50};font-family:{FONT}">',
        f'<div style="display:none;font-size:1px;color:{NEUTRAL_50};line-height:1px;'
        f'max-height:0;max-width:0;opacity:0;overflow:hidden">{preheader}</div>',
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' border="0" style="background:{NEUTRAL_50}"><tr>'
        f'<td align="center" style="padding:32px 12px">',

        # ============ 卡片 ============
        '<table role="presentation" class="wrap" width="600" cellpadding="0"'
        ' cellspacing="0" border="0"'
        ' style="width:600px;max-width:600px;background:#FFFFFF;border-radius:12px">',

        # ---- 页头 ----
        # 浅底 + 底部描边。原来是整块 accent-700 深底白字，那套配色属于
        # 上一代「深底反白」的品牌语言；现在的标识是藏青 + 青蓝，深色画在
        # 深色上根本看不见，所以这里必须跟着标识改成浅底。
        f'<tr><td style="background:{ACCENT_50};padding:18px 32px;'
        f'border-bottom:1px solid {ACCENT_200};'
        f'border-radius:12px 12px 0 0">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td valign="middle">{_logo_lockup(name)}</td>'
        f'<td class="hide-sm" valign="middle" align="right" style="font-size:12px;'
        f'color:{NEUTRAL_500};letter-spacing:2px">账号安全</td>'
        "</tr></table></td></tr>",

        # ---- 正文 ----
        '<tr><td class="px" style="background:#FFFFFF;padding:34px 32px 28px">',

        # 层级 1：用途标签（小号 + 字距 + 主色，先把「这是什么」交代清楚）
        f'<p style="margin:0 0 10px;font-size:12px;font-weight:600;color:{ACCENT_600};'
        f'letter-spacing:2px">{spec.subject.replace("验证码", "验证")}</p>',
        # 层级 2：主标题
        f'<h1 class="h1" style="margin:0 0 10px;font-size:21px;font-weight:700;'
        f'color:{NEUTRAL_900};line-height:1.4">您正在{spec.action}</h1>',
        # 层级 3：说明
        f'<p style="margin:0 0 24px;font-size:14px;color:{NEUTRAL_600};line-height:1.7">'
        f"请使用下面的验证码完成验证，{minutes} 分钟内有效。</p>",

        # 层级 4：验证码主体。独立成块 + 放大 + 字距，一眼可辨。
        # letter-spacing 会在最后一个字符右侧留出等宽空隙，
        # 用等值 text-indent 抵消，否则整串看着偏左。
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td align="center" style="background:{ACCENT_50};'
        f'border:1px solid {ACCENT_200};border-radius:12px;padding:22px 10px">'
        f'<div class="code" style="font-size:36px;font-weight:700;letter-spacing:10px;'
        f'text-indent:10px;color:{NEUTRAL_900};line-height:1.1">{code}</div>'
        "</td></tr></table>",

        f'<p style="margin:16px 0 0;text-align:center;font-size:13px;color:{NEUTRAL_500}">'
        f'有效期 <b style="color:{NEUTRAL_600}">{minutes} 分钟</b>'
        ' &nbsp;·&nbsp; 仅可使用一次</p>',

        # 层级 5：安全提示（琥珀色块 + 左侧色条，和正文明确分区）
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        ' border="0" style="margin-top:26px"><tr>'
        f'<td style="background:{WARN_BG};border-left:3px solid {WARN_LINE};'
        f'border-radius:0 8px 8px 0;padding:14px 16px">'
        f'<p style="margin:0 0 5px;font-size:13px;font-weight:700;color:{WARN_TEXT}">安全提示</p>'
        f'<p style="margin:0;font-size:13px;color:{WARN_TEXT};line-height:1.65">'
        f"{spec.mail_tail}。如非本人操作，忽略本邮件即可。</p>"
        "</td></tr></table>",

        "</td></tr>",

        # ---- 页脚 ----
        f'<tr><td class="px" style="background:{ACCENT_50};padding:20px 32px;'
        f'border-top:1px solid {ACCENT_200};border-radius:0 0 12px 12px">'
        f'<p style="margin:0 0 6px;font-size:12px;color:{NEUTRAL_500};line-height:1.6">'
        f"此邮件由系统自动发出，请勿直接回复。{sent_to}</p>"
        f'<p style="margin:0;font-size:12px;color:{NEUTRAL_500};line-height:1.6">'
        f"© {date.today().year} {name} · {site}</p>"
        "</td></tr>",

        "</table>",
        # ============ 卡片结束 ============

        "</td></tr></table>",
        "</body></html>",
    ])

    return MailCopy(subject=subject, text=text, html=html)
