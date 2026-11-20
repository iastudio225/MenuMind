# Orchestrateur n8n — SMS, emails, CRM

MenuMind émet des **webhooks sortants** vers n8n à chaque événement métier.
n8n se charge ensuite des actions : SMS (Twilio), emails (Resend/SendGrid),
agenda (Cal.com), CRM, etc. Le backend ne dépend d'aucun fournisseur d'action.

## 1. Configuration

### Variables d'environnement (backend)
```env
# Fallback global (optionnel) ; un établissement peut le surcharger.
N8N_WEBHOOK_URL=https://n8n.exemple.com/webhook/menumind

# Secret HMAC-SHA256 (optionnel mais recommandé)
WEBHOOK_SECRET=une-chaine-aleatoire-longue

# Timeout d'envoi (secondes)
WEBHOOK_TIMEOUT_SECONDS=5
```

### Par établissement (recommandé)
Dashboard → **Paramètres** → onglet **Notifications** :
- URL du webhook n8n (prioritaire sur `N8N_WEBHOOK_URL`)
- Secret de signature (prioritaire sur `WEBHOOK_SECRET`)
- Bouton **Tester le webhook**

Le propriétaire/manager peut tester via `POST /api/notifications/test`.

## 2. Événements

| Événement | Déclencheur | Contenu |
|-----------|-------------|---------|
| `order.created` | commande publique créée | commande complète |
| `order.status_changed` | changement de statut dashboard | `old_status`, `new_status`, commande |
| `order.cancelled` | annulation dashboard | `reason`, commande |
| `test` | bouton « Tester » | message de test |

### Enveloppe commune
```json
{
  "event": "order.created",
  "occurred_at": "2026-11-20T12:00:00+00:00",
  "restaurant": {
    "id": "…",
    "name": "Chez Awa",
    "public_id": "rest_demo_chezawa",
    "secteur": "restaurant"
  },
  "data": { }
}
```

### `order.created` — `data`
```json
{
  "reference": "CMD-2026-00042",
  "status": "PENDING",
  "order_type": "DELIVERY",
  "total": 12500,
  "subtotal": 10500,
  "delivery_fee": 2000,
  "customer": {
    "first_name": "Awa",
    "last_name": "Koné",
    "phone": "+2250700000000",
    "email": "awa@example.ci"
  },
  "items": [
    {
      "item_name_snapshot": "Poulet braisé",
      "quantity": 2,
      "unit_price_snapshot": 5000,
      "line_total": 10000,
      "options": []
    }
  ],
  "delivery_address": "Cocody, Rue des Jardins",
  "pickup_address": "",
  "dropoff_address": "",
  "tracking_token": "…",
  "created_at": "…"
}
```

## 3. Vérifier la signature (n8n — Function node)

```js
const crypto = require('crypto');
const secret = $env.WEBHOOK_SECRET; // ou le secret de l'établissement
const raw = $input.first().binary?.data
  ? Buffer.from($input.first().binary.data.data, 'base64').toString('utf8')
  : JSON.stringify($json.body);
const expected = 'sha256=' + crypto.createHmac('sha256', secret).update(raw).digest('hex');
if ($json.headers['x-menumind-signature'] !== expected) {
  throw new Error('Signature invalide');
}
return $input.all();
```

> En pratique, dans un Webhook n8n, activez **Raw Body** pour comparer
> exactement les octets reçus. L'en-tête est `X-MenuMind-Signature`.

## 4. Exemple de workflow n8n

```
[Webhook POST /menumind]  (Raw Body ON)
        │
        ▼
[Function: vérifier la signature]
        │
        ▼
[Switch sur {{$json.event}}]
   ├─ order.created ──────► [Twilio: SMS confirmation client]
   │                        [Resend: email récapitulatif]
   │                        [HTTP: créer un événement Cal.com (optionnel)]
   ├─ order.status_changed ► [Twilio: SMS « votre commande est prête »]
   ├─ order.cancelled ─────► [Resend: email d'annulation]
   └─ test ────────────────► [NoOp / Slack: « webhook OK »]
```

### Exemple d'appel cURL (test rapide)
```bash
curl -X POST "https://n8n.exemple.com/webhook/menumind" \
  -H "Content-Type: application/json" \
  -H "X-MenuMind-Event: test" \
  -d '{"event":"test","data":{"message":"hello"}}'
```

## 5. Sécurité et limites

- **Tenant isolation** : le webhook est lu dans le document du restaurant ;
  un établissement ne peut pas déclencher les webhooks d'un autre.
- **Best-effort** : l'envoi se fait en tâche de fond (`BackgroundTasks`) ;
  un échec n8n ne bloque jamais la commande.
- Chaque tentative est journalisée dans `audit_logs` (`WEBHOOK_DELIVERY`).
- Pas de retry automatique pour l'instant : n8n peut renvoyer un 5xx pour
  déclencher un retry côté n8n (ou ajouter une file plus tard).
