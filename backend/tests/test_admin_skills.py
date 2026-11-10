"""
管理后台 · 技能管理测试。

覆盖三件事：

1. **写入安全** —— slug 是拼进文件系统路径的，注入与路径穿越必须被拦下
2. **增删改真的落到文件上**，并且**扫盘器无需重启就能看到**
3. **权限边界** —— 非管理员拿不到，前端隐藏入口不算数

注意：写路径会动真实文件系统，所以整个模块通过 ``skills_env`` fixture
把 ``skills_root`` 指到临时目录。仓库里的 ``skills/`` 绝不能被测试污染。
"""
import json

import pytest
from httpx import AsyncClient

from app.services.skill import store as skill_store


#: 合法的最小 frontmatter。name 与 systemPrompt 是事实上的必填项。
GOOD_META = {
    "name": "周报生成助手",
    "description": "把零散的日报记录汇总成一页周报，突出进展、风险与下周计划。",
    "specialty": "周报",
    "systemPrompt": "你是周报撰写助手。只使用材料中出现的事实，不确定的标 TBD。",
    "userPrompt": "请根据以下材料生成周报：\n\n{{input}}",
    "variables": [{"name": "input", "type": "string"}],
}


@pytest.fixture
def skills_env(tmp_path, monkeypatch):
    """把 skills_root 指到临时目录。

    ``repo_root`` 带 ``lru_cache``，改环境变量后必须清缓存才生效；
    ``store`` 的列表缓存也要一起清，否则读到的是上一个测试的残留。
    """
    from app.core.paths import repo_root

    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("AGENTFLOW_REPO_ROOT", str(root))
    repo_root.cache_clear()
    skill_store.invalidate_cache()

    yield skill_store

    repo_root.cache_clear()
    skill_store.invalidate_cache()


# ---------------------------------------------------------------------------
# slug 校验
# ---------------------------------------------------------------------------


class TestSlugValidation:
    """slug 直接拼进文件系统路径，必须收得非常紧。"""

    @pytest.mark.parametrize("bad", [
        "",
        "   ",
        "Weekly_Report",     # 大写
        "weekly_report",     # 下划线
        "../etc",            # 路径穿越
        "a/b",               # 斜杠
        "a\\b",              # 反斜杠
        "a b",               # 空格
        "周报",              # 中文
        "-abc",              # 连字符开头
        ".hidden",           # 点开头
        "a" * 65,            # 超长
    ])
    def test_rejects_bad_slug(self, skills_env, bad):
        with pytest.raises(skill_store.SkillWriteError):
            skills_env.normalize_slug(bad)

    @pytest.mark.parametrize("good", [
        "abc", "a1", "9x", "a-b-c", "a" * 64, "x" * 64,
    ])
    def test_accepts_good_slug(self, skills_env, good):
        assert skills_env.normalize_slug(good) == good

    def test_folds_case(self, skills_env):
        """写入侧把大写折叠成小写，保证同一技能在大小写不分的
        文件系统上也只有一份目录。"""
        assert skills_env.normalize_slug("  Weekly-Report  ") == "weekly-report"

    @pytest.mark.parametrize("slug", sorted(skill_store.HIDDEN_SLUGS))
    def test_rejects_reserved_slugs(self, skills_env, slug):
        """平台保留目录不许通过后台创建。

        这些目录在广场里本来就是隐藏的，建了也看不见，只会让人以为功能坏了。
        """
        with pytest.raises(skill_store.SkillWriteError) as exc:
            skills_env.normalize_slug(slug)
        assert "保留" in str(exc.value)


class TestPathGuard:
    """即使 slug 校验被绕过，路径也必须在 skills_root 之内。"""

    @pytest.mark.parametrize("slug", ["../outside", "a/../../b", "/etc/passwd"])
    def test_rejects_paths_outside_root(self, skills_env, slug):
        with pytest.raises(skill_store.SkillWriteError):
            skills_env.skill_dir(slug)

    def test_allows_normal_slug(self, skills_env):
        path = skills_env.skill_dir("weekly-report")
        assert path.name == "weekly-report"
        assert path.parent == skills_env.skills_root()


# ---------------------------------------------------------------------------
# 读写往返
# ---------------------------------------------------------------------------


class TestRenderRoundTrip:
    """序列化必须与解析严格对称，否则写完自己读不回来。"""

    def test_round_trip(self, skills_env):
        text = skills_env._render_md(GOOD_META, "# 标题\n\n正文")
        meta, body = skills_env._split_skill_md(text)

        assert meta == GOOD_META
        assert body == "# 标题\n\n正文"

    def test_handles_chinese_without_escaping(self, skills_env):
        """ensure_ascii=False：中文必须原样落盘，不能变成 \\uXXXX。"""
        text = skills_env._render_md(GOOD_META, "正文")

        assert "周报生成助手" in text
        assert "\\u" not in text

    def test_body_with_frontmatter_fence_still_parses(self, skills_env):
        """正文里出现 `---` 不该把文件结构搞乱。"""
        text = skills_env._render_md(GOOD_META, "## 分割\n\n---\n\n继续")

        meta, body = skills_env._split_skill_md(text)

        assert meta["name"] == "周报生成助手"
        assert "继续" in body


class TestCreateSkill:
    def test_creates_file(self, skills_env):
        skills_env.create_skill("weekly-report", GOOD_META, "# 周报\n")

        path = skills_env.skill_dir("weekly-report") / "SKILL.md"
        assert path.is_file()
        assert "周报生成助手" in path.read_text(encoding="utf-8")

    def test_forces_id_to_match_slug(self, skills_env):
        """id 必须等于目录名。

        不一致时 ``get_skill`` 走不了快路径，得全表扫一遍才能找到，
        而且用户从广场点进去的链接会失效。
        """
        meta = dict(GOOD_META, id="something-else")
        skills_env.create_skill("weekly-report", meta, "正文")

        read_back, _ = skills_env.read_skill_md("weekly-report")
        assert read_back["id"] == "weekly-report"

    def test_applies_defaults(self, skills_env):
        skills_env.create_skill("weekly-report", GOOD_META, "正文")

        meta, _ = skills_env.read_skill_md("weekly-report")
        assert meta["authorName"] == "平台预置"
        assert meta["visibility"] == "public"
        assert meta["status"] == "published"

    @pytest.mark.parametrize("missing", ["name", "systemPrompt"])
    def test_rejects_missing_required_fields(self, skills_env, missing):
        """缺 systemPrompt 的技能能加载但一调用就产出空内容，
        必须在写入时就拦掉，而不是等用户踩到。"""
        meta = {k: v for k, v in GOOD_META.items() if k != missing}

        with pytest.raises(skill_store.SkillWriteError) as exc:
            skills_env.create_skill("weekly-report", meta, "正文")

        assert missing in str(exc.value)

    def test_refuses_to_overwrite(self, skills_env):
        """已存在就拒绝，避免一次误点把线上技能覆盖掉。"""
        skills_env.create_skill("weekly-report", GOOD_META, "旧正文")

        with pytest.raises(skill_store.SkillWriteError):
            skills_env.create_skill("weekly-report", GOOD_META, "新正文")

        _, body = skills_env.read_skill_md("weekly-report")
        assert body == "旧正文"

    def test_author_is_forced_to_platform_preset(self, skills_env):
        """authorId 必须被强制成 platform-preset。

        ``GET /skills/plaza`` 走 ``curated_only=True``，只认这个值。
        若允许调用方自带 authorId，就会出现「建完了但广场上怎么也看不到」
        —— 而且不报错，只是凭空不出现，极难排查。
        """
        skills_env.create_skill(
            "weekly-report", dict(GOOD_META, authorId="someone-else"), "正文"
        )

        meta, _ = skills_env.read_skill_md("weekly-report")
        assert meta["authorId"] == "platform-preset"

    def test_visible_to_plaza_loader(self, skills_env):
        """**核心用例**：新建的技能要被广场的扫盘器看见，且无需重启。

        扫盘靠「目录名集合 + mtime」判断缓存是否过期；写完之后必须失效缓存，
        否则管理员建完发现广场上没有，会以为功能是坏的。
        """
        skills_env.create_skill("weekly-report", GOOD_META, "正文")

        skills = {s.id: s for s in skills_env.list_skills()}

        assert "weekly-report" in skills
        assert skills["weekly-report"].name == "周报生成助手"
        assert skills["weekly-report"].system_prompt_enc == GOOD_META["systemPrompt"]

    def test_deleted_skill_disappears_from_loader(self, skills_env):
        skills_env.create_skill("weekly-report", GOOD_META, "正文")
        assert "weekly-report" in {s.id for s in skill_store.list_skills()}

        skills_env.remove_skill_dir("weekly-report")

        assert "weekly-report" not in {s.id for s in skill_store.list_skills()}


class TestUpdateSkill:
    def test_overwrites_content(self, skills_env):
        skills_env.create_skill("weekly-report", GOOD_META, "旧正文")

        skills_env.update_skill("weekly-report", dict(GOOD_META, name="改名后"), "新正文")

        meta, body = skills_env.read_skill_md("weekly-report")
        assert meta["name"] == "改名后"
        assert body == "新正文"

    def test_missing_skill_fails(self, skills_env):
        with pytest.raises(skill_store.SkillWriteError):
            skills_env.update_skill("nope", GOOD_META, "正文")

    def test_update_is_visible_to_loader(self, skills_env):
        """改完也要立刻在广场上体现。"""
        skills_env.create_skill("weekly-report", GOOD_META, "正文")

        skills_env.update_skill("weekly-report", dict(GOOD_META, name="新名字"), "正文")

        skills = {s.id: s for s in skills_env.list_skills()}
        assert skills["weekly-report"].name == "新名字"


class TestDeleteSkill:
    def test_removes_scripts_dir_too(self, skills_env):
        skills_env.create_skill("weekly-report", GOOD_META, "正文")
        (skills_env.skill_dir("weekly-report") / "scripts").mkdir()
        (skills_env.skill_dir("weekly-report") / "scripts" / "run.py").write_text("x")

        skills_env.remove_skill_dir("weekly-report")

        assert not skills_env.skill_dir("weekly-report").exists()

    def test_missing_skill_fails(self, skills_env):
        with pytest.raises(skill_store.SkillWriteError):
            skills_env.remove_skill_dir("nope")

    def test_refuses_to_delete_root(self, skills_env):
        """双保险：绝不允许删到技能根目录本身。"""
        with pytest.raises(skill_store.SkillWriteError):
            # skill_dir('') 解析出来就是根目录
            skills_env.remove_skill_dir("")


# ---------------------------------------------------------------------------
# API 层
# ---------------------------------------------------------------------------


class TestAdminSkillsApi:
    """``/api/v1/admin/skills`` 的权限与增删改闭环。"""

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.get("/api/v1/admin/skills")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_non_admin(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """普通用户必须拿不到 —— 前端隐藏入口不算数，后端要独立拦。"""
        for call in (
            async_client.get("/api/v1/admin/skills", headers=auth_headers),
            async_client.post(
                "/api/v1/admin/skills", json={}, headers=auth_headers
            ),
            async_client.delete(
                "/api/v1/admin/skills/whatever", headers=auth_headers
            ),
        ):
            resp = await call
            assert resp.status_code == 403, resp.text

    @pytest.mark.asyncio
    async def test_full_cycle(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        """建 → 查 → 改 → 删，并且每步都和广场的数据源对齐。"""
        payload = {
            "slug": "weekly-report",
            "frontmatter": GOOD_META,
            "body": "# 周报\n\n正文",
        }

        created = await async_client.post(
            "/api/v1/admin/skills", json=payload, headers=admin_headers
        )
        assert created.status_code == 201, created.text
        assert created.json()["slug"] == "weekly-report"
        # id 被强制对齐到 slug
        assert created.json()["frontmatter"]["id"] == "weekly-report"

        detail = await async_client.get(
            "/api/v1/admin/skills/weekly-report", headers=admin_headers
        )
        assert detail.status_code == 200
        assert detail.json()["body"] == "# 周报\n\n正文"

        # 广场接口要能看到它 —— 这才是「加技能」的最终目的
        plaza = await async_client.get("/api/v1/skills/plaza", headers=admin_headers)
        assert plaza.status_code == 200, plaza.text
        assert "weekly-report" in {s["id"] for s in plaza.json()}

        updated = await async_client.patch(
            "/api/v1/admin/skills/weekly-report",
            json={**payload, "frontmatter": dict(GOOD_META, name="改名后")},
            headers=admin_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "改名后"

        deleted = await async_client.delete(
            "/api/v1/admin/skills/weekly-report", headers=admin_headers
        )
        assert deleted.status_code == 200
        gone = await async_client.get(
            "/api/v1/admin/skills/weekly-report", headers=admin_headers
        )
        assert gone.status_code == 404

    @pytest.mark.asyncio
    async def test_create_rejects_bad_slug(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        resp = await async_client.post(
            "/api/v1/admin/skills",
            json={"slug": "../escape", "frontmatter": GOOD_META, "body": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "slug" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_rejects_reserved_slug(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        resp = await async_client.post(
            "/api/v1/admin/skills",
            json={
                "slug": sorted(skill_store.HIDDEN_SLUGS)[0],
                "frontmatter": GOOD_META,
                "body": "x",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "保留" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_rejects_missing_system_prompt(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        meta = {k: v for k, v in GOOD_META.items() if k != "systemPrompt"}
        resp = await async_client.post(
            "/api/v1/admin/skills",
            json={"slug": "no-prompt", "frontmatter": meta, "body": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "systemPrompt" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_duplicate_slug_is_400_not_overwrite(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        payload = {"slug": "weekly-report", "frontmatter": GOOD_META, "body": "旧"}
        assert (
            await async_client.post(
                "/api/v1/admin/skills", json=payload, headers=admin_headers
            )
        ).status_code == 201

        again = await async_client.post(
            "/api/v1/admin/skills",
            json={**payload, "body": "新"},
            headers=admin_headers,
        )
        assert again.status_code == 400

        detail = await async_client.get(
            "/api/v1/admin/skills/weekly-report", headers=admin_headers
        )
        assert detail.json()["body"] == "旧", "重名请求不该覆盖已有技能"

    @pytest.mark.asyncio
    async def test_rename_via_mismatched_slug_is_rejected(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        """路径 slug 与 body slug 不一致时拒绝，而不是静默改名。"""
        payload = {"slug": "weekly-report", "frontmatter": GOOD_META, "body": "x"}
        assert (
            await async_client.post(
                "/api/v1/admin/skills", json=payload, headers=admin_headers
            )
        ).status_code == 201

        resp = await async_client.patch(
            "/api/v1/admin/skills/weekly-report",
            json={**payload, "slug": "renamed"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_rejects_reserved_slug(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        """平台保留目录（预置但未接入广场）不能删。"""
        slug = sorted(skill_store.HIDDEN_SLUGS)[0]
        folder = skills_env.skill_dir(slug)
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("x", encoding="utf-8")

        resp = await async_client.delete(
            f"/api/v1/admin/skills/{slug}", headers=admin_headers
        )
        assert resp.status_code == 400
        assert folder.is_dir(), "被拒绝的删除不该动文件系统"

    @pytest.mark.asyncio
    async def test_list_marks_broken_skill(
        self, async_client: AsyncClient, admin_headers: dict, skills_env
    ):
        """frontmatter 坏掉的技能在广场里是直接消失的。

        管理端必须把它连同失败原因列出来，否则没人知道该去修哪个目录。
        """
        folder = skills_env.skill_dir("broken-skill")
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            "---\n{ 这不是合法 JSON }\n---\n\n正文", encoding="utf-8"
        )

        resp = await async_client.get("/api/v1/admin/skills", headers=admin_headers)
        assert resp.status_code == 200
        # 该接口返回裸数组（技能没有分页），不是 { items, total }
        row = next(s for s in resp.json() if s["slug"] == "broken-skill")

        assert row["broken"], "坏掉的技能必须带失败原因"
        assert "JSON" in row["broken"]

        # 广场上不该出现它（load 会失败并跳过）
        plaza = await async_client.get("/api/v1/skills/plaza", headers=admin_headers)
        assert plaza.status_code == 200
        assert "broken-skill" not in {s["id"] for s in plaza.json()}
