import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2, Phone, ShoppingBag, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";

export default function CustomersPage() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/customers").then(({ data }) => setCustomers(data))
      .catch((e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)))
      .finally(() => setLoading(false));
  }, []);

  const openDetail = async (c) => {
    setOpen(true); setDetail(null);
    try { const { data } = await api.get(`/customers/${c.id}`); setDetail(data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const filtered = customers.filter((c) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return `${c.first_name} ${c.last_name} ${c.phone}`.toLowerCase().includes(q);
  });

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="customers-title">Clients</h1>
        <p className="text-muted-foreground mt-1 text-sm">Base clients de votre restaurant et historique de commandes.</p>
      </div>

      <div className="relative mb-5 max-w-sm">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Rechercher nom ou téléphone…" value={search}
          onChange={(e) => setSearch(e.target.value)} data-testid="customers-search" />
      </div>

      {loading ? (
        <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>
      ) : filtered.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground" data-testid="customers-empty">
          Aucun client pour le moment.
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="customers-table">
              <thead className="bg-secondary/50 text-muted-foreground">
                <tr>
                  <th className="text-left font-medium px-5 py-3">Client</th>
                  <th className="text-left font-medium px-5 py-3">Téléphone</th>
                  <th className="text-right font-medium px-5 py-3">Commandes</th>
                  <th className="text-right font-medium px-5 py-3">Total dépensé</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id} onClick={() => openDetail(c)} className="border-t border-border cursor-pointer hover:bg-secondary/30"
                    data-testid={`customer-row-${c.id}`}>
                    <td className="px-5 py-3 font-medium">{c.first_name} {c.last_name}</td>
                    <td className="px-5 py-3 text-muted-foreground">{c.phone}</td>
                    <td className="px-5 py-3 text-right">{c.orders_count}</td>
                    <td className="px-5 py-3 text-right font-mono font-semibold">{formatFCFA(c.total_spent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="customer-detail-dialog">
          {!detail ? (
            <div className="grid place-items-center py-10"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>{detail.first_name} {detail.last_name}</DialogTitle>
                <DialogDescription className="flex items-center gap-2"><Phone className="w-3.5 h-3.5" /> {detail.phone}</DialogDescription>
              </DialogHeader>
              <div className="flex gap-4 mb-2">
                <div className="flex-1 rounded-xl bg-secondary/50 p-3 text-center">
                  <p className="text-2xl font-bold font-heading">{detail.orders_count}</p>
                  <p className="text-xs text-muted-foreground">commandes</p>
                </div>
                <div className="flex-1 rounded-xl bg-secondary/50 p-3 text-center">
                  <p className="text-2xl font-bold font-heading">{formatFCFA(detail.total_spent)}</p>
                  <p className="text-xs text-muted-foreground">dépensé</p>
                </div>
              </div>
              <h3 className="font-semibold text-sm flex items-center gap-2 mt-2"><ShoppingBag className="w-4 h-4" /> Historique</h3>
              <div className="space-y-2">
                {(detail.orders || []).length === 0 && <p className="text-sm text-muted-foreground">Aucune commande.</p>}
                {(detail.orders || []).map((o) => (
                  <div key={o.id} className="flex justify-between items-center text-sm border border-border rounded-lg px-3 py-2">
                    <div>
                      <span className="font-mono font-medium">{o.reference}</span>
                      <span className="text-muted-foreground ml-2">{new Date(o.created_at).toLocaleDateString("fr-FR")}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{o.status}</Badge>
                      <span className="font-mono">{formatFCFA(o.total)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
