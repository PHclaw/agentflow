"""
技能包导入测试。

zip 是**不可信输入**，所以这里大半用例是在试攻击：
路径穿越、符号链接、zip bomb、多顶层目录、覆盖既有技能。
漏一个就可能被写入 skills_root 之外，或者盖掉线上技能。
"""
import io
import os
import time
import zipfile

import pytest
from httpx import AsyncClient

from app.services import skill_package
from app.services.skill import store as skill_store
from app.services.skill_package import PackageError, import_zip, inspect_zip

GOOD_MD = """---
{
  "name": "测试技能",
  "description": "用于导入测试",
  "systemPrompt": "你是测试助手。",
  "userPrompt": "{{input}}"
}
---

# 测试技能
"""

GOOD_MD_NO_NAME = """---
{
  "description": "缺 name",
  "systemPrompt": "x"
}
---
"""


def make_zip(entries: dict[str, str], top: str | None = "demo-skill") -> bytes:
    """打一个 zip。top=None 表示文件直接放在根，没有顶层目录。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            full = f"{top}/{name}" if top else name
            if isinstance(content, str):
                content = content.encode()
            zf.writestr(full, content)
    return buf.getvalue()


def make_zip_with_infos(infos: list[tuple[str, bytes, int]]) -> bytes:
    """手工构造 ZipInfo，用来造符号链接这类特殊条目。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data, mode in infos:
            info = zipfile.ZipInfo(name)
            info.external_attr = (mode << 16)
            zf.writestr(info, data)
    return buf.getvalue()


#: Claude Code 生态风格的技能：YAML frontmatter，没有 systemPrompt，
#: 靠一大段正文当指令。ppt-master-main.zip 里的 SKILL.md 就是这样。
YAML_MD = (
    """---
name: ppt-master
description: >
  AI-driven presentation workflow for generating editable PPTX decks,
  reconstructing page visuals and filling native templates.
metadata:
  version: 1.0.0
---

# PPT Master
"""
    + "这里是给模型看的完整指令，说明什么时候该读哪个 reference。" * 4
)


def make_repo_zip(extra: dict[str, str] | None = None) -> bytes:
    """造一个和 ``ppt-master-main.zip`` 同构的**仓库整包**。

    顶层是仓库名，真正的技能在 ``skills/<name>/`` 里，外面还摊着 README、
    CI 配置、docs 截图 —— 那些都不该被导进技能目录。
    """
    files = {
        "README.md": "# 仓库说明",
        ".github/workflows/ci.yml": "on: push",
        "docs/assets/hero.png": "x" * 200,
        "skills/ppt-master/SKILL.md": YAML_MD,
        "skills/ppt-master/scripts/build.py": "print('build')",
        "skills/ppt-master/templates/t1.txt": "tpl",
    }
    files.update(extra or {})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(f"ppt-master-main/{name}", content)
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


# ---------------------------------------------------------------------------
# 正常路径
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_imports_flat_package(self, skills_env):
        data = make_zip({"SKILL.md": GOOD_MD})

        preview = import_zip(data)

        assert preview.slug == "demo-skill"
        assert preview.name == "测试技能"
        assert preview.has_scripts is False

    def test_imports_package_with_scripts(self, skills_env):
        data = make_zip({
            "SKILL.md": GOOD_MD,
            "scripts/run.py": "print('hi')",
            "scripts/lib/util.py": "X = 1",
        })

        preview = import_zip(data)

        assert preview.has_scripts is True
        base = skills_env.skill_dir(preview.slug)
        assert (base / "SKILL.md").is_file()
        assert (base / "scripts" / "run.py").is_file()
        assert (base / "scripts" / "lib" / "util.py").is_file()
        assert (base / "scripts" / "run.py").read_text() == "print('hi')"

    def test_imported_skill_is_visible_to_loader(self, skills_env):
        """导入的技能必须被广场的扫盘器看见，且无需重启。"""
        import_zip(make_zip({"SKILL.md": GOOD_MD}))

        skills = {s.id for s in skills_env.list_skills()}
        assert "demo-skill" in skills

    def test_imported_skill_is_callable_shape(self, skills_env):
        """导入后读回来，systemPrompt 必须原样在。"""
        preview = import_zip(make_zip({"SKILL.md": GOOD_MD}))

        meta, body = skills_env.read_skill_md(preview.slug)
        assert meta["systemPrompt"] == "你是测试助手。"
        assert meta["id"] == preview.slug
        assert "测试技能" in body

    def test_slug_override(self, skills_env):
        data = make_zip({"SKILL.md": GOOD_MD})

        preview = import_zip(data, slug_override="renamed-skill")

        assert preview.slug == "renamed-skill"
        assert skills_env.skill_dir("renamed-skill").is_dir()

    def test_no_top_level_dir_uses_frontmatter_id(self, skills_env):
        md = GOOD_MD.replace('"name": "测试技能"', '"name": "测试技能", "id": "from-meta"')
        data = make_zip({"SKILL.md": md}, top=None)

        preview = inspect_zip(data)[0]

        assert preview.slug == "from-meta"


# ---------------------------------------------------------------------------
# 恶意 / 畸形输入
# ---------------------------------------------------------------------------


class TestMaliciousInput:
    def test_rejects_path_traversal(self, skills_env):
        data = make_zip({
            "SKILL.md": GOOD_MD,
            "../../evil.py": "x",
        })

        with pytest.raises(PackageError) as exc:
            import_zip(data)
        assert "穿越" in str(exc.value) or "非法" in str(exc.value)

    def test_rejects_absolute_path_entry(self, skills_env):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("demo-skill/SKILL.md", GOOD_MD)
            zf.writestr("/etc/passwd", "root:x:0:0")
        with pytest.raises(PackageError):
            import_zip(buf.getvalue())

    def test_rejects_symlink_entry(self, skills_env):
        """符号链接能指向 skills_root 之外，解压后往里写就中招。"""
        data = make_zip_with_infos([
            ("demo-skill/SKILL.md", GOOD_MD.encode(), 0o100644),
            ("demo-skill/link.py", b"/etc/passwd", 0o120777),
        ])

        with pytest.raises(PackageError) as exc:
            import_zip(data)
        assert "符号链接" in str(exc.value)

    def test_rejects_too_many_entries(self, skills_env, monkeypatch):
        """技能目录内文件数超限就拒绝。

        真实上限是 5 万（PPT / 图表类技能带一两万个模板文件很正常），
        所以这里把阈值压小 —— 为了测一条边界去造五万个 zip 条目不值当。
        """
        monkeypatch.setattr(skill_package, "MAX_ENTRIES", 5)
        entries = {"SKILL.md": GOOD_MD}
        for i in range(8):
            entries[f"scripts/f{i}.py"] = "x"

        with pytest.raises(PackageError) as exc:
            import_zip(make_zip(entries))
        assert "文件过多" in str(exc.value)

    def test_rejects_zip_bomb(self, skills_env, monkeypatch):
        """按声明的 file_size 累加预判，不等到真写满盘。"""
        monkeypatch.setattr(skill_package, "MAX_TOTAL_BYTES", 4096)
        data = make_zip({"SKILL.md": GOOD_MD, "scripts/big.bin": b"\0" * 5000})

        with pytest.raises(PackageError) as exc:
            import_zip(data)
        assert "上限" in str(exc.value)

    def test_read_entry_counts_actual_bytes(self, skills_env):
        """体积必须按**实际**解压量记账，不能只信声明的 file_size。

        ``info.file_size`` 是压缩包自己填的值，可以撒谎。以前直接
        ``zf.read(info)`` 并靠声明值求和，伪造声明就能让一次 read 把内存
        吃满 —— 而检查「看起来」是通过的。
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("demo-skill/SKILL.md", GOOD_MD)
            zf.writestr("demo-skill/scripts/blob.bin", b"\0" * 200_000)

        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
            blob = next(
                i for i in skill_package._iter_infos(zf)
                if i.filename.endswith("blob.bin")
            )
            # 预算只剩 1KB，而实际有 200KB —— 必须在读完之前抛
            budget = [skill_package.MAX_TOTAL_BYTES - 1024]
            with pytest.raises(PackageError):
                skill_package._read_entry(zf, blob, budget)

    def test_rejects_bad_zip(self, skills_env):
        with pytest.raises(PackageError) as exc:
            import_zip(b"this is not a zip")
        assert "zip" in str(exc.value).lower()

    def test_rejects_missing_skill_md(self, skills_env):
        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"readme.txt": "hi"}))
        assert "SKILL.md" in str(exc.value)

    def test_rejects_missing_name(self, skills_env):
        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"SKILL.md": GOOD_MD_NO_NAME}))
        assert "name" in str(exc.value)

    def test_rejects_missing_system_prompt(self, skills_env):
        """缺 systemPrompt 的技能能加载但一调用就产出空内容。"""
        md = '---\n{"name": "X"}\n---\n\n正文'
        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"SKILL.md": md}))
        assert "systemPrompt" in str(exc.value)

    def test_rejects_unparseable_frontmatter(self, skills_env):
        """JSON 和 YAML **都**解析不了才算坏。

        ``{ 坏 JSON }`` 现在会被 YAML 收下（``{'坏 JSON': None}``），所以
        拿它当「坏 frontmatter」的样本已经不成立了；这里换成一个两边都不
        合法的截断对象。
        """
        # 正文刻意写长，免得它先因为「正文太短」被拒，掩盖了真正要测的解析
        md = '---\n{"name": "X"\n---\n\n' + "正文。" * 40

        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"SKILL.md": md}))
        assert "解析失败" in str(exc.value)

    def test_rejects_multiple_skills_same_depth(self, skills_env):
        """同深度有多个 SKILL.md 时**不猜**，报错并列出候选。

        很多第三方仓库一次放几十个技能。挑第一个导进来的话，结果是一个
        内容完全不对、但「导入成功」的技能 —— 比直接失败难查得多。
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("skills/alpha/SKILL.md", GOOD_MD)
            zf.writestr("skills/beta/SKILL.md", GOOD_MD)

        with pytest.raises(PackageError) as exc:
            import_zip(buf.getvalue())
        msg = str(exc.value)
        assert "多个技能" in msg
        assert "skills/alpha" in msg and "skills/beta" in msg

    def test_multiple_top_level_dirs_is_not_an_error(self, skills_env):
        """顶层目录多**不是**问题 —— 决定技能边界的是 SKILL.md 在哪。

        老实现按「顶层目录必须唯一」判断，于是 ``aaa/SKILL.md`` +
        ``bbb/readme.txt`` 会被误判成「无法判断哪个是技能」。
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("aaa/SKILL.md", GOOD_MD)
            zf.writestr("bbb/readme.txt", "hi")

        preview = import_zip(buf.getvalue())

        assert preview.slug == "aaa"
        assert preview.skill_path == "aaa"
        assert not (skill_store.skill_dir("aaa") / "bbb").exists()

    def test_rejects_reserved_slug(self, skills_env):
        """保留目录名不能导入，否则导完在广场上看不到。"""
        for slug in sorted(skill_store.HIDDEN_SLUGS)[:2]:
            with pytest.raises(PackageError) as exc:
                import_zip(make_zip({"SKILL.md": GOOD_MD}), slug_override=slug)
            assert "保留" in str(exc.value)


class TestOverwrite:
    def test_refuses_to_overwrite_by_default(self, skills_env):
        import_zip(make_zip({"SKILL.md": GOOD_MD}))

        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"SKILL.md": GOOD_MD.replace("测试助手", "改过的")}))
        assert "已存在" in str(exc.value)

        # 原内容不该被改动
        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["systemPrompt"] == "你是测试助手。"

    def test_overwrite_replaces_content(self, skills_env):
        import_zip(make_zip({"SKILL.md": GOOD_MD}))

        import_zip(
            make_zip({"SKILL.md": GOOD_MD.replace("测试助手", "改过的"),
                      "scripts/new.py": "y"}),
            overwrite=True,
        )

        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["systemPrompt"] == "你是改过的。"
        assert (skill_store.skill_dir("demo-skill") / "scripts" / "new.py").is_file()

    def test_overwrite_removes_stale_scripts(self, skills_env):
        """覆盖时旧包里的 scripts 不该残留。

        否则换过一次技能的脚本目录会同时留着新旧两批文件，
        跑起来用哪个全看导入顺序，极难排查。
        """
        import_zip(make_zip({"SKILL.md": GOOD_MD, "scripts/old.py": "x"}))
        import_zip(make_zip({"SKILL.md": GOOD_MD, "scripts/new.py": "y"}),
                   overwrite=True)

        base = skill_store.skill_dir("demo-skill")
        assert not (base / "scripts" / "old.py").exists()
        assert (base / "scripts" / "new.py").exists()

    def test_failed_import_leaves_no_partial_dir(self, skills_env):
        """导入中途失败不能留下半个技能目录。

        坏目录会让 load_skill_from_dir 抛异常并被跳过 ——
        用户看到的就是「技能凭空消失」。
        """
        import_zip(make_zip({"SKILL.md": GOOD_MD}))

        # 第二次用一个会触发异常的包（保留 slug 走覆盖路径后再炸）
        bad = make_zip({"SKILL.md": "---\n{ 坏 }\n---\n"})
        with pytest.raises(PackageError):
            import_zip(bad, overwrite=True)

        # 原技能仍然完好
        assert (skill_store.skill_dir("demo-skill") / "SKILL.md").is_file()
        # 没有残留的临时目录
        root = skill_store.skills_root()
        assert not any(p.name.startswith(".import-") for p in root.iterdir())

    def test_cleans_up_staging_left_by_a_killed_import(self, skills_env):
        """被**强杀**的导入留下的暂存目录，下次预览时要回收。

        上面的 ``except`` 清不了这种：进程被 kill 时那段代码没机会跑，
        于是整个技能目录的副本就那么留在盘上（ppt-master 那个是 37MB）。
        ``list_skills`` 会跳过点开头的目录，所以广场上看不出异常，
        只是磁盘在被慢慢吃掉 —— 这类泄漏没人会注意到。
        """
        root = skill_store.skills_root()
        stale = root / ".import-dead"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("x")
        # 把 mtime 拨回两小时前，模拟「上一次失败的导入」
        old = time.time() - 7200
        os.utime(stale, (old, old))

        # 正在进行的导入：mtime 很新，不能被误删
        running = root / ".import-running"
        running.mkdir(parents=True)

        inspect_zip(make_zip({"SKILL.md": GOOD_MD}))

        assert not stale.exists()
        assert running.exists()


class TestPreview:
    def test_preview_does_not_write(self, skills_env):
        data = make_zip({"SKILL.md": GOOD_MD, "scripts/a.py": "x"})

        preview, meta = inspect_zip(data)

        assert preview.slug == "demo-skill"
        assert preview.has_scripts is True
        assert not skill_store.skill_dir("demo-skill").exists()

    def test_preview_reports_existing(self, skills_env):
        import_zip(make_zip({"SKILL.md": GOOD_MD}))

        preview, _ = inspect_zip(make_zip({"SKILL.md": GOOD_MD}))
        assert preview.exists is True

    def test_preview_warns_about_missing_description(self, skills_env):
        md = '---\n{"name": "X", "systemPrompt": "y"}\n---\n\n正文'
        preview, _ = inspect_zip(make_zip({"SKILL.md": md}))
        assert any("description" in w for w in preview.warnings)

    def test_preview_warns_about_reserved_slug(self, skills_env):
        slug = sorted(skill_store.HIDDEN_SLUGS)[0]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{slug}/SKILL.md", GOOD_MD)

        preview, _ = inspect_zip(buf.getvalue())
        assert any("保留" in w for w in preview.warnings)
        assert preview.exists is False


# ---------------------------------------------------------------------------
# API 层
# ---------------------------------------------------------------------------


class TestImportApi:
    """API 层。

    这些用例**必须**挂 ``skills_env``：导入最终写的是文件系统，
    不重定向的话会往仓库真实的 ``skills/`` 目录里灌测试数据，
    而且第二次运行时「已存在」会让用例莫名其妙地失败。
    """

    @pytest.fixture(autouse=True)
    def _isolate_skills(self, tmp_path, monkeypatch):
        from app.core.paths import repo_root

        root = tmp_path / "repo"
        root.mkdir()
        monkeypatch.setenv("AGENTFLOW_REPO_ROOT", str(root))
        repo_root.cache_clear()
        skill_store.invalidate_cache()
        yield
        repo_root.cache_clear()
        skill_store.invalidate_cache()

    @pytest.mark.asyncio
    async def test_preview_endpoint(self, async_client: AsyncClient, admin_headers: dict):
        resp = await async_client.post(
            "/api/v1/admin/skills/import/preview",
            files={"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")},
            headers=admin_headers,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["slug"] == "demo-skill"
        assert body["name"] == "测试技能"
        assert body["file_count"] >= 1

    @pytest.mark.asyncio
    async def test_import_endpoint(self, async_client: AsyncClient, admin_headers: dict):
        resp = await async_client.post(
            "/api/v1/admin/skills/import",
            files={"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")},
            headers=admin_headers,
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["slug"] == "demo-skill"

    @pytest.mark.asyncio
    async def test_import_conflict_returns_409(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        payload = {"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")}
        assert (await async_client.post(
            "/api/v1/admin/skills/import", files=payload, headers=admin_headers
        )).status_code == 200

        again = await async_client.post(
            "/api/v1/admin/skills/import", files=payload, headers=admin_headers
        )
        assert again.status_code == 409
        assert "已存在" in again.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_with_overwrite_flag(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        payload = {"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")}
        await async_client.post("/api/v1/admin/skills/import", files=payload, headers=admin_headers)

        resp = await async_client.post(
            "/api/v1/admin/skills/import?overwrite=true", files=payload, headers=admin_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_traversal_zip(self, async_client: AsyncClient, admin_headers: dict):
        resp = await async_client.post(
            "/api/v1/admin/skills/import",
            files={"file": ("pkg.zip", make_zip({
                "SKILL.md": GOOD_MD, "../../evil.py": "x"
            }), "application/zip")},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_requires_admin(self, async_client: AsyncClient, auth_headers: dict):
        resp = await async_client.post(
            "/api/v1/admin/skills/import",
            files={"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/admin/skills/import",
            files={"file": ("pkg.zip", make_zip({"SKILL.md": GOOD_MD}), "application/zip")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_preview_reports_skill_path(self, async_client: AsyncClient, admin_headers: dict):
        """仓库整包要能看出「究竟导的是哪一层」。"""
        resp = await async_client.post(
            "/api/v1/admin/skills/import/preview",
            files={"file": ("pkg.zip", make_repo_zip(), "application/zip")},
            headers=admin_headers,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["skill_path"] == "ppt-master-main/skills/ppt-master"
        assert body["slug"] == "ppt-master"
        assert body["file_count"] == 3
        assert body["ignored_files"] == 3  # README / ci.yml / hero.png

    @pytest.mark.asyncio
    async def test_import_accepts_custom_description(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        """整个包导进来，广场描述由管理员自己写 —— 这是这条需求的落点。"""
        resp = await async_client.post(
            "/api/v1/admin/skills/import",
            files={"file": ("pkg.zip", make_repo_zip(), "application/zip")},
            params={"description": "做 PPT 的技能", "name": "PPT 助手"},
            headers=admin_headers,
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["description"] == "做 PPT 的技能"

        detail = await async_client.get(
            "/api/v1/admin/skills/ppt-master", headers=admin_headers
        )
        fm = detail.json()["frontmatter"]
        assert fm["name"] == "PPT 助手"
        assert fm["description"] == "做 PPT 的技能"


# ---------------------------------------------------------------------------
# 仓库整包
# ---------------------------------------------------------------------------


class TestRepoPackage:
    """GitHub「Download ZIP」那种整包：自动下钻，只导入 SKILL.md 那一层。"""

    def test_locates_nested_skill_dir(self, skills_env):
        preview, _ = inspect_zip(make_repo_zip())

        assert preview.skill_path == "ppt-master-main/skills/ppt-master"
        # slug 取技能目录名，而不是仓库名 ppt-master-main
        assert preview.slug == "ppt-master"

    def test_only_imports_files_under_skill_dir(self, skills_env):
        preview = import_zip(make_repo_zip())
        base = skill_store.skill_dir(preview.slug)

        assert (base / "SKILL.md").is_file()
        assert (base / "scripts" / "build.py").is_file()
        assert (base / "templates" / "t1.txt").is_file()
        # 仓库的 README / CI / docs 不该被搬进技能目录
        assert not (base / "README.md").exists()
        assert not (base / ".github").exists()
        assert not (base / "docs").exists()

    def test_reports_ignored_files(self, skills_env):
        """跳过多少要能看见 —— 否则管理员不知道到底导进来了什么。"""
        preview, _ = inspect_zip(make_repo_zip())

        assert preview.file_count == 3
        assert preview.ignored_files == 3

    def test_nested_skill_is_visible_to_plaza(self, skills_env):
        """这条守的是一个**真的老 bug**。

        ``import_zip`` 落盘时写的是 ``authorId="platform-admin"``，而广场走
        ``curated_only`` 只认 ``platform-preset`` —— 于是**通过技能包导入的
        技能从来不会出现在广场上**。而且不报错，只是不见了。老测试用的是
        不过滤的 ``list_skills()``，所以一直没照出来。
        """
        import_zip(make_repo_zip())

        plaza = {s.id for s in skills_env.list_skills(curated_only=True)}
        assert "ppt-master" in plaza

    def test_skill_path_selects_among_multiple(self, skills_env):
        """包里有多个技能时用 skill_path 指定。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("repo/skills/alpha/SKILL.md", YAML_MD)
            zf.writestr("repo/skills/beta/SKILL.md", YAML_MD)

        preview, _ = inspect_zip(buf.getvalue(), skill_path="repo/skills/beta")

        assert preview.skill_path == "repo/skills/beta"
        assert preview.slug == "beta"

    def test_bad_skill_path_lists_candidates(self, skills_env):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("repo/skills/alpha/SKILL.md", YAML_MD)

        with pytest.raises(PackageError) as exc:
            inspect_zip(buf.getvalue(), skill_path="repo/skills/nope")

        assert "repo/skills/alpha" in str(exc.value)

    def test_warns_when_other_skills_are_present(self, skills_env):
        """候选深度不同时取最浅的那个，但要提示还有别的。

        （候选同深度是**报错**，不是警告 —— 见
        ``test_rejects_multiple_skills_same_depth``。）
        """
        md = GOOD_MD.replace('"name": "测试技能"', '"name": "测试技能", "id": "root-skill"')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("SKILL.md", md)
            zf.writestr("skills/alpha/SKILL.md", YAML_MD)

        preview, _ = inspect_zip(buf.getvalue())

        assert preview.skill_path == ""      # 根上那个最浅
        assert preview.slug == "root-skill"  # 根上没有目录名可用，退到 id
        assert sorted(preview.skill_candidates) == ["", "skills/alpha"]
        assert any("多个技能" in w for w in preview.warnings)


# ---------------------------------------------------------------------------
# frontmatter 格式
# ---------------------------------------------------------------------------


class TestFrontmatterFormats:
    """AgentFlow 自己写 JSON，但第三方技能大量用 YAML。"""

    def test_accepts_yaml_frontmatter(self, skills_env):
        preview = import_zip(make_zip({"SKILL.md": YAML_MD}))

        assert preview.name == "ppt-master"
        meta, _ = skill_store.read_skill_md(preview.slug)
        assert meta["name"] == "ppt-master"
        assert meta["description"].startswith("AI-driven")
        # 落盘后是 JSON —— 加载路径永远不必认 YAML
        assert meta["id"] == preview.slug

    def test_yaml_metadata_block_is_kept(self, skills_env):
        """YAML 的嵌套 metadata 要原样留下，别在转换时丢掉。"""
        import_zip(make_zip({"SKILL.md": YAML_MD}))

        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["metadata"]["version"] == "1.0.0"

    def test_body_becomes_system_prompt_with_warning(self, skills_env):
        """没有 systemPrompt 时用正文兜底 —— 那段正文本来就是给模型看的。

        但必须**显式警告**：默认值是「一大段指令」这件事，管理员需要知道，
        否则他不会去改它。
        """
        preview, meta = inspect_zip(make_zip({"SKILL.md": YAML_MD}))

        assert meta["systemPrompt"].startswith("# PPT Master")
        assert any("正文" in w for w in preview.warnings)

    def test_short_body_is_not_a_prompt(self, skills_env):
        """正文短到像占位符时不能拿来当提示词。

        那样的技能能加载、能调用、产出垃圾 —— 比直接失败更难发现。
        """
        with pytest.raises(PackageError) as exc:
            import_zip(make_zip({"SKILL.md": "---\nname: X\n---\n\n正文"}))

        assert "systemPrompt" in str(exc.value)


# ---------------------------------------------------------------------------
# 覆盖值
# ---------------------------------------------------------------------------


class TestOverrides:
    """确认框里填的值。第三方包的字段往往不符合 AgentFlow 的约定。"""

    def test_description_override_wins(self, skills_env):
        preview = import_zip(
            make_zip({"SKILL.md": YAML_MD}),
            overrides={"description": "做 PPT 的技能"},
        )

        assert preview.description == "做 PPT 的技能"
        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["description"] == "做 PPT 的技能"

    def test_blank_override_keeps_package_value(self, skills_env):
        """表单没填的字段会以空串传上来 —— 那意思是「用包里的值」。

        不做这个区分的话，一次导入会把 name / description 全抹掉。
        """
        import_zip(
            make_zip({"SKILL.md": YAML_MD}),
            overrides={"description": "", "name": "   "},
        )

        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["name"] == "ppt-master"
        assert meta["description"].startswith("AI-driven")

    def test_system_prompt_override_wins(self, skills_env):
        """管理员自己写了提示词就不该被正文兜底盖掉。"""
        import_zip(
            make_zip({"SKILL.md": YAML_MD}),
            overrides={"systemPrompt": "你是 PPT 助手。"},
        )

        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["systemPrompt"] == "你是 PPT 助手。"

    def test_cannot_override_identity_fields(self, skills_env):
        """authorId / id 由流程强制，不接受外部指定。

        authorId 被改掉技能就在广场上凭空消失；id 与目录名不一致会让
        get_skill 走全表扫描兜底。
        """
        import_zip(
            make_zip({"SKILL.md": YAML_MD}),
            overrides={"authorId": "someone-else", "id": "hacked"},
        )

        meta, _ = skill_store.read_skill_md("demo-skill")
        assert meta["authorId"] == "platform-preset"
        assert meta["id"] == "demo-skill"


class TestLimitsFitRealRepos:
    """上限得装得下真实仓库整包。

    早先 ``MAX_ZIP_BYTES=20MB`` / ``MAX_ENTRIES=500``，那个假设是「技能包
    就是几个 md 和 py」。pptx 类仓库整包是 54MB、一万三千条，直接被挡在
    门外 —— 而它真正的技能只有 37MB。真实防线是「解压后」的上限。
    """

    def test_zip_cap_fits_repo_downloads(self):
        assert skill_package.MAX_ZIP_BYTES >= 100 * 1024 * 1024

    def test_entry_cap_fits_template_heavy_skills(self):
        assert skill_package.MAX_ENTRIES >= 20_000

    def test_extract_budget_is_still_bounded(self):
        """放宽不等于不设防 —— 解压后仍然必须有上限。"""
        assert skill_package.MAX_TOTAL_BYTES <= 1024 * 1024 * 1024
        assert skill_package.MAX_TOTAL_BYTES >= 100 * 1024 * 1024
