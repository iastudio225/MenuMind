import React, { useEffect, useState, useCallback, useRef, useContext } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ChefHat, CheckCircle2, Truck, PackageCheck, XCircle, Bell, Loader2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { secteurConfig } from "@/lib/secteurs";
import { useAuth } from "@/context/AuthContext";
import { DashboardRestaurantContext } from "@/layouts/DashboardLayout";

const STATUS_COLORS = {
  PENDING: { color: "bg-amber-50 text-amber-600", dot: "bg-amber-500" },
  CONFIRMED: { color: "bg-blue-50 text-blue-600", dot: "bg-blue-500" },
  PREPARING: { color: "bg-indigo-50 text-indigo-600", dot: "bg-indigo-500" },
  READY: { color: "bg-emerald-50 text-emerald-600", dot: "bg-emerald-500" },
  OUT_FOR_DELIVERY: { color: "bg-cyan-50 text-cyan-600", dot: "bg-cyan-500" },
  DELIVERED: { color: "bg-green-50 text-green-700", dot: "bg-green-600" },
  CANCELLED: { color: "bg-red-50 text-red-600", dot: "bg-red-500" },
};
const ACTION_ICONS = { check: CheckCircle2, chef: ChefHat, package: PackageCheck, truck: Truck };

export default function OrdersPage() {
  const { user } = useAuth();
  const restaurant = useContext(DashboardRestaurantContext);
  const sector = secteurConfig(restaurant?.secteur);
  const canCancel = user?.role === "RESTAURANT_OWNER" || user?.role === "RESTAURANT_MANAGER";
  const statusMeta = (status) => ({
    ...(STATUS_COLORS[status] || {}),
    label: sector.statusLabels?.[status] || status,
  });
  const filters = [["all", "Toutes"], ...Object.entries(sector.statusLabels || {})];
  const orderTypeLabel = (type) => sector.orderTypeLabels?.[type] || type;
  const cap = (value) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : value);
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const knownIds = useRef(new Set());
  const firstLoad = useRef(true);

  const load = useCallback(async (silent = false) => {
    try {
      const { data } = await api.get("/orders", { params: { ...(filter === "all" ? {} : { status: filter }), page, page_size: 50 } });
      const items = Array.isArray(data) ? data : data.items;
      setTotal(Array.isArray(data) ? data.length : data.total);
      if (!firstLoad.current && !silent) {/* noop */}
      // new order detection (only when viewing all / pending)
      if (!firstLoad.current) {
        const fresh = items.filter((o) => !knownIds.current.has(o.id) && o.status === "PENDING");
        if (fresh.length) {
          fresh.forEach((o) => toast(`🔔 Nouvelle ${sector.orderNoun} ${o.reference}`, { description: formatFCFA(o.total) }));
        }
      }
      items.forEach((o) => knownIds.current.add(o.id));
      firstLoad.current = false;
      setOrders(items);
    } catch (e) { if (!silent) toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [filter, page, sector.orderNoun]);

  useEffect(() => { firstLoad.current = true; setPage(1); setLoading(true); load(); }, [filter, page, load]);

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
      toast.success(`${cap(sector.orderNoun)} annulée.`);
      load(true); if (selected?.id === o.id) openDetail(o);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="orders-title">{sector.ordersLabel}</h1>
          <p className="text-muted-foreground mt-1 text-sm">Suivez et gérez vos {sector.ordersLabel.toLowerCase()} en temps réel.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => load()} data-testid="orders-refresh"><RefreshCw className="w-4 h-4 mr-1" /> Actualiser</Button>
      </div>

      <div className="flex gap-2 flex-wrap mb-5">
        {filters.map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)} data-testid={`filter-${v}`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === v ? "bg-primary-ink text-white" : "bg-secondary text-muted-foreground hover:text-foreground"}`}>
            {l}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>
      ) : orders.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground" data-testid="orders-empty">
          <Bell className="w-8 h-8 mx-auto mb-3 opacity-50" /> Aucune {sector.orderNoun} pour ce filtre.
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
                  const m = statusMeta(o.status);
                  return (
                    <tr key={o.id} onClick={() => openDetail(o)} className="border-t border-border cursor-pointer hover:bg-secondary/30"
                      data-testid={`order-row-${o.reference}`}>
                      <td className="px-5 py-3 font-mono font-medium">{o.reference}</td>
                      <td className="px-5 py-3">{o.customer_snapshot?.first_name} {o.customer_snapshot?.last_name}</td>
                      <td className="px-5 py-3"><Badge variant="secondary">{orderTypeLabel(o.order_type)}</Badge></td>
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

      {!loading && total > 50 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <span className="text-muted-foreground">{(page - 1) * 50 + 1}–{Math.min(page * 50, total)} sur {total}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Précédent</Button>
            <Button variant="outline" size="sm" disabled={page * 50 >= total} onClick={() => setPage((p) => p + 1)}>Suivant</Button>
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
                  {orderTypeLabel(detail.order_type)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                <div className="rounded-xl bg-secondary/50 p-4">
                  <p className="font-semibold">{detail.customer_snapshot?.first_name} {detail.customer_snapshot?.last_name}</p>
                  <p className="text-sm text-muted-foreground">{detail.customer_snapshot?.phone}</p>
                  {detail.delivery_address && <p className="text-sm text-muted-foreground mt-1">📍 {detail.delivery_address} {detail.delivery_zone_name ? `(${detail.delivery_zone_name})` : ""}</p>}
                  {detail.customer_note && <p className="text-sm italic mt-2">« {detail.customer_note} »</p>}
                </div>

                {sector.value === "logistique" && (detail.pickup_address || detail.dropoff_address) && (
                  <div className="rounded-xl bg-secondary/50 p-4 text-sm" data-testid="order-trip">
                    <p className="font-semibold flex items-center gap-2"><Truck className="w-4 h-4" /> Trajet</p>
                    <p className="mt-1"><span className="text-muted-foreground">Ramassage :</span> {detail.pickup_address || "—"}</p>
                    <p><span className="text-muted-foreground">Livraison :</span> {detail.dropoff_address || detail.delivery_address || "—"}</p>
                  </div>
                )}

                <div className="space-y-2">
                  {detail.items.map((it, i) => (
                    <div key={i} className="flex justify-between text-sm" data-testid={`detail-item-${i}`}>
                      <div>
                        <span className="font-medium">{it.quantity} × {it.item_name_snapshot}</span>
                        {it.options?.length > 0 && <span className="text-muted-foreground"> — {it.options.map((o) => o.option_name_snapshot).join(", ")}</span>}
                        {it.variant_sku_snapshot && <span className="text-xs text-muted-foreground ml-2">SKU {it.variant_sku_snapshot}</span>}
                        {it.booking?.distance_km ? <span className="text-xs text-muted-foreground ml-2">· {it.booking.distance_km} km</span> : null}
                        {it.booking?.weight_kg ? <span className="text-xs text-muted-foreground ml-2">· {it.booking.weight_kg} kg</span> : null}
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
                  {(sector.statusActions?.[detail.status] || [])
                    .filter(([status]) => status !== "OUT_FOR_DELIVERY" || detail.order_type === "DELIVERY")
                    .map(([status, label, iconKey]) => {
                      const Icon = ACTION_ICONS[iconKey] || CheckCircle2;
                      return (
                        <Button key={status} size="sm" onClick={() => changeStatus(detail, status)} data-testid={`action-${status}`}>
                          <Icon className="w-4 h-4 mr-1" /> {label}
                        </Button>
                      );
                    })}
                  {canCancel && ["PENDING", "CONFIRMED", "PREPARING"].includes(detail.status) && (
                    <Button size="sm" variant="outline" className="text-destructive" onClick={() => cancelOrder(detail)} data-testid="action-cancel">
                      <XCircle className="w-4 h-4 mr-1" /> Annuler
                    </Button>
                  )}
                  {["DELIVERED", "CANCELLED"].includes(detail.status) && (
                    <Badge variant="secondary">{statusMeta(detail.status).label} — aucune action</Badge>
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
