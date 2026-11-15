"""导入的技能必须**真的能用**，而不只是「导入成功」。

这份文件守的是一个真实故障：``ppt-master`` 导进来之后，它启动时会跑自己的
完整性闸门 ``scripts/attribution_guard.py``。那个脚本拿**逐字符正则**核对
SKILL.md 的 frontmatter：

    rf"(?m)^  copyright\\s*:\\s*\"Copyright (c) 2025-2026 Hugo He\"\\s*$"

也就是要求恰好两个空格缩进、键名不带引号。而导入流程当时把 YAML frontmatter
重写成了 JSON —— 缩进变四格、键名带上引号、外面还套了 ``metadata`` —— 正则
全部落空，退出码 78，技能当场自我中止，回给用户一句「演示文稿制作流程在启动
时的完整性校验未通过」。

**导入本身报的是「成功」**：广场里看得到、字段都对、systemPrompt 也生效。
故障只在技能自己的闸门上才现形。所以约定是硬的：**导入不修改 SKILL.md 的
任何一个字节**，平台需要的字段写旁挂文件 ``agentflow.json``。
"""
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from app.services.skill import store as skill_store
from app.services.skill.store import (
    SIDECAR_FILENAME,
    SKILL_FILENAME,
    load_skill_from_dir,
)
from app.services.skill_package import import_zip, inspect_zip

#: 仿 ppt-master 的 SKILL.md：YAML frontmatter、没有 systemPrompt、
#: frontmatter 里的格式必须逐字节保住。
THIRD_PARTY_MD = """---
name: ppt-master
description: >
  AI-driven presentation workflow for generating editable PPTX decks,
  reconstructing page visuals and filling native templates.
metadata:
  version: "6.7.0"
  copyright: "Copyright (c) 2025-2026 Hugo He"
  license: "MIT"
  official_repository: "https://github.com/hugohe3/ppt-master"
  sponsors:
    - SPONSORS.md
---

# PPT Master

## 启动顺序（Mandatory Load Order）

1. 读 `references/workflow.md`。
2. 跑 `python3 "${SKILL_DIR}/scripts/attribution_guard.py"`。
   非零即停，不得绕过。
3. 再读 `references/layouts.md`。
"""


def make_zip(files: dict[str, str], top: str = "demo-skill") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(f"{top}/{name}", content)
    return buf.getvalue()


@pytest.fixture
def skills_env(tmp_path, monkeypatch):
    from app.core.paths import repo_root

    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("AGENTFLOW_REPO_ROOT", str(root))
    repo_root.cache_clear()
    skill_store.invalidate_cache()
    yield skill_store
    repo_root.cache_clear()
    skill_store.invalidate_cache()


def read_md_bytes(slug: str) -> bytes:
    return (skill_store.skill_dir(slug) / SKILL_FILENAME).read_bytes()


# ---------------------------------------------------------------------------
# SKILL.md 必须逐字节不变
# ---------------------------------------------------------------------------


class TestSkillMdIsPreserved:
    def test_import_does_not_touch_a_single_byte(self, skills_env):
        """核心约定。改一个字节就可能让第三方的签名/自检失效。"""
        original = THIRD_PARTY_MD.encode("utf-8")
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        assert read_md_bytes("demo-skill") == original

    def test_crlf_package_stays_crlf(self, skills_env):
        """换行风格也是字节的一部分，统一成 LF 同样会破坏比对。"""
        crlf = THIRD_PARTY_MD.replace("\n", "\r\n").encode("utf-8")
        import_zip(make_zip({"SKILL.md": crlf.decode("utf-8")}))

        assert read_md_bytes("demo-skill") == crlf


# ---------------------------------------------------------------------------
# 模拟第三方完整性闸门
# ---------------------------------------------------------------------------


def third_party_integrity_check(slug: str) -> int:
    """照抄 ppt-master ``attribution_guard.py`` 的判定方式。

    0 = 通过，78 = 失败（原脚本用的就是 78）。
    """
    text = (skill_store.skill_dir(slug) / SKILL_FILENAME).read_text(encoding="utf-8")
    end = text.find("\n---\n", 4)
    if end < 0:
        return 78
    fm = text[4:end]

    exact = {
        "copyright": '"Copyright (c) 2025-2026 Hugo He"',
        "license": '"MIT"',
        "official_repository": '"https://github.com/hugohe3/ppt-master"',
    }
    for field, value in exact.items():
        if len(re.findall(rf"(?m)^  {re.escape(field)}\s*:\s*{re.escape(value)}\s*$", fm)) != 1:
            return 78
    if len(re.findall(r"(?m)^  sponsors\s*:", fm)) != 1:
        return 78
    if text.count('python3 "${SKILL_DIR}/scripts/attribution_guard.py"') != 1:
        return 78
    return 0


class TestThirdPartyGateStillPasses:
    def test_gate_passes_after_import(self, skills_env):
        """这条就是那个真实故障的回归测试。

        改造之前这里返回 78 —— 因为导入把 YAML frontmatter 序列化成了 JSON，
        缩进和引号全变了。技能于是「导入成功但一用就自我中止」。
        """
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        assert third_party_integrity_check("demo-skill") == 0

    def test_round_trip_save_is_byte_identical(self, skills_env):
        """**打开就算不动、点一次保存**，SKILL.md 必须一个字节都不变。

        这是真实风险最高的一条：管理后台的编辑器把 frontmatter 和正文读出来
        给表单，保存时再写回去。只要这条路径上有任何「顺手规整一下」
        （strip、重新序列化、换行翻译），第三方自检就挂了 —— 而用户只是
        打开看了一眼又保存。
        """
        original = THIRD_PARTY_MD.encode("utf-8")
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        meta, body = skill_store.read_skill_md("demo-skill")
        skill_store.update_skill("demo-skill", meta, body)

        assert read_md_bytes("demo-skill") == original
        assert third_party_integrity_check("demo-skill") == 0

    def test_gate_still_passes_after_body_edit(self, skills_env):
        """管理员往正文里补内容，闸门不能因此挂掉。

        正文是技能本体的一部分，改它是允许的；frontmatter 的格式不能顺手动。
        注意闸门标记本身也在正文里（这条技能把「启动顺序」写在正文），所以
        这里模拟的是**追加**而不是整段替换 —— 整段替换掉标记，闸门本来就会
        失败，那是这条技能自己的设计，不归我们兜。
        """
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))
        _meta, body = skill_store.read_skill_md("demo-skill")

        skill_store.update_skill(
            "demo-skill",
            {"name": "PPT Master", "description": "做 PPT 的技能",
             "systemPrompt": "你是 PPT 助手。"},
            body + "\n## 补充说明\n\n管理员补的一句话。\n",
        )

        assert third_party_integrity_check("demo-skill") == 0
        assert "管理员补的一句话" in read_md_bytes("demo-skill").decode("utf-8")

    def test_body_edit_actually_lands(self, skills_env):
        """正文要真的被替换掉，别只改了个旁挂、正文纹丝不动。"""
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        skill_store.update_skill(
            "demo-skill", {"name": "X", "systemPrompt": "y"},
            "# 新正文\n\n补的内容。\n",
        )

        text = read_md_bytes("demo-skill").decode("utf-8")
        assert "补的内容" in text
        assert "Mandatory Load Order" not in text   # 旧正文确实没了
        assert 'copyright: "Copyright (c) 2025-2026 Hugo He"' in text  # frontmatter 还在


# ---------------------------------------------------------------------------
# 旁挂元数据
# ---------------------------------------------------------------------------


class TestSidecar:
    def test_carries_platform_fields(self, skills_env):
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        sidecar = json.loads(
            (skill_store.skill_dir("demo-skill") / SIDECAR_FILENAME).read_text("utf-8")
        )
        assert sidecar["id"] == "demo-skill"
        assert sidecar["authorId"] == "platform-preset"
        assert sidecar["status"] == "published"

    def test_does_not_duplicate_the_whole_frontmatter(self, skills_env):
        """只放导入时定下来的那几项。

        复制整份 frontmatter 会让以后改 SKILL.md 的描述失效（旁挂优先），
        现场看着就是「改了没反应」。
        """
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        sidecar = json.loads(
            (skill_store.skill_dir("demo-skill") / SIDECAR_FILENAME).read_text("utf-8")
        )
        assert "metadata" not in sidecar       # 包里的嵌套块不该被搬过来
        assert "sponsors" not in sidecar

    def test_overrides_win(self, skills_env):
        import_zip(
            make_zip({"SKILL.md": THIRD_PARTY_MD}),
            overrides={"name": "PPT 助手", "description": "做 PPT 的技能"},
        )

        skill = load_skill_from_dir(skill_store.skill_dir("demo-skill"))
        assert skill.name == "PPT 助手"
        assert skill.description == "做 PPT 的技能"

    def test_corrupted_sidecar_does_not_break_loading(self, skills_env):
        """旁挂读坏不能让技能消失 —— SKILL.md 才是本体。"""
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))
        (skill_store.skill_dir("demo-skill") / SIDECAR_FILENAME).write_text(
            "{ 这不是 JSON", encoding="utf-8"
        )
        skill_store.invalidate_cache()

        skill = load_skill_from_dir(skill_store.skill_dir("demo-skill"))

        assert skill is not None
        # 退回包里那份 frontmatter
        assert skill.name == "ppt-master"


# ---------------------------------------------------------------------------
# YAML frontmatter 必须能被加载
# ---------------------------------------------------------------------------


class TestYamlFrontmatterLoads:
    def test_loader_reads_yaml(self, skills_env):
        """导入保留 YAML，加载路径就必须认 YAML。

        早先只有 ``_split_skill_md`` 的 JSON 分支，保留原始 frontmatter 的
        技能会直接加载失败 —— 表现是「导入成功，但广场里没有」。
        """
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        skill = load_skill_from_dir(skill_store.skill_dir("demo-skill"))

        assert skill is not None
        assert skill.name == "ppt-master"
        assert skill.description.startswith("AI-driven")

    def test_nested_metadata_is_readable(self, skills_env):
        """YAML 的嵌套块要能读出来（``metadata.sponsors`` 这类）。"""
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        meta, _ = skill_store.read_skill_md("demo-skill")

        assert meta["metadata"]["version"] == "6.7.0"
        assert meta["metadata"]["sponsors"] == ["SPONSORS.md"]

    def test_body_fallback_supplies_system_prompt(self, skills_env):
        """包里没有 systemPrompt 时，用正文兜底并存进旁挂。

        没有这一步，技能能加载、能被调用，但产出空内容 —— 比加载失败更难查。
        """
        preview, meta = inspect_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        assert meta["systemPrompt"].startswith("# PPT Master")
        assert any("正文" in w for w in preview.warnings)

        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))
        skill = load_skill_from_dir(skill_store.skill_dir("demo-skill"))
        assert skill.system_prompt_enc.startswith("# PPT Master")

    def test_garbage_head_is_still_rejected(self, skills_env):
        """YAML 兜底不能变成「什么都收」。

        ``yaml.safe_load`` 几乎不挑食，单靠它兜底会让**本来会被跳过的坏
        SKILL.md** 带着一堆乱码元数据被加载进来 —— 静默加载一个坏技能比
        跳过它难发现得多。所以要求头部至少像 YAML 映射。
        """
        from app.services.skill_package import PackageError

        # 不像 frontmatter 的一坨文本
        md = "---\n这不是键值对，只是一句话\n---\n\n" + "长正文。" * 30
        with pytest.raises(PackageError):
            import_zip(make_zip({"SKILL.md": md}))

    def test_truncated_json_head_is_still_rejected(self, skills_env):
        from app.services.skill_package import PackageError

        md = '---\n{"name": "X"\n---\n\n' + "长正文。" * 30
        with pytest.raises(PackageError):
            import_zip(make_zip({"SKILL.md": md}))

    def test_no_pyyaml_degrades_to_json_only(self, skills_env, monkeypatch):
        """没装 pyyaml 时退回 JSON-only，而不是整个崩掉。

        ``store`` 是加载路径，它坏掉的代价是「所有技能一起消失」。
        """
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(ValueError):
            skill_store._split_skill_md(THIRD_PARTY_MD)

        # JSON 的技能不受影响
        meta, _ = skill_store._split_skill_md(
            '---\n{"name": "X", "systemPrompt": "y"}\n---\n\n正文\n'
        )
        assert meta["name"] == "X"


# ---------------------------------------------------------------------------
# 平台自建技能不受影响
# ---------------------------------------------------------------------------


class TestPlatformSkillsUnchanged:
    def test_create_writes_plain_json_skill_md(self, skills_env):
        """平台自己建的技能不该多出旁挂文件 —— 没必要，也少一处不一致。"""
        skill_store.create_skill(
            "mine", {"name": "我的技能", "systemPrompt": "你是助手。"}, "# 正文\n"
        )

        folder = skill_store.skill_dir("mine")
        assert (folder / SKILL_FILENAME).is_file()
        assert not (folder / SIDECAR_FILENAME).exists()
        assert read_md_bytes("mine").decode("utf-8").lstrip().startswith("---\n{")

    def test_update_without_sidecar_rewrites_skill_md(self, skills_env):
        """回归：没有旁挂的（平台自建）技能，更新仍然写 SKILL.md。

        否则管理员改自己建的技能会「改了没反应」—— 改动全落到一个别人
        不读的文件里。
        """
        skill_store.create_skill(
            "mine", {"name": "旧名", "systemPrompt": "你是助手。"}, "# 旧正文\n"
        )

        skill_store.update_skill(
            "mine", {"name": "新名", "systemPrompt": "你是新助手。"}, "# 新正文\n"
        )

        meta, body = skill_store.read_skill_md("mine")
        assert meta["name"] == "新名"
        assert "新正文" in body
        assert not (skill_store.skill_dir("mine") / SIDECAR_FILENAME).exists()


# ---------------------------------------------------------------------------
# 端到端：导入的技能出现在广场且可用
# ---------------------------------------------------------------------------


class TestEndToEndUsability:
    def test_imported_skill_is_in_plaza_and_loadable(self, skills_env):
        """一次把「能用」需要的东西全查一遍。

        前几轮分别在两处栽过：
          * ``authorId`` 写成 platform-admin → 广场（curated_only）看不到；
          * frontmatter 被转成 JSON → 第三方自检挂掉。
        真正「能用」得同时满足：广场可见 + 字段齐 + 加载不报错 + 自检能过。
        """
        import_zip(make_zip({"SKILL.md": THIRD_PARTY_MD}))

        plaza = {s.id for s in skill_store.list_skills(curated_only=True)}
        assert "demo-skill" in plaza

        skill = next(s for s in skill_store.list_skills() if s.id == "demo-skill")
        assert skill.name == "ppt-master"
        assert skill.description
        assert skill.system_prompt_enc

        assert third_party_integrity_check("demo-skill") == 0
