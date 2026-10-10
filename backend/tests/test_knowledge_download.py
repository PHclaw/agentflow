"""
测试知识库文档下载与上传前置校验

覆盖 app/api/knowledge.py 中：
- GET  /{kb_id}/documents/{doc_id}/download
- POST /{kb_id}/documents 的 embedding 凭证前置校验

下载链路不需要向量库，因此可直接构造 Document 行做端到端校验。
"""
from datetime import datetime, timezone
from urllib.parse import unquote

import pytest

from app.api import knowledge as knowledge_api
from app.models.document import Document


@pytest.fixture
def upload_dir(monkeypatch, tmp_path):
    """把上传目录指向临时目录，避免污染真实 backend/uploads"""
    monkeypatch.setattr(knowledge_api, "UPLOAD_DIR", tmp_path)
    return tmp_path


async def make_document(async_db, kb_id: str, stored_path: str | None, filename: str = "报告.txt") -> Document:
    doc = Document(
        kb_id=kb_id,
        filename=filename,
        file_type="txt",
        file_size=12,
        stored_path=stored_path,
        status="done",
        created_at=datetime.now(timezone.utc),
    )
    async_db.add(doc)
    await async_db.commit()
    await async_db.refresh(doc)
    return doc


class TestDownloadDocument:
    """下载原始文件"""

    @pytest.mark.asyncio
    async def test_downloads_file_content(
        self, async_client, async_db, test_knowledge_base, auth_headers, upload_dir
    ):
        stored_name = "abc123_报告.txt"
        (upload_dir / stored_name).write_bytes("知识库内容".encode("utf-8"))
        doc = await make_document(async_db, test_knowledge_base.id, stored_name)

        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/{doc.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.content.decode("utf-8") == "知识库内容"
        # 非 ASCII 文件名在响应头中为 URL 编码，需解码后再比对
        disposition = unquote(response.headers["content-disposition"])
        assert "attachment" in disposition
        assert doc.filename in disposition

    @pytest.mark.asyncio
    async def test_unknown_document_returns_404(
        self, async_client, test_knowledge_base, auth_headers, upload_dir
    ):
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/999999/download",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_document_of_other_kb_returns_404(
        self, async_client, async_db, test_knowledge_base, auth_headers, upload_dir
    ):
        stored_name = "x_file.txt"
        (upload_dir / stored_name).write_bytes(b"data")
        doc = await make_document(async_db, test_knowledge_base.id, stored_name)

        response = await async_client.get(
            f"/api/v1/knowledge/some-other-kb/documents/{doc.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_legacy_document_without_stored_path_returns_404(
        self, async_client, async_db, test_knowledge_base, auth_headers, upload_dir
    ):
        doc = await make_document(async_db, test_knowledge_base.id, None)

        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/{doc.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "未保留原始文件" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_missing_file_on_disk_returns_404(
        self, async_client, async_db, test_knowledge_base, auth_headers, upload_dir
    ):
        doc = await make_document(async_db, test_knowledge_base.id, "gone.txt")

        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/{doc.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "丢失" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_path_traversal_is_blocked(
        self, async_client, async_db, test_knowledge_base, auth_headers, upload_dir, tmp_path
    ):
        # 在 UPLOAD_DIR 之外放一个敏感文件
        secret = tmp_path.parent / "secret.txt"
        secret.write_bytes(b"top-secret")

        doc = await make_document(
            async_db, test_knowledge_base.id, f"../{secret.name}"
        )

        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/{doc.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert b"top-secret" not in response.content

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client, test_knowledge_base, upload_dir):
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/1/download"
        )

        assert response.status_code == 401


class TestUploadPrecondition:
    """上传前的凭证校验"""

    @pytest.mark.asyncio
    async def test_missing_embedding_credentials_returns_503(
        self, async_client, test_knowledge_base, auth_headers, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

        response = await async_client.post(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents",
            headers=auth_headers,
            files={"file": ("a.txt", b"hello", "text/plain")},
        )

        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]
