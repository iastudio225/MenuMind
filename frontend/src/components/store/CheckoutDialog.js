import React, { useMemo, useState } from "react";
import axios from "axios";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { formatFCFA } from "@/lib/format";
import CartLine from "@/components/store/CartLine";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const genKey = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));

// D1.52: déplacé depuis StoreFront.js (extraction prévue en D1.49). Parcours,
// testids et protections Idempotency-Key strictement inchangés — voir D1.51
// pour la purge (onCartInvalid) sur 404/409 et la conservation en cas d'erreur
// réseau.
export default function CheckoutDialog({ open, onOpenChange, cart, cartId, zones, onChangeQty, onRemove, onConfirmed, onCartInvalid }) {
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
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erreur lors de la commande");
      // D1.51: 404/409 = panier introuvable ou déjà commandé (confirmé par le
      // serveur) : purge de la session pour ne pas réutiliser ce panier.
      // Erreur réseau (pas de response) : identifiants et Idempotency-Key
      // conservés pour permettre la réessai existant.
      if (e.response?.status === 409 || e.response?.status === 404) onCartInvalid?.();
    }
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
              <CartLine key={line.cart_item_id} line={line} onChangeQty={onChangeQty} onRemove={onRemove} />
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
