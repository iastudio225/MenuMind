"""Per-tenant vector knowledge base (RAG).

Storage: Supabase PostgreSQL + pgvector (`knowledge_documents`).
Embeddings: Gemini `gemini-embedding-001` (768 dimensions) through the same
loop-aware Google GenAI client as the text provider.
"""
import asyncio
import io
import json
import os
import re
import secrets
from typing import List, Optional

import httpx
from fastapi import HTTPException
from google.genai import types

EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.environ.get("RAG_EMBEDDING_DIM", "768") or 768)
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "1200") or 1200)
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "150") or 150)
MAX_SOURCE_CHARS = int(os.environ.get("RAG_MAX_SOURCE_CHARS", "200000") or 200000)
MAX_CHUNKS_PER_SOURCE = int(os.environ.get("RAG_MAX_CHUNKS_PER_SOURCE", "200") or 200)
EMBED_BATCH = 50
EMBED_TIMEOUT_S = 60


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks, preferring paragraph/sentence cuts."""
    text = (text or "").strip()
    if not text:
        return []
    size = max(200, int(size or 1200))
    overlap = max(0, min(int(overlap or 0), size // 2))
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                cut = text.rfind(sep, start + size // 2, end)
                if cut > start:
                    end = cut + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks[:MAX_CHUNKS_PER_SOURCE]


def _vec_literal(values) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


async def embed_texts(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """Embed texts in bounded batches; raises 503 when no Gemini key is configured."""
    if not texts:
        return []
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="RAG non configuré : GEMINI_API_KEY manquant.")

    from services.ai.gemini_provider import _get_client

    client = _get_client(api_key)
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM)
    values: List[List[float]] = []
    for offset in range(0, len(texts), EMBED_BATCH):
        batch = texts[offset:offset + EMBED_BATCH]
        try:
            response = await asyncio.wait_for(
                client.aio.models.embed_content(model=EMBEDDING_MODEL, contents=batch, config=config),
                timeout=EMBED_TIMEOUT_S,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Échec de l'embedding : {exc}") from exc
        embeddings = getattr(response, "embeddings", None) or []
        batch_values = [list(e.values) for e in embeddings if getattr(e, "values", None)]
        if len(batch_values) != len(batch):
            raise HTTPException(status_code=502, detail="Réponse d'embedding incomplète.")
        values.extend(batch_values)
    return values


async def ingest_text(db, restaurant_id: str, title: str, content: str,
                      source_type: str = "text", metadata: Optional[dict] = None) -> dict:
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Document vide.")
    if len(text) > MAX_SOURCE_CHARS:
        raise HTTPException(status_code=400, detail=f"Document trop volumineux (max {MAX_SOURCE_CHARS} caractères).")
    if db.pool is None:
        raise HTTPException(status_code=503, detail="Base de données non disponible.")

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Aucun contenu exploitable.")
    embeddings = await embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")

    source_id = secrets.token_hex(12)
    meta = json.dumps(metadata or {}, ensure_ascii=False)
    rows = [
        (secrets.token_hex(12), restaurant_id, source_id, source_type,
         (title or "Document").strip(), index, chunk, _vec_literal(embedding), meta)
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.executemany(
                """INSERT INTO public.knowledge_documents
                   (id, restaurant_id, source_id, source_type, title, chunk_index, content, embedding, metadata)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8::vector,$9::jsonb)""",
                rows,
            )
    return {"source_id": source_id, "title": title or "Document", "source_type": source_type,
            "chunks": len(rows)}


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


async def ingest_url(db, restaurant_id: str, url: str, title: Optional[str] = None) -> dict:
    if not str(url or "").startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL invalide (http/https attendu).")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Impossible de récupérer l'URL : {exc}") from exc

    content_type = (response.headers.get("content-type") or "").lower()
    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        return await ingest_pdf(db, restaurant_id, title or url, response.content)
    text = _html_to_text(response.text) if "html" in content_type else response.text
    return await ingest_text(db, restaurant_id, title or url, text,
                             source_type="url", metadata={"url": url})


async def ingest_pdf(db, restaurant_id: str, title: str, data: bytes) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(status_code=400, detail="Lecture PDF indisponible (pypdf non installé).")
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF illisible : {exc}") from exc
    text = "\n\n".join(page for page in pages if page.strip())
    if not text.strip():
        raise HTTPException(status_code=400, detail="Aucun texte extractible du PDF.")
    return await ingest_text(db, restaurant_id, title, text, source_type="pdf")


async def search_knowledge(db, restaurant_id: str, query: str, limit: int = 5) -> List[dict]:
    """Vector search restricted to the tenant; returns the closest chunks."""
    q = (query or "").strip()
    if not q:
        return []
    if db.pool is None:
        raise HTTPException(status_code=503, detail="Base de données non disponible.")
    embeddings = await embed_texts([q], task_type="RETRIEVAL_QUERY")
    vector = _vec_literal(embeddings[0])
    rows = await db.pool.fetch(
        """SELECT source_id, title, source_type, chunk_index, content, metadata,
                  1 - (embedding <=> $1::vector) AS score
           FROM public.knowledge_documents
           WHERE restaurant_id = $2
           ORDER BY embedding <=> $1::vector
           LIMIT $3""",
        vector, restaurant_id, max(1, min(int(limit or 5), 10)),
    )
    return [{
        "source_id": row["source_id"], "title": row["title"],
        "source_type": row["source_type"], "chunk_index": row["chunk_index"],
        "content": row["content"], "score": float(row["score"]),
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
    } for row in rows]


async def list_sources(db, restaurant_id: str) -> List[dict]:
    if db.pool is None:
        raise HTTPException(status_code=503, detail="Base de données non disponible.")
    rows = await db.pool.fetch(
        """SELECT source_id, source_type, title, count(*) AS chunks, min(created_at) AS created_at
           FROM public.knowledge_documents
           WHERE restaurant_id = $1
           GROUP BY source_id, source_type, title
           ORDER BY min(created_at) DESC""",
        restaurant_id,
    )
    return [{
        "source_id": row["source_id"], "source_type": row["source_type"],
        "title": row["title"], "chunks": row["chunks"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    } for row in rows]


async def delete_source(db, restaurant_id: str, source_id: str) -> int:
    if db.pool is None:
        raise HTTPException(status_code=503, detail="Base de données non disponible.")
    result = await db.pool.execute(
        "DELETE FROM public.knowledge_documents WHERE restaurant_id = $1 AND source_id = $2",
        restaurant_id, source_id,
    )
    return int(result.rsplit(" ", 1)[-1])
