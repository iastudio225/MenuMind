"""D1.54 étape 6 — contrôles statiques du widget embarqué.

Le dépôt ne dispose d'aucun mécanisme de test navigateur/HTML (AGENTS.md : aucun
test frontend, aucune dépendance installable ici). Ces tests lisent le fichier
static/widget/widget-frame.html et verrouillent le CONTRAT des scénarios imposés
par l'étape 6 : le code exécuté en navigateur n'est PAS exécuté ici (signalé
explicitement dans le rapport).
"""
from pathlib import Path

FRAME = Path(__file__).resolve().parents[1] / "static" / "widget" / "widget-frame.html"
CODE = FRAME.read_text(encoding="utf-8")
JS = CODE.split("<script>", 1)[1].split("</script>", 1)[0]


def _region(start, end):
    """Sous-chaîne JS entre deux marqueurs (l'ordre des fonctions est verrouillé
    par ce test — reformulation du fichier = mise à jour consciente des tests)."""
    i = JS.index(start)
    return JS[i:JS.index(end, i)]


def test_frame_present_et_sans_dependance_externe():
    assert FRAME.is_file()
    assert "<script src" not in CODE
    assert 'rel="stylesheet"' not in CODE


def test_scenario_1_reponse_sans_products_aucun_bloc():
    # Champ capturé dans la réponse (rétrocompatible: absent -> []) + garde de rendu.
    assert "Array.isArray(r.data.products)" in JS
    assert "if (m.products && m.products.length > 0)" in JS


def test_scenario_2_produit_disponible_sans_options_ajout_direct():
    body = _region("function onAddClick(p)", "function openSelector(p)")
    assert "if (!p.options || !p.options.length)" in body
    assert "startAdd(p, [], 1)" in body
    assert '/api/public/cart/" + encodeURIComponent(cid) + "/items' in JS


def test_scenario_3_produit_indisponible_aucun_ajout():
    body = _region("function buildProductCard(p)", "function onAddClick(p)")
    # Le bouton d'ajout n'existe QUE dans la branche available.
    assert "if (p.available)" in body
    assert 'none.textContent = "Indisponible"' in body
    assert 'chat-product-add-' in body
    assert body.index("if (p.available)") < body.index('none.textContent = "Indisponible"')


def test_scenario_4_option_obligatoire_confirmation_impossible():
    valid = _region("function validSelector()", "function recapPrice()")
    assert "if (g.required && count < Math.max(1, min)) return false;" in valid
    issue = _region("function groupIssue(g)", "function validSelector()")
    assert "obligatoire manquante" in issue
    # Le message bloquant est appliqué au groupe + confirm désactivé.
    state = _region("function updateSelectorState()", "function renderSelector()")
    assert "el.optConfirm.disabled = !ok || adding;" in state


def test_scenario_5_options_multiples_min_max():
    valid = _region("function validSelector()", "function recapPrice()")
    assert "if (count < min) return false;" in valid
    assert "if (g.max && count > Number(g.max)) return false;" in valid
    toggle = _region("function toggleChoice(g, cid)", "function updateSelectorState()")
    assert "arr.length < Number(g.max || 1)" in toggle


def test_scenario_6_option_indisponible_selection_interdite():
    render = _region("function renderSelector()", "function send(text")
    assert "input.disabled = !c.available;" in render
    assert "input.addEventListener(\"change\"" in render
    # Désactivé côté DOM ET bloqué en CSS (pointer-events).
    assert ".opt-choice.off" in CODE
    assert "pointer-events: none" in CODE


def test_scenario_7_annulation_aucun_appel_dajout():
    close = _region("function closeSelector(restoreFocus)", "function groupIssue(g)")
    assert "fetch(" not in close
    assert "startAdd" not in close
    assert 'el.optCancel.addEventListener("click", function () { closeSelector(true); });' in JS


def test_scenario_8_succes_api_confirmation_et_synchronisation():
    body = _region("function startAdd(product, optionIds, qty)", "function buildProductCard(p)")
    assert "closeSelector(false);" in body
    assert "applyCartUpdate(r.data);" in body
    assert "storageSet(STORAGE_CART, cartId);" in body
    assert "ajouté au panier" in body
    upd = _region("function applyCartUpdate(data)", "function ensureCart()")
    assert "messages[i].cart = merged;" in upd
    # Le toast de succès n'est atteint qu'après la garde 2xx.
    assert body.index("if (r.status >= 200") < body.index("ajouté au panier")


def test_scenario_9_echec_api_ou_409_pas_de_pseudo_succes():
    body = _region("function startAdd(product, optionIds, qty)", "function buildProductCard(p)")
    assert "r.status === 404 || r.status === 409" in body
    assert "purgeSession();" in body
    assert 'showToast(detail + " Envoyez un message' in body
    # 400 / réseau -> message d'erreur ET sélecteur conservé (aucune
    # fermeture après le showOptErr de la branche échec): sélection sûre
    # pour une nouvelle tentative. (404/409 ferment APRÈS purgeSession:
    # session invalide, plus rien à conserver.)
    assert "showOptErr(detail);" in body
    tail = body[body.index("showOptErr(detail);"):]
    assert "closeSelector" not in tail
    assert "ajouté au panier" not in tail


def test_scenario_10_double_clic_verrou_synchrone():
    assert JS.count("if (adding) return;") >= 2  # startAdd + onAddClick
    body = _region("function startAdd(product, optionIds, qty)", "function buildProductCard(p)")
    assert "adding = false;" in body
    assert "if (selector) updateSelectorState();" in body


def test_scenario_11_textes_html_non_interpretes():
    body = _region("function buildProductCard(p)", "function onAddClick(p)")
    assert "innerHTML" not in body
    assert "textContent = p.name" in body
    assert 'img.setAttribute("src", p.image_url)' in body
    # Aucune interpolation de donnée serveur en HTML exécutable côté carte.
    sel = _region("function renderSelector()", "function send(text")
    assert 'textContent = g.name' in sel
    assert 'textContent = c.name' in sel
