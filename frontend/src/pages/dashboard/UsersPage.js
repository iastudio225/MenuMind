import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Loader2, UserPlus, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatApiErrorDetail, ROLE_LABELS } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

const ROLE_OPTIONS = [
  { value: "RESTAURANT_MANAGER", label: "Manager" },
  { value: "RESTAURANT_STAFF", label: "Serveur / Cuisine" },
  { value: "RESTAURANT_OWNER", label: "Propriétaire" },
];

export default function UsersPage() {
  const { user } = useAuth();
  const isOwner = user?.role === "RESTAURANT_OWNER";
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "RESTAURANT_STAFF" });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const createUser = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/users", form);
      toast.success("Utilisateur créé");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "RESTAURANT_STAFF" });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const changeRole = async (id, role) => {
    try {
      await api.patch(`/users/${id}`, { role });
      toast.success("Rôle mis à jour");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const toggleActive = async (id, active) => {
    try {
      await api.patch(`/users/${id}`, { active });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="users-title">Utilisateurs</h1>
          <p className="text-muted-foreground mt-1 text-sm">Gérez les accès et rôles de votre équipe.</p>
        </div>
        {isOwner && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button data-testid="invite-user-button"><UserPlus className="w-4 h-4 mr-1" /> Ajouter un membre</Button>
            </DialogTrigger>
            <DialogContent data-testid="create-user-dialog">
              <DialogHeader>
                <DialogTitle>Ajouter un membre</DialogTitle>
                <DialogDescription>Créez un accès pour un membre de votre équipe et attribuez-lui un rôle.</DialogDescription>
              </DialogHeader>
              <form onSubmit={createUser} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nom</Label>
                  <Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="new-user-name" />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input type="email" required value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} data-testid="new-user-email" />
                </div>
                <div className="space-y-2">
                  <Label>Mot de passe</Label>
                  <Input type="password" required minLength={6} value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} data-testid="new-user-password" />
                </div>
                <div className="space-y-2">
                  <Label>Rôle</Label>
                  <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
                    <SelectTrigger data-testid="new-user-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {ROLE_OPTIONS.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={saving} data-testid="submit-new-user">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Créer"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {!isOwner && (
        <div className="mb-6 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 px-4 py-3 text-sm flex items-center gap-2">
          <ShieldAlert className="w-4 h-4" /> Seul le propriétaire peut ajouter ou modifier des utilisateurs.
        </div>
      )}

      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        {loading ? (
          <div className="grid place-items-center py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="users-table">
              <thead className="bg-secondary/50 text-muted-foreground">
                <tr>
                  <th className="text-left font-medium px-5 py-3">Membre</th>
                  <th className="text-left font-medium px-5 py-3">Rôle</th>
                  <th className="text-left font-medium px-5 py-3">Statut</th>
                  {isOwner && <th className="text-right font-medium px-5 py-3">Actif</th>}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-border" data-testid={`user-row-${u.id}`}>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span className="w-9 h-9 rounded-full bg-primary/10 text-primary grid place-items-center font-semibold">
                          {u.name?.[0]?.toUpperCase()}
                        </span>
                        <div>
                          <p className="font-medium">{u.name}</p>
                          <p className="text-xs text-muted-foreground">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      {isOwner && u.id !== user.id && u.role !== "RESTAURANT_OWNER" ? (
                        <Select value={u.role} onValueChange={(v) => changeRole(u.id, v)}>
                          <SelectTrigger className="w-44 h-9" data-testid={`role-select-${u.id}`}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {ROLE_OPTIONS.filter((r) => r.value !== "RESTAURANT_OWNER").map((r) => (
                              <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <Badge variant="secondary">{ROLE_LABELS[u.role]}</Badge>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {u.active ? <span className="text-emerald-600">Actif</span> : <span className="text-muted-foreground">Désactivé</span>}
                    </td>
                    {isOwner && (
                      <td className="px-5 py-3 text-right">
                        {u.id !== user.id && u.role !== "RESTAURANT_OWNER" && (
                          <Switch checked={u.active} onCheckedChange={(v) => toggleActive(u.id, v)} data-testid={`active-switch-${u.id}`} />
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
