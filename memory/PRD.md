# RestoIA — Réceptionniste IA 24/7 pour restaurants (SaaS B2B multi-tenant)

## Problème / Vision
SaaS B2B pour restaurants (marché Côte d'Ivoire, devise FCFA). Un agent IA prend les commandes des clients en langage naturel, consulte le vrai menu du restaurant, construit un panier, calcule le total et crée une commande exploitable. Produit multi-tenant commercialisable auprès de milliers de restaurants, chaque restaurant strictement isolé. Premier canal : widget web intégrable. Architecture prête pour WhatsApp, paiement, livraison, voix, mobile.

Positionnement : « Votre réceptionniste IA qui prend vos commandes 24h/24. »

## Stack (choisie avec l'utilisateur)
- Frontend : React 19 + Tailwind + shadcn/ui + framer-motion (craco, alias `@/` → src)
- Backend : FastAPI (Python), routes préfixées `/api`
- DB : MongoDB (motor). Isolation tenant via `restaurant_id` dérivé du JWT
- Auth : JWT custom (httpOnly cookies, bcrypt, token_version, brute force, reset email)
- IA (phases ultérieures) : Gemini

## Personas / Rôles
- SUPER_ADMIN — plateforme (voir/activer/suspendre restaurants, plans, métriques globales)
- RESTAURANT_OWNER — gère restaurant, utilisateurs, menu, commandes, abonnement
- RESTAURANT_MANAGER — commandes, menu, clients, stats (pas d'abonnement)
- RESTAURANT_STAFF — consulte commandes, modifie statut

## Architecture backend
- `server.py` — assemblage app, CORS (origine FRONTEND_URL), `/api/`, `/api/plans`, startup seed
- `auth.py` — hash/verify bcrypt, JWT access/refresh, `get_current_user`, `require_roles`, `tenant_id_of`, email reset
- `models.py` — constantes rôles, modèles Pydantic requête, `serialize()` (_id→id)
- `database.py` — client motor
- `routers/` — auth_router, restaurant_router, user_router, dashboard_router, admin_router
- `seed.py` — index Mongo, super admin, 3 plans, restaurant démo « Chez Awa » (menu + zones)

## Collections MongoDB
users, restaurants, menu_categories, menu_items, delivery_zones, orders, customers, plans, audit_logs, login_attempts, password_reset_tokens, password_reset_requests, ai_conversations (futur).

## ✅ PHASE A — FOUNDATION (TERMINÉE — 2026-06, testée 19/19 backend + frontend)
- Inscription (crée user OWNER + tenant restaurant isolé), connexion, déconnexion, /me, refresh
- Récupération de mot de passe complète (forgot/reset, enumeration parity, token sha256, token_version)
- Brute force (verrou 5 tentatives / 15 min, clé X-Forwarded-For:email)
- Rôles + permissions backend (403/400 vérifiés), isolation tenant stricte (restaurant_id du JWT)
- Onboarding restaurant (wizard 3 étapes)
- Dashboard restaurant : shell + sidebar + vue d'ensemble (stat cards)
- Gestion des utilisateurs (OWNER crée/modifie MANAGER/STAFF)
- Paramètres : restaurant, horaires, apparence widget
- Super Admin : métriques SaaS, liste restaurants, suspendre/réactiver, créer restaurant
- Landing page marketing (hero + chat IA animé, features, pricing FCFA, CTA)
- Seed : super admin (cooldigital.africa@gmail.com) + démo « Chez Awa »

## ✅ PHASE B — MENU & CATALOGUE (TERMINÉE — 2026-06, testée 32/32 : 19 régression A + 13 B)
- Collections : menu_categories, menu_items (+image_url, +option_group_ids), menu_option_groups, menu_options
- Router `routers/menu_router.py` : CRUD catégories (+reorder, suppression bloquée si articles), CRUD articles (+search/filter, availability toggle, reorder), groupes d'options + options (delete groupe = détache des articles + supprime options), catalogue public `/api/menu/public/:publicId` (expose uniquement active=true, jamais de données sensibles)
- Validations backend : prix>=0 (422), catégorie/option même tenant (400), max>=min (400), nom requis (422)
- Permissions : OWNER/MANAGER gèrent la structure ; STAFF lecture + toggle disponibilité ; SUPER_ADMIN exclu
- Index Mongo : restaurant_id (+category_id, +display_order), option_groups/options
- Seed Chez Awa enrichi : groupes « Accompagnement » (1/1 : Alloco/Attiéké/Frites) et « Suppléments » (0/5 : Fromage/Œuf/Viande)
- Frontend `pages/dashboard/MenuPage.js` : onglets Catalogue + Groupes d'options, dialogs CRUD, prix inline, toggle dispo 1-clic, reorder haut/bas, aperçu public

## ✅ PHASE C — PANIER + CLIENTS + COMMANDES + LIVRAISON (TERMINÉE — 2026-06, testée 69/69 : 19 A + 13 B + 37 C)
- Couche services réutilisable `services/order_service.py` (indépendante de l'UI, prête pour l'IA Phase D) : create/add/update/remove/clear cart, calculate_cart, validate_cart (détection prix changé via expected_unit_price), get_delivery_zones, calculate_delivery_fee, upsert_customer (normalize_phone), next_reference (counters atomiques), create_order (snapshots + idempotency + revalidation), update_order_status (TRANSITIONS), cancel_order (CANCELLABLE)
- Collections : carts, orders (items[] + options[] snapshots embarqués), customers, counters, order_status_history
- Routers : cart_router (public /api/public/cart*, /menu, /delivery-zones), order_router (public /api/public/orders + dashboard /api/orders), customer_router, delivery_router (zones CRUD)
- Serveur = source de vérité : prix/options/frais/total recalculés côté serveur, jamais de confiance au client
- Statuts contrôlés (transitions validées), annulation restreinte, OUT_FOR_DELIVERY réservé DELIVERY
- Idempotency-Key anti-double-soumission ; référence CMD-AAAA-NNNNN atomique par restaurant
- Permissions : OWNER/MANAGER complet ; STAFF liste + changement statut (pas annulation/clients/zones) ; isolation tenant vérifiée (404/listes vides)
- Frontend : StoreFront client public `/order/:publicId` (catalogue → panier → infos → livraison/retrait → récap → confirmation), dashboard Commandes (filtres, détail, actions, notification polling), Clients (historique), Livraison (zones CRUD), Overview (stats semaine)

## Backlog priorisé (à valider phase par phase par l'utilisateur)
- P0 PHASE C — Commandes : panier serveur, clients, commandes, statuts, zones de livraison, calcul total/frais
- P0 PHASE D — Agent IA (Gemini) : conversation, tools contrôlés (get_menu, calculate_order, create_order…), confirmation
- P1 PHASE E — Widget public intégrable + personnalisation
- P1 PHASE F — Abonnements SaaS : quotas/limites appliqués backend, usage IA, événements
- P2 PHASE G — Préparation canaux (WhatsApp/Instagram), paiement (Wave/OM/MoMo), livraison

## Identifiants de test
Voir `/app/memory/test_credentials.md`
- Super Admin : cooldigital.africa@gmail.com / Admin1234!
- Démo propriétaire (Chez Awa) : awa@chezawa.ci / Demo1234!

## Prochaine étape
Attendre la validation de l'utilisateur avant de démarrer la PHASE D (Agent IA — couche au-dessus des services déterministes).
