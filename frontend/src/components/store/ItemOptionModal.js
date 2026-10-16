import React, { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Minus, Plus } from "lucide-react";
import { formatFCFA } from "@/lib/format";

// D1.52: déplacé tel quel depuis StoreFront.js (extraction prévue en D1.49).
export default function ItemOptionModal({ item, onClose, onAdd }) {
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
