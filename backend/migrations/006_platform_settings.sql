-- 006_platform_settings.sql
-- Réglages globaux de la plateforme (ex. modèle IA par défaut).
-- Payload JSONB, comme les autres collections.
CREATE TABLE IF NOT EXISTS public.platform_settings (
  id text PRIMARY KEY,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS platform_settings_data_gin
  ON public.platform_settings USING gin (data jsonb_path_ops);
