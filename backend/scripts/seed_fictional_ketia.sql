-- Fictional demo catalogue for the development restaurant Les Délices de Kétia.
-- Safe to rerun: stable IDs and ON CONFLICT keep existing rows untouched.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.restaurants WHERE id = 'cee770c3a54a1e3483dda96d'
                 AND data->>'name' = 'Les Délices de Kétia') THEN
    RAISE EXCEPTION 'Development restaurant cee770c3a54a1e3483dda96d not found';
  END IF;
END $$;

WITH cats(id, name, description, display_order) AS (
  VALUES
    (left(md5('ketia.cat.plats'),24), 'Plats ivoiriens', 'Les recettes généreuses qui font le goût de la Côte d’Ivoire.', 1),
    (left(md5('ketia.cat.grillades'),24), 'Grillades', 'Viandes et poissons marinés, grillés à la commande.', 2),
    (left(md5('ketia.cat.accompagnements'),24), 'Accompagnements', 'Les indispensables pour composer votre assiette.', 3),
    (left(md5('ketia.cat.boissons'),24), 'Boissons', 'Boissons fraîches et jus maison.', 4),
    (left(md5('ketia.cat.desserts'),24), 'Desserts', 'Une touche douce pour terminer le repas.', 5)
)
INSERT INTO public.menu_categories(id, data)
SELECT id, jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','name',name,'description',description,
  'display_order',display_order,'active',true,'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM cats ON CONFLICT (id) DO NOTHING;

WITH groups(id, name, description, required, min_selections, max_selections, display_order) AS (
  VALUES
    (left(md5('ketia.group.accompagnement'),24), 'Accompagnement', 'Choisissez un accompagnement avec votre plat.', true, 1, 1, 1),
    (left(md5('ketia.group.sauce'),24), 'Sauces maison', 'Ajoutez une sauce douce ou relevée.', false, 0, 2, 2)
)
INSERT INTO public.menu_option_groups(id, data)
SELECT id, jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','name',name,'description',description,
  'required',required,'min_selections',min_selections,'max_selections',max_selections,
  'display_order',display_order,'active',true,'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM groups ON CONFLICT (id) DO NOTHING;

WITH opts(id, group_id, name, description, price_delta, display_order) AS (
  VALUES
    (left(md5('ketia.opt.attieke'),24), left(md5('ketia.group.accompagnement'),24), 'Attiéké', 'Semoule de manioc légère et légèrement acidulée.', 0, 1),
    (left(md5('ketia.opt.alloco'),24), left(md5('ketia.group.accompagnement'),24), 'Alloco', 'Bananes plantain mûres, dorées et fondantes.', 500, 2),
    (left(md5('ketia.opt.riz'),24), left(md5('ketia.group.accompagnement'),24), 'Riz parfumé', 'Riz tendre cuisiné aux épices maison.', 0, 3),
    (left(md5('ketia.opt.frites'),24), left(md5('ketia.group.accompagnement'),24), 'Frites maison', 'Pommes de terre dorées et croustillantes.', 500, 4),
    (left(md5('ketia.opt.moyo'),24), left(md5('ketia.group.sauce'),24), 'Sauce moyo', 'Tomates, oignons frais et citron vert.', 0, 1),
    (left(md5('ketia.opt.piment'),24), left(md5('ketia.group.sauce'),24), 'Piment maison', 'Piment frais, servi à part.', 0, 2),
    (left(md5('ketia.opt.graine'),24), left(md5('ketia.group.sauce'),24), 'Sauce graine', 'Sauce onctueuse aux graines de palme.', 500, 3)
)
INSERT INTO public.menu_options(id, data)
SELECT id, jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','group_id',group_id,'name',name,'description',description,
  'price_delta',price_delta,'active',true,'available',true,'display_order',display_order,
  'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM opts ON CONFLICT (id) DO NOTHING;

WITH products(id, category_id, name, description, image_url, price, display_order, group_ids) AS (
  VALUES
    (left(md5('ketia.item.poulet-braise'),24), left(md5('ketia.cat.grillades'),24), 'Poulet braisé', 'Poulet mariné aux épices maison, grillé lentement et servi avec votre accompagnement au choix.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 5500, 1, ARRAY[left(md5('ketia.group.accompagnement'),24),left(md5('ketia.group.sauce'),24)]::text[]),
    (left(md5('ketia.item.demi-poulet'),24), left(md5('ketia.cat.grillades'),24), 'Demi-poulet braisé', 'Une généreuse demi-portion, marinée aux herbes et grillée à la braise.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 3500, 2, ARRAY[left(md5('ketia.group.accompagnement'),24),left(md5('ketia.group.sauce'),24)]::text[]),
    (left(md5('ketia.item.poisson-braise'),24), left(md5('ketia.cat.grillades'),24), 'Poisson braisé du jour', 'Poisson frais braisé, relevé juste comme il faut, avec sauce moyo et accompagnement.', 'https://images.unsplash.com/photo-1556814901-18c866c057da?auto=format&fit=crop&w=900&q=80', 7000, 3, ARRAY[left(md5('ketia.group.accompagnement'),24),left(md5('ketia.group.sauce'),24)]::text[]),
    (left(md5('ketia.item.tilapia'),24), left(md5('ketia.cat.grillades'),24), 'Tilapia braisé', 'Tilapia assaisonné, grillé à la braise et servi avec citron et sauce maison.', 'https://images.unsplash.com/photo-1577193459085-2da60ca7fd77?auto=format&fit=crop&w=900&q=80', 6500, 4, ARRAY[left(md5('ketia.group.accompagnement'),24),left(md5('ketia.group.sauce'),24)]::text[]),
    (left(md5('ketia.item.kedjenou'),24), left(md5('ketia.cat.plats'),24), 'Kédjénou de poulet', 'Poulet mijoté à l’étouffée avec tomates, oignons et aromates ivoiriens.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 5000, 1, ARRAY[left(md5('ketia.group.accompagnement'),24),left(md5('ketia.group.sauce'),24)]::text[]),
    (left(md5('ketia.item.sauce-graine'),24), left(md5('ketia.cat.plats'),24), 'Sauce graine', 'Sauce graine parfumée, mijotée avec viande tendre et épices du jour.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 5000, 2, ARRAY[left(md5('ketia.group.accompagnement'),24)]::text[]),
    (left(md5('ketia.item.jollof'),24), left(md5('ketia.cat.plats'),24), 'Riz jollof maison', 'Riz cuisiné dans une sauce tomate épicée, accompagné de légumes frais.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 3000, 3, ARRAY[]::text[]),
    (left(md5('ketia.item.alloco-oeuf'),24), left(md5('ketia.cat.plats'),24), 'Alloco & œuf', 'Alloco doré servi avec œuf et une petite salade fraîche.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 2500, 4, ARRAY[]::text[]),
    (left(md5('ketia.item.attieke-portion'),24), left(md5('ketia.cat.accompagnements'),24), 'Portion d’attiéké', 'Attiéké vapeur, léger et prêt à accompagner vos grillades.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 1000, 1, ARRAY[]::text[]),
    (left(md5('ketia.item.alloco-portion'),24), left(md5('ketia.cat.accompagnements'),24), 'Portion d’alloco', 'Bananes plantain mûres, frites à la minute.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 1500, 2, ARRAY[]::text[]),
    (left(md5('ketia.item.riz-portion'),24), left(md5('ketia.cat.accompagnements'),24), 'Riz parfumé', 'Riz tendre, délicatement parfumé aux épices.', 'https://images.unsplash.com/photo-1665334217407-6688e6941a47?auto=format&fit=crop&w=900&q=80', 1000, 3, ARRAY[]::text[]),
    (left(md5('ketia.item.bissap'),24), left(md5('ketia.cat.boissons'),24), 'Jus de bissap', 'Infusion d’hibiscus fraîche, légèrement sucrée et servie bien glacée.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 1000, 1, ARRAY[]::text[]),
    (left(md5('ketia.item.gingembre'),24), left(md5('ketia.cat.boissons'),24), 'Jus de gingembre', 'Gingembre frais pressé, citronné et délicatement sucré.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 1000, 2, ARRAY[]::text[]),
    (left(md5('ketia.item.eau'),24), left(md5('ketia.cat.boissons'),24), 'Eau minérale', 'Bouteille d’eau fraîche 50 cl.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 500, 3, ARRAY[]::text[]),
    (left(md5('ketia.item.soda'),24), left(md5('ketia.cat.boissons'),24), 'Soda', 'Boisson gazeuse fraîche, 33 cl.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 800, 4, ARRAY[]::text[]),
    (left(md5('ketia.item.degue'),24), left(md5('ketia.cat.desserts'),24), 'Dégué maison', 'Crème de mil onctueuse au lait et à la vanille, servie fraîche.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 1500, 1, ARRAY[]::text[]),
    (left(md5('ketia.item.salade-fruits'),24), left(md5('ketia.cat.desserts'),24), 'Salade de fruits', 'Fruits frais de saison découpés chaque jour.', 'https://images.unsplash.com/photo-1599390719613-912787a6e65a?auto=format&fit=crop&w=900&q=80', 1500, 2, ARRAY[]::text[])
)
INSERT INTO public.menu_items(id, data)
SELECT id, jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','category_id',category_id,'name',name,'description',description,
  'image_url',image_url,'price',price,'active',true,'available',true,'display_order',display_order,
  'option_group_ids',to_jsonb(group_ids),'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM products ON CONFLICT (id) DO NOTHING;

UPDATE public.menu_items
SET data = jsonb_set(data, '{image_url}', to_jsonb('https://images.unsplash.com/photo-1691382075965-3bc7a6db6e3a?auto=format&fit=crop&w=900&q=80'::text), true)
WHERE id IN (left(md5('ketia.item.eau'),24), left(md5('ketia.item.soda'),24));

UPDATE public.menu_items
SET data = jsonb_set(data, '{image_url}', to_jsonb('https://images.unsplash.com/photo-1774041877283-a3aaad1f2ad2?auto=format&fit=crop&w=900&q=80'::text), true)
WHERE id IN (left(md5('ketia.item.degue'),24), left(md5('ketia.item.salade-fruits'),24));

WITH zones(name, description, fee) AS (
  VALUES ('Koumassi','Livraison dans Koumassi et quartiers voisins.',500),
         ('Marcory','Livraison à Marcory.',1000),
         ('Treichville','Livraison à Treichville.',1000),
         ('Zone 4','Livraison en Zone 4.',1500),
         ('Plateau','Livraison au Plateau.',1500),
         ('Cocody','Livraison à Cocody et Angré.',2000)
)
INSERT INTO public.delivery_zones(id, data)
SELECT left(md5('ketia.zone.' || name),24), jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','name',name,'description',description,'fee',fee,
  'active',true,'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM zones ON CONFLICT (id) DO NOTHING;

WITH day_menus(day, item_keys) AS (
  VALUES
    ('monday', ARRAY['ketia.item.kedjenou','ketia.item.poulet-braise']::text[]),
    ('tuesday', ARRAY['ketia.item.sauce-graine','ketia.item.poisson-braise']::text[]),
    ('wednesday', ARRAY['ketia.item.jollof','ketia.item.demi-poulet']::text[]),
    ('thursday', ARRAY['ketia.item.kedjenou','ketia.item.tilapia']::text[]),
    ('friday', ARRAY['ketia.item.poisson-braise','ketia.item.alloco-oeuf']::text[]),
    ('saturday', ARRAY['ketia.item.poulet-braise','ketia.item.jollof']::text[]),
    ('sunday', ARRAY['ketia.item.sauce-graine','ketia.item.demi-poulet']::text[])
)
INSERT INTO public.weekly_menus(id, data)
SELECT left(md5('ketia.week.' || day),24), jsonb_build_object(
  'restaurant_id','cee770c3a54a1e3483dda96d','day',day,'active',true,
  'item_ids',(SELECT jsonb_agg(left(md5(key),24)) FROM unnest(item_keys) key),
  'created_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
  'updated_at',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
FROM day_menus ON CONFLICT (id) DO NOTHING;

UPDATE public.restaurants
SET data = jsonb_set(data, '{widget,welcome_message}', to_jsonb('Bonjour 👋 Bienvenue chez Les Délices de Kétia ! Grillades, plats ivoiriens et jus maison vous attendent. Que souhaitez-vous commander ?'::text), true)
WHERE id = 'cee770c3a54a1e3483dda96d';

COMMIT;
