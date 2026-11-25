-- Public link attribution events (visits) — see
-- services/attribution.py and routers/public_events_router.py.
-- Payload is JSONB like every other entity table; ids stay text.
CREATE TABLE IF NOT EXISTS public.public_events (
    id text PRIMARY KEY,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS public_events_gin
    ON public.public_events USING gin (data jsonb_path_ops);

CREATE INDEX IF NOT EXISTS public_events_resto_date
    ON public.public_events ((data->>'restaurant_id'), created_at DESC);

-- One visit per restaurant and browser session; the endpoint also checks
-- before inserting, this index is the race-proof backstop.
CREATE UNIQUE INDEX IF NOT EXISTS public_events_visit_uq
    ON public.public_events ((data->>'restaurant_id'), (data->>'session_id'))
    WHERE data->>'kind' = 'visit';
