import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot, Building2, CheckCircle2, PauseCircle, Wallet, ShoppingBag, LogOut,
  Plus, Loader2, Shield,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

function Metric({ icon: Icon, label, value, testid }) {
  return (
    <div className="bg-card border border-border rounded-2xl p-6" data-testid={testid}>
      <span className="w-10 h-10 rounded-xl bg-primary/10 text-primary grid place-items-center mb-4"><Icon className="w-5 h-5" /></span>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold font-heading mt-1">{value}</p>
    </div>
  );
}

export default function SuperAdmin() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [restaurants, setRestaurants] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", owner_name: "", owner_email: "", owner_password: "", plan: "STARTER" });

  const load = async () => {
    try {
      const [m, r] = await Promise.all([api.get("/admin/metrics"), api.get("/admin/restaurants")]);
      setMetrics(m.data);
      setRestaurants(r.data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  useEffect(() => { load(); }, []);

  const toggleStatus = async (id, current) => {
    const status = current === "active" ? "suspended" : "active";
    try {
      await api.patch(`/admin/restaurants/${id}/status`, { status });
      toast.success(`Restaurant ${status === "active" ? "réactivé" : "suspendu"}`);
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const createRestaurant = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/admin/restaurants", form);
      toast.success("Restaurant créé");
      setOpen(false);
      setForm({ name: "", owner_name: "", owner_email: "", owner_password: "", plan: "STARTER" });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 border-b border-border bg-card flex items-center justify-between px-4 sm:px-8">
        <div className="flex items-center gap-2 font-heading font-bold text-lg">
          <span className="w-8 h-8 rounded-lg bg-[#0F172A] text-white grid place-items-center"><Shield className="w-4 h-4 text-primary" /></span>
          RestoIA <span className="text-muted-foreground font-normal text-sm">· Super Admin</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground hidden sm:inline">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={doLogout} data-testid="admin-logout"><LogOut className="w-4 h-4 mr-1" /> Déconnexion</Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-8 py-8">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="admin-title">Supervision SaaS</h1>
            <p className="text-muted-foreground mt-1 text-sm">Pilotez l'ensemble des restaurants de la plateforme.</p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button data-testid="admin-create-restaurant-btn"><Plus className="w-4 h-4 mr-1" /> Nouveau restaurant</Button>
            </DialogTrigger>
            <DialogContent data-testid="admin-create-dialog">
              <DialogHeader>
                <DialogTitle>Créer un restaurant</DialogTitle>
                <DialogDescription>Ajoutez un nouvel établissement et son compte propriétaire sur la plateforme.</DialogDescription>
              </DialogHeader>
              <form onSubmit={createRestaurant} className="space-y-4">
                <div className="space-y-2"><Label>Nom du restaurant</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="admin-new-name" /></div>
                <div className="space-y-2"><Label>Nom du propriétaire</Label><Input required value={form.owner_name} onChange={(e) => setForm((f) => ({ ...f, owner_name: e.target.value }))} data-testid="admin-new-owner-name" /></div>
                <div className="space-y-2"><Label>Email propriétaire</Label><Input type="email" required value={form.owner_email} onChange={(e) => setForm((f) => ({ ...f, owner_email: e.target.value }))} data-testid="admin-new-owner-email" /></div>
                <div className="space-y-2"><Label>Mot de passe</Label><Input type="password" required minLength={6} value={form.owner_password} onChange={(e) => setForm((f) => ({ ...f, owner_password: e.target.value }))} data-testid="admin-new-owner-password" /></div>
                <div className="space-y-2">
                  <Label>Plan</Label>
                  <Select value={form.plan} onValueChange={(v) => setForm((f) => ({ ...f, plan: v }))}>
                    <SelectTrigger data-testid="admin-new-plan"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="STARTER">Starter</SelectItem>
                      <SelectItem value="BUSINESS">Business</SelectItem>
                      <SelectItem value="PRO">Pro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={saving} data-testid="admin-submit-restaurant">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Créer"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {metrics && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            <Metric icon={Building2} label="Restaurants actifs" value={metrics.active_restaurants} testid="metric-active" />
            <Metric icon={PauseCircle} label="Suspendus" value={metrics.suspended_restaurants} testid="metric-suspended" />
            <Metric icon={Wallet} label="MRR estimé" value={formatFCFA(metrics.estimated_mrr)} testid="metric-mrr" />
            <Metric icon={ShoppingBag} label="Commandes traitées" value={metrics.total_orders} testid="metric-orders" />
          </div>
        )}

        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border font-semibold">Restaurants ({restaurants.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="admin-restaurants-table">
              <thead className="bg-secondary/50 text-muted-foreground">
                <tr>
                  <th className="text-left font-medium px-5 py-3">Restaurant</th>
                  <th className="text-left font-medium px-5 py-3">Propriétaire</th>
                  <th className="text-left font-medium px-5 py-3">Plan</th>
                  <th className="text-left font-medium px-5 py-3">Statut</th>
                  <th className="text-right font-medium px-5 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {restaurants.map((r, i) => (
                  <tr key={r.id} className="border-t border-border" data-testid={`admin-tenant-row-${i}`}>
                    <td className="px-5 py-3">
                      <p className="font-medium">{r.name}</p>
                      <p className="text-xs text-muted-foreground">{r.city || "—"} · {r.orders_count} cmd</p>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">{r.owner_email || "—"}</td>
                    <td className="px-5 py-3"><Badge variant="secondary">{r.plan}</Badge></td>
                    <td className="px-5 py-3">
                      {r.status === "active" ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Actif</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-muted-foreground"><PauseCircle className="w-4 h-4" /> Suspendu</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Button size="sm" variant={r.status === "active" ? "outline" : "default"}
                        onClick={() => toggleStatus(r.id, r.status)} data-testid={`toggle-status-${i}`}>
                        {r.status === "active" ? "Suspendre" : "Réactiver"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
