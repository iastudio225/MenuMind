# AGENTS.md

## Projet

MenuMind — SaaS de prise de commande IA pour restaurants (Côte d'Ivoire).
FastAPI + Motor (MongoDB async) backend, React CRA+craco frontend, widget JS embarquable.

Repo GitHub : `iastudio225/MenuMind` (branche `main`). Déploiement : Coolify via `docker-compose.yml`.

## Commandes

### Backend
```bash
# Lancer (MONGO_URL et DO_NAME obligatoires AVANT l'import de database.py)
export MONGO_URL="mongodb://127.0.0.1:27017/restoia-test"
export DB_NAME="restoia-test"
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```
`start_backend.ps1` = wrapper supervision (port 8001, refuse MONGO_URL non-loopback).
Python : `C:\Users\frede\AppData\Local\Programs\Python\Python314\python.exe`

### Frontend
```bash
cd frontend
# Dev server (port 3000) — sur Windows, le shim craco.cmd manque :
node node_modules/@craco/craco/dist/bin/craco.js start
# Build production
node node_modules/@craco/craco/dist/bin/craco.js build
```
`REACT_APP_BACKEND_URL` doit être défini avant le build (brûlé dans le bundle).

### Tests backend
```bash
cd backend
# pytest.ini impose -n 2 --dist loadscope — ne PAS utiliser -p no:xdist (erreur)
# Serial : -n 0
python -m pytest tests/test_admin.py -v
# Un seul test :
python -m pytest tests/test_admin.py::test_soft_delete_hides_everywhere -v
```

### Tests UI (Playwright)
```bash
# Nécessite backend (8002) + frontend (3000) lancés
PYTHONIOENCODING=utf-8 python script_test.py
```

## Architecture

```
backend/
  server.py          # FastAPI app, CORS, seed au démarrage
  database.py        # AsyncIOMotorClient — lit MONGO_URL/DB_NAME à l'import
  auth.py            # JWT cookies, hash bcrypt, require_roles
  seed.py            # Super-admin + plans + restaurant démo « Chez Awa »
  routers/           # auth, restaurant, user, dashboard, admin, menu, cart,
                     # order, customer, delivery, ai, embed
  services/          # order_service, ai/ (provider + agent_service)
  static/widget/     # widget.js + widget-frame.html (servis par embed_router)
  models.py          # Pydantic models, serialize(), now_iso()
frontend/
  src/pages/         # Route components (Login, Register, Dashboard, Admin/*)
  src/lib/api.js     # Axios instance withCredentials, baseURL=REACT_APP_BACKEND_URL
  src/lib/format.js  # formatFCFA, formatApiErrorDetail
  src/components/ui/ # shadcn/ui (Button, Dialog, Select, Badge, Tabs, ...)
```

## Pièges critiques

- **`database.py` lit `MONGO_URL`/`DB_NAME` à l'import** : les définir dans l'environnement AVANT d'importer le module, sinon crash.
- **`server.py` charge `.env` sans override** : les variables d'environnement existantes gagnent sur `.env`.
- **Cookie `Secure`** : les tests requests/Playwright en http:// doivent patcher `DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True` sinon les cookies ne sont pas renvoyés.
- **`REACT_APP_BACKEND_URL` sans slash final** : un slash crée des URLs doubles (`//api/`) qui cassent CORS.
- **Widget routes** : `/widget.js` et `/widget-frame.html` sont à la racine du backend (pas sous `/api`).
- **Tripwires IA** : ne pas modifier `gemini_provider.get_default_provider` ni `bytez_provider.provider_from_env`.
- **Soft-delete** : `status="deleted"` — exclu des listes/métriques/menu public. Les routes publiques filtrent déjà `status: "active"`.
- **Alias `@`** = `frontend/src` (craco.config.js).

## Conventions

- Frontend : shadcn/ui + Tailwind, lucide-react icons, sonner toast, testids kebab-case (`admin-detail-btn-0`).
- Backend : `require_roles(SUPER_ADMIN)` pour admin, `get_current_user` + `tenant_id_of` pour tenant isolation.
- Audit logs : `db.audit_logs.insert_one(...)` sur chaque mutation admin.
- Formats : `formatFCFA()` pour l'argent, `formatApiErrorDetail()` pour les erreurs API.
- Ne jamais committer : `.env`, `cookies_owner.txt`, `login_owner.txt`, `memory/test_credentials.md`, `/*.txt` racine, `/_*.py`.
- Tests : nettoyer les données de test (soft-delete API + cleanup pymongo), baseline `orders=54, carts=116, restaurants=1, users=2`.
