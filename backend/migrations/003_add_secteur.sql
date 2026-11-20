-- 003_add_secteur.sql
-- Ajoute le secteur d'activité dans le payload JSONB des restaurants/tenants.
-- Valeur par défaut rétro-compatible : "restaurant".
-- Aucun changement de schéma physique : l'adaptateur PostgreSQL lit `data`.

UPDATE public.restaurants
SET data = data || '{"secteur": "restaurant"}'::jsonb
WHERE data->>'secteur' IS NULL;

CREATE INDEX IF NOT EXISTS restaurants_secteur_idx
  ON public.restaurants ((data->>'secteur'));
