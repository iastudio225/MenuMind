# MenuMind — dossier de reprise pour LLM

> Document de passation établi le 5 novembre 2026 à partir du dépôt. En cas de contradiction, le code actuellement présent et les tests sont la source de vérité ; les documents PRD/plan décrivent parfois un état antérieur.

## 1. Résumé du produit

MenuMind est un SaaS B2B multi-tenant de prise de commandes pour restaurants, ciblant d’abord la Côte d’Ivoire (FCFA, français). Chaque restaurant gère son profil, son catalogue, ses commandes, ses clients, ses zones de livraison et son assistant IA. Les clients finaux commandent sans compte, par catalogue/panier visuel ou conversation avec l’assistant. Le restaurant reçoit une commande persistée qu’il traite depuis son tableau de bord.

Valeur produit : réceptionniste IA disponible en continu, qui s’appuie sur le menu réellement configuré, collecte les informations nécessaires, calcule les montants côté serveur et ne soumet la commande qu’après confirmation explicite. Le widget web est un canal déjà présent. WhatsApp, paiement en ligne, voix et suivi temps réel sont des extensions futures, pas des capacités à supposer déjà livrées.

## 2. État constaté et écarts documentaires

Le dépôt contient aujourd’hui les briques A/B/C et une implémentation IA plus avancée que le plan initial : agent conversationnel public, console IA authentifiée, widget flottant dans la page de commande, widget web embarquable, menus hebdomadaires, outils de menu du jour/cartes produit, quotas et rétention. Le panier visuel et l’agent sont maintenant reliés via `cart_id` (travaux D1.50+), malgré l’ancien avertissement dans AGENTS.md disant qu’ils ne sont pas liés.

Les documents `memory/PRD.md` et `plan/plan.md` restent utiles pour l’intention et les décisions historiques, mais leurs statuts « phase D à construire », « panier indépendant » et « modèle gemini-3.5-flash » sont périmés au regard du code/configuration actuels. La configuration versionnée utilise actuellement `gemini-2.5-flash` par défaut. Vérifier code et tests avant de reprendre un ancien backlog. Le présent document décrit la présence du code, pas une validation fonctionnelle en production : aucun test ni échange Gemini réel n’a été exécuté pour cette passation.

## 3. Rôles et isolation

- `SUPER_ADMIN` : gestion de la plateforme, restaurants, plans et métriques.
- `RESTAURANT_OWNER` : gestion complète du restaurant, des utilisateurs, menus, commandes et paramètres.
- `RESTAURANT_MANAGER` : opérations du restaurant, sans privilèges de propriétaire liés à l’abonnement.
- `RESTAURANT_STAFF` : consultation/opérations de commandes et disponibilités selon les routes.

Les utilisateurs de restaurant portent un `restaurant_id`; `auth.py` expose `get_current_user`, `require_roles` et `tenant_id_of`. Pour toute route tenant, tirer l’identifiant du JWT/session, jamais d’un champ client. Les recherches et mutations doivent inclure le tenant dans leurs filtres. L’API publique prend un `public_id` de restaurant actif. Pour les conversations, le restaurant est fixé à la création et les identifiants inconnus/étrangers doivent échouer ou redémarrer sans révéler l’existence d’un autre tenant. La console IA dérive le restaurant de l’utilisateur authentifié.

## 4. Stack et lancement

- Backend : Python, FastAPI, Pydantic v2, Motor/PyMongo asynchrone, MongoDB, JWT/cookies, bcrypt. Point d’entrée `backend/server.py`.
- Frontend : React 19, CRA + CRACO, React Router, Tailwind, composants shadcn/Radix, lucide, sonner, Axios. Alias `@` vers `frontend/src`.
- IA : contrat fournisseur dans `backend/services/ai/provider.py`, implémentations Gemini et Bytez, fournisseur scripté pour tests.
- Déploiement : `docker-compose.yml` (backend, frontend nginx, MongoDB 7), Coolify. Détails opératoires dans `COOLIFY.md`.

Variables locales backend avant tout import de `database.py` : `MONGO_URL` et `DB_NAME` (lus à l’import). `.env` de `server.py` est chargé sans écraser les variables d’environnement existantes.

```powershell
$env:MONGO_URL="mongodb://127.0.0.1:27017/restoia-test"
$env:DB_NAME="restoia-test"
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```

Frontend : depuis `frontend`, le shim `npm start` est connu comme absent ; démarrer avec `node node_modules/@craco/craco/dist/bin/craco.js start`. Build : `node node_modules/@craco/craco/dist/bin/craco.js build`. `REACT_APP_BACKEND_URL` est injecté au build, doit viser le backend public et ne pas avoir de slash final.

## 5. Organisation du dépôt

```text
backend/server.py                 assemblage FastAPI, CORS, seed, inclusion des routes
backend/database.py               client Mongo (env requis à l’import)
backend/auth.py                   sessions, JWT, rôles et tenant
backend/models.py                 modèles/constantes/sérialisation
backend/seed.py                   index, admin, plans et restaurant démo Chez Awa
backend/routers/                  routes HTTP découpées par domaine
backend/services/order_service.py moteur déterministe panier/validation/commande
backend/services/ai/              orchestration IA, outils, fournisseurs, quota, rétention
backend/static/widget/             widget installable + document iframe
backend/tests/                     tests unitaires et intégration
frontend/src/App.js                routes frontend
frontend/src/pages/                vitrine, storefront, dashboard, admin
frontend/src/components/           widget client, composants partagés
frontend/src/lib/api.js            Axios, cookies, base URL
memory/PRD.md                     vision/historique (statuts à revalider)
plan/plan.md                      plan de reprise historique (à revalider)
```

## 6. Fonctionnalités métier

### Plateforme et restaurant

Inscription, connexion, déconnexion, session `/me`, renouvellement, récupération/réinitialisation de mot de passe, limitation des tentatives de connexion, onboarding du restaurant. Les paramètres et les rôles permettent de déléguer le travail. L’admin plateforme consulte les métriques, gère les restaurants (y compris suspension/réactivation) et les plans. Les mutations admin/tenant doivent écrire un événement dans `audit_logs` selon les conventions existantes.

### Catalogue et menus

Catégories, articles, ordre d’affichage, disponibilité, image, groupes d’options et options avec suppléments/prix. Les contraintes (prix non négatif, minimum/maximum, cohérence de tenant) sont validées côté serveur. Le catalogue public ne publie que les entités actives, avec disponibilité et options exposées sans champs internes sensibles. Il existe deux routes catalogue différentes : `/api/public/menu/{public_id}` (StoreFront/widget) et `/api/menu/public/{public_id}` (route menu dédiée, structure potentiellement différente). Ne pas les fusionner sans vérifier leurs consommateurs.

Les menus hebdomadaires sont gérés par `weekly_menu_router.py` et `WeeklyMenuPage.js`; l’agent dispose d’outils associés au menu du jour. Préserver la sémantique des jours, le filtrage tenant et la règle d’affichage existante.

### Commande et livraison

`services/order_service.py` est le noyau déterministe réutilisé par l’UI et l’agent : création/modification/suppression/vidage panier, calcul et validation, zones/frais, client, référence atomique et création commande. Le serveur recharge produits/options et recalcule les prix/totaux ; les valeurs du navigateur ou du LLM ne sont pas autoritaires. La validation détecte notamment les changements de prix. Les commandes embarquent des instantanés d’articles/options pour préserver l’historique.

Clés métier : `Idempotency-Key` contre les doubles soumissions, référence `CMD-AAAA-NNNNN`, transitions de statut contrôlées, annulation limitée, historique de statut, suivi public par jeton. Le détail des transitions est dans `order_service.py`. Les zones et frais appartiennent au tenant. La vue publique doit rester minimale.

### Expérience client

`/order/:publicId` affiche le catalogue, options, panier, checkout, livraison/retrait et confirmation. `StoreFront.js` persiste localement les identifiants de panier/conversation par restaurant, mais ces identifiants restent des références non autorisantes et sont revérifiés côté serveur. `StoreChatWidget.js` fournit le chat, cartes produits, ajout d’article et affichage du panier renvoyé par le backend. Le panier partagé est la même ressource serveur pour les deux parcours ; ne pas créer un troisième panier.

Le widget tiers est servi à la racine backend (`/widget.js`, `/widget-frame.html`), et non sous `/api`. Les réglages de widget sont associés au restaurant; vérifier les origines/CORS et la communication iframe lors de toute modification.

### Agent conversationnel

`ai_router.py` expose `POST /api/public/ai/chat` (public) et `POST /api/ai/test/chat` (session authentifiée). La limite actuelle est 20 appels par minute par IP en mémoire et la longueur du message est limitée à 1000 caractères. Ce limiteur local n’est ni distribué ni persistant.

`agent_service.py` construit le contexte à partir du restaurant, menu réel, zones, panier, brouillon et conversation, demande au fournisseur une action structurée, puis exécute les outils contrôlés via `services/ai/tools.py`. Le modèle n’écrit jamais directement en base. L’agent doit demander les informations manquantes, revalider le panier, afficher un récapitulatif exact, obtenir une confirmation explicite avant création. Le backend ignore les prix/totaux générés et recalcule tout. Une conversation ne doit pas commander deux fois; les paniers fermés et changements dangereux de panier sont refusés.

Les données de contact sont masquées dans l’historique persisté (meilleur effort, pas une garantie cryptographique) et ne doivent pas être injectées dans le prompt plus que nécessaire. Il existe quota/usage et politique de rétention ; voir `quota.py`, `retention.py` et tests dédiés. Protéger ces comportements lors des changements de prompt/outils.

Configuration : `AI_GATEWAY=gemini|bytez`; Gemini utilise `GEMINI_API_KEY`/`GEMINI_MODEL` (défaut configuré `gemini-2.5-flash`); Bytez utilise `BYTEZ_API_KEY`, `BYTEZ_PROVIDER_KEY`, `AI_MODEL`. Secrets uniquement backend. Respecter le tripwire AGENTS.md : ne pas changer `gemini_provider.get_default_provider` ni `bytez_provider.provider_from_env` sans raison/test explicite.

## 7. Routes API par domaine (préfixe `/api` sauf mention)

- Auth : `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/refresh`, `/auth/forgot-password`, `/auth/reset-password`.
- Restaurant : `/restaurants/me`, `/restaurants/public/{public_id}`.
- Utilisateurs : `/users` et `/users/{id}`.
- Dashboard/admin : `/dashboard/overview`, `/admin/metrics`, `/admin/restaurants...`, `/admin/plans...`.
- Menu : catégories, articles, options via `/menu/...`; catalogue dédié `/menu/public/{public_id}`; menus semaine `/menu/weekly...`.
- Public panier/catalogue : `/public/menu/{public_id}`, `/public/delivery-zones/{public_id}`, `/public/cart...`.
- Public commandes : `POST /public/orders`, suivi `GET /public/orders/{tracking_token}`.
- Gestion tenant : `/orders...`, `/customers...`, `/delivery/zones...`.
- IA : `/public/ai/chat`, `/ai/test/chat`.
- Widget statique : `GET /widget.js`, `GET /widget-frame.html` (racine, hors `/api`).

Consulter les décorateurs dans `backend/routers/` avant d’inférer les verbes, permissions ou schémas exacts.

## 8. Données Mongo principales

Collections constatées dans le seed/services : `users`, `restaurants`, `plans`, `menu_categories`, `menu_items`, `menu_option_groups`, `menu_options`, `weekly_menus`, `carts`, `orders`, `customers`, `counters`, `order_status_history`, `delivery_zones`, `ai_conversations`, `audit_logs`, `login_attempts`, `password_reset_tokens`, `password_reset_requests`.

La plupart des documents métier contiennent `restaurant_id`; les références option/article du panier sont validées contre ce tenant. Les index sont créés au seed (`seed.py`), incluant unicité email/public_id/cart_id/conversation_id, index tenant et index d’expiration pour les jetons/demandes de reset. Le modèle est en partie dénormalisé volontairement : les commandes conservent des snapshots.

## 9. Frontend et navigation

Routes publiques : `/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, `/order/:publicId`. Espace tenant protégé : `/dashboard` (aperçu, commandes, menu, menus semaine, clients, livraison, IA, utilisateurs, paramètres). Admin protégé : `/admin`. `AuthContext` porte la session; `ProtectedRoute` vérifie les rôles. L’API Axios utilise `withCredentials`; tenir compte des cookies `Secure` et CORS avec credentials en local/intégration.

Pages principales : `Landing`, `StoreFront`, `Overview`, `OrdersPage`, `MenuPage`, `WeeklyMenuPage`, `CustomersPage`, `DeliveryPage`, `AiTestConsole`, `UsersPage`, `SettingsPage`, `SuperAdmin`.

## 10. Tests, pièges et pratiques de reprise

Deux familles backend : tests unitaires (fakes/mocks, sans Mongo/serveur) et intégration (API active + seed). `backend/pytest.ini` impose `-n 2 --dist loadscope`; ne pas éditer. Pour une exécution sérielle utiliser `-n 0`, ne pas utiliser `-p no:xdist`. Les suites d’intégration attendent la base locale `restoia-test`, le backend sur 8001 et `REACT_APP_BACKEND_URL=http://127.0.0.1:8001`. Les cookies `Secure` nécessitent le patch déjà documenté dans `tests/test_orders.py` pour les appels HTTP.

Tests unitaires existants couvrent notamment panier agent, service agent, intégrité commandes, confidentialité, quota, fournisseurs Gemini/Bytez et rétention. Les tests menu/commandes/admin sont intégration. Les tests widget, menu hebdomadaire, panier partagé et menu du jour ont aussi des fichiers dédiés. Ne pas lancer une suite d’intégration sans préparer l’environnement et garantir le nettoyage de `restoia-test`.

Autres pièges importants :

- `database.py` exige les variables d’environnement avant import.
- `server.py` charge `.env` mais les variables déjà exportées ont priorité.
- `/widget.js` est à la racine.
- le build frontend incorpore `REACT_APP_BACKEND_URL`, sans slash final.
- les routes publiques filtrent les restaurants actifs et les entités de menu actives; le soft-delete restaurant utilise `status="deleted"`.
- ne pas exposer ni committer secrets, identifiants ou données de test sensibles. `.gitignore` fait foi.
- le seed utilise `rest_demo_chezawa`; vérifier les identifiants de test dans la mémoire locale autorisée plutôt que de les recopier dans un artefact public.

## 11. Déploiement

`docker-compose.yml` construit le backend et frontend et utilise MongoDB 7 avec volume persistant. Coolify injecte `JWT_SECRET`, `FRONTEND_URL`, `REACT_APP_BACKEND_URL` et éventuellement variables d’admin/IA. Ne pas exposer Mongo au public. Le backend a healthcheck `/api/`; frontend nginx sonde `/`. Après déploiement, vérifier la santé API, la page publique, les ressources `/widget.js` et `/widget-frame.html`, et effectuer un parcours réel avec un compte de test. Les domaines frontend/backend doivent correspondre aux origines CORS/cookie prévues. Lire `COOLIFY.md` pour le runbook complet.

## 12. Points de vigilance et suite recommandée

Avant tout nouveau développement :

1. lire `AGENTS.md`, ce document, puis les fichiers du sous-système ciblé;
2. examiner `git status` et les changements déjà présents;
3. établir le comportement actuel avec tests existants ciblés et, si nécessaire, un environnement local isolé;
4. vérifier les contrats de réponse utilisés par les deux catalogues, le storefront, le widget externe et l’agent;
5. maintenir les invariants : isolation tenant, source de vérité serveur, confirmation explicite, idempotence, snapshots commandes, confidentialité;
6. ajouter des tests adaptés au changement (unitaires et/ou intégration), sans modifier la configuration pytest;
7. mettre à jour PRD/plan lorsqu’un statut ou une décision persistante a changé.

Chantiers plausibles à évaluer, sans présumer qu’ils sont autorisés ou urgents : automatiser quota/rétention en environnement multi-instance, examiner le rate-limit en mémoire, vérifier les coûts/limites IA et l’observabilité, confirmer une démonstration de bout en bout, réconcilier les documents historiques avec le code, planifier les abonnements réellement appliqués et les politiques de rétention. Les capacités paiement, canaux sociaux, voix, streaming et temps réel restent à définir.

## 13. Prompt de démarrage suggéré pour un autre LLM

> Tu reprends MenuMind dans ce dépôt. Commence par lire `AGENTS.md` et `LLM_HANDOFF.md`, puis vérifie le code et les tests du domaine concerné : la documentation de phases peut être périmée. Ne change pas l’architecture sans nécessité. Toute donnée/prix/total de commande doit être validé côté backend; conserve l’isolation stricte par `restaurant_id`, la confirmation explicite avant création et l’idempotence. N’importe pas `database.py` avant d’avoir défini `MONGO_URL` et `DB_NAME`. Respecte `pytest.ini` (`-n 2 --dist loadscope`, série `-n 0`). Ne démarre pas un chantier hors demande : résume l’état, les hypothèses, risques d’intégrité et tests pertinents avant d’éditer.
