import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import {
  Check, ChefHat, ChevronRight, CircleAlert, Clock3,
  MessageCircle, Plus, ShoppingBag, UtensilsCrossed,
} from "lucide-react";
import { toast } from "sonner";
import StoreChatWidget from "@/components/StoreChatWidget";
import ItemOptionModal from "@/components/store/ItemOptionModal";
import CartLine from "@/components/store/CartLine";
import CheckoutDialog from "@/components/store/CheckoutDialog";
import { Button } from "@/components/ui/button";
import { getVisibleExperienceCategories } from "@/lib/experienceMenu";
import { formatApiErrorDetail, formatFCFA } from "@/lib/format";
import "@/pages/ExperiencePage.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cartStorageKey = (pid) => `menumind:cart:${pid}`;
const convStorageKey = (pid) => `menumind:conv:${pid}`;
const FALLBACK_PRIMARY = "#E05638";
const FALLBACK_SECONDARY = "#0F172A";

function clearStoredSession(pid) {
  localStorage.removeItem(cartStorageKey(pid));
  localStorage.removeItem(convStorageKey(pid));
}

function validColor(value, fallback) {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value) ? value : fallback;
}

function useViewportHeight() {
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () => {
      const height = viewport?.height || window.innerHeight;
      document.documentElement.style.setProperty("--experience-viewport-height", `${height}px`);
    };
    update();
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      document.documentElement.style.removeProperty("--experience-viewport-height");
    };
  }, []);
}

export default function ExperiencePage() {
  const { publicId } = useParams();
  useViewportHeight();

  const [restaurant, setRestaurant] = useState(null);
  const [menu, setMenu] = useState(null);
  const [zones, setZones] = useState([]);
  const [cartId, setCartId] = useState(null);
  const [cart, setCart] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);
  const [activeView, setActiveView] = useState("home");
  const [selectedItem, setSelectedItem] = useState(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [screenElement, setScreenElement] = useState(null);

  const publicIdRef = useRef(publicId);
  const cartIdRef = useRef(null);
  const pendingCartRef = useRef(null);

  useEffect(() => {
    let alive = true;
    publicIdRef.current = publicId;
    setLoading(true);
    setLoadError("");
    setRestaurant(null);
    setMenu(null);
    setZones([]);
    setCart(null);
    setCartId(null);
    cartIdRef.current = null;
    setConversationId(null);
    setOrder(null);
    setActiveView("home");
    setSessionEpoch((value) => value + 1);

    Promise.all([
      axios.get(`${API}/public/menu/${encodeURIComponent(publicId)}`),
      axios.get(`${API}/public/delivery-zones/${encodeURIComponent(publicId)}`),
      axios.get(`${API}/restaurants/public/${encodeURIComponent(publicId)}`),
    ]).then(async ([menuResponse, zonesResponse, restaurantResponse]) => {
      if (!alive || publicIdRef.current !== publicId) return;
      const publicRestaurant = restaurantResponse.data || {};
      const menuRestaurant = menuResponse.data?.restaurant || {};
      setRestaurant({ ...menuRestaurant, ...publicRestaurant,
        widget: { ...(menuRestaurant.widget || {}), ...(publicRestaurant.widget || {}) },
        welcome_message: menuRestaurant.welcome_message || publicRestaurant.widget?.welcome_message || "",
        primary_color: menuRestaurant.primary_color || publicRestaurant.widget?.primary_color || "",
      });
      setMenu(menuResponse.data || { restaurant: menuRestaurant, categories: [] });
      setZones(Array.isArray(zonesResponse.data) ? zonesResponse.data : []);

      const storedConversation = localStorage.getItem(convStorageKey(publicId));
      if (storedConversation) setConversationId(storedConversation);
      const storedCart = localStorage.getItem(cartStorageKey(publicId));
      if (!storedCart) return;
      try {
        const { data } = await axios.get(`${API}/public/cart/${encodeURIComponent(storedCart)}`);
        if (!alive || publicIdRef.current !== publicId) return;
        if (data?.status === "open") {
          const id = data.cart_id || storedCart;
          cartIdRef.current = id;
          setCartId(id);
          setCart(data);
        } else {
          clearStoredSession(publicId);
          setConversationId(null);
        }
      } catch (error) {
        if (!alive || publicIdRef.current !== publicId) return;
        if (error.response) {
          clearStoredSession(publicId);
          setConversationId(null);
        } else {
          toast.error("Impossible de restaurer votre panier. Vérifiez votre connexion.");
        }
      }
    }).catch((error) => {
      if (!alive || publicIdRef.current !== publicId) return;
      setLoadError(formatApiErrorDetail(error.response?.data?.detail) || "Restaurant introuvable.");
    }).finally(() => {
      if (alive && publicIdRef.current === publicId) setLoading(false);
    });

    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publicId]);

  const ensureCart = useCallback(() => {
    if (cartIdRef.current) return Promise.resolve(cartIdRef.current);
    if (pendingCartRef.current) return pendingCartRef.current;
    const pid = publicId;
    pendingCartRef.current = axios.post(`${API}/public/cart`, { restaurant_public_id: pid })
      .then(({ data }) => {
        const id = data.cart_id;
        if (publicIdRef.current === pid) {
          cartIdRef.current = id;
          setCartId(id);
          setCart((current) => current || { cart_id: id, items: [], subtotal: 0, delivery_fee: 0, total: 0 });
        }
        localStorage.setItem(cartStorageKey(pid), id);
        return id;
      }).finally(() => { pendingCartRef.current = null; });
    return pendingCartRef.current;
  }, [publicId]);

  const applyCart = useCallback((view, id) => {
    const resolvedId = id || view?.cart_id;
    if (resolvedId) {
      cartIdRef.current = resolvedId;
      setCartId(resolvedId);
      localStorage.setItem(cartStorageKey(publicId), resolvedId);
    }
    if (view) setCart(view);
  }, [publicId]);

  const clearSession = useCallback(() => {
    clearStoredSession(publicId);
    cartIdRef.current = null;
    setCartId(null);
    setCart(null);
    setConversationId(null);
    setCheckoutOpen(false);
    setSessionEpoch((value) => value + 1);
  }, [publicId]);

  const handleConversationChange = useCallback((id) => {
    setConversationId(id);
    if (id) localStorage.setItem(convStorageKey(publicId), id);
    else localStorage.removeItem(convStorageKey(publicId));
  }, [publicId]);

  const handleCartError = async (error, id) => {
    const detail = formatApiErrorDetail(error.response?.data?.detail) || "Une erreur est survenue.";
    toast.error(detail);
    if (![404, 409].includes(error.response?.status) || !id) return;
    try {
      const { data } = await axios.get(`${API}/public/cart/${encodeURIComponent(id)}`);
      if (publicIdRef.current === publicId && data?.status === "open") applyCart(data, id);
      else if (publicIdRef.current === publicId) clearSession();
    } catch (checkError) {
      if (checkError.response && publicIdRef.current === publicId) clearSession();
    }
  };

  const addToCart = async (item, optionIds, quantity) => {
    let id = null;
    try {
      id = await ensureCart();
      const { data } = await axios.post(`${API}/public/cart/${encodeURIComponent(id)}/items`, {
        item_id: item.id, quantity, option_ids: optionIds || [],
      });
      applyCart(data, id);
      setSelectedItem(null);
      toast.success(`${item.name} ajouté au panier`);
    } catch (error) {
      await handleCartError(error, id || cartIdRef.current);
    }
  };

  const removeLine = async (lineId) => {
    const id = cartIdRef.current;
    if (!id) return;
    try {
      const { data } = await axios.delete(`${API}/public/cart/${encodeURIComponent(id)}/items/${encodeURIComponent(lineId)}`);
      applyCart(data, id);
    } catch (error) { await handleCartError(error, id); }
  };

  const changeQuantity = async (line, delta) => {
    if (line.quantity + delta < 1) return removeLine(line.cart_item_id);
    const id = cartIdRef.current;
    if (!id) return;
    try {
      const { data } = await axios.patch(`${API}/public/cart/${encodeURIComponent(id)}/items/${encodeURIComponent(line.cart_item_id)}`, {
        quantity: line.quantity + delta,
      });
      applyCart(data, id);
    } catch (error) { await handleCartError(error, id); }
  };

  const startNewConversation = () => {
    localStorage.removeItem(convStorageKey(publicId));
    setConversationId(null);
    setSessionEpoch((value) => value + 1);
    const id = cartIdRef.current;
    if (!id) return;
    axios.get(`${API}/public/cart/${encodeURIComponent(id)}`).then(({ data }) => {
      if (publicIdRef.current === publicId && data?.status !== "open") clearSession();
    }).catch((error) => {
      if (error.response && publicIdRef.current === publicId) clearSession();
    });
  };

  const finishOrder = (orderData) => {
    if (!orderData?.reference) return;
    setOrder(orderData);
    clearSession();
  };

  const primaryColor = validColor(restaurant?.primary_color || restaurant?.widget?.primary_color, FALLBACK_PRIMARY);
  const secondaryColor = validColor(restaurant?.widget?.secondary_color, FALLBACK_SECONDARY);
  const theme = useMemo(() => ({
    "--experience-primary": primaryColor,
    "--experience-secondary": secondaryColor,
  }), [primaryColor, secondaryColor]);
  const itemCount = cart?.items?.reduce((sum, line) => sum + Number(line.quantity || 0), 0) || 0;
  const visibleCategories = getVisibleExperienceCategories(menu?.categories);
  const allItems = visibleCategories.flatMap((category) => category.items);
  const featuredItems = allItems.filter((item) => item.available).slice(0, 3);

  if (loading) return <main className="experience-state" style={theme}><span className="experience-spinner" />Chargement du restaurant…</main>;
  if (loadError || !restaurant || !menu) return (
    <main className="experience-state" style={theme}>
      <CircleAlert aria-hidden="true" />
      <h1>Restaurant indisponible</h1>
      <p>{loadError || "Impossible de charger ce restaurant."}</p>
    </main>
  );

  return (
    <main className="experience-scene" style={theme} data-testid="experience-page">
      <div className="experience-device" aria-label={`Application de commande ${restaurant.name}`}>
        <div className="experience-screen" ref={setScreenElement}>
          <header className="experience-header">
            <div className="experience-brand">
              <div className="experience-logo">
                {restaurant.logo ? <img src={restaurant.logo} alt="" /> : <ChefHat aria-hidden="true" />}
              </div>
              <div className="experience-brand-copy">
                <p className="experience-eyebrow">COMMANDE EN LIGNE</p>
                <h1>{restaurant.name}</h1>
              </div>
            </div>
            <button className="experience-header-cart" onClick={() => setActiveView("cart")} aria-label={`Ouvrir le panier, ${itemCount} article${itemCount === 1 ? "" : "s"}`}>
              <ShoppingBag aria-hidden="true" />
              {itemCount > 0 && <span>{itemCount}</span>}
            </button>
          </header>

          <div className={`experience-content${activeView === "chat" ? " is-chat" : ""}`}>
            {activeView === "home" && (
              <section className="experience-home" aria-labelledby="experience-welcome-title">
                <div className="experience-welcome-card">
                  <span className="experience-welcome-icon"><UtensilsCrossed aria-hidden="true" /></span>
                  <p className="experience-eyebrow">BIENVENUE CHEZ</p>
                  <h2 id="experience-welcome-title">{restaurant.name}</h2>
                  <p>{restaurant.welcome_message || "Découvrez notre menu et passez commande en quelques instants."}</p>
                  <div className="experience-home-actions">
                    <Button onClick={() => setActiveView("menu")} data-testid="experience-browse-menu">Découvrir le menu <ChevronRight aria-hidden="true" /></Button>
                    <button className="experience-text-action" onClick={() => setActiveView("chat")}><MessageCircle aria-hidden="true" /> Commander en discutant</button>
                  </div>
                </div>
                {featuredItems.length > 0 && (
                  <div className="experience-featured">
                    <div className="experience-section-heading"><div><p className="experience-eyebrow">À DÉCOUVRIR</p><h2>Nos suggestions</h2></div><button onClick={() => setActiveView("menu")}>Tout le menu <ChevronRight aria-hidden="true" /></button></div>
                    <div className="experience-featured-list">
                      {featuredItems.map((item) => <ProductCard key={item.id} item={item} onSelect={setSelectedItem} />)}
                    </div>
                  </div>
                )}
              </section>
            )}

            {activeView === "menu" && (
              <section className="experience-menu" aria-label="Menu du restaurant">
                <div className="experience-page-title"><p className="experience-eyebrow">À LA CARTE</p><h2>Le menu</h2><p>Choisissez vos plats, vous pourrez ajuster votre commande ensuite.</p></div>
                {visibleCategories.length === 0 ? <EmptyState title="Le menu arrive bientôt" body="Aucun plat n’est disponible pour le moment." /> : visibleCategories.map((category) => (
                  <section className="experience-category" key={category.id}>
                    <h3>{category.name}</h3>
                    <div className="experience-menu-list">{(category.items || []).map((item) => <ProductCard key={item.id} item={item} onSelect={setSelectedItem} />)}</div>
                  </section>
                ))}
              </section>
            )}

            <section className={`experience-chat${activeView === "chat" ? "" : " experience-view-hidden"}`} aria-label="Conversation avec l’assistant" aria-hidden={activeView !== "chat"}>
                <StoreChatWidget
                  embedded
                  hideHeader
                  restaurantPublicId={publicId}
                  welcomeMessage={restaurant.welcome_message || "Bonjour 👋 Que vous ferait plaisir ?"}
                  cartId={cartId}
                  conversationId={conversationId}
                  onConversationChange={handleConversationChange}
                  onCartChange={applyCart}
                  onOrderCreated={finishOrder}
                  portalContainer={screenElement}
                  ensureCart={ensureCart}
                  onNewConversation={startNewConversation}
                  sessionEpoch={sessionEpoch}
                />
            </section>

            {activeView === "cart" && (
              <section className="experience-cart" aria-label="Votre panier">
                <div className="experience-page-title"><p className="experience-eyebrow">VOTRE SÉLECTION</p><h2>Votre panier</h2></div>
                {!cart?.items?.length ? (
                  <EmptyState title="Votre panier est vide" body="Ajoutez quelques plats du menu ou demandez conseil à notre assistant." action={<><Button variant="outline" onClick={() => setActiveView("menu")}>Voir le menu</Button><Button onClick={() => setActiveView("chat")}>Parler à l’assistant</Button></>} />
                ) : (
                  <>
                    <div className="experience-cart-lines">{cart.items.map((line) => <CartLine key={line.cart_item_id} line={line} onChangeQty={changeQuantity} onRemove={removeLine} testIdPrefix="experience-cart-line" />)}</div>
                    <div className="experience-cart-total"><span>Sous-total</span><strong>{formatFCFA(cart.subtotal)}</strong></div>
                    <p className="experience-cart-hint">Les frais de livraison seront calculés selon votre zone.</p>
                    <Button className="experience-checkout-button" onClick={() => setCheckoutOpen(true)} data-testid="experience-checkout">Continuer vers la commande <ChevronRight aria-hidden="true" /></Button>
                  </>
                )}
              </section>
            )}
          </div>

          <nav className="experience-nav" aria-label="Navigation de commande">
            <NavButton active={activeView === "home" || activeView === "menu"} label="Menu" onClick={() => setActiveView("menu")}><UtensilsCrossed aria-hidden="true" /></NavButton>
            <NavButton active={activeView === "chat"} label="Assistant" onClick={() => setActiveView("chat")}><MessageCircle aria-hidden="true" /></NavButton>
            <NavButton active={activeView === "cart"} label="Panier" count={itemCount} onClick={() => setActiveView("cart")}><ShoppingBag aria-hidden="true" /></NavButton>
          </nav>
          {order && <OrderConfirmation order={order} onContinue={() => { setOrder(null); setActiveView("menu"); }} />}
        </div>
      </div>

      {selectedItem && <ItemOptionModal item={selectedItem} onClose={() => setSelectedItem(null)} onAdd={addToCart} portalContainer={screenElement} />}
      {checkoutOpen && <CheckoutDialog open={checkoutOpen} onOpenChange={setCheckoutOpen} cart={cart} cartId={cartId} zones={zones} portalContainer={screenElement}
        onChangeQty={changeQuantity} onRemove={removeLine} onConfirmed={(createdOrder) => { setCheckoutOpen(false); finishOrder(createdOrder); }} onCartInvalid={clearSession} />}
    </main>
  );
}

function ProductCard({ item, onSelect }) {
  return (
    <article className="experience-product" data-testid={`experience-item-${item.id}`}>
      {item.image_url ? <img src={item.image_url} alt="" loading="lazy" /> : <div className="experience-product-placeholder"><UtensilsCrossed aria-hidden="true" /></div>}
      <div className="experience-product-info"><h3>{item.name}</h3>{item.description && <p>{item.description}</p>}{item.options?.length > 0 && <span className="experience-product-options">Personnalisable · {item.options.map((group) => group.name).join(", ")}</span>}<strong>{formatFCFA(item.price)}</strong>
        {item.available ? <button className="experience-add" onClick={() => onSelect(item)} aria-label={`Choisir ${item.name}`} data-testid={`experience-add-${item.id}`}><Plus aria-hidden="true" /></button> : <span className="experience-unavailable">Indisponible</span>}
      </div>
    </article>
  );
}

function EmptyState({ title, body, action }) {
  return <div className="experience-empty"><span><ShoppingBag aria-hidden="true" /></span><h3>{title}</h3><p>{body}</p>{action && <div className="experience-empty-actions">{action}</div>}</div>;
}

function NavButton({ active, label, count, onClick, children }) {
  return <button className={`experience-nav-button${active ? " active" : ""}`} onClick={onClick} aria-current={active ? "page" : undefined}>
    <span className="experience-nav-icon">{children}{count > 0 && <i>{count}</i>}</span><span>{label}</span>
  </button>;
}

function OrderConfirmation({ order, onContinue }) {
  const statusLabels = { PENDING: "En attente de prise en charge", CONFIRMED: "Confirmée", PREPARING: "En préparation", READY: "Prête", OUT_FOR_DELIVERY: "En livraison", COMPLETED: "Terminée" };
  return <div className="experience-confirmation-backdrop"><section className="experience-confirmation" role="status" aria-live="polite" data-testid="experience-order-confirmation">
    <span className="experience-confirmation-check"><Check aria-hidden="true" /></span><p className="experience-eyebrow">COMMANDE ENREGISTRÉE</p><h2>Merci pour votre commande !</h2>
    <p className="experience-confirmation-copy">Votre restaurant a bien reçu votre demande.</p>
    <div className="experience-order-reference"><span>Numéro de commande</span><strong data-testid="experience-order-reference">{order.reference}</strong></div>
    <div className="experience-order-total"><span>Total</span><strong>{formatFCFA(order.total)}</strong></div>
    <div className="experience-order-status"><Clock3 aria-hidden="true" /><span>{statusLabels[order.status] || order.status}</span></div>
    {order.tracking_token && <p className="experience-tracking-note">Conservez votre numéro de commande pour vos échanges avec le restaurant.</p>}
    <Button className="experience-confirmation-button" onClick={onContinue}>Retour au restaurant</Button>
  </section></div>;
}
