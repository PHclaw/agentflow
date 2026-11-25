"""
测试知识库服务

覆盖 app/services/knowledge.py 中不依赖真实 LLM / 向量库的部分：
- cosine_similarity
- 向量存储路径
- 知识库创建
- 文档列表与统计信息
"""
from datetime import datetime

import pytest

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.knowledge import KnowledgeService, cosine_similarity


class TestCosineSimilarity:
    """余弦相似度"""

    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_does_not_divide_by_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0)


class TestVectorStorePath:
    """向量存储路径"""

    def test_path_is_namespaced_by_kb(self, monkeypatch, tmp_path):
        # 向量库必须与 API 存原始文件的目录同源，因此跟随 uploads_root()
        # （认AGENTFLOW_UPLOADS_DIR），而不是相对的 settings.UPLOAD_DIR ——
        # 后者会解析到进程工作目录（backend/）下，与 uploads/ 不是同一处
        monkeypatch.setenv("AGENTFLOW_UPLOADS_DIR", str(tmp_path))
        service = KnowledgeService(db=None, kb_id="kb-1")

        path = service._get_vector_store_path("kb-1")

        assert path == tmp_path / "vectorstore" / "kb-1"
        assert path.parent.name == "vectorstore"


class TestCreateKnowledgeBase:
    """创建知识库"""

    @pytest.mark.asyncio
    async def test_creates_row_and_directory(self, async_db, monkeypatch, tmp_path):
        monkeypatch.setenv("AGENTFLOW_UPLOADS_DIR", str(tmp_path))
        service = KnowledgeService(db=async_db)

        kb = await service.create_knowledge_base(name="产品文档", description="对外文档")

        assert kb.id
        assert kb.name == "产品文档"
        assert kb.description == "对外文档"
        assert (tmp_path / "vectorstore" / kb.id).exists()


class TestDocumentsAndStats:
    """文档列表与统计"""

    @pytest.mark.asyncio
    async def test_get_documents_orders_by_created_at_desc(self, async_db, test_knowledge_base):
        older = Document(
            kb_id=test_knowledge_base.id,
            filename="old.txt",
            file_type="txt",
            file_size=10,
            status="done",
            created_at=datetime(2024, 1, 1),
        )
        newer = Document(
            kb_id=test_knowledge_base.id,
            filename="new.txt",
            file_type="txt",
            file_size=20,
            status="done",
            created_at=datetime(2024, 6, 1),
        )
        async_db.add_all([older, newer])
        await async_db.commit()

        service = KnowledgeService(db=async_db, kb_id=test_knowledge_base.id)
        docs = await service.get_documents(test_knowledge_base.id)

        assert [d.filename for d in docs] == ["new.txt", "old.txt"]

    @pytest.mark.asyncio
    async def test_get_kb_stats_counts_documents_and_chunks(self, async_db, test_knowledge_base):
        kb_id = test_knowledge_base.id
        done_doc = Document(kb_id=kb_id, filename="a.txt", file_type="txt", file_size=100, status="done")
        failed_doc = Document(kb_id=kb_id, filename="b.txt", file_type="txt", file_size=50, status="failed")
        async_db.add_all([done_doc, failed_doc])
        await async_db.commit()

        async_db.add_all([
            DocumentChunk(document_id=done_doc.id, kb_id=kb_id, chunk_index=0, content="x"),
            DocumentChunk(document_id=done_doc.id, kb_id=kb_id, chunk_index=1, content="y"),
        ])
        await async_db.commit()

        service = KnowledgeService(db=async_db, kb_id=kb_id)
        stats = await service.get_kb_stats(kb_id)

        assert stats["document_count"] == 2
        assert stats["chunk_count"] == 2
        assert stats["total_size"] == 150
        assert stats["done_count"] == 1
        assert stats["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_get_kb_stats_on_empty_kb(self, async_db, test_knowledge_base):
        service = KnowledgeService(db=async_db, kb_id=test_knowledge_base.id)

        stats = await service.get_kb_stats("kb-that-does-not-exist")

        assert stats["document_count"] == 0
        assert stats["total_size"] == 0
