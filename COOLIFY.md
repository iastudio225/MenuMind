# Déploiement sur Coolify

Repo : https://github.com/iastudio225/MenuMind

Architecture déployée : `docker-compose.yml` à la racine (backend FastAPI + frontend React/nginx + Supabase PostgreSQL hébergé).

## Étapes dans Coolify

1. **New resource** → **Docker Compose** → connectez le repo Git `iastudio225/MenuMind` (branche `main`).
2. Coolify détecte `docker-compose.yml` à la racine.
3. Onglet **Environment** — définissez ces variables (les `${...}` du compose) :

   | Variable | Obligatoire | Valeur |
   |---|---|---|
   | `JWT_SECRET` | oui | chaîne aléatoire longue (ex. `openssl rand -hex 32`) |
   | `FRONTEND_URL` | oui | URL publique du frontend, ex. `https://menumind.example.com` (sert au CORS) |
   | `REACT_APP_BACKEND_URL` | oui | URL publique du **backend**, ex. `https://api.menumind.example.com` (brûlée dans le bundle React) |
   | `SUPABASE_DB_URL` | oui | URI PostgreSQL de Supabase (préférer le Session Pooler pour ce backend persistant) |
   | `ADMIN_EMAIL` | conseillé | email du super-admin seedé au 1er démarrage |
   | `ADMIN_PASSWORD` | conseillé | mot de passe du super-admin (défaut vide = `admin123` — à changer !) |
   | `CORS_ORIGINS` | non | origines supplémentaires, séparées par virgules |
   | `AI_GATEWAY` | non | `gemini` (défaut) ou `bytez` |
   | `GEMINI_API_KEY` | pour l'IA | clé Gemini (laisser vide = pas d'IA, erreurs propres) |
   | `GEMINI_MODEL` | non | défaut `gemini-2.5-flash` |
   | `BYTEZ_API_KEY`, `BYTEZ_PROVIDER_KEY`, `AI_MODEL` | si `AI_GATEWAY=bytez` | passerelle Bytez |

4. **Domains** : attachez un domaine (ou le sous-domaine fourni par Coolify) aux services :
   - `frontend` → domaine public principal (ex. `menumind.example.com`)
   - `backend` → domaine API (ex. `api.menumind.example.com`) — le widget s'y accroche via `${REACT_APP_BACKEND_URL}/widget.js`
5. **Créer le schéma** : depuis `backend/`, avec `SUPABASE_DB_URL` configurée, lancer `python -m scripts.migrate_postgres`.
6. Ajouter `SUPABASE_DB_URL` dans les variables Coolify. Comme la base est neuve, activer `MENUMIND_SEED_ON_STARTUP=true` pour créer le super-admin, les plans et le restaurant de démonstration « Chez Awa ». Définir `ADMIN_EMAIL` et `ADMIN_PASSWORD`.
7. **Deploy**.

## Après déploiement — vérifications

- `GET https://<backend>/widget.js` → **200**, `application/javascript`, contient `data-restaurant`
- `GET https://<backend>/widget-frame.html` → **200**, `text/html`
- `GET https://<backend>/api/` → 200 JSON `{"message": "MenuMind API"}`
- Frontend : connexion avec `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- Settings → Widget : snippet d'intégration avec l'URL du backend public

## Notes

- Le seed crée au besoin le restaurant démo (id public `rest_demo_chezawa`) — idéal pour la démo.
- Les variables ne sont **jamais** commitées : tout passe par l'UI Coolify.
- Les données MongoDB ne sont pas reprises. Le backend démarre avec les tables Supabase neuves puis crée les données de seed si `MENUMIND_SEED_ON_STARTUP=true`.
- Retour arrière : dans Coolify, redeploy de la révision précédente (Historique des déploiements). La révision précédente attend MongoDB et ne lira pas les nouvelles écritures Postgres.
