# Phase D — Reprise de l'Agent IA conversationnel (RestoIA)

Un agent IA (Gemini) qui prend la commande d'un client en langage naturel et la transforme
en une vraie commande calculée et enregistrée par le backend. Cette reprise finit ce qui a été
interrompu : le cerveau de l'agent existe déjà côté serveur ; il manque surtout l'interface client.

## Pour qui
- **Le client final d'un restaurant** : commande en discutant, sans créer de compte, depuis la page de commande du restaurant.
- **Le restaurateur** : teste son propre agent depuis son tableau de bord et récupère l'extrait d'intégration.

## État actuel de la Phase D (constaté dans le projet)

### ✅ Déjà terminé (backend)
- **Abstraction fournisseur IA** : interface commune + implémentation Gemini + fournisseur « scripté » pour les tests (changement de fournisseur possible plus tard).
- **Agent conversationnel** : construit un contexte « ancré » (menu réel, zones, panier serveur, choix en cours) et dialogue tour par tour ; le backend reste la seule source de vérité pour les prix et totaux.
- **Outils contrôlés** : consulter le menu/les zones, ajouter / modifier / retirer du panier, choisir livraison ou retrait, enregistrer le client, recalculer le panier, créer la commande. L'agent n'écrit jamais directement en base ; tout passe par le moteur de commande validé de la Phase C.
- **Garde-fous** : aucune commande créée sans confirmation explicite du client ; les montants proposés par le modèle sont ignorés (recalcul serveur) ; anti-double-commande (idempotence par conversation) ; refus si produit indisponible ou zone inconnue.
- **Endpoint public de dialogue** avec limite de débit et taille de message maximale.
- **Isolation multi-tenant** : la conversation est rattachée à un seul restaurant déterminé de façon sûre ; une conversation ne peut pas atteindre les données d'un autre restaurant.
- **Configuration** présente (clé IA côté backend uniquement, fournisseur et modèle paramétrables).

### 🟡 Partiellement / à ajuster
- **Modèle Gemini** : actuellement réglé sur la variante « pro ». Décision retenue : passer au modèle **flash** (plus rapide et moins coûteux, adapté à la prise de commande).
- **Vérification au démarrage** : la session s'étant arrêtée en pleine écriture, le serveur avec le nouvel endpoint IA doit être redémarré et confirmé fonctionnel, puis un échange réel avec Gemini doit être validé de bout en bout.
- **Page « Réceptionniste IA » du dashboard** : encore un simple espace réservé.

### ❌ Non commencé
- **Interface client** : la bulle de chat qui permet réellement au client de parler à l'agent.
- **Console de test côté restaurateur** + extrait d'intégration.
- **Tests automatisés de la Phase D** (menu réel, produit inexistant/indisponible, prix ignoré, total serveur, options, option étrangère, livraison/zone inconnue, confirmation, double commande, modification, isolation, injection de prompt) et vérification que les tests des phases précédentes restent au vert.
- **Démonstration bout-en-bout** d'une commande passée entièrement via l'IA, visible ensuite dans le tableau de bord du restaurant.

## Fonctionnalités et expérience (à livrer dans cette reprise)
- **Bulle de chat flottante** sur la page de commande du restaurant : le client ouvre la discussion, commande en langage naturel, voit son panier et le total (calculés par le serveur) se mettre à jour, puis confirme.
- **Récapitulatif avant confirmation** : l'agent présente le détail (articles, options, sous-total, livraison, total) et demande une confirmation explicite ; la commande n'est créée qu'après un « oui » clair.
- **Confirmation finale** : affichage du numéro de commande réel et du total ; la commande apparaît immédiatement dans le tableau de bord du restaurant.
- **Console de test pour le restaurateur** : depuis le tableau de bord, il discute avec son propre agent pour le valider, et récupère l'extrait d'intégration à poser sur son site.

## Parcours client
1. Le client ouvre la page de commande du restaurant et clique sur la bulle de chat.
2. Il écrit par ex. « deux poulets braisés avec attiéké et une Coca ».
3. L'agent identifie les plats réels, demande les options manquantes, propose livraison ou retrait.
4. Pour une livraison, il demande la zone et l'adresse ; les frais sont calculés par le serveur.
5. Il demande le prénom et le téléphone.
6. Il présente le récapitulatif avec le total officiel et demande confirmation.
7. Après un « oui » explicite, la commande est créée et le numéro de suivi est affiché.

## Ressenti UI/UX
- Cohérent avec l'interface existante (même palette chaleureuse, même style de composants). Priorité à la **fiabilité et à la clarté** plutôt qu'aux effets.
- Bulle discrète en bas de page, fenêtre de chat lisible sur mobile, panier/total toujours visibles pendant la discussion, bouton de confirmation mis en avant au bon moment.

## Phases de mise en œuvre

### Phase 1 — à construire maintenant (clôture de la Phase D)
- Basculer le modèle Gemini sur la variante **flash**.
- Ajouter la **bulle de chat flottante** sur la page de commande, connectée à l'agent (affichage des messages, du panier et du total serveur, confirmation finale avec numéro de commande).
- Remplacer la page « Réceptionniste IA » du dashboard par une **console de test en direct** + extrait d'intégration.
- Écrire et faire passer les **tests de la Phase D**, vérifier la **non-régression** des phases A/B/C, et réaliser la **démonstration bout-en-bout** (commande IA visible dans le dashboard) ainsi que le **contrôle multi-tenant** (agent du restaurant A ne sert que le menu de A).

### Phase 2 — plus tard (non inclus)
- Réponse en flux (streaming) mot à mot et apparition en temps réel des nouvelles commandes dans le dashboard.
- Personnalisation de l'accueil et de l'apparence de la bulle par restaurant.

### Phase 3 — plus tard (non inclus)
- Nouveaux canaux (WhatsApp, Instagram, Messenger), paiement en ligne, suivi client en direct, voix. Hors périmètre de cette reprise.

## Hypothèses (choix faits sans redemander)
- Le **widget client** est une bulle flottante intégrée à la page de commande existante (choix confirmé).
- La **page IA du dashboard** est une console de test en direct avec extrait d'intégration (choix confirmé).
- Le **modèle** passe à `gemini-3.5-flash` (choix confirmé).
- La **clé IA** est configurée uniquement côté backend (`EMERGENT_LLM_KEY`) ; aucune clé n'est demandée au restaurateur.
- Aucune des fonctionnalités explicitement hors périmètre (WhatsApp, paiement, streaming, impression cuisine, temps réel, voix) n'est développée dans cette reprise.
- Le travail backend déjà présent est **réutilisé tel quel** ; il n'est ni réécrit ni remplacé, seuls des ajustements ciblés sont faits.
- À la fin de la Phase D, l'arrêt est respecté : la Phase E n'est pas démarrée sans validation.
