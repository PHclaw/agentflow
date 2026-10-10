"""
测试 knowledge API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import KnowledgeBase


class TestKnowledgeAPI:
    """Knowledge API 测试"""
    
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试空列表"""
        response = await async_client.get(
            "/api/v1/knowledge",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "knowledge_bases" in data
        assert isinstance(data["knowledge_bases"], list)
    
    @pytest.mark.asyncio
    async def test_empty_knowledge_base_is_not_marked_indexing(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """空知识库不应永远停留在「索引中」状态"""
        response = await async_client.get("/api/v1/knowledge", headers=auth_headers)

        assert response.status_code == 200
        kb = next(
            item
            for item in response.json()["knowledge_bases"]
            if item["id"] == test_knowledge_base.id
        )
        assert kb["document_count"] == 0
        assert kb["status"] == "empty"

    @pytest.mark.asyncio
    async def test_create_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试创建知识库"""
        response = await async_client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={
                "name": "Test KB",
                "description": "A test knowledge base",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test KB"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """测试获取知识库"""
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_knowledge_base.id
        assert data["name"] == test_knowledge_base.name
    
    @pytest.mark.asyncio
    async def test_delete_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """测试删除知识库"""
        response = await async_client.delete(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # 验证已删除
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_search_knowledge(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试知识库搜索"""
        response = await async_client.post(
            "/api/v1/knowledge/search",
            headers=auth_headers,
            json={
                "query": "test query",
                "top_k": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
    
    @pytest.mark.asyncio
    async def test_knowledge_base_is_scoped_to_owner(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """别人的知识库既看不到也删不掉"""
        # 另造一个账号，用它的令牌访问
        other = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "kb-other@test.com", "password": "Other@12345"},
        )
        assert other.status_code in (200, 201), other.text
        other_headers = {"Authorization": f"Bearer {other.json()['token']}"}

        listing = await async_client.get("/api/v1/knowledge", headers=other_headers)
        assert all(
            item["id"] != test_knowledge_base.id for item in listing.json()["knowledge_bases"]
        )

        detail = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}", headers=other_headers
        )
        assert detail.status_code == 404

        removal = await async_client.delete(
            f"/api/v1/knowledge/{test_knowledge_base.id}", headers=other_headers
        )
        assert removal.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_without_embedding_credentials_explains_why(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
        monkeypatch,
    ):
        """没配向量凭证时要给出可操作提示，而不是无信息的 500"""
        from app.services import knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod.settings, "OPENAI_API_KEY", "", raising=False)
        monkeypatch.setattr(knowledge_mod.settings, "MODEL_BASE_URL", "", raising=False)

        def no_credentials(self):
            raise knowledge_mod.EmbeddingNotConfiguredError("知识库需要向量模型凭证：请在「设置 → 模型配置」中填写 API Key")

        monkeypatch.setattr(
            knowledge_mod.KnowledgeService, "_get_embeddings", no_credentials
        )

        response = await async_client.post(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents",
            headers=auth_headers,
            files={"file": ("a.txt", b"hello", "text/plain")},
        )

        assert response.status_code == 503
        assert "模型配置" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_search_keeps_relevance_order(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """检索分数是「相关性」，不能再取 1-score 把排名反转

        此前会把最相关的结果算成 0.05，永远过不了阈值。
        """
        from app.services import knowledge as knowledge_mod

        class FakeStore:
            def similarity_search_with_relevance_scores(self, query, k, filter=None):
                from langchain_core.documents import Document as LCDoc

                return [
                    (LCDoc(page_content="最相关", metadata={"source": "a.md"}), 0.95),
                    (LCDoc(page_content="一般", metadata={"source": "a.md"}), 0.72),
                    (LCDoc(page_content="不相关", metadata={"source": "a.md"}), 0.31),
                ]

        service = knowledge_mod.KnowledgeService(None, "kb-x")

        async def fake_store(kb_id):
            return FakeStore()

        service._get_or_create_vector_store = fake_store

        results = await service.search("问题", ["kb-x"], top_k=5, threshold=0.5)

        assert [r["content"] for r in results] == ["最相关", "一般"]
        assert results[0]["score"] == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_unauthorized_access(
        self,
        async_client: AsyncClient,
    ):
        """测试未授权访问"""
        response = await async_client.get("/api/v1/knowledge")
        assert response.status_code == 401
