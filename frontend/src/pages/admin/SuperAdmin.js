import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2, CheckCircle2, PauseCircle, Wallet, ShoppingBag, LogOut,
  Plus, Loader2, Eye, Pencil, Trash2, KeyRound, Copy, XCircle,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import BrandLogo from "@/components/BrandLogo";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

function licenseExpired(expiresAt) {
  if (!expiresAt) return false;
  return expiresAt.slice(0, 10) < new Date().toISOString().slice(0, 10);
}

const LIMIT_FIELDS = [
  { key: "max_orders_per_month", label: "Commandes / mois (-1 = illimité)" },
  { key: "max_ai_conversations", label: "Conversations IA / mois (-1 = illimité)" },
  { key: "max_users", label: "Utilisateurs (-1 = illimité)" },
];
const BOOL_FIELDS = [
  { key: "whatsapp_enabled", label: "WhatsApp" },
  { key: "analytics_enabled", label: "Analytics" },
  { key: "custom_branding", label: "Branding custom" },
];

function PlanDialog({ open, onOpenChange, editing, onSaved, plans }) {
  const empty = { code: "", name: "", price: 0, currency: "FCFA",
    limits: { max_orders_per_month: 300, max_ai_conversations: 500, max_users: 2,
      whatsapp_enabled: false, analytics_enabled: false, custom_branding: false } };
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(editing ? { ...editing, limits: { ...empty.limits, ...(editing.limits || {}) } } : empty);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing]);

  const setLimit = (k, v) => setForm((f) => ({ ...f, limits: { ...f.limits, [k]: v } }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = {
      name: form.name,
      price: Number(form.price),
      currency: form.currency,
      limits: {
        ...form.limits,
        max_orders_per_month: Number(form.limits.max_orders_per_month),
        max_ai_conversations: Number(form.limits.max_ai_conversations),
        max_users: Number(form.limits.max_users),
      },
    };
    try {
      if (editing) {
        await api.patch(`/admin/plans/${editing.code}`, payload);
        toast.success("Plan mis à jour");
      } else {
        await api.post("/admin/plans", { ...payload, code: form.code.toUpperCase() });
        toast.success("Plan créé");
      }
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="plan-dialog" className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Modifier ${editing.code}` : "Nouveau plan"}</DialogTitle>
          <DialogDescription>
            {editing ? "Mettez à jour le prix et les limites de la licence." : "Ajoutez un plan au catalogue."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input required disabled={!!editing} value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="EXTRA" data-testid="plan-code" />
            </div>
            <div className="space-y-2">
              <Label>Nom</Label>
              <Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                data-testid="plan-name" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Prix (FCFA / mois)</Label>
              <Input required type="number" min="0" value={form.price}
                onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))} data-testid="plan-price" />
            </div>
          </div>
          <div className="space-y-3">
            <Label className="font-semibold">Limites</Label>
            {LIMIT_FIELDS.map((lf) => (
              <div key={lf.key} className="space-y-1">
                <Label className="text-xs text-muted-foreground">{lf.label}</Label>
                <Input type="number" value={form.limits[lf.key]}
                  onChange={(e) => setLimit(lf.key, e.target.value)} data-testid={`plan-limit-${lf.key}`} />
              </div>
            ))}
            <div className="flex flex-wrap gap-4 pt-1">
              {BOOL_FIELDS.map((bf) => (
                <label key={bf.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!form.limits[bf.key]}
                    onChange={(e) => setLimit(bf.key, e.target.checked)}
                    data-testid={`plan-limit-${bf.key}`} />
                  {bf.label}
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving} data-testid="plan-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : editing ? "Enregistrer" : "Créer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function SuperAdmin() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [restaurants, setRestaurants] = useState([]);
  const [plans, setPlans] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", owner_name: "", owner_email: "", owner_password: "", plan: "STARTER" });

  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [planEditing, setPlanEditing] = useState(null);
  const [planDelete, setPlanDelete] = useState(null);
  const [pwTarget, setPwTarget] = useState(null); // {id, name, email}
  const [pwValue, setPwValue] = useState("");
  const [pwSaving, setPwSaving] = useState(false);

  const load = async () => {
    try {
      const [m, r, p] = await Promise.all([
        api.get("/admin/metrics"), api.get("/admin/restaurants"), api.get("/admin/plans"),
      ]);
      setMetrics(m.data);
      setRestaurants(r.data);
      setPlans(p.data);
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

  const openDetail = async (id) => {
    try {
      const { data } = await api.get(`/admin/restaurants/${id}`);
      setDetail(data);
      setDetailOpen(true);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const openEdit = (r) => {
    setEditTarget(r);
    setEditForm({
      name: r.name || "", description: r.description || "", phone: r.phone || "",
      whatsapp: r.whatsapp || "", email: r.email || "", address: r.address || "",
      city: r.city || "", plan: r.plan || "STARTER",
      plan_activated_at: r.plan_activated_at ? r.plan_activated_at.slice(0, 10) : "",
      plan_expires_at: r.plan_expires_at ? r.plan_expires_at.slice(0, 10) : "",
    });
    setEditOpen(true);
  };

  const submitEdit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = {
      ...editForm,
      plan_activated_at: editForm.plan_activated_at || null,
      plan_expires_at: editForm.plan_expires_at || null,
    };
    try {
      await api.patch(`/admin/restaurants/${editTarget.id}`, payload);
      toast.success("Restaurant mis à jour");
      setEditOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    try {
      await api.delete(`/admin/restaurants/${deleteTarget.id}`);
      toast.success("Restaurant supprimé");
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const submitPasswordReset = async (e) => {
    e.preventDefault();
    setPwSaving(true);
    try {
      await api.patch(`/admin/users/${pwTarget.id}/password`, { password: pwValue });
      toast.success(`Mot de passe de ${pwTarget.name} réinitialisé`);
      setPwTarget(null);
      setPwValue("");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setPwSaving(false);
    }
  };

  const confirmPlanDelete = async () => {
    try {
      await api.delete(`/admin/plans/${planDelete.code}`);
      toast.success("Plan supprimé");
      setPlanDelete(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      setPlanDelete(null);
    }
  };

  const copyWidget = (publicId) => {
    const backend = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
    navigator.clipboard.writeText(
      `<script src="${backend}/widget.js"\n  data-restaurant="${publicId}"></script>`
    ).then(() => toast.success("Snippet du widget copié"));
  };

  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 border-b border-border bg-card flex items-center justify-between px-4 sm:px-8">
        <div className="flex items-center gap-2 font-heading font-bold text-lg">
          <BrandLogo size="lg" />
          MenuMind <span className="text-muted-foreground font-normal text-sm">· Super Admin</span>
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
                      {plans.map((p) => (
                        <SelectItem key={p.code} value={p.code}>{p.name} — {formatFCFA(p.price)}</SelectItem>
                      ))}
                      {plans.length === 0 && (
                        <>
                          <SelectItem value="STARTER">Starter</SelectItem>
                          <SelectItem value="BUSINESS">Business</SelectItem>
                          <SelectItem value="PRO">Pro</SelectItem>
                        </>
                      )}
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

        <Tabs defaultValue="restaurants" className="mt-2">
          <TabsList>
            <TabsTrigger value="restaurants" data-testid="admin-tab-restaurants">Restaurants</TabsTrigger>
            <TabsTrigger value="plans" data-testid="admin-tab-plans">Plans & licences</TabsTrigger>
          </TabsList>

          <TabsContent value="restaurants">
            <div className="bg-card border border-border rounded-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border font-semibold">Restaurants ({restaurants.length})</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="admin-restaurants-table">
                  <thead className="bg-secondary/50 text-muted-foreground">
                    <tr>
                      <th className="text-left font-medium px-5 py-3">Restaurant</th>
                      <th className="text-left font-medium px-5 py-3">Propriétaire</th>
                      <th className="text-left font-medium px-5 py-3">Licence</th>
                      <th className="text-left font-medium px-5 py-3">Statut</th>
                      <th className="text-right font-medium px-5 py-3">Actions</th>
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
                        <td className="px-5 py-3">
                          <Badge variant="secondary" data-testid={`tenant-plan-${i}`}>{r.plan}</Badge>
                          {r.plan_expires_at && (
                            licenseExpired(r.plan_expires_at) ? (
                              <Badge variant="destructive" className="ml-2" data-testid={`tenant-license-expired-${i}`}>Expirée</Badge>
                            ) : (
                              <span className="ml-2 text-xs text-muted-foreground">jusqu'au {r.plan_expires_at.slice(0, 10)}</span>
                            )
                          )}
                        </td>
                        <td className="px-5 py-3">
                          {r.status === "active" ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Actif</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-muted-foreground"><PauseCircle className="w-4 h-4" /> Suspendu</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-right space-x-1">
                          <Button size="sm" variant="ghost" onClick={() => openDetail(r.id)}
                            title="Détails" data-testid={`admin-detail-btn-${i}`}>
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => openEdit(r)}
                            title="Modifier" data-testid={`admin-edit-btn-${i}`}>
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button size="sm" variant={r.status === "active" ? "outline" : "default"}
                            onClick={() => toggleStatus(r.id, r.status)}
                            data-testid={`toggle-status-${i}`}>
                            {r.status === "active" ? "Suspendre" : "Réactiver"}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(r)}
                            title="Supprimer" className="text-destructive hover:text-destructive"
                            data-testid={`admin-delete-btn-${i}`}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="plans">
            <div className="bg-card border border-border rounded-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                <span className="font-semibold">Catalogue des plans ({plans.length})</span>
                <Button size="sm" onClick={() => { setPlanEditing(null); setPlanDialogOpen(true); }}
                  data-testid="plan-create-btn">
                  <Plus className="w-4 h-4 mr-1" /> Nouveau plan
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="admin-plans-table">
                  <thead className="bg-secondary/50 text-muted-foreground">
                    <tr>
                      <th className="text-left font-medium px-5 py-3">Plan</th>
                      <th className="text-left font-medium px-5 py-3">Prix / mois</th>
                      <th className="text-left font-medium px-5 py-3">Limites</th>
                      <th className="text-left font-medium px-5 py-3">Licences actives</th>
                      <th className="text-right font-medium px-5 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.map((p, i) => (
                      <tr key={p.code} className="border-t border-border" data-testid={`plan-row-${i}`}>
                        <td className="px-5 py-3">
                          <p className="font-medium">{p.name}</p>
                          <p className="text-xs text-muted-foreground">{p.code}</p>
                        </td>
                        <td className="px-5 py-3 font-mono">{formatFCFA(p.price)}</td>
                        <td className="px-5 py-3 text-xs text-muted-foreground">
                          {p.limits?.max_orders_per_month === -1 ? "cmd illimitées" : `${p.limits?.max_orders_per_month ?? 0} cmd`} ·
                          {" "}{p.limits?.max_ai_conversations === -1 ? "IA illimitée" : `${p.limits?.max_ai_conversations ?? 0} conv IA`} ·
                          {" "}{p.limits?.max_users === -1 ? "users illimités" : `${p.limits?.max_users ?? 0} users`}
                          {p.limits?.whatsapp_enabled && " · WhatsApp"}
                          {p.limits?.analytics_enabled && " · Analytics"}
                          {p.limits?.custom_branding && " · Branding"}
                        </td>
                        <td className="px-5 py-3" data-testid={`plan-assignments-${i}`}>{p.restaurants_count ?? 0}</td>
                        <td className="px-5 py-3 text-right space-x-1">
                          <Button size="sm" variant="ghost" title="Modifier"
                            onClick={() => { setPlanEditing(p); setPlanDialogOpen(true); }}
                            data-testid={`plan-edit-btn-${i}`}>
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button size="sm" variant="ghost" title="Supprimer"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setPlanDelete(p)} data-testid={`plan-delete-btn-${i}`}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>

      {/* Dialog détails */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent data-testid="admin-detail-dialog" className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{detail?.name || "Détails"}</DialogTitle>
            <DialogDescription>Fiche complète du restaurant.</DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div><p className="text-muted-foreground">Ville</p><p>{detail.city || "—"}</p></div>
                <div><p className="text-muted-foreground">Adresse</p><p>{detail.address || "—"}</p></div>
                <div><p className="text-muted-foreground">Téléphone</p><p>{detail.phone || "—"}</p></div>
                <div><p className="text-muted-foreground">WhatsApp</p><p>{detail.whatsapp || "—"}</p></div>
                <div><p className="text-muted-foreground">Email</p><p>{detail.email || "—"}</p></div>
                <div><p className="text-muted-foreground">Commandes</p><p>{detail.orders_count}</p></div>
                <div>
                  <p className="text-muted-foreground">Licence</p>
                  <p><Badge variant="secondary">{detail.plan}</Badge>
                    {detail.plan_activated_at && (
                      <span className="ml-2 text-xs text-muted-foreground">activée le {detail.plan_activated_at.slice(0, 10)}</span>
                    )}
                    {detail.plan_expires_at && (
                      licenseExpired(detail.plan_expires_at)
                        ? <Badge variant="destructive" className="ml-2">Expirée</Badge>
                        : <span className="ml-2 text-xs">jusqu'au {detail.plan_expires_at.slice(0, 10)}</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Widget public</p>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="text-xs bg-secondary rounded px-2 py-1">{detail.public_id}</code>
                    <Button size="sm" variant="ghost" onClick={() => copyWidget(detail.public_id)}
                      title="Copier le snippet" data-testid="admin-copy-widget">
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
              <div>
                <p className="text-muted-foreground mb-2">Comptes utilisateurs</p>
                {(detail.users || []).map((u) => (
                  <div key={u.id} className="flex items-center justify-between border-t border-border py-2">
                    <span>{u.name} <span className="text-muted-foreground">({u.email})</span></span>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{u.role}</Badge>
                      <Button size="sm" variant="ghost" title="Réinitialiser le mot de passe"
                        onClick={() => { setPwTarget({ id: u.id, name: u.name, email: u.email }); setPwValue(""); }}
                        data-testid={`reset-pw-btn-${u.id}`}>
                        <Lock className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dialog modification */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent data-testid="admin-edit-dialog" className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modifier {editTarget?.name}</DialogTitle>
            <DialogDescription>Identité, coordonnées et licence du restaurant.</DialogDescription>
          </DialogHeader>
          {editForm && (
            <form onSubmit={submitEdit} className="space-y-4">
              <div className="space-y-2"><Label>Nom</Label><Input required value={editForm.name}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} data-testid="edit-name" /></div>
              <div className="space-y-2"><Label>Description</Label><Input value={editForm.description}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} data-testid="edit-description" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2"><Label>Ville</Label><Input value={editForm.city}
                  onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value }))} data-testid="edit-city" /></div>
                <div className="space-y-2"><Label>Adresse</Label><Input value={editForm.address}
                  onChange={(e) => setEditForm((f) => ({ ...f, address: e.target.value }))} data-testid="edit-address" /></div>
                <div className="space-y-2"><Label>Téléphone</Label><Input value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))} data-testid="edit-phone" /></div>
                <div className="space-y-2"><Label>WhatsApp</Label><Input value={editForm.whatsapp}
                  onChange={(e) => setEditForm((f) => ({ ...f, whatsapp: e.target.value }))} data-testid="edit-whatsapp" /></div>
              </div>
              <div className="space-y-2"><Label>Email restaurant</Label><Input type="email" value={editForm.email}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))} data-testid="edit-email" /></div>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label className="inline-flex items-center gap-1"><KeyRound className="w-3 h-3" /> Plan (licence)</Label>
                  <Select value={editForm.plan} onValueChange={(v) => setEditForm((f) => ({ ...f, plan: v }))}>
                    <SelectTrigger data-testid="edit-plan"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {plans.map((p) => (
                        <SelectItem key={p.code} value={p.code}>{p.name} — {formatFCFA(p.price)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Activation licence</Label>
                  <Input type="date" value={editForm.plan_activated_at}
                    onChange={(e) => setEditForm((f) => ({ ...f, plan_activated_at: e.target.value }))}
                    data-testid="edit-plan-activated" />
                </div>
                <div className="space-y-2">
                  <Label>Expiration licence</Label>
                  <Input type="date" value={editForm.plan_expires_at}
                    onChange={(e) => setEditForm((f) => ({ ...f, plan_expires_at: e.target.value }))}
                    data-testid="edit-plan-expires" />
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={saving} data-testid="edit-submit">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Confirmation suppression restaurant */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent data-testid="admin-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer {deleteTarget?.name} ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le restaurant sera retiré de la plateforme (suppression douce) : plus visible,
              widget et vitrine désactivés. Ses commandes restent pour l'historique comptable.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="admin-delete-cancel">Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="admin-delete-confirm"
              className="bg-destructive text-white hover:bg-destructive/90">
              <Trash2 className="w-4 h-4 mr-1" /> Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog plan (création/édition) */}
      <PlanDialog open={planDialogOpen} onOpenChange={setPlanDialogOpen}
        editing={planEditing} onSaved={load} plans={plans} />

      {/* Confirmation suppression plan */}
      <AlertDialog open={!!planDelete} onOpenChange={(o) => !o && setPlanDelete(null)}>
        <AlertDialogContent data-testid="plan-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer le plan {planDelete?.code} ?</AlertDialogTitle>
            <AlertDialogDescription>
              {planDelete?.restaurants_count > 0
                ? `Ce plan est assigné à ${planDelete.restaurants_count} restaurant(s). Réassignez-les avant de supprimer.`
                : "Ce plan n'est assigné à aucun restaurant. Suppression définitive du catalogue."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="plan-delete-cancel">Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={confirmPlanDelete} disabled={planDelete?.restaurants_count > 0}
              data-testid="plan-delete-confirm"
              className="bg-destructive text-white hover:bg-destructive/90">
              <XCircle className="w-4 h-4 mr-1" /> Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog réinitialisation mot de passe */}
      <Dialog open={!!pwTarget} onOpenChange={(o) => { if (!o) { setPwTarget(null); setPwValue(""); } }}>
        <DialogContent data-testid="reset-pw-dialog">
          <DialogHeader>
            <DialogTitle>Réinitialiser le mot de passe</DialogTitle>
            <DialogDescription>
              {pwTarget?.name} ({pwTarget?.email}) — la session active sera déconnectée.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitPasswordReset} className="space-y-4">
            <div className="space-y-2">
              <Label>Nouveau mot de passe (min. 6 caractères)</Label>
              <Input type="password" required minLength={6} value={pwValue}
                onChange={(e) => setPwValue(e.target.value)} data-testid="reset-pw-input" />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={pwSaving} data-testid="reset-pw-submit">
                {pwSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Lock className="w-4 h-4 mr-1" /> Réinitialiser</>}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
