import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Clock, ChefHat, CheckCircle2, Truck, PackageCheck, XCircle, Bell, Loader2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

const STATUS_META = {
  PENDING: { label: "En attente", color: "bg-amber-50 text-amber-600", dot: "bg-amber-500" },
  CONFIRMED: { label: "Confirmée", color: "bg-blue-50 text-blue-600", dot: "bg-blue-500" },
  PREPARING: { label: "En préparation", color: "bg-indigo-50 text-indigo-600", dot: "bg-indigo-500" },
  READY: { label: "Prête", color: "bg-emerald-50 text-emerald-600", dot: "bg-emerald-500" },
  OUT_FOR_DELIVERY: { label: "En livraison", color: "bg-cyan-50 text-cyan-600", dot: "bg-cyan-500" },
  DELIVERED: { label: "Livrée", color: "bg-green-50 text-green-700", dot: "bg-green-600" },
  CANCELLED: { label: "Annulée", color: "bg-red-50 text-red-600", dot: "bg-red-500" },
};
const FILTERS = [
  ["all", "Toutes"], ["PENDING", "En attente"], ["CONFIRMED", "Confirmées"], ["PREPARING", "Préparation"],
  ["READY", "Prêtes"], ["OUT_FOR_DELIVERY", "Livraison"], ["DELIVERED", "Livrées"], ["CANCELLED", "Annulées"],
];
const NEXT_ACTIONS = {
  PENDING: [["CONFIRMED", "Confirmer", CheckCircle2]],
  CONFIRMED: [["PREPARING", "Préparer", ChefHat]],
  PREPARING: [["READY", "Marquer prête", PackageCheck]],
  READY: [["OUT_FOR_DELIVERY", "Mettre en livraison", Truck], ["DELIVERED", "Marquer livrée", CheckCircle2]],
  OUT_FOR_DELIVERY: [["DELIVERED", "Marquer livrée", CheckCircle2]],
};

export default function OrdersPage() {
  const { user } = useAuth();
  const canCancel = user?.role === "RESTAURANT_OWNER" || user?.role === "RESTAURANT_MANAGER";
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const knownIds = useRef(new Set());
  const firstLoad = useRef(true);

  const load = useCallback(async (silent = false) => {
    try {
      const { data } = await api.get("/orders", { params: filter === "all" ? {} : { status: filter } });
      if (!firstLoad.current && !silent) {/* noop */}
      // new order detection (only when viewing all / pending)
      if (!firstLoad.current) {
        const fresh = data.filter((o) => !knownIds.current.has(o.id) && o.status === "PENDING");
        if (fresh.length) {
          fresh.forEach((o) => toast(`🔔 Nouvelle commande ${o.reference}`, { description: formatFCFA(o.total) }));
        }
      }
      data.forEach((o) => knownIds.current.add(o.id));
      firstLoad.current = false;
      setOrders(data);
    } catch (e) { if (!silent) toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { firstLoad.current = true; setLoading(true); load(); }, [filter, load]);

  // polling for new orders
  useEffect(() => {
    const t = setInterval(() => load(true), 15000);
    return () => clearInterval(t);
  }, [load]);

  const openDetail = async (o) => {
    setSelected(o); setDetail(null);
    try { const { data } = await api.get(`/orders/${o.id}`); setDetail(data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const changeStatus = async (o, status) => {
    try {
      await api.patch(`/orders/${o.id}/status`, { status });
      toast.success("Statut mis à jour.");
      load(true); if (selected?.id === o.id) openDetail(o);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const cancelOrder = async (o) => {
    try {
      await api.post(`/orders/${o.id}/cancel`, { reason: "Annulée depuis le dashboard" });
      toast.success("Commande annulée.");
      load(true); if (selected?.id === o.id) openDetail(o);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="orders-title">Commandes</h1>
          <p className="text-muted-foreground mt-1 text-sm">Suivez et gérez les commandes en temps réel.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => load()} data-testid="orders-refresh"><RefreshCw className="w-4 h-4 mr-1" /> Actualiser</Button>
      </div>

      <div className="flex gap-2 flex-wrap mb-5">
        {FILTERS.map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)} data-testid={`filter-${v}`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === v ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"}`}>
            {l}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>
      ) : orders.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground" data-testid="orders-empty">
          <Bell className="w-8 h-8 mx-auto mb-3 opacity-50" /> Aucune commande pour ce filtre.
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="orders-table">
              <thead className="bg-secondary/50 text-muted-foreground">
                <tr>
                  <th className="text-left font-medium px-5 py-3">Référence</th>
                  <th className="text-left font-medium px-5 py-3">Client</th>
                  <th className="text-left font-medium px-5 py-3">Type</th>
                  <th className="text-right font-medium px-5 py-3">Montant</th>
                  <th className="text-left font-medium px-5 py-3 pl-6">Statut</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const m = STATUS_META[o.status];
                  return (
                    <tr key={o.id} onClick={() => openDetail(o)} className="border-t border-border cursor-pointer hover:bg-secondary/30"
                      data-testid={`order-row-${o.reference}`}>
                      <td className="px-5 py-3 font-mono font-medium">{o.reference}</td>
                      <td className="px-5 py-3">{o.customer_snapshot?.first_name} {o.customer_snapshot?.last_name}</td>
                      <td className="px-5 py-3"><Badge variant="secondary">{o.order_type === "DELIVERY" ? "Livraison" : o.order_type === "PICKUP" ? "Retrait" : "Sur place"}</Badge></td>
                      <td className="px-5 py-3 text-right font-mono font-semibold">{formatFCFA(o.total)}</td>
                      <td className="px-5 py-3 pl-6">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${m.color}`}>
                          <span className={`w-2 h-2 rounded-full ${m.dot}`} /> {m.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detail dialog */}
      <Dialog open={!!selected} onOpenChange={(v) => !v && setSelected(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="order-detail-dialog">
          {!detail ? (
            <div className="grid place-items-center py-10"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="font-mono">{detail.reference}</DialogTitle>
                <DialogDescription>
                  {new Date(detail.created_at).toLocaleString("fr-FR")} ·{" "}
                  {detail.order_type === "DELIVERY" ? "Livraison" : detail.order_type === "PICKUP" ? "Retrait" : "Sur place"}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                <div className="rounded-xl bg-secondary/50 p-4">
                  <p className="font-semibold">{detail.customer_snapshot?.first_name} {detail.customer_snapshot?.last_name}</p>
                  <p className="text-sm text-muted-foreground">{detail.customer_snapshot?.phone}</p>
                  {detail.delivery_address && <p className="text-sm text-muted-foreground mt-1">📍 {detail.delivery_address} {detail.delivery_zone_name ? `(${detail.delivery_zone_name})` : ""}</p>}
                  {detail.customer_note && <p className="text-sm italic mt-2">« {detail.customer_note} »</p>}
                </div>

                <div className="space-y-2">
                  {detail.items.map((it, i) => (
                    <div key={i} className="flex justify-between text-sm" data-testid={`detail-item-${i}`}>
                      <div>
                        <span className="font-medium">{it.quantity} × {it.item_name_snapshot}</span>
                        {it.options?.length > 0 && <span className="text-muted-foreground"> — {it.options.map((o) => o.option_name_snapshot).join(", ")}</span>}
                      </div>
                      <span className="font-mono">{formatFCFA(it.line_total)}</span>
                    </div>
                  ))}
                </div>

                <div className="border-t border-border pt-3 space-y-1 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">Sous-total</span><span className="font-mono">{formatFCFA(detail.subtotal)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Livraison</span><span className="font-mono">{formatFCFA(detail.delivery_fee)}</span></div>
                  <div className="flex justify-between font-semibold text-base"><span>Total</span><span className="font-mono">{formatFCFA(detail.total)}</span></div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-2 pt-2">
                  {(NEXT_ACTIONS[detail.status] || []).map(([status, label, Icon]) => (
                    <Button key={status} size="sm" onClick={() => changeStatus(detail, status)} data-testid={`action-${status}`}>
                      <Icon className="w-4 h-4 mr-1" /> {label}
                    </Button>
                  ))}
                  {canCancel && ["PENDING", "CONFIRMED", "PREPARING"].includes(detail.status) && (
                    <Button size="sm" variant="outline" className="text-destructive" onClick={() => cancelOrder(detail)} data-testid="action-cancel">
                      <XCircle className="w-4 h-4 mr-1" /> Annuler
                    </Button>
                  )}
                  {["DELIVERED", "CANCELLED"].includes(detail.status) && (
                    <Badge variant="secondary">{STATUS_META[detail.status].label} — aucune action</Badge>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
