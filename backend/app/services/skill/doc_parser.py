"""调用 demo-1.1-SNAPSHOT.jar（torchv-document-api）做文档→Markdown / 抽图。"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.logging_setup import get_logger

logger = get_logger("docparse")

from app.core.paths import generated_root

GENERATED_DIR = generated_root()
DEFAULT_JAR = ROOT / "demo-1.1-SNAPSHOT.jar"

PARSEABLE_SUFFIX = {
    ".doc",
    ".docx",
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".html",
    ".htm",
    ".rtf",
    ".odt",
}

_PROC: subprocess.Popen | None = None
_LOCK = threading.Lock()


def _base_url() -> str:
    settings = get_settings()
    return (getattr(settings, "document_parse_url", None) or "http://127.0.0.1:15003").rstrip("/")


def _jar_path() -> Path:
    settings = get_settings()
    raw = getattr(settings, "document_parse_jar", None) or str(DEFAULT_JAR)
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p)


def parser_alive() -> bool:
    try:
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            resp = client.get(_base_url() + "/v3/api-docs")
        return resp.status_code < 500
    except Exception:  # noqa: BLE001
        return False


def ensure_parser(*, timeout_sec: float = 90.0) -> None:
    """本地未启动时拉起 Spring Boot JAR（local 配置，免 MySQL）。"""
    settings = get_settings()
    if not getattr(settings, "document_parse_autostart", True):
        if not parser_alive():
            raise RuntimeError(
                f"文档解析服务未启动：{_base_url()} 。请先运行 "
                f"java -Dspring.profiles.active=local -jar {_jar_path().name}"
            )
        return
    if parser_alive():
        return
    with _LOCK:
        if parser_alive():
            return
        global _PROC
        jar = _jar_path()
        if not jar.is_file():
            raise RuntimeError(f"未找到文档解析 JAR：{jar}")
        java = os.environ.get("JAVA_HOME")
        java_bin = str(Path(java) / "bin" / "java.exe") if java else "java"
        if java and not Path(java_bin).is_file():
            java_bin = "java"
        log_path = ROOT / "logs" / "doc-parser.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fp = log_path.open("a", encoding="utf-8")
        parsed = urlparse(_base_url())
        port = parsed.port or 15003
        cmd = [
            java_bin,
            f"-Dspring.profiles.active=local",
            f"-Dserver.port={port}",
            f"-Ddocument.images.public-base-url={_base_url()}",
            "-jar",
            str(jar),
        ]
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        logger.info("start doc parser cmd=%s", " ".join(cmd))
        _PROC = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(ROOT),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if parser_alive():
                logger.info("doc parser ready url=%s pid=%s", _base_url(), _PROC.pid)
                return
            if _PROC.poll() is not None:
                raise RuntimeError(
                    f"文档解析 JAR 启动失败（exit={_PROC.returncode}），见 logs/doc-parser.log"
                )
            time.sleep(1.2)
        raise RuntimeError(f"文档解析服务启动超时（{timeout_sec:.0f}s）：{_base_url()}")


def _public_url(filename: str) -> str:
    return f"/static/generated/{filename}"


def _save_markdown_and_images(
    *,
    source_name: str,
    markdown: str,
    images: list[dict[str, Any]],
) -> tuple[str, str, list[str], str]:
    """把 Markdown 与抽到的图落到 /static/generated，并改写占位符。"""
    import re
    import uuid

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(source_name).stem or "doc"
    uid = uuid.uuid4().hex[:10]
    local_urls: list[str] = []
    md = markdown or ""

    with httpx.Client(timeout=30.0, trust_env=False) as client:
        for i, img in enumerate(images or [], 1):
            remote = str(img.get("url") or "").strip()
            if not remote:
                continue
            ext = Path(urlparse(remote).path).suffix.lower() or ".jpg"
            if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
                ext = ".jpg"
            fname = f"{stem}-img{i}-{uid}{ext}"
            out = GENERATED_DIR / fname
            try:
                resp = client.get(remote)
                resp.raise_for_status()
                out.write_bytes(resp.content)
            except Exception as exc:  # noqa: BLE001
                logger.warning("copy parse image fail url=%s err=%s", remote, exc)
                local_urls.append(remote)
                continue
            local = _public_url(fname)
            local_urls.append(local)
            md = md.replace(remote, local)
            md = re.sub(
                rf"-\{{=image-{i}=\}}-",
                f"![]({local})",
                md,
            )

    md_name = f"{stem}-parsed-{uid}.md"
    md_path = GENERATED_DIR / md_name
    md_path.write_text(md, encoding="utf-8")
    return _public_url(md_name), md_name, local_urls, md


def convert_document(path: Path, *, source_name: str | None = None) -> dict[str, Any]:
    ensure_parser()
    src_name = source_name or path.name
    url = _base_url() + "/api/v1/documents/markdown"
    with path.open("rb") as fp:
        files = {"file": (src_name, fp, "application/octet-stream")}
        with httpx.Client(timeout=120.0, trust_env=False) as client:
            resp = client.post(url, files=files, data={"renderMode": "STANDARD"})
    if resp.status_code >= 400:
        raise RuntimeError(f"文档解析 HTTP {resp.status_code}: {resp.text[:800]}")
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"文档解析失败: {payload}")
    data = payload.get("data") or {}
    markdown = str(data.get("markdown") or "")
    images = list(data.get("images") or [])
    md_url, md_name, image_urls, md_body = _save_markdown_and_images(
        source_name=src_name,
        markdown=markdown,
        images=images,
    )
    return {
        "markdown": md_body,
        "markdownUrl": md_url,
        "markdownName": md_name,
        "imageUrls": image_urls,
        "imageCount": len(image_urls),
        "parseDurationMs": data.get("parseDurationMs"),
        "originalFilename": data.get("originalFilename") or src_name,
    }


def parse_uploaded(files: list[dict], *, intent: str = "parse") -> dict[str, Any]:
    if not files:
        return {
            "intent": intent,
            "exitCode": 1,
            "note": "未找到可解析的文档（支持 pdf / word / excel / ppt 等）。",
            "stdout": "",
            "stderr": "",
        }
    src = files[0]
    path = Path(str(src.get("path") or ""))
    if not path.is_file():
        return {
            "intent": intent,
            "exitCode": 1,
            "note": f"文件不存在: {src.get('name')}",
            "stdout": "",
            "stderr": "",
        }
    try:
        result = convert_document(path, source_name=str(src.get("name") or path.name))
    except Exception as exc:  # noqa: BLE001
        logger.error("doc parse fail: %s", exc)
        return {
            "intent": intent,
            "script": "torchv-document-api",
            "exitCode": 1,
            "stdout": "",
            "stderr": str(exc),
            "note": f"文档解析失败: {exc}",
        }

    md_preview = (result["markdown"] or "")[:6000]
    lines = [
        f"source={result['originalFilename']}",
        f"imageCount={result['imageCount']}",
        f"downloadUrl={result['markdownUrl']}",
        f"downloadName={result['markdownName']}",
    ]
    if result["imageUrls"]:
        lines.append("images:")
        lines.extend(f"  - {u}" for u in result["imageUrls"][:40])
    lines.append("markdownPreview:")
    lines.append(md_preview)
    note = (
        f"已解析为 Markdown，并提取 {result['imageCount']} 张图像"
        if result["imageCount"]
        else "已解析为 Markdown（文档中未抽出图像）"
    )
    return {
        "intent": intent,
        "script": "torchv-document-api",
        "exitCode": 0,
        "stdout": "\n".join(lines),
        "stderr": "",
        "note": note,
        "downloadUrl": result["markdownUrl"],
        "downloadName": result["markdownName"],
        "downloadUrls": result["imageUrls"],
        "imageCount": result["imageCount"],
        "markdownChars": len(result["markdown"] or ""),
        "markdown": result["markdown"] or "",
    }


def parseable_uploads(uploaded: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for f in uploaded or []:
        name = str(f.get("name") or "")
        path = str(f.get("path") or "")
        if Path(name).suffix.lower() in PARSEABLE_SUFFIX and path and Path(path).is_file():
            out.append(f)
    return out


def parse_uploads_for_llm(uploaded: list[dict] | None) -> tuple[str, dict | None]:
    """解析全部上传文档，返回给 LLM 的上下文 + 工具轨迹。"""
    files = parseable_uploads(uploaded)
    if not files:
        return "", None
    sections: list[str] = []
    image_urls: list[str] = []
    md_urls: list[str] = []
    errors: list[str] = []
    last_ok: dict[str, Any] | None = None
    for f in files:
        tr = parse_uploaded([f], intent="parse")
        name = str(f.get("name") or "file")
        if int(tr.get("exitCode", 1)) != 0:
            errors.append(f"{name}: {tr.get('note') or tr.get('stderr') or '解析失败'}")
            continue
        last_ok = tr
        body = str(tr.get("markdown") or "")[:80_000]
        sections.append(f"### 文件：{name}\n\n{body or '（解析结果为空）'}")
        if tr.get("downloadUrl"):
            md_urls.append(str(tr["downloadUrl"]))
        image_urls.extend(str(u) for u in (tr.get("downloadUrls") or []))

    if not sections and errors:
        return (
            "平台尝试解析上传文件但失败：\n" + "\n".join(errors),
            {
                "intent": "parse",
                "script": "torchv-document-api",
                "exitCode": 1,
                "note": "；".join(errors),
                "stdout": "",
                "stderr": "\n".join(errors),
            },
        )

    parts = [
        "以下内容已由平台从用户上传的文件解析得到，是你回答的依据。",
        "必须基于这些内容回答。禁止说无法读取、看不到文件、请粘贴或请再上传。",
        "",
        "## 平台已解析的文档",
        "\n\n".join(sections),
    ]
    if md_urls:
        parts.append("\n## Markdown 下载")
        parts.extend(f"- {u}" for u in md_urls)
    if image_urls:
        parts.append("\n## 提取的图像")
        parts.extend(f"- {u}" for u in image_urls[:40])
    if errors:
        parts.append("\n## 部分文件解析失败")
        parts.extend(f"- {e}" for e in errors)

    trace = {
        "intent": "parse",
        "script": "torchv-document-api",
        "exitCode": 0 if last_ok else 1,
        "note": (last_ok or {}).get("note") or "已解析上传文档",
        "stdout": "\n".join(sections)[:8000],
        "stderr": "\n".join(errors),
        "downloadUrl": md_urls[0] if md_urls else None,
        "downloadName": (last_ok or {}).get("downloadName"),
        "downloadUrls": image_urls,
        "imageCount": len(image_urls),
    }
    return "\n".join(parts), trace
