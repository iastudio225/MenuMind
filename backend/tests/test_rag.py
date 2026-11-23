"""RAG — chunking, configuration et extraction HTML."""
import pytest
from fastapi import HTTPException

from services import rag


def test_chunk_text_empty():
    assert rag.chunk_text("") == []
    assert rag.chunk_text("   ") == []


def test_chunk_text_respects_size_and_overlap():
    text = ("phrase courte. " * 500).strip()
    chunks = rag.chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 320 for chunk in chunks)
    # Consécutifs : un chevauchement existe entre deux chunks.
    assert chunks[0][-20:] in chunks[1] or chunks[1][:20] in chunks[0]


def test_chunk_text_prefers_paragraph_boundary():
    text = "Premier paragraphe.\n\nDeuxième paragraphe."
    chunks = rag.chunk_text(text, size=40, overlap=0)
    assert chunks[0].endswith(".")


def test_embed_texts_empty_is_noop():
    assert __import__("asyncio").run(rag.embed_texts([])) == []


def test_embed_texts_requires_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        __import__("asyncio").run(rag.embed_texts(["bonjour"]))
    assert exc.value.status_code == 503


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><head><script>x()</script></head><body><h1>Titre</h1><p>Contenu</p></body></html>"
    text = rag._html_to_text(html)
    assert "Titre" in text
    assert "Contenu" in text
    assert "x()" not in text


def test_vec_literal_format():
    assert rag._vec_literal([0.5, 1]) == "[0.50000000,1.00000000]"
