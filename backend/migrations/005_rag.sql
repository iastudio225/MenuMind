-- 005_rag.sql
-- Base de connaissances vectorielle par établissement (RAG).
-- Nécessite l'extension pgvector (Supabase : Database > Extensions > vector).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.knowledge_documents (
  id text PRIMARY KEY,
  restaurant_id text NOT NULL,
  source_id text NOT NULL,
  source_type text NOT NULL DEFAULT 'text',
  title text NOT NULL DEFAULT '',
  chunk_index integer NOT NULL DEFAULT 0,
  content text NOT NULL,
  embedding vector(768) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS knowledge_documents_restaurant_idx
  ON public.knowledge_documents (restaurant_id);

CREATE INDEX IF NOT EXISTS knowledge_documents_source_idx
  ON public.knowledge_documents (restaurant_id, source_id);

CREATE INDEX IF NOT EXISTS knowledge_documents_embedding_idx
  ON public.knowledge_documents USING hnsw (embedding vector_cosine_ops);
