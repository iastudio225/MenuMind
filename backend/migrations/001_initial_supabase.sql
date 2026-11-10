-- Phase 1 PostgreSQL schema for the Mongo-to-Supabase transition.
-- Payloads remain JSONB to preserve all current API contracts during cutover.
-- IDs remain text so existing 24-character IDs, JWT subjects and references survive.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users','restaurants','plans','menu_items','menu_categories','menu_option_groups',
    'menu_options','weekly_menus','orders','carts','customers','order_status_history',
    'ai_conversations','delivery_zones','audit_logs','password_reset_tokens',
    'login_attempts','password_reset_requests','counters','pending_registrations',
    'email_verification_tokens','trial_eligibility','license_operations','license_history',
    'verification_rate_limits','license_conversion_requests'
  ] LOOP
    EXECUTE format('CREATE TABLE IF NOT EXISTS public.%I (id text PRIMARY KEY, data jsonb NOT NULL DEFAULT ''{}''::jsonb, created_at timestamptz NOT NULL DEFAULT now())', t);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON public.%I USING gin (data jsonb_path_ops)', t || '_data_gin', t);
  END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS users_email_uq ON public.users ((data->>'email'));
CREATE UNIQUE INDEX IF NOT EXISTS restaurants_public_id_uq ON public.restaurants ((data->>'public_id'));
CREATE UNIQUE INDEX IF NOT EXISTS weekly_menus_restaurant_day_uq ON public.weekly_menus ((data->>'restaurant_id'), (data->>'day'));
CREATE UNIQUE INDEX IF NOT EXISTS carts_cart_id_uq ON public.carts ((data->>'cart_id'));
CREATE UNIQUE INDEX IF NOT EXISTS ai_conversations_conversation_id_uq ON public.ai_conversations ((data->>'conversation_id'));
CREATE UNIQUE INDEX IF NOT EXISTS password_reset_tokens_hash_uq ON public.password_reset_tokens ((data->>'token_hash'));
CREATE UNIQUE INDEX IF NOT EXISTS orders_idempotency_uq ON public.orders ((data->>'restaurant_id'), (data->>'idempotency_key')) WHERE data ? 'idempotency_key' AND data->>'idempotency_key' IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS pending_registrations_email_active_uq ON public.pending_registrations ((data->>'email_normalized')) WHERE data->>'state' IN ('PENDING_VERIFICATION','VERIFIED','FINALIZING','FAILED_RETRYABLE');
CREATE UNIQUE INDEX IF NOT EXISTS trial_eligibility_email_uq ON public.trial_eligibility ((data->>'email_normalized'));
CREATE UNIQUE INDEX IF NOT EXISTS license_operations_operation_uq ON public.license_operations ((data->>'operation_id'));
CREATE UNIQUE INDEX IF NOT EXISTS verification_rate_limits_scope_key_uq ON public.verification_rate_limits ((data->>'scope'), (data->>'key_hash'));
