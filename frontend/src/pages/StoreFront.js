import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ShoppingCart, Plus, Minus, Trash2, Loader2, CheckCircle2, Bot, X,
} from "lucide-react";
import { toast } from "sonner";
import { formatFCFA } from "@/lib/format";
import StoreChatWidget from "@/components/StoreChatWidget";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const genKey = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));

export default function StoreFront() {
  const { publicId } = useParams();
  const [menu, setMenu] = useState(null);
  const [zones, setZones] = useState([]);
  const [cartId, setCartId] = useState(null);
  const [cart, setCart] = useState(null);
  const [itemModal, setItemModal] = useState(null);
  const [checkout, setCheckout] = useState(false);
  const [confirmed, setConfirmed] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/public/menu/${publicId}`),
      axios.get(`${API}/public/delivery-zones/${publicId}`),
    ]).then(([m, z]) => { setMenu(m.data); setZones(z.data); })
      .catch(() => toast.error("Restaurant introuvable"))
      .finally(() => setLoading(false));
  }, [publicId]);

  const ensureCart = async () => {
    if (cartId) return cartId;
    const { data } = await axios.post(`${API}/public/cart`, { restaurant_public_id: publicId });
    setCartId(data.cart_id);
    return data.cart_id;
  };

  const refreshCart = async (cid) => {
    const { data } = await axios.get(`${API}/public/cart/${cid}`);
    setCart(data);
  };

  const addToCart = async (item, optionIds, qty) => {
    try {
      const cid = await ensureCart();
      await axios.post(`${API}/public/cart/${cid}/items`, { item_id: item.id, quantity: qty, option_ids: optionIds });
      await refreshCart(cid);
      toast.success(`${item.name} ajouté au panier`);
      setItemModal(null);
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur"); }
  };

  const removeLine = async (cartItemId) => {
    await axios.delete(`${API}/public/cart/${cartId}/items/${cartItemId}`);
    refreshCart(cartId);
  };
  const changeQty = async (line, delta) => {
    const q = line.quantity + delta;
    if (q < 1) return removeLine(line.cart_item_id);
    await axios.patch(`${API}/public/cart/${cartId}/items/${line.cart_item_id}`, { quantity: q });
    refreshCart(cartId);
  };

  if (loading) return <div className="min-h-screen grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;
  if (!menu) return <div className="min-h-screen grid place-items-center text-muted-foreground">Restaurant introuvable</div>;

  const itemCount = cart?.items?.reduce((s, i) => s + i.quantity, 0) || 0;

  return (
    <div className="min-h-screen bg-background pb-28">
      {/* Header */}
      <header className="bg-[#0F172A] text-white">
        <div className="max-w-3xl mx-auto px-4 py-6 flex items-center gap-4">
          <span className="w-12 h-12 rounded-xl bg-primary grid place-items-center overflow-hidden">
            {menu.restaurant.logo ? <img src={menu.restaurant.logo} alt="" className="w-full h-full object-cover" /> : <Bot className="w-6 h-6" />}
          </span>
          <div>
            <h1 className="font-heading text-xl font-bold" data-testid="store-name">{menu.restaurant.name}</h1>
            <p className="text-xs text-white/70">{menu.restaurant.welcome_message || "Commandez en ligne"}</p>
          </div>
        </div>
      </header>

      {/* Menu */}
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-8">
        {menu.categories.map((cat) => (
          <section key={cat.id} data-testid={`store-category-${cat.id}`}>
            <h2 className="font-heading text-lg font-semibold mb-3">{cat.name}</h2>
            <div className="space-y-3">
              {cat.items.map((it) => (
                <div key={it.id} className="bg-card border border-border rounded-xl p-4 flex items-center justify-between gap-3" data-testid={`store-item-${it.id}`}>
                  <div className="flex-1">
                    <p className="font-medium">{it.name}</p>
                    {it.description && <p className="text-sm text-muted-foreground">{it.description}</p>}
                    <p className="font-mono text-sm font-semibold mt-1">{formatFCFA(it.price)}</p>
                  </div>
                  {it.available ? (
                    <Button size="sm" onClick={() => setItemModal(it)} data-testid={`store-add-${it.id}`}><Plus className="w-4 h-4" /></Button>
                  ) : (
                    <span className="text-xs text-red-500 font-medium">Indisponible</span>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}
      </main>

      {/* Cart bar */}
      {itemCount > 0 && (
        <div className="fixed bottom-0 inset-x-0 bg-card border-t border-border p-4">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <div className="text-sm"><span className="font-semibold">{itemCount}</span> article(s) · <span className="font-mono font-semibold">{formatFCFA(cart?.subtotal || 0)}</span></div>
            <Button onClick={() => setCheckout(true)} data-testid="open-cart-btn"><ShoppingCart className="w-4 h-4 mr-1" /> Voir le panier</Button>
          </div>
        </div>
      )}

      {/* Item option modal */}
      {itemModal && <ItemOptionModal item={itemModal} onClose={() => setItemModal(null)} onAdd={addToCart} />}

      {/* Checkout */}
      {checkout && (
        <CheckoutDialog open={checkout} onOpenChange={setCheckout} cart={cart} cartId={cartId} zones={zones}
          onChangeQty={changeQty} onRemove={removeLine} onConfirmed={(o) => { setConfirmed(o); setCheckout(false); setCart(null); setCartId(null); }} />
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

      {/* Assistant de commande */}
      <StoreChatWidget restaurantPublicId={publicId} welcomeMessage={menu.restaurant.welcome_message || ""} />
    </div>
  );
}

function ItemOptionModal({ item, onClose, onAdd }) {
  const [selected, setSelected] = useState({});
  const [qty, setQty] = useState(1);

  const toggle = (group, choiceId) => {
    setSelected((prev) => {
      const cur = prev[group.id] || [];
      if (group.max === 1) return { ...prev, [group.id]: [choiceId] };
      if (cur.includes(choiceId)) return { ...prev, [group.id]: cur.filter((x) => x !== choiceId) };
      if (cur.length >= group.max) return prev;
      return { ...prev, [group.id]: [...cur, choiceId] };
    });
  };

  const optionIds = Object.values(selected).flat();
  const extra = (item.options || []).flatMap((g) => g.choices).filter((c) => optionIds.includes(c.id)).reduce((s, c) => s + c.price_delta, 0);

  const valid = (item.options || []).every((g) => {
    const count = (selected[g.id] || []).length;
    if (g.required && count < Math.max(1, g.min)) return false;
    if (count < g.min) return false;
    return true;
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="item-option-modal">
        <DialogHeader><DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>{item.description || "Personnalisez votre commande"}</DialogDescription></DialogHeader>
        <div className="space-y-5">
          {(item.options || []).map((g) => (
            <div key={g.id} data-testid={`store-group-${g.id}`}>
              <p className="font-medium text-sm mb-2">{g.name} {g.required && <span className="text-primary text-xs">(obligatoire)</span>}
                <span className="text-xs text-muted-foreground ml-1">{g.max === 1 ? "— 1 choix" : `— max ${g.max}`}</span></p>
              <div className="space-y-2">
                {g.choices.map((c) => (
                  <label key={c.id} className={`flex items-center justify-between px-3 py-2 rounded-lg border cursor-pointer text-sm ${
                    (selected[g.id] || []).includes(c.id) ? "border-primary bg-primary/5" : "border-border"} ${!c.available ? "opacity-40 pointer-events-none" : ""}`}
                    data-testid={`store-choice-${c.id}`} onClick={() => c.available && toggle(g, c.id)}>
                    <span>{c.name}</span>
                    <span className="font-mono text-xs">{c.price_delta > 0 ? `+${formatFCFA(c.price_delta)}` : ""}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-center gap-4">
            <Button size="icon" variant="outline" onClick={() => setQty((q) => Math.max(1, q - 1))}><Minus className="w-4 h-4" /></Button>
            <span className="font-semibold text-lg w-8 text-center" data-testid="item-qty">{qty}</span>
            <Button size="icon" variant="outline" onClick={() => setQty((q) => q + 1)}><Plus className="w-4 h-4" /></Button>
          </div>
        </div>
        <DialogFooter>
          <Button className="w-full" disabled={!valid} onClick={() => onAdd(item, optionIds, qty)} data-testid="confirm-add-item">
            Ajouter — {formatFCFA((item.price + extra) * qty)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CheckoutDialog({ open, onOpenChange, cart, cartId, zones, onChangeQty, onRemove, onConfirmed }) {
  const [step, setStep] = useState("cart"); // cart | info | recap
  const [orderType, setOrderType] = useState("DELIVERY");
  const [zoneId, setZoneId] = useState("");
  const [form, setForm] = useState({ first_name: "", last_name: "", phone: "", email: "", address: "", customer_note: "" });
  const [placing, setPlacing] = useState(false);
  const [idemKey] = useState(genKey());

  const deliveryFee = useMemo(() => {
    if (orderType !== "DELIVERY") return 0;
    const z = zones.find((x) => x.id === zoneId);
    return z ? z.fee : 0;
  }, [orderType, zoneId, zones]);
  const total = (cart?.subtotal || 0) + deliveryFee;

  const place = async () => {
    if (!form.first_name || !form.phone) { toast.error("Prénom et téléphone requis"); setStep("info"); return; }
    if (orderType === "DELIVERY" && (!zoneId || !form.address)) { toast.error("Zone et adresse requises"); setStep("info"); return; }
    setPlacing(true);
    try {
      const { data } = await axios.post(`${API}/public/orders`, {
        cart_id: cartId, order_type: orderType, delivery_zone_id: orderType === "DELIVERY" ? zoneId : null,
        customer_note: form.customer_note,
        customer: { first_name: form.first_name, last_name: form.last_name, phone: form.phone, email: form.email, address: form.address },
      }, { headers: { "Idempotency-Key": idemKey } });
      onConfirmed(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur lors de la commande"); }
    finally { setPlacing(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="checkout-dialog">
        <DialogHeader><DialogTitle>Votre commande</DialogTitle>
          <DialogDescription>{step === "cart" ? "Vérifiez votre panier" : step === "info" ? "Vos informations" : "Récapitulatif"}</DialogDescription></DialogHeader>

        {step === "cart" && (
          <div className="space-y-3">
            {cart?.items?.map((line) => (
              <div key={line.cart_item_id} className="flex items-center justify-between gap-2" data-testid={`cart-line-${line.cart_item_id}`}>
                <div className="flex-1">
                  <p className="text-sm font-medium">{line.name}</p>
                  {line.options?.length > 0 && <p className="text-xs text-muted-foreground">{line.options.map((o) => o.name).join(", ")}</p>}
                  <p className="font-mono text-xs">{formatFCFA(line.line_total)}</p>
                </div>
                <div className="flex items-center gap-1">
                  <Button size="icon" variant="outline" className="h-7 w-7" onClick={() => onChangeQty(line, -1)}><Minus className="w-3 h-3" /></Button>
                  <span className="w-6 text-center text-sm">{line.quantity}</span>
                  <Button size="icon" variant="outline" className="h-7 w-7" onClick={() => onChangeQty(line, 1)}><Plus className="w-3 h-3" /></Button>
                  <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => onRemove(line.cart_item_id)}><Trash2 className="w-3 h-3" /></Button>
                </div>
              </div>
            ))}
            <div className="border-t border-border pt-2 flex justify-between font-semibold"><span>Sous-total</span><span className="font-mono">{formatFCFA(cart?.subtotal || 0)}</span></div>
            <Button className="w-full" disabled={!cart?.items?.length} onClick={() => setStep("info")} data-testid="checkout-next-info">Continuer</Button>
          </div>
        )}

        {step === "info" && (
          <div className="space-y-4">
            <div className="flex gap-2">
              {[["DELIVERY", "Livraison"], ["PICKUP", "À emporter"]].map(([v, l]) => (
                <button key={v} onClick={() => setOrderType(v)} data-testid={`order-type-${v}`}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border ${orderType === v ? "border-primary bg-primary/5 text-primary" : "border-border"}`}>{l}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label>Prénom *</Label><Input value={form.first_name} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} data-testid="checkout-firstname" /></div>
              <div className="space-y-1"><Label>Nom</Label><Input value={form.last_name} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} data-testid="checkout-lastname" /></div>
            </div>
            <div className="space-y-1"><Label>Téléphone *</Label><Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} placeholder="+225 07 00 00 00 00" data-testid="checkout-phone" /></div>
            {orderType === "DELIVERY" && (
              <>
                <div className="space-y-1"><Label>Zone de livraison *</Label>
                  <Select value={zoneId} onValueChange={setZoneId}>
                    <SelectTrigger data-testid="checkout-zone"><SelectValue placeholder="Choisir une zone" /></SelectTrigger>
                    <SelectContent>{zones.map((z) => <SelectItem key={z.id} value={z.id}>{z.name} — {formatFCFA(z.fee)}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1"><Label>Adresse *</Label><Input value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} data-testid="checkout-address" /></div>
              </>
            )}
            <div className="space-y-1"><Label>Note (optionnel)</Label><Textarea rows={2} value={form.customer_note} onChange={(e) => setForm((f) => ({ ...f, customer_note: e.target.value }))} data-testid="checkout-note" /></div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("cart")}>Retour</Button>
              <Button className="flex-1" onClick={() => setStep("recap")} data-testid="checkout-next-recap">Voir le récapitulatif</Button>
            </div>
          </div>
        )}

        {step === "recap" && (
          <div className="space-y-3">
            <div className="rounded-xl bg-secondary/50 p-3 text-sm">
              <p className="font-semibold">{form.first_name} {form.last_name}</p>
              <p className="text-muted-foreground">{form.phone}</p>
              <p className="text-muted-foreground">{orderType === "DELIVERY" ? `Livraison — ${form.address}` : "À emporter"}</p>
            </div>
            <div className="space-y-1 text-sm">
              {cart?.items?.map((l) => (
                <div key={l.cart_item_id} className="flex justify-between"><span>{l.quantity} × {l.name}</span><span className="font-mono">{formatFCFA(l.line_total)}</span></div>
              ))}
            </div>
            <div className="border-t border-border pt-2 space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Sous-total</span><span className="font-mono">{formatFCFA(cart?.subtotal || 0)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Livraison</span><span className="font-mono">{formatFCFA(deliveryFee)}</span></div>
              <div className="flex justify-between font-bold text-base"><span>Total</span><span className="font-mono" data-testid="recap-total">{formatFCFA(total)}</span></div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("info")}>Retour</Button>
              <Button className="flex-1" disabled={placing} onClick={place} data-testid="confirm-order-btn">
                {placing ? <Loader2 className="w-4 h-4 animate-spin" /> : "Confirmer la commande"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
