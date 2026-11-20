-- 004_menu_variants.sql
-- Matrice de variantes : une ligne par combinaison d'options d'un article.
-- variant_key = identifiants d'options triés et joints par "|".
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'menu_variants'
  ) THEN
    CREATE TABLE public.menu_variants (
      id text PRIMARY KEY,
      data jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS menu_variants_data_gin
  ON public.menu_variants USING gin (data jsonb_path_ops);

CREATE UNIQUE INDEX IF NOT EXISTS menu_variants_item_key_uq
  ON public.menu_variants ((data->>'item_id'), (data->>'variant_key'));

CREATE INDEX IF NOT EXISTS menu_variants_restaurant_idx
  ON public.menu_variants ((data->>'restaurant_id'));
