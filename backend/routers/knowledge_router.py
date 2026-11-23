"""Tenant knowledge base endpoints (RAG ingestion & management)."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from database import db
from auth import require_roles, tenant_id_of
from models import RESTAURANT_OWNER, RESTAURANT_MANAGER
from services import rag

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)


class TextDocument(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source_type: Optional[str] = "text"


class UrlDocument(BaseModel):
    url: str = Field(min_length=8)
    title: Optional[str] = None


@router.get("/documents")
async def list_documents(user: dict = Depends(MANAGE)):
    return await rag.list_sources(db, tenant_id_of(user))


@router.post("/documents")
async def add_text_document(body: TextDocument, user: dict = Depends(MANAGE)):
    return await rag.ingest_text(db, tenant_id_of(user), body.title, body.content,
                                 source_type=body.source_type or "text")


@router.post("/documents/url")
async def add_url_document(body: UrlDocument, user: dict = Depends(MANAGE)):
    return await rag.ingest_url(db, tenant_id_of(user), body.url, body.title)


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), title: str = Form(""),
                          user: dict = Depends(MANAGE)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    filename = file.filename or "Document"
    if filename.lower().endswith(".pdf"):
        return await rag.ingest_pdf(db, tenant_id_of(user), title or filename, data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Encodage non supporté (UTF-8 attendu).")
    return await rag.ingest_text(db, tenant_id_of(user), title or filename, text,
                                 source_type="upload")


@router.delete("/documents/{source_id}")
async def delete_document(source_id: str, user: dict = Depends(MANAGE)):
    deleted = await rag.delete_source(db, tenant_id_of(user), source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return {"message": "Document supprimé", "chunks": deleted}
