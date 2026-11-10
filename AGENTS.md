# AGENTS.md

## Projet

MenuMind — SaaS de prise de commande IA pour restaurants (Côte d'Ivoire).
FastAPI backend on Supabase PostgreSQL (asyncpg), React CRA+craco frontend, widget JS embarquable.

Repo GitHub : `iastudio225/MenuMind` (branche `main`). Déploiement : Coolify via `docker-compose.yml`
— variables d'env et vérifications post-déploy dans `COOLIFY.md`. Aucune CI (pas de `.github/`).
Référentiels métier : `memory/PRD.md`, `plan/plan.md`.

## Commandes

### Backend (PowerShell — environnement Windows)
```powershell
$env:SUPABASE_DB_URL="postgresql://..."   # connection URI Supabase; required at startup
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```
Apply SQL migrations explicitly before the first startup: `python -m scripts.migrate_postgres` from `backend/`.
Python : `C:\Users\frede\AppData\Local\Programs\Python\Python314\python.exe` (tout y est installé).
Pas de script de lancement ; le 8001 est aussi le port du healthcheck du compose.

### Frontend
```powershell
cd frontend
# Dev (port 3000) : `npm start` échoue — le shim craco.cmd est absent de node_modules\.bin :
node node_modules/@craco/craco/dist/bin/craco.js start
# Build production (REACT_APP_BACKEND_URL brûlé dans le bundle, SANS slash final)
node node_modules/@craco/craco/dist/bin/craco.js build
```

### Tests backend — deux familles
```powershell
cd backend
# Unitaires — ni Mongo ni serveur (fakes/mocks partout) :
python -m pytest tests/test_agent_cart.py -v               # un fichier
python -m pytest tests/test_agent_cart.py::test_xxx -v     # un test
#   → test_agent_cart, test_agent_service, test_order_integrity, test_privacy,
#     test_quota, test_gemini_provider, test_bytez_provider, test_retention

# Les anciens tests d'intégration MongoDB ne sont pas compatibles avec Supabase
# et doivent être réécrits avant d'être utilisés.
```
- `pytest.ini` impose `addopts = -n 2 --dist loadscope` : **ne pas le modifier**, ne jamais ajouter
  `-p no:xdist` (plante). Sériel = `-n 0` uniquement.
- The current PostgreSQL adapter stores one JSONB payload per entity table. SQL schema evolution lives in `backend/migrations/`.
- Fixtures : seed = resto `rest_demo_chezawa`, identifiants de test en dur dans les fichiers de test.
- Pas de lint/typecheck configuré (black/flake8/mypy dans requirements.txt mais aucune config ni CI),
  aucun test frontend, plus de suite Playwright (le vieux `script_test.py` n'existe pas).

## Architecture

```
backend/
  server.py          # FastAPI app, CORS, seed au démarrage
  database.py        # asyncpg pool + compatibility layer over Supabase PostgreSQL tables
  auth.py            # JWT cookies, hash bcrypt, require_roles
  seed.py            # Super-admin + plans + restaurant démo « Chez Awa »
  routers/           # auth, restaurant, user, dashboard, admin, menu, cart,
                     # order, customer, delivery, ai, embed
  services/          # order_service (panier/totaux/commandes), ai/ (provider, agent_service, tools)
  static/widget/     # widget.js + widget-frame.html (servis par embed_router)
  tests/             # pytest — unitaires vs intégration (voir ci-dessus)
  models.py          # Pydantic models, serialize(), now_iso()
frontend/
  src/pages/         # Route components (Login, Register, StoreFront, Dashboard, Admin/*)
  src/lib/api.js     # Axios instance withCredentials, baseURL=REACT_APP_BACKEND_URL
  src/lib/format.js  # formatFCFA, formatApiErrorDetail
  src/components/ui/ # shadcn/ui (Button, Dialog, Select, Badge, Tabs, ...)
```

## Pièges critiques

- **`SUPABASE_DB_URL` est lu à la connexion au démarrage**, pas à l'import. Appliquer les migrations avec `python -m scripts.migrate_postgres` avant le lancement.
- **`server.py` charge `.env` sans override** : les variables d'environnement existantes gagnent sur `.env`.
- **Cookie `Secure`** : tout test `requests` en http:// doit patcher
  `DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True` (ex. `tests/test_orders.py:15`),
  sinon les cookies ne sont jamais renvoyés.
- **`REACT_APP_BACKEND_URL` sans slash final** : un slash crée des URLs doubles (`//api/`) qui cassent CORS.
- **Widget routes** : `/widget.js` et `/widget-frame.html` sont à la racine du backend (pas sous `/api`).
- **Tripwires IA** : ne pas modifier `gemini_provider.get_default_provider` ni `bytez_provider.provider_from_env`.
- **Soft-delete** : `status="deleted"` — exclu des listes/métriques/menu public. Les routes publiques
  filtrent déjà `status: "active"`.
- **Alias `@`** = `frontend/src` (craco.config.js).
- **Deux paniers distincts coexistent déjà** : le panier visuel du StoreFront (`cartId`, routes
  `/api/public/cart*`) et le panier de la conversation IA (`conv["cart_id"]`, créé dans
  `agent_service._get_or_create_conversation`) ne sont **jamais liés**, et la réponse de
  `POST /api/public/ai/chat` ne contient pas de `cart_id`. Toute évolution « panier unique » doit
  lier les deux sans en créer un troisième.
- **Deux endpoints catalogue divergents** : `GET /api/public/menu/{public_id}` (StoreFront + widget,
  **sans `image_url`**) vs `GET /api/menu/public/{public_id}` (avec `image_url`, sans
  `welcome_message`/`widget`).

## Conventions

- Frontend : shadcn/ui + Tailwind, lucide-react icons, sonner toast, testids kebab-case (`admin-detail-btn-0`).
- Backend : `require_roles(SUPER_ADMIN)` pour admin, `get_current_user` + `tenant_id_of` pour tenant
  isolation ; chaque mutation admin insère un `db.audit_logs.insert_one(...)`.
- Formats : `formatFCFA()` pour l'argent, `formatApiErrorDetail()` pour les erreurs API.
- Git : la `.gitignore` fait foi — surtout `.env*`, `*_owner.txt`, `/_*.py`, `/*.txt` à la racine,
  `memory/test_credentials.md`.
- Legacy script `backend/scripts/create_superadmin.py` and the integration suites still target MongoDB; do not use them against the Supabase backend until they are ported.
