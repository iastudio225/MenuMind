-- Keep tenant-filtered dashboard aggregates scoped to that restaurant's rows.
CREATE INDEX IF NOT EXISTS orders_restaurant_created_idx
  ON public.orders ((data->>'restaurant_id'), (data->>'created_at'));
CREATE INDEX IF NOT EXISTS menu_items_restaurant_idx
  ON public.menu_items ((data->>'restaurant_id'));
CREATE INDEX IF NOT EXISTS customers_restaurant_idx
  ON public.customers ((data->>'restaurant_id'));
CREATE INDEX IF NOT EXISTS users_restaurant_idx
  ON public.users ((data->>'restaurant_id'));
