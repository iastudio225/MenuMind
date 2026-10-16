import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ShoppingCart, Plus, Loader2, CheckCircle2, Bot, MessageSquare, UtensilsCrossed } from "lucide-react";
import { toast } from "sonner";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import StoreChatWidget from "@/components/StoreChatWidget";
import ItemOptionModal from "@/components/store/ItemOptionModal";
import CheckoutDialog from "@/components/store/CheckoutDialog";
import CartLine from "@/components/store/CartLine";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
// D1.51: identifiants de session client — jamais une autorisation, seulement
// un cache d'ids vérifiés côté serveur (GET cart) à chaque chargement.
const cartStorageKey = (pid) => `menumind:cart:${pid}`;
const convStorageKey = (pid) => `menumind:conv:${pid}`;

export default function StoreFront() {
  const { publicId } = useParams();
  const [menu, setMenu] = useState(null);
  const [zones, setZones] = useState([]);
  const [cartId, setCartId] = useState(null);
  const [cart, setCart] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);
  const [itemModal, setItemModal] = useState(null);
  const [checkout, setCheckout] = useState(false);
  const [confirmed, setConfirmed] = useState(null);
  const [loading, setLoading] = useState(true);
  // D1.52: onglet initial Menu (décision fonctionnelle).
  const [activeTab, setActiveTab] = useState("menu");
  const publicIdRef = React.useRef(publicId);
  const cartIdRef = React.useRef(null);
  const cartPendingRef = React.useRef(null);
  const restoreRef = React.useRef(null);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/public/menu/${publicId}`),
      axios.get(`${API}/public/delivery-zones/${publicId}`),
    ]).then(([m, z]) => { setMenu(m.data); setZones(z.data); })
      .catch(() => toast.error("Restaurant introuvable"))
      .finally(() => setLoading(false));
  }, [publicId]);

  // D1.51: à chaque changement de restaurant, purge de l'état local (aucune
  // réutilisation des ids du restaurant précédent), puis restauration paresseuse
  // du panier/conversation persistés. restoreRef dédoublonne les exécutions
  // multiples de l'effet (StrictMode) pour un même publicId.
  useEffect(() => {
    publicIdRef.current = publicId;
    setCartId(null);
    cartIdRef.current = null;
    setCart(null);
    setConversationId(null);
    setSessionEpoch((e) => e + 1);
    setActiveTab("menu");
    if (!publicId) return;
    if (restoreRef.current?.id !== publicId) {
      restoreRef.current = { id: publicId, promise: restoreSession(publicId) };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publicId]);

  const restoreSession = async (pid) => {
    const storedCartId = localStorage.getItem(cartStorageKey(pid));
    const storedConvId = localStorage.getItem(convStorageKey(pid));
    if (storedConvId) setConversationId(storedConvId);
    if (!storedCartId) return;
    try {
      const { data } = await axios.get(`${API}/public/cart/${storedCartId}`);
      if (publicIdRef.current !== pid) return;
      if (data?.status === "open") {
        const cid = data.cart_id || storedCartId;
        setCartId(cid);
        cartIdRef.current = cid;
        setCart(data);
      } else {
        // Panier commandé/fermé confirmé par le serveur : session propre.
        purgeSessionKeys(pid);
        setConversationId(null);
      }
    } catch (e) {
      if (publicIdRef.current !== pid) return;
      if (e.response) {
        // 404 (ou 409 défensif) : panier inconnu / étranger / inutilisable.
        purgeSessionKeys(pid);
        setConversationId(null);
      } else {
        // Erreur réseau : on conserve les identifiants pour permettre une
        // nouvelle tentative au rechargement.
        toast.error("Impossible de restaurer votre panier. Vérifiez votre connexion.");
      }
    }
  };

  const ensureCart = () => {
    if (cartIdRef.current) return Promise.resolve(cartIdRef.current);
    if (cartPendingRef.current) return cartPendingRef.current;
    const pid = publicId;
    cartPendingRef.current = axios.post(`${API}/public/cart`, { restaurant_public_id: pid })
      .then(({ data }) => {
        const cid = data.cart_id;
        if (publicIdRef.current === pid) {
          setCartId(cid);
          cartIdRef.current = cid;
        }
        localStorage.setItem(cartStorageKey(pid), cid);
        return cid;
      })
      .finally(() => { cartPendingRef.current = null; });
    return cartPendingRef.current;
  };

  const applyCart = (cartView, cid) => {
    const id = cid || cartView?.cart_id;
    if (id) {
      setCartId(id);
      cartIdRef.current = id;
      localStorage.setItem(cartStorageKey(publicId), id);
    }
    if (cartView) setCart(cartView);
  };

  const purgeSessionKeys = (pid) => {
    localStorage.removeItem(cartStorageKey(pid));
    localStorage.removeItem(convStorageKey(pid));
  };

  const clearSession = () => {
    purgeSessionKeys(publicId);
    setCartId(null);
    cartIdRef.current = null;
    setCart(null);
    setConversationId(null);
    setCheckout(false);
    setSessionEpoch((e) => e + 1);
  };

  const handleConversationId = (cid) => {
    setConversationId(cid);
    if (cid) localStorage.setItem(convStorageKey(publicId), cid);
    else localStorage.removeItem(convStorageKey(publicId));
  };

  // D1.51 §3.5: après un 404/409 de mutation, on demande confirmation au
  // serveur (GET cart) avant de purger — un 404 peut venir d'une ligne
  // obsolète, pas forcément du panier lui-même.
  const handleCartMutationError = async (e, cid) => {
    const detail = formatApiErrorDetail(e.response?.data?.detail) || "Erreur";
    const status = e.response?.status;
    if (status !== 404 && status !== 409) { toast.error(detail); return; }
    toast.error(detail);
    if (!cid) return;
    try {
      const { data } = await axios.get(`${API}/public/cart/${cid}`);
      if (publicIdRef.current !== publicId) return;
      if (data?.status !== "open") clearSession();
      else applyCart(data, cid);
    } catch (ge) {
      if (ge.response && publicIdRef.current === publicId) clearSession();
    }
  };

  const startNewConversation = () => {
    localStorage.removeItem(convStorageKey(publicId));
    setConversationId(null);
    setSessionEpoch((e) => e + 1);
    const cid = cartIdRef.current;
    if (!cid) return;
    axios.get(`${API}/public/cart/${cid}`).then(({ data }) => {
      if (publicIdRef.current !== publicId) return;
      if (data?.status !== "open") clearSession();
    }).catch((e) => {
      if (e.response && publicIdRef.current === publicId) clearSession();
    });
  };

  const addToCart = async (item, optionIds, qty) => {
    let cid = null;
    try {
      cid = await ensureCart();
      const { data } = await axios.post(`${API}/public/cart/${cid}/items`, { item_id: item.id, quantity: qty, option_ids: optionIds });
      applyCart(data, cid);
      toast.success(`${item.name} ajouté au panier`);
      setItemModal(null);
    } catch (e) { handleCartMutationError(e, cid || cartIdRef.current); }
  };

  const removeLine = async (cartItemId) => {
    try {
      const { data } = await axios.delete(`${API}/public/cart/${cartId}/items/${cartItemId}`);
      applyCart(data, cartId);
    } catch (e) { handleCartMutationError(e, cartId); }
  };
  const changeQty = async (line, delta) => {
    const q = line.quantity + delta;
    if (q < 1) return removeLine(line.cart_item_id);
    try {
      const { data } = await axios.patch(`${API}/public/cart/${cartId}/items/${line.cart_item_id}`, { quantity: q });
      applyCart(data, cartId);
    } catch (e) { handleCartMutationError(e, cartId); }
  };

  if (loading) return <div className="min-h-screen grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;
  if (!menu) return <div className="min-h-screen grid place-items-center text-muted-foreground">Restaurant introuvable</div>;

  const itemCount = cart?.items?.reduce((s, i) => s + i.quantity, 0) || 0;
  // D1.52: thème widget — accent visuel du store, jamais une donnée privée
  // (primary_color provient du menu public depuis D1.50).
  const primaryColor = menu.restaurant.primary_color || "";
  const accentStyle = primaryColor ? { backgroundColor: primaryColor, borderColor: primaryColor } : undefined;

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="shrink-0 bg-[#0F172A] text-white">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <span className="w-12 h-12 rounded-xl bg-primary grid place-items-center overflow-hidden">
            {menu.restaurant.logo ? <img src={menu.restaurant.logo} alt="" className="w-full h-full object-cover" /> : <Bot className="w-6 h-6" />}
          </span>
          <div>
            <h1 className="font-heading text-xl font-bold" data-testid="store-name">{menu.restaurant.name}</h1>
            <p className="text-xs text-white/70">{menu.restaurant.welcome_message || "Commandez en ligne"}</p>
          </div>
        </div>
      </header>

      {/* Onglet Menu — cartes produits avec images */}
      <div className={activeTab === "menu" ? "flex-1 overflow-y-auto" : "hidden"}>
        <main className="max-w-3xl mx-auto px-4 py-6 space-y-8">
          {menu.categories.map((cat) => (
            <section key={cat.id} data-testid={`store-category-${cat.id}`}>
              <h2 className="font-heading text-lg font-semibold mb-3">{cat.name}</h2>
              <div className="space-y-3">
                {cat.items.map((it) => (
                  <div key={it.id} className="bg-card border border-border rounded-xl overflow-hidden flex items-stretch" data-testid={`store-item-${it.id}`}>
                    {it.image_url ? (
                      <img src={it.image_url} alt="" loading="lazy" className="w-28 shrink-0 self-stretch object-cover" />
                    ) : null}
                    <div className="flex flex-1 items-center justify-between gap-3 p-4">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium">{it.name}</p>
                        {it.description && <p className="text-sm text-muted-foreground line-clamp-2">{it.description}</p>}
                        <p className="font-mono text-sm font-semibold mt-1">{formatFCFA(it.price)}</p>
                      </div>
                      {it.available ? (
                        <Button size="sm" className="shrink-0" style={accentStyle} onClick={() => setItemModal(it)} data-testid={`store-add-${it.id}`}><Plus className="w-4 h-4" /></Button>
                      ) : (
                        <span className="text-xs text-red-500 font-medium shrink-0">Indisponible</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </main>
      </div>

      {/* Onglet Panier — vue synthèse; le checkout reste le parcours classique */}
      <div className={activeTab === "cart" ? "flex-1 overflow-y-auto" : "hidden"}>
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4" data-testid="cart-tab">
          <h2 className="font-heading text-lg font-semibold">Votre panier</h2>
          {!cart?.items?.length ? (
            <p className="text-sm text-muted-foreground" data-testid="cart-tab-empty">Votre panier est vide. Ajoutez des plats depuis le menu.</p>
          ) : (
            <>
              <div className="space-y-3 rounded-xl border border-border bg-card p-4">
                {cart.items.map((line) => (
                  <CartLine key={line.cart_item_id} line={line} onChangeQty={changeQty} onRemove={removeLine} testIdPrefix="cart-tab-line" />
                ))}
              </div>
              <div className="flex justify-between font-semibold">
                <span>Sous-total</span>
                <span className="font-mono" data-testid="cart-tab-subtotal">{formatFCFA(cart?.subtotal || 0)}</span>
              </div>
              <Button className="w-full" onClick={() => setCheckout(true)} data-testid="open-cart-btn">
                <ShoppingCart className="w-4 h-4 mr-1" /> Voir le panier
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Onglet Assistant — widget embarqué, resté monté (état messages préservé
          en changeant d'onglet grâce au masquage CSS) */}
      <div className={activeTab === "chat" ? "flex min-h-0 flex-1 flex-col p-4" : "hidden"}>
        <StoreChatWidget
          embedded
          restaurantPublicId={publicId}
          welcomeMessage={menu.restaurant.welcome_message || ""}
          cartId={cartId}
          conversationId={conversationId}
          onConversationChange={handleConversationId}
          onCartChange={applyCart}
          ensureCart={ensureCart}
          onNewConversation={startNewConversation}
          sessionEpoch={sessionEpoch}
        />
      </div>

      {/* Accès rapide à l'assistant depuis Menu/Panier (remplace le launcher
          overlay du widget en mode onglets — même testid, même rôle) */}
      {activeTab !== "chat" && (
        <Button
          onClick={() => setActiveTab("chat")}
          aria-label="Ouvrir l'assistant de commande"
          aria-expanded="false"
          data-testid="chat-launcher"
          className="fixed bottom-20 right-4 z-40 h-14 w-14 rounded-full shadow-xl sm:right-6"
          size="icon"
          style={accentStyle}
        >
          <MessageSquare className="w-6 h-6" />
        </Button>
      )}

      {/* Tabbar */}
      <nav className="shrink-0 border-t border-border bg-card" data-testid="store-tabs">
        <div className="max-w-3xl mx-auto grid grid-cols-3">
          {[
            ["menu", "Menu", <UtensilsCrossed key="i" className="w-5 h-5" />, null],
            ["cart", "Panier", <ShoppingCart key="i" className="w-5 h-5" />, itemCount > 0 ? itemCount : null],
            ["chat", "Assistant", <MessageSquare key="i" className="w-5 h-5" />, null],
          ].map(([id, label, icon, badge]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              data-testid={`store-tab-${id}`}
              aria-current={activeTab === id ? "page" : undefined}
              className={`relative flex flex-col items-center gap-0.5 py-2 text-xs font-medium ${activeTab === id ? "text-primary" : "text-muted-foreground"}`}
            >
              <span className="relative">
                {icon}
                {badge != null && (
                  <span
                    className="absolute -top-1.5 -right-2.5 min-w-[1.1rem] rounded-full px-1 text-[10px] font-bold leading-4 text-white text-center"
                    style={accentStyle || { backgroundColor: "hsl(var(--primary))" }}
                    data-testid="cart-tab-badge"
                  >{badge}</span>
                )}
              </span>
              {label}
            </button>
          ))}
        </div>
      </nav>

      {/* Item option modal */}
      {itemModal && <ItemOptionModal item={itemModal} onClose={() => setItemModal(null)} onAdd={addToCart} />}

      {/* Checkout */}
      {checkout && (
        <CheckoutDialog open={checkout} onOpenChange={setCheckout} cart={cart} cartId={cartId} zones={zones}
          onChangeQty={changeQty} onRemove={removeLine}
          onConfirmed={(o) => { setConfirmed(o); clearSession(); setActiveTab("menu"); }}
          onCartInvalid={clearSession} />
      )}

      {/* Confirmation */}
      <Dialog open={!!confirmed} onOpenChange={(v) => !v && setConfirmed(null)}>
        <DialogContent data-testid="order-confirmed-dialog">
          <DialogHeader className="sr-only">
            <DialogTitle>Commande confirmée</DialogTitle>
            <DialogDescription>Votre commande a bien été enregistrée.</DialogDescription>
          </DialogHeader>
          <div className="text-center py-4">
            <CheckCircle2 className="w-14 h-14 text-emerald-500 mx-auto mb-4" />
            <h2 className="font-heading text-xl font-bold">Commande confirmée !</h2>
            <p className="text-muted-foreground mt-2 text-sm">Votre numéro de commande est</p>
            <p className="font-mono text-2xl font-bold my-2" data-testid="confirmed-reference">{confirmed?.reference}</p>
            <p className="text-lg font-semibold">Total : {formatFCFA(confirmed?.total)}</p>
            <p className="text-sm text-muted-foreground mt-3">Le restaurant prépare votre commande. 🍽️</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
