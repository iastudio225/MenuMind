import React from "react";
import { Button } from "@/components/ui/button";
import { Minus, Plus, Trash2 } from "lucide-react";
import { formatFCFA } from "@/lib/format";

// D1.52: ligne de panier partagée entre l'onglet Panier et l'étape « panier »
// du CheckoutDialog (un seul moteur d'affichage pour qty/suppression).
export default function CartLine({ line, onChangeQty, onRemove, testIdPrefix = "cart-line" }) {
  return (
    <div className="flex items-center justify-between gap-2" data-testid={`${testIdPrefix}-${line.cart_item_id}`}>
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
  );
}
