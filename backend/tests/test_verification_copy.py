"""验证码文案测试。

把文案要求固化成断言，避免后续改字时无意破坏：

1. 用途明确（注册 / 登录 / 重置密码 各不相同）
2. 验证码清晰可辨
3. 含有效期
4. 含安全提示
5. 短信控制在单条 70 字内
6. 短信签名合规（【】包裹且置顶）
"""
import re
from html.parser import HTMLParser

import pytest

from app.core.config import settings
from app.services import verification_copy as vc

CODE = "483920"
MINUTES = 5

ALL_PURPOSES = [
    vc.PURPOSE_REGISTER,
    vc.PURPOSE_LOGIN,
    vc.PURPOSE_PASSWORD_RESET,
]


# --------------------------------------------------------------------------
# 短信
# --------------------------------------------------------------------------


class TestSmsCopy:
    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    def test_contains_every_required_element(self, purpose):
        """一次断言六项要求，任何一项被改掉都会失败。"""
        sms = vc.render_sms(purpose, CODE, MINUTES)
        spec = vc.spec_for(purpose)

        assert spec.action in sms, "缺少用途说明（要求 1）"
        assert CODE in sms, "缺少验证码（要求 2）"
        assert f"{MINUTES} 分钟内有效" in sms, "缺少有效期（要求 3）"
        assert spec.sms_tail in sms, "缺少安全提示（要求 4）"

    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    def test_signature_is_bracketed_and_leading(self, purpose):
        """国内运营商要求签名在前，且必须用【】。"""
        sms = vc.render_sms(purpose, CODE, MINUTES)

        assert sms.startswith(f"【{vc.brand()}】"), "签名必须置顶且用【】包裹"

    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    @pytest.mark.parametrize("minutes", [1, 5, 30, 60])
    def test_within_single_segment_limit(self, purpose, minutes):
        """超 70 字会拆条计费，还可能把安全提示截断。"""
        sms = vc.render_sms(purpose, CODE, minutes)

        assert len(sms) <= vc.SMS_MAX_CHARS, (
            f"{purpose} / {minutes} 分钟 的短信 {len(sms)} 字，超出单条上限"
        )

    def test_purposes_are_distinguishable(self):
        """三条短信必须能区分开，否则用户不知道这条码要填到哪。"""
        texts = {p: vc.render_sms(p, CODE, MINUTES) for p in ALL_PURPOSES}

        assert len(set(texts.values())) == len(ALL_PURPOSES)
        assert "注册" in texts[vc.PURPOSE_REGISTER]
        assert "登录" in texts[vc.PURPOSE_LOGIN]
        assert "重置密码" in texts[vc.PURPOSE_PASSWORD_RESET]

    def test_password_reset_mentions_non_self_operation(self):
        """重置密码是敏感操作，安全提示要覆盖「非本人操作」。"""
        sms = vc.render_sms(vc.PURPOSE_PASSWORD_RESET, CODE, MINUTES)

        assert "非本人操作" in sms
        assert "请勿泄露" in sms

    def test_no_marketing_style_decoration(self):
        """短信里不该出现 HTML 标签或多余符号 —— 会直接显示成乱码。"""
        sms = vc.render_sms(vc.PURPOSE_REGISTER, CODE, MINUTES)

        assert "<" not in sms and ">" not in sms
        assert "&" not in sms


# --------------------------------------------------------------------------
# 邮件
# --------------------------------------------------------------------------


class TestEmailCopy:
    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    def test_subject_carries_purpose_and_validity(self, purpose):
        copy = vc.render_email(purpose, CODE, MINUTES)
        spec = vc.spec_for(purpose)

        assert spec.subject in copy.subject
        assert f"{MINUTES} 分钟内有效" in copy.subject
        assert copy.subject.startswith(f"【{vc.brand()}】")

    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    def test_plain_text_is_self_contained(self, purpose):
        """一部分客户端只显示纯文本，它必须独立可用。"""
        copy = vc.render_email(purpose, CODE, MINUTES)
        spec = vc.spec_for(purpose)

        assert copy.text.strip()
        assert CODE in copy.text
        assert spec.action in copy.text
        assert f"{MINUTES} 分钟内有效" in copy.text
        assert spec.mail_tail in copy.text
        assert "如非本人操作" in copy.text
        # 重置密码那封曾在正文里出现两次「非本人操作」，这里守住不重复
        assert copy.text.count("非本人操作") == 1

    @pytest.mark.parametrize("purpose", ALL_PURPOSES)
    def test_html_highlights_code_and_keeps_context(self, purpose):
        copy = vc.render_email(purpose, CODE, MINUTES)

        # 验证码要放大 + 加字距，便于一眼扫到
        assert CODE in copy.html
        assert re.search(r"font-size:\s*(3[0-9]|[4-9]\d)px", copy.html), "验证码字号不够突出"
        assert "letter-spacing" in copy.html
        # 用途、有效期、安全提示同样不能少
        assert vc.spec_for(purpose).action in copy.html
        assert f"{MINUTES} 分钟内有效" in copy.html
        assert vc.spec_for(purpose).mail_tail in copy.html
        assert copy.html.count("非本人操作") == 1, "安全提示重复了"

    def test_email_purposes_are_distinguishable(self):
        subjects = {p: vc.render_email(p, CODE, MINUTES).subject for p in ALL_PURPOSES}

        assert len(set(subjects.values())) == len(ALL_PURPOSES)


# --------------------------------------------------------------------------
# 邮件排版：兼容性与结构约束
# --------------------------------------------------------------------------

#: HTML 里本来就不需要闭合标签的元素
VOID_TAGS = {"br", "img", "meta", "link", "input", "hr", "area", "base", "col"}


class _TagBalance(HTMLParser):
    """检查标签是否成对闭合。

    标签不闭合在浏览器里能容错，但 Outlook 会**直接截断**后半封邮件，
    所以值得当硬性约束守起来。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"多余的 </{tag}>")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> 无法闭合 <{self.stack[-1]}>")
        else:
            self.stack.pop()


def _html() -> str:
    return vc.render_email(vc.PURPOSE_REGISTER, CODE, MINUTES).html


class TestEmailCompatibility:
    """邮件客户端的兼容性约束。"""

    def test_layout_is_table_based(self):
        """Outlook 桌面版用 Word 排版引擎，不支持 flex / grid。"""
        html = _html()

        assert "<table" in html
        assert 'role="presentation"' in html, "布局表格要标 role，否则读屏软件会当数据表朗读"
        assert "display:flex" not in html
        assert "display:grid" not in html
        # 卡片宽度必须内联给出，<head> 的样式可能被剥掉
        assert "width:600px" in html

    def test_has_viewport_and_responsive_media_query(self):
        html = _html()

        assert 'name="viewport"' in html
        assert "max-width:620px" in html, "缺少窄屏媒体查询"
        assert 'name="x-apple-disable-message-reformatting"' in html

    def test_declares_light_color_scheme(self):
        """不声明的话，深色模式会按客户端算法反色，墨绿底和琥珀框容易变脏色。"""
        html = _html()

        assert 'name="color-scheme" content="light"' in html
        assert 'name="supported-color-schemes" content="light"' in html

    def test_code_is_real_text_not_an_image(self):
        """图片默认不加载，验证码做成图就等于收件人什么都看不到。"""
        html = _html()

        assert f">{CODE}</div>" in html, "验证码必须是可选中复制的纯文本"

    def test_has_hidden_preheader(self):
        """收件箱摘要要可控，否则客户端会抓正文里的随机片段当预览。"""
        html = _html()

        assert CODE in html
        assert "max-height:0" in html and "opacity:0" in html
        assert "display:none" in html

    def test_avoids_web_fonts(self):
        """QQ 邮箱 / Outlook / 网易系都会丢弃 @font-face，加载失败的字形更难看。"""
        html = _html()

        assert "@font-face" not in html
        assert "fonts.googleapis" not in html
        assert "-apple-system" in html, "应使用系统字体栈"

    def test_has_outlook_conditional_comment(self):
        html = _html()

        assert "<!--[if mso]>" in html
        assert "<![endif]-->" in html

    def test_tags_are_balanced(self):
        parser = _TagBalance()
        parser.feed(_html())
        parser.close()

        assert not parser.errors, parser.errors
        assert not parser.stack, f"未闭合的标签: {parser.stack}"

    def test_has_lang_attribute(self):
        """语言声明影响部分客户端的字体回退与断行规则。"""
        assert 'lang="zh-CN"' in _html()


class TestEmailBrandMark:
    """页头标识。

    标识是藏青 + 青蓝双色，**邮件页头因此必须浅底** —— 深色画在深色上看不见。
    引图只有绝对 http/https 一条路（内联 SVG 被 Outlook/Gmail 丢弃，
    base64 被 Windows 版 Outlook 屏蔽），所以拿不到地址时必须能不依赖图片显示。
    """

    def test_falls_back_to_two_tone_wordmark_when_no_url(self, monkeypatch):
        """没有可用图片时退化成双色字标，且不引任何图片。

        原来这里退化成「色块 + 首字母 A」—— 那只是因为当时没有标识图，
        拿字母凑数。现在有正式标识了，再退回字母块既不像标志也不像文字。
        """
        monkeypatch.setattr(settings, "MAIL_LOGO_URL", "", raising=False)
        monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "", raising=False)
        html = _html()

        assert "<img" not in html, "没有图片地址时不该引用任何图片"
        assert vc.LOGO_NAVY in html
        assert vc.LOGO_CYAN in html
        assert ">agent</span>" in html and ">flow</span>" in html
        # 字标本身承担品牌名，不能再叠一个品牌名，否则显示成「agentflow AgentFlow」
        assert html.count("AgentFlow") <= 2, "页头不应同时出现字标和品牌名"

    def test_uses_static_mark_when_public_base_url_set(self, monkeypatch):
        """配了 PUBLIC_BASE_URL 就自动引随包发布的标识 PNG。"""
        monkeypatch.setattr(settings, "MAIL_LOGO_URL", "", raising=False)
        monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://af.example.com/", raising=False)

        html = _html()

        assert 'src="https://af.example.com/static/brand/af-mark@2x.png"' in html

    def test_explicit_logo_url_wins(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MAIL_LOGO_URL", "https://cdn.test/logo.png", raising=False
        )
        monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://af.example.com", raising=False)

        html = _html()

        assert 'src="https://cdn.test/logo.png"' in html
        assert "static/brand" not in html, "显式配置的 logo 应优先于内置标识"

    def test_image_has_fixed_size(self, monkeypatch):
        """图片必须给死宽高，否则 Outlook 会按原图尺寸撑破排版。"""
        monkeypatch.setattr(
            settings, "MAIL_LOGO_URL", "https://cdn.test/logo.png", raising=False
        )
        html = _html()

        assert "width:30px" in html and "height:22px" in html

    def test_header_is_light_background(self, monkeypatch):
        """页头必须是浅底。

        标识的藏青画在 accent-700 深底上会糊成一片 —— 这是配色改动时
        连带必须改的地方，容易漏。
        """
        monkeypatch.setattr(
            settings, "MAIL_LOGO_URL", "https://cdn.test/logo.png", raising=False
        )
        html = _html()

        assert vc.ACCENT_50 in html
        assert "background:#FFFFFF;letter-spacing:2px" not in html, "页头不该再有深底白字"

    def test_custom_brand_name_is_not_replaced_by_default_wordmark(self, monkeypatch):
        """自定义了 MAIL_FROM_NAME 时，不能硬显示成 agentflow。

        ``_logo_lockup`` 是在渲染时读 ``MAIL_FROM_NAME`` 的，所以这里必须改设置
        再渲染 —— 事后替换 HTML 里的字符串改不到它的判断依据。
        """
        monkeypatch.setattr(settings, "MAIL_LOGO_URL", "", raising=False)
        monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "", raising=False)
        monkeypatch.setattr(settings, "MAIL_FROM_NAME", "Acme", raising=False)

        html = vc.render_email(vc.PURPOSE_REGISTER, CODE, MINUTES).html

        assert "Acme" in html
        assert ">flow</span>" not in html, "非默认品牌名不该套用默认双色字标"
        assert ">agent</span>" not in html

    def test_no_inline_svg(self, monkeypatch):
        """邮件里绝不能内联 SVG —— Outlook 是 Word 引擎，完全不认。"""
        monkeypatch.setattr(
            settings, "MAIL_LOGO_URL", "https://cdn.test/logo.png", raising=False
        )

        assert "<svg" not in _html().lower()


class TestEmailRecipient:
    def test_shows_recipient_when_provided(self):
        html = vc.render_email(vc.PURPOSE_REGISTER, CODE, MINUTES,
                               recipient="someone@example.com").html

        assert "someone@example.com" in html
        assert "发送至" in html

    def test_omits_recipient_line_when_absent(self):
        html = _html()

        assert "发送至" not in html


# --------------------------------------------------------------------------
# 兜底
# --------------------------------------------------------------------------


class TestFallback:
    def test_unknown_purpose_falls_back_instead_of_raising(self):
        """新增 purpose 时不应 500，先按通用措辞发出去。"""
        sms = vc.render_sms("some_new_purpose", CODE, MINUTES)
        copy = vc.render_email("some_new_purpose", CODE, MINUTES)

        assert CODE in sms and len(sms) <= vc.SMS_MAX_CHARS
        assert CODE in copy.text
        assert copy.subject

    def test_brand_follows_config(self, monkeypatch):
        monkeypatch.setattr(settings, "MAIL_FROM_NAME", "示例品牌", raising=False)

        sms = vc.render_sms(vc.PURPOSE_REGISTER, CODE, MINUTES)
        assert sms.startswith("【示例品牌】")
