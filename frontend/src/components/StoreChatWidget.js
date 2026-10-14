import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Bot, Loader2, MessageSquare, RefreshCw, Send, ShoppingCart, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const FALLBACK_WELCOME = "Bonjour 👋 Je suis l'assistant de commande. Comment puis-je vous aider ?";

const ORDER_TYPE_LABELS = { DELIVERY: "Livraison", PICKUP: "À emporter" };

export default function StoreChatWidget({ restaurantPublicId, welcomeMessage }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {role: "user"|"assistant", content, cart?}
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); // {text, retryText} | null
  const sendingRef = useRef(false); // anti double-soumission (synchrone)
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading, error]);

  const send = async (text, appendUser = true) => {
    const msg = (text || "").trim();
    if (!msg || sendingRef.current) return;
    sendingRef.current = true;
    setLoading(true);
    setError(null);
    if (appendUser) setMessages((m) => [...m, { role: "user", content: msg }]);
    try {
      const body = { restaurant_public_id: restaurantPublicId, message: msg };
      if (conversationId) body.conversation_id = conversationId;
      const { data } = await axios.post(`${API}/public/ai/chat`, body);
      setConversationId(data.conversation_id || null);
      setMessages((m) => [...m, { role: "assistant", content: data.message || "", cart: data.cart || null }]);
    } catch (e) {
      setError({
        text: formatApiErrorDetail(e.response?.data?.detail) || "Erreur de connexion. Vérifiez votre réseau.",
        retryText: msg,
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

  const onPanelKeyDown = (e) => {
    if (e.key === "Escape") setOpen(false);
  };

  if (!restaurantPublicId) return null;

  return (
    <>
      {/* Bouton flottant */}
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

      {/* Panneau de conversation */}
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="Assistant de commande"
          aria-modal="false"
          onKeyDown={onPanelKeyDown}
          data-testid="chat-panel"
          className="fixed inset-x-3 bottom-44 z-50 flex max-h-[70vh] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl sm:inset-auto sm:bottom-24 sm:right-6 sm:w-[24rem]"
        >
          {/* En-tête */}
          <div className="flex items-center gap-3 border-b border-border bg-[#0F172A] px-4 py-3 text-white">
            <span className="w-9 h-9 rounded-full bg-primary grid place-items-center">
              <Bot className="w-5 h-5" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">Assistant de commande</p>
              <p className="text-xs text-white/70">Répond instantanément</p>
            </div>
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
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 shrink-0"
                  disabled={loading}
                  onClick={() => send(error.retryText, false)}
                  data-testid="chat-retry"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1" /> Réessayer
                </Button>
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
    </>
  );
}
