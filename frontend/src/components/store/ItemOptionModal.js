import React, { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Minus, Plus } from "lucide-react";
import { formatFCFA } from "@/lib/format";

// D1.52: déplacé tel quel depuis StoreFront.js (extraction prévue en D1.49).
// P1 logistique: la modale collecte km/poids quand le service les facture.
// Le prix affiché est une estimation ; le serveur reste la source de vérité.
export default function ItemOptionModal({ item, onClose, onAdd, portalContainer }) {
  const [selected, setSelected] = useState({});
  const [qty, setQty] = useState(1);
  const [distance, setDistance] = useState("");
  const [weight, setWeight] = useState("");

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

  const rules = item.pricing_rules || {};
  const needsDistance = Number(rules.per_km || 0) > 0;
  const needsWeight = Number(rules.per_kg || 0) > 0;
  const base = Number(rules.base ?? item.price ?? 0);
  const selectedKey = [...optionIds].sort().join("|");
  const matchedVariant = (item.variants || []).find((v) => v.key === selectedKey) || null;
  const variantDelta = matchedVariant ? Number(matchedVariant.price_delta || 0) : 0;
  const extraTotal = matchedVariant ? 0 : extra;
  const estimatedUnit = Math.max(
    Number(rules.min || 0),
    base + variantDelta
      + Math.round(Number(rules.per_km || 0) * Number(distance || 0))
      + Math.round(Number(rules.per_kg || 0) * Number(weight || 0)),
  );

  const booking = {};
  if (needsDistance) booking.distance_km = Number(distance || 0);
  if (needsWeight) booking.weight_kg = Number(weight || 0);

  const optionsValid = (item.options || []).every((g) => {
    const count = (selected[g.id] || []).length;
    if (g.required && count < Math.max(1, g.min)) return false;
    if (count < g.min) return false;
    return true;
  });
  const bookingValid = (!needsDistance || Number(distance) > 0) && (!needsWeight || Number(weight) > 0);
  const variantAvailable = !matchedVariant || matchedVariant.in_stock !== false;
  const valid = optionsValid && bookingValid && variantAvailable;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent
        portalContainer={portalContainer}
        overlayClassName={portalContainer ? "experience-inline-dialog-overlay" : undefined}
        className={`max-h-[90vh] overflow-y-auto${portalContainer ? " experience-inline-dialog-content" : ""}`}
        data-testid="item-option-modal"
      >
        <DialogHeader><DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>{item.description || "Personnalisez votre commande"}</DialogDescription></DialogHeader>
        <div className="space-y-5">
          {(needsDistance || needsWeight) && (
            <div className="grid grid-cols-2 gap-3" data-testid="booking-fields">
              {needsDistance && (
                <div className="space-y-1">
                  <Label htmlFor="booking-distance">Distance (km) *</Label>
                  <Input id="booking-distance" type="number" min="0" step="0.1" value={distance}
                    onChange={(e) => setDistance(e.target.value)} data-testid="booking-distance-input" />
                </div>
              )}
              {needsWeight && (
                <div className="space-y-1">
                  <Label htmlFor="booking-weight">Poids (kg) *</Label>
                  <Input id="booking-weight" type="number" min="0" step="0.1" value={weight}
                    onChange={(e) => setWeight(e.target.value)} data-testid="booking-weight-input" />
                </div>
              )}
              <p className="col-span-2 text-xs text-muted-foreground">
                Le prix final est calculé et confirmé par le serveur.
              </p>
            </div>
          )}
          {(item.options || []).map((g) => (
            <div key={g.id} data-testid={`store-group-${g.id}`}>
              <p className="font-medium text-sm mb-2">{g.name} {g.required && <span className="text-primary text-xs">(obligatoire)</span>}
                <span className="text-xs text-muted-foreground ml-1">{g.max === 1 ? "— 1 choix" : `— max ${g.max}`}</span></p>
              <div className="space-y-2">
                {g.choices.map((c) => {
                  const choiceOk = c.available && c.in_stock !== false;
                  return (
                    <label key={c.id} className={`flex items-center justify-between px-3 py-2 rounded-lg border cursor-pointer text-sm ${
                      (selected[g.id] || []).includes(c.id) ? "border-primary bg-primary/5" : "border-border"} ${!choiceOk ? "opacity-40 pointer-events-none" : ""}`}
                      data-testid={`store-choice-${c.id}`} onClick={() => choiceOk && toggle(g, c.id)}>
                      <span className="flex items-center gap-2">
                        {c.name}
                        {c.in_stock === false && <span className="text-[10px] font-medium text-red-500">Rupture</span>}
                        {c.available === false && <span className="text-[10px] font-medium text-muted-foreground">Indisponible</span>}
                      </span>
                      <span className="font-mono text-xs">{c.price_delta > 0 ? `+${formatFCFA(c.price_delta)}` : ""}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-center gap-4">
            <Button size="icon" variant="outline" onClick={() => setQty((q) => Math.max(1, q - 1))}><Minus className="w-4 h-4" /></Button>
            <span className="font-semibold text-lg w-8 text-center" data-testid="item-qty">{qty}</span>
            <Button size="icon" variant="outline" onClick={() => setQty((q) => q + 1)}><Plus className="w-4 h-4" /></Button>
          </div>
          {!variantAvailable && (
            <p className="text-sm font-medium text-red-500 text-center" data-testid="variant-out-of-stock">
              Cette combinaison est en rupture de stock.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button className="w-full" disabled={!valid}
            onClick={() => onAdd(item, optionIds, qty, (needsDistance || needsWeight) ? booking : undefined)}
            data-testid="confirm-add-item">
            Ajouter — {formatFCFA((estimatedUnit + extraTotal) * qty)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
