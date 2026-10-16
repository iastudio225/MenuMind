# AGENTS.md

## Projet

MenuMind — SaaS de prise de commande IA pour restaurants (Côte d'Ivoire).
FastAPI + Motor (MongoDB async) backend, React CRA+craco frontend, widget JS embarquable.

Repo GitHub : `iastudio225/MenuMind` (branche `main`). Déploiement : Coolify via `docker-compose.yml`
— variables d'env et vérifications post-déploy dans `COOLIFY.md`. Aucune CI (pas de `.github/`).
Référentiels métier : `memory/PRD.md`, `plan/plan.md`.

## Commandes

### Backend (PowerShell — environnement Windows)
```powershell
$env:MONGO_URL="mongodb://127.0.0.1:27017/restoia-test"   # OBLIGATOIRE avant l'import de database.py
$env:DB_NAME="restoia-test"
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```
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

# Intégration — exigent un backend démarré + seed :
$env:REACT_APP_BACKEND_URL="http://127.0.0.1:8001"
python -m pytest tests/test_admin.py tests/test_menu.py tests/test_orders.py -v
# Runner raccourci à la racine (backend supposé déjà sur 8001) : python _run_tests.py
```
- `pytest.ini` impose `addopts = -n 2 --dist loadscope` : **ne pas le modifier**, ne jamais ajouter
  `-p no:xdist` (plante). Sériel = `-n 0` uniquement.
- Sans env, `test_admin` retombe sur `http://127.0.0.1:8002`, `test_orders`/`test_menu` cherchent
  `/app/frontend/.env` (chemin Docker) → crash en local. Toujours définir `REACT_APP_BACKEND_URL`.
- `test_admin` fait son cleanup pymongo en dur sur `mongodb://127.0.0.1:27017/restoia-test` :
  le backend de test doit tourner sur cette même base.
- Fixtures : seed = resto `rest_demo_chezawa`, identifiants de test en dur dans les fichiers de test.
- Pas de lint/typecheck configuré (black/flake8/mypy dans requirements.txt mais aucune config ni CI),
  aucun test frontend, plus de suite Playwright (le vieux `script_test.py` n'existe pas).

## Architecture

```
backend/
  server.py          # FastAPI app, CORS, seed au démarrage
  database.py        # AsyncIOMotorClient — lit MONGO_URL/DB_NAME À L'IMPORT
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

- **`database.py` lit `MONGO_URL`/`DB_NAME` à l'import** (`os.environ[...]`) : les définir dans
  l'environnement AVANT d'importer le module, sinon KeyError.
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
- Tests d'intégration : chaque suite nettoie ses données de test (pattern `test_admin.py` :
  soft-delete API + `delete_many` pymongo) — ne rien laisser traîner dans `restoia-test`.
