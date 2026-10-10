"""Skill API smoke tests."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestSkillsAPI:
    @pytest.mark.asyncio
    async def test_plaza_unauthorized(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/skills/plaza")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_plaza_returns_curated_skills(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        response = await async_client.get(
            "/api/v1/skills/plaza",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 8
        assert all(item.get("id") for item in data)

    @pytest.mark.asyncio
    async def test_get_skill_rejects_invalid_slug(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        response = await async_client.get(
            "/api/v1/skills/../etc/passwd",
            headers=auth_headers,
        )
        assert response.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_call_intro_without_tools(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        from app.schemas import AgentCallResponse

        mock_response = AgentCallResponse(
            output="我是会议纪要助手，可以帮你整理会议要点。",
            latency_ms=42,
            agent_version="v1.0.0",
            tool_trace={"intent": "intro"},
        )
        with patch(
            "app.api.skills.skill_service.call_agent",
            new=AsyncMock(return_value=mock_response),
        ):
            response = await async_client.post(
                "/api/v1/skills/meeting-minutes/call",
                headers=auth_headers,
                json={"variables": {"input": "你能做什么？"}},
            )
        assert response.status_code == 200
        body = response.json()
        assert body.get("output")
        assert body.get("toolTrace", {}).get("intent") == "intro"


class TestSkillModulesImport:
    """技能相关模块必须能正常导入

    doc_parser 曾在模块顶层使用未定义的 ROOT，导致 import 即抛 NameError，
    凡是走文档解析的技能全部不可用，而且报错点离根因很远。
    这里做一次导入冒烟，成本极低但能挡住同类问题。
    """

    @pytest.mark.parametrize(
        "module_name",
        [
            "app.services.skill.doc_parser",
            "app.services.skill.pdf_word",
            "app.services.skill.ppt_html",
            "app.services.skill.stat_pipeline",
            "app.services.skill.capability",
            "app.services.skill.store",
            "app.services.skill_service",
        ],
    )
    def test_module_imports(self, module_name):
        import importlib

        assert importlib.import_module(module_name) is not None

    def test_repo_root_resolves(self):
        from app.core.paths import repo_root
        from app.services.skill import doc_parser

        assert doc_parser.ROOT == repo_root()
        assert doc_parser.ROOT.is_dir()
