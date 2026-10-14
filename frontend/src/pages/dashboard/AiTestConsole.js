import React, { useEffect, useRef, useState } from "react";
import { Bot, Loader2, RefreshCw, RotateCcw, Send, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";

const ORDER_TYPE_LABELS = { DELIVERY: "Livraison", PICKUP: "À emporter" };

export default function AiTestConsole() {
  const [restaurant, setRestaurant] = useState(null);
  const [messages, setMessages] = useState([]); // {role: "user"|"assistant", content, cart?}
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); // {text, retryText} | null
  const sendingRef = useRef(false); // anti double-soumission (synchrone)
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    api.get("/restaurants/me").then(({ data }) => setRestaurant(data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

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
      const body = { message: msg };
      if (conversationId) body.conversation_id = conversationId;
      const { data } = await api.post("/ai/test/chat", body);
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

  const resetConversation = () => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    if (inputRef.current) inputRef.current.focus();
  };

  return (
    <div className="max-w-3xl">
      <div className="flex flex-wrap items-center gap-3">
        <h1
          className="font-heading text-2xl sm:text-3xl font-bold tracking-tight"
          data-testid="ai-console-title"
        >
          Réceptionniste IA
        </h1>
        <span
          className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary"
          data-testid="ai-test-badge"
        >
          Console de test
        </span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground" data-testid="ai-console-description">
        Échangez directement avec votre agent de commande pour vérifier ses réponses.
        Ce canal est réservé à vos tests — les conversations de vos clients restent séparées.
      </p>
      {restaurant && (
        <p className="mt-1 text-xs text-muted-foreground" data-testid="ai-restaurant-name">
          Vous testez l'agent de <span className="font-medium text-foreground">{restaurant.name}</span>
        </p>
      )}

      <div className="mt-6 flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm" style={{ height: "min(640px, calc(100vh - 280px))" }}>
        {/* En-tête */}
        <div className="flex items-center justify-between gap-3 border-b border-border bg-[#0F172A] px-4 py-3 text-white">
          <div className="flex min-w-0 items-center gap-3">
            <span className="w-9 h-9 rounded-full bg-primary grid place-items-center">
              <Bot className="w-5 h-5" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">Votre réceptionniste</p>
              <p className="text-xs text-white/70">Mode test — utilise le menu réel</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetConversation}
            disabled={loading || (messages.length === 0 && !conversationId)}
            aria-label="Démarrer une nouvelle conversation de test"
            data-testid="ai-new-conversation"
            className="shrink-0 text-white hover:bg-white/10 hover:text-white"
          >
            <RotateCcw className="w-4 h-4 mr-1.5" /> Nouvelle conversation
          </Button>
        </div>

        {/* Messages */}
        <div
          className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
          aria-live="polite"
          aria-label="Messages de la conversation de test"
          data-testid="ai-chat-messages"
        >
          {messages.length === 0 && (
            <div
              className="rounded-xl bg-secondary/60 px-3 py-2 text-sm text-foreground"
              data-testid="ai-chat-welcome"
            >
              {restaurant?.widget?.welcome_message || "Bonjour 👋 Testez votre agent en écrivant un message ci-dessous."}
            </div>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end" data-testid="ai-message-user">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground whitespace-pre-wrap">
                  {m.content}
                </p>
              </div>
            ) : (
              <div key={i} className="space-y-2" data-testid="ai-message-assistant">
                <div className="flex justify-start">
                  <p className="max-w-[85%] rounded-2xl rounded-bl-sm bg-secondary px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
                    {m.content}
                  </p>
                </div>
                {m.cart && m.cart.items && m.cart.items.length > 0 && (
                  <div
                    className="ml-1 rounded-xl border border-border bg-background p-3 text-sm"
                    data-testid="ai-cart-card"
                  >
                    <p className="flex items-center gap-1.5 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                      <ShoppingCart className="w-3.5 h-3.5" /> Panier généré par l'agent
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
                        <span className="font-mono" data-testid="ai-cart-total">{formatFCFA(m.cart.total)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          )}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="ai-chat-loading">
              <Loader2 className="w-4 h-4 animate-spin" /> L'agent écrit…
            </div>
          )}
          {error && (
            <div
              className="flex items-center justify-between gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              data-testid="ai-chat-error"
            >
              <span>{error.text}</span>
              <Button
                variant="outline"
                size="sm"
                className="h-7 shrink-0"
                disabled={loading}
                onClick={() => send(error.retryText, false)}
                data-testid="ai-chat-retry"
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
            placeholder="Écrivez comme le ferait un client…"
            aria-label="Message de test"
            disabled={loading}
            maxLength={1000}
            data-testid="ai-chat-input"
            className="flex-1"
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim()}
            aria-label="Envoyer le message de test"
            data-testid="ai-chat-send"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
