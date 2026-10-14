import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Plus, Pencil, Trash2, Loader2, MapPin } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

export default function DeliveryPage() {
  const { user } = useAuth();
  const canManage = user?.role === "RESTAURANT_OWNER" || user?.role === "RESTAURANT_MANAGER";
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => api.get("/delivery/zones").then(({ data }) => setZones(data))
    .catch((e) => toast.error(formatApiErrorDetail(e.response?.data?.detail))).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="delivery-title">Livraison & Zones</h1>
          <p className="text-muted-foreground mt-1 text-sm">Définissez vos zones de livraison et leurs frais.</p>
        </div>
        {canManage && <ZoneDialog onSaved={load} trigger={<Button data-testid="add-zone-btn"><Plus className="w-4 h-4 mr-1" /> Ajouter une zone</Button>} />}
      </div>

      {loading ? (
        <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>
      ) : zones.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground" data-testid="zones-empty">
          <MapPin className="w-8 h-8 mx-auto mb-3 opacity-50" /> Aucune zone de livraison.
        </div>
      ) : (
        <div className="space-y-3" data-testid="zones-list">
          {zones.map((z) => (
            <div key={z.id} className="bg-card border border-border rounded-xl px-5 py-4 flex items-center justify-between" data-testid={`zone-row-${z.id}`}>
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-lg bg-primary/10 text-primary grid place-items-center"><MapPin className="w-5 h-5" /></span>
                <div>
                  <p className="font-medium flex items-center gap-2">{z.name} {!z.active && <Badge variant="secondary" className="text-[10px]">Inactive</Badge>}</p>
                  {z.description && <p className="text-xs text-muted-foreground">{z.description}</p>}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono font-semibold">{formatFCFA(z.fee)}</span>
                {canManage && (
                  <>
                    <ZoneDialog zone={z} onSaved={load} trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-zone-${z.id}`}><Pencil className="w-4 h-4" /></Button>} />
                    <ConfirmDelete name={z.name} onConfirm={async () => { try { await api.delete(`/delivery/zones/${z.id}`); toast.success("Zone supprimée."); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } }}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-zone-${z.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ZoneDialog({ trigger, zone, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", fee: "", active: true });
  useEffect(() => {
    if (open) setForm(zone ? { name: zone.name, description: zone.description || "", fee: String(zone.fee), active: zone.active } : { name: "", description: "", fee: "", active: true });
  }, [open, zone]);
  const submit = async (e) => {
    e.preventDefault();
    const fee = parseInt(form.fee, 10);
    if (isNaN(fee) || fee < 0) { toast.error("Frais invalides"); return; }
    setSaving(true);
    try {
      if (zone) await api.patch(`/delivery/zones/${zone.id}`, { ...form, fee });
      else await api.post("/delivery/zones", { ...form, fee });
      toast.success(zone ? "Zone modifiée." : "Zone ajoutée.");
      setOpen(false); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent data-testid="zone-dialog">
        <DialogHeader><DialogTitle>{zone ? "Modifier la zone" : "Nouvelle zone"}</DialogTitle>
          <DialogDescription>Ex. Cocody — 1 000 FCFA de frais de livraison.</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nom de la zone</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="zone-name-input" /></div>
          <div className="space-y-2"><Label>Description</Label><Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="zone-description-input" /></div>
          <div className="space-y-2"><Label>Frais de livraison (FCFA)</Label><Input type="number" min={0} required value={form.fee} onChange={(e) => setForm((f) => ({ ...f, fee: e.target.value }))} data-testid="zone-fee-input" /></div>
          <div className="flex items-center justify-between"><Label>Active</Label><Switch checked={form.active} onCheckedChange={(v) => setForm((f) => ({ ...f, active: v }))} data-testid="zone-active-switch" /></div>
          <DialogFooter><Button type="submit" disabled={saving} data-testid="zone-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ConfirmDelete({ trigger, name, onConfirm }) {
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <AlertDialogContent>
        <AlertDialogHeader><AlertDialogTitle>Supprimer la zone ?</AlertDialogTitle>
          <AlertDialogDescription>« {name} » sera supprimée.</AlertDialogDescription></AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} data-testid="confirm-delete-zone">Supprimer</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
