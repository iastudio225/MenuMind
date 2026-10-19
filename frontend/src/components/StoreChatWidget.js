import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Bot, Loader2, MessageSquare, Plus, RefreshCw, Send, ShoppingCart, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import ItemOptionModal from "@/components/store/ItemOptionModal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const FALLBACK_WELCOME = "Bonjour 👋 Je suis l'assistant de commande. Comment puis-je vous aider ?";

const ORDER_TYPE_LABELS = { DELIVERY: "Livraison", PICKUP: "À emporter" };

export default function StoreChatWidget({
  restaurantPublicId,
  welcomeMessage,
  cartId,
  conversationId,
  onConversationChange,
  onCartChange,
  ensureCart,
  onNewConversation,
  sessionEpoch = 0,
  // D1.52: embedded=true rend le panneau dans le flux de l'onglet Assistant
  // (pas de launcher ni de panneau overlay — le parent gère la navigation).
  embedded = false,
}) {
  const [open, setOpen] = useState(!embedded);
  const [messages, setMessages] = useState([]); // {role: "user"|"assistant", content, cart?}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); // {text, retryText, status} | null
  // D1.54: carte produit cliquée → modale options/quantité (même parcours que le menu public).
  const [itemModal, setItemModal] = useState(null);
  const sendingRef = useRef(false); // anti double-soumission (synchrone)
  const addingRef = useRef(false); // anti double-ajout depuis une carte
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading, error]);

  // D1.51: le parent bump cet epoch quand la session change (commande confirmée,
  // « nouvelle conversation » après 409) — l'historique local est alors purgé.
  useEffect(() => {
    setMessages([]);
    setError(null);
    setItemModal(null);
  }, [sessionEpoch]);

  const send = async (text, appendUser = true) => {
    const msg = (text || "").trim();
    if (!msg || sendingRef.current) return;
    sendingRef.current = true;
    setLoading(true);
    setError(null);
    if (appendUser) setMessages((m) => [...m, { role: "user", content: msg }]);
    try {
      // D1.51: panier partagé — le panier est créé paresseusement (ensureCart)
      // et son id transmis au backend qui lie la conversation dessus (D1.50).
      let cid = cartId;
      if (ensureCart) cid = await ensureCart();
      const body = { restaurant_public_id: restaurantPublicId, message: msg };
      if (conversationId) body.conversation_id = conversationId;
      if (cid) body.cart_id = cid;
      const { data } = await axios.post(`${API}/public/ai/chat`, body);
      if (!data || !data.conversation_id || !data.cart || !data.cart_id) {
        // Réponse malformée: on n'efface ni panier ni conversation valides.
        setError({ text: "Réponse inattendue de l'assistant. Réessayez.", retryText: msg, status: null });
        return;
      }
      onConversationChange?.(data.conversation_id);
      setMessages((m) => [...m, {
        role: "assistant",
        content: data.message || "",
        cart: data.cart || null,
        // D1.54: cartes produits du serveur (rétrocompatible: champ absent -> []).
        products: Array.isArray(data.products) ? data.products : [],
      }]);
      onCartChange?.(data.cart, data.cart_id);
    } catch (e) {
      // 429 (quota), 503 (provider) et erreurs réseau conservent panier et
      // conversation: l'utilisateur peut réessayer sans perte d'état.
      setError({
        text: formatApiErrorDetail(e.response?.data?.detail) || "Erreur de connexion. Vérifiez votre réseau.",
        retryText: msg,
        status: e.response?.status || null,
      });
    } finally {
      setLoading(false);
      sendingRef.current = false;
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    send(input, true);
  };

  // D1.54: ajout direct depuis une carte de la conversation — mêmes règles que
  // le menu public (panier créé paresseusement, serveur seul juge des prix,
  // options et disponibilité).
  const addFromCard = async (item, optionIds, qty) => {
    if (addingRef.current) return;
    addingRef.current = true;
    try {
      let cid = cartId;
      if (ensureCart) cid = await ensureCart();
      const { data } = await axios.post(`${API}/public/cart/${cid}/items`, {
        item_id: item.id,
        quantity: qty,
        option_ids: optionIds,
      });
      onCartChange?.(data, cid);
      setItemModal(null);
      toast.success(`${item.name} ajouté au panier`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Impossible d'ajouter ce produit. Réessayez.");
    } finally {
      addingRef.current = false;
    }
  };

  const onPanelKeyDown = (e) => {
    if (e.key === "Escape") setOpen(false);
  };

  if (!restaurantPublicId) return null;

  return (
    <>
      {/* Bouton flottant (mode overlay uniquement — en embedded, le parent
          rend son propre accès à l'assistant) */}
      {!embedded && (
        <Button
          onClick={() => setOpen((o) => !o)}
          aria-label={open ? "Fermer l'assistant de commande" : "Ouvrir l'assistant de commande"}
          aria-expanded={open}
          data-testid="chat-launcher"
          className="fixed bottom-24 right-4 z-40 h-14 w-14 rounded-full shadow-xl sm:bottom-6 sm:right-6"
          size="icon"
        >
          {open ? <X className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
        </Button>
      )}

      {/* Panneau de conversation */}
      {(embedded || open) && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="Assistant de commande"
          aria-modal="false"
          onKeyDown={onPanelKeyDown}
          data-testid="chat-panel"
          className={embedded
            ? "relative flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card"
            : "fixed inset-x-3 bottom-44 z-50 flex max-h-[70vh] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl sm:inset-auto sm:bottom-24 sm:right-6 sm:w-[24rem]"}
        >
          {/* En-tête */}
          <div className="flex items-center gap-3 border-b border-border bg-[#0F172A] px-4 py-3 text-white">
            <span className="w-9 h-9 rounded-full bg-primary grid place-items-center">
              <Bot className="w-5 h-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold truncate">Assistant de commande</p>
              <p className="text-xs text-white/70">Répond instantanément</p>
            </div>
            {!embedded && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Fermer l'assistant"
                onClick={() => setOpen(false)}
                className="h-8 w-8 text-white hover:bg-white/10 hover:text-white"
              >
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>

          {/* Messages */}
          <div
            className="flex-1 space-y-3 overflow-y-auto px-4 py-3"
            aria-live="polite"
            aria-label="Messages de la conversation"
            data-testid="chat-messages"
          >
            {messages.length === 0 && (
              <div
                className="rounded-xl bg-secondary/60 px-3 py-2 text-sm text-foreground"
                data-testid="chat-welcome"
              >
                {welcomeMessage || FALLBACK_WELCOME}
              </div>
            )}
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end" data-testid="chat-message-user">
                  <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground whitespace-pre-wrap">
                    {m.content}
                  </p>
                </div>
              ) : (
                <div key={i} className="space-y-2" data-testid="chat-message-assistant">
                  <div className="flex justify-start">
                    <p className="max-w-[85%] rounded-2xl rounded-bl-sm bg-secondary px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
                      {m.content}
                    </p>
                  </div>
                  {/* D1.54: cartes produits livrées par le backend (menu du jour,
                      recommandation, catalogue paginé) — rendues telles quelles. */}
                  {m.products && m.products.length > 0 && (
                    <div className="ml-1 space-y-2" data-testid="chat-products">
                      {m.products.map((p) => (
                        <div
                          key={p.id}
                          className="flex items-stretch overflow-hidden rounded-xl border border-border bg-background"
                          data-testid="chat-product"
                        >
                          {p.image_url ? (
                            <img src={p.image_url} alt="" loading="lazy" className="w-16 shrink-0 object-cover" />
                          ) : null}
                          <div className="flex min-w-0 flex-1 items-center justify-between gap-2 p-2.5">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium">{p.name}</p>
                              {p.description ? (
                                <p className="line-clamp-2 text-xs text-muted-foreground">{p.description}</p>
                              ) : null}
                              <p className="mt-0.5 font-mono text-xs font-semibold">{formatFCFA(p.price)}</p>
                            </div>
                            {p.available ? (
                              <Button
                                size="icon"
                                variant="outline"
                                className="h-8 w-8 shrink-0"
                                aria-label={`Ajouter ${p.name}`}
                                onClick={() => setItemModal(p)}
                                data-testid={`chat-product-add-${p.id}`}
                              >
                                <Plus className="w-4 h-4" />
                              </Button>
                            ) : (
                              <span
                                className="shrink-0 text-[11px] font-medium text-red-500"
                                data-testid={`chat-product-unavailable-${p.id}`}
                              >
                                Indisponible
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {m.cart && m.cart.items && m.cart.items.length > 0 && (
                    <div
                      className="ml-1 rounded-xl border border-border bg-background p-3 text-sm"
                      data-testid="chat-cart-card"
                    >
                      <p className="flex items-center gap-1.5 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                        <ShoppingCart className="w-3.5 h-3.5" /> Votre panier
                      </p>
                      <div className="mt-2 space-y-1">
                        {m.cart.items.map((line) => (
                          <div key={line.cart_item_id} className="flex justify-between gap-2">
                            <span className="min-w-0">
                              {line.quantity} × {line.name}
                              {line.options && line.options.length > 0 && (
                                <span className="block text-xs text-muted-foreground">
                                  {line.options.map((o) => o.name).join(", ")}
                                </span>
                              )}
                            </span>
                            <span className="font-mono whitespace-nowrap">{formatFCFA(line.line_total)}</span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-2 space-y-0.5 border-t border-border pt-2 text-xs">
                        {Number(m.cart.delivery_fee) > 0 && (
                          <div className="flex justify-between text-muted-foreground">
                            <span>Livraison</span>
                            <span className="font-mono">{formatFCFA(m.cart.delivery_fee)}</span>
                          </div>
                        )}
                        {m.cart.order_type && ORDER_TYPE_LABELS[m.cart.order_type] && (
                          <div className="flex justify-between text-muted-foreground">
                            <span>Mode</span>
                            <span>{ORDER_TYPE_LABELS[m.cart.order_type]}</span>
                          </div>
                        )}
                        <div className="flex justify-between font-semibold text-sm text-foreground">
                          <span>Total</span>
                          <span className="font-mono" data-testid="chat-cart-total">{formatFCFA(m.cart.total)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            )}
            {loading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="chat-loading">
                <Loader2 className="w-4 h-4 animate-spin" /> L'assistant est en train d'écrire…
              </div>
            )}
            {error && (
              <div
                className="flex items-center justify-between gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                data-testid="chat-error"
              >
                <span>{error.text}</span>
                <div className="flex shrink-0 items-center gap-1">
                  {error.status === 409 && onNewConversation && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7"
                      disabled={loading}
                      onClick={() => { onNewConversation(); setError(null); }}
                      data-testid="chat-new-conversation"
                    >
                      Nouvelle conversation
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7"
                    disabled={loading}
                    onClick={() => send(error.retryText, false)}
                    data-testid="chat-retry"
                  >
                    <RefreshCw className="w-3.5 h-3.5 mr-1" /> Réessayer
                  </Button>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Saisie */}
          <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-border p-3">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Votre message…"
              aria-label="Votre message"
              disabled={loading}
              maxLength={1000}
              data-testid="chat-input"
              className="flex-1"
            />
            <Button
              type="submit"
              size="icon"
              disabled={loading || !input.trim()}
              aria-label="Envoyer le message"
              data-testid="chat-send"
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </div>
      )}

      {/* D1.54: options/quantité d'une carte ajoutée depuis la conversation */}
      {itemModal && (
        <ItemOptionModal item={itemModal} onClose={() => setItemModal(null)} onAdd={addFromCard} />
      )}
    </>
  );
}
