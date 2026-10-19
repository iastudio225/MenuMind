import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Loader2, Plus, Trash2, ChevronUp, ChevronDown, Search, Image as ImageIcon,
  Save, CalendarDays, Copy, RotateCcw, X,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur");

const DAYS = [
  ["monday", "Lundi"], ["tuesday", "Mardi"], ["wednesday", "Mercredi"], ["thursday", "Jeudi"],
  ["friday", "Vendredi"], ["saturday", "Samedi"], ["sunday", "Dimanche"],
];
const DAY_LABEL = Object.fromEntries(DAYS);

export default function WeeklyMenuPage() {
  const { user } = useAuth();
  const canManage = user?.role === "RESTAURANT_OWNER" || user?.role === "RESTAURANT_MANAGER";

  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [sel, setSel] = useState("monday");
  // Local drafts: day -> {item_ids, active}. A draft only exists after an edit
  // and survives day switches, so unsaved work is never lost silently.
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [copyOpen, setCopyOpen] = useState(false);
  const [copyGuard, setCopyGuard] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = async () => {
    try {
      const [w, m] = await Promise.all([api.get("/menu/weekly"), api.get("/menu/items")]);
      setDays(w.data.days);
      setCatalog(m.data);
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const catalogById = useMemo(
    () => Object.fromEntries(catalog.map((i) => [i.id, i])), [catalog]);

  const day = days.find((d) => d.day === sel) || {};
  const draft = drafts[sel] || null;
  const ids = draft ? draft.item_ids : (day.item_ids || []);
  const active = draft ? draft.active : !!day.active;
  const configured = draft ? true : !!day.configured;

  const isDirty = (key) => {
    const d = days.find((x) => x.day === key) || {};
    const dr = drafts[key];
    if (!dr) return false;
    return dr.item_ids.join(",") !== (d.item_ids || []).join(",")
      || dr.active !== !!d.active;
  };
  const dirty = isDirty(sel);

  // ids that no longer exist in the catalogue (deleted after planning) are
  // shown as a warning and dropped on the next save, never re-listed.
  const planned = ids.map((id) => catalogById[id]).filter(Boolean);
  const ghosts = ids.length - planned.length;

  // Browser guard: leave/refuse while a day still holds unsaved edits.
  useEffect(() => {
    const hasDirty = DAYS.some(([k]) => isDirty(k));
    const handler = (e) => {
      if (!hasDirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  });

  const edit = (fn) => setDrafts((prev) => {
    const base = prev[sel] || {
      // normalise on first edit: drop ids whose product was deleted
      item_ids: (day.item_ids || []).filter((id) => catalogById[id]),
      active: day.configured ? !!day.active : true,
    };
    return { ...prev, [sel]: fn({ ...base }) };
  });

  const move = (id, dir) => edit((b) => {
    const arr = [...b.item_ids];
    const i = arr.indexOf(id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= arr.length) return b;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    return { ...b, item_ids: arr };
  });

  const remove = (id) => edit((b) => ({ ...b, item_ids: b.item_ids.filter((x) => x !== id) }));
  const toggleActive = () => edit((b) => ({ ...b, active: !b.active }));
  const addItems = (newIds) => {
    edit((b) => ({ ...b, item_ids: [...b.item_ids, ...newIds] }));
    setAddOpen(false);
    toast.success(`${newIds.length} produit(s) ajouté(s) au brouillon.`);
  };

  const clearDraft = () => setDrafts((prev) => {
    const { [sel]: gone, ...rest } = prev;
    return rest;
  });

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const { data } = await api.put(`/menu/weekly/${sel}`,
        { item_ids: draft.item_ids, active: draft.active });
      setDays((prev) => prev.map((d) => (d.day === sel ? data : d)));
      clearDraft();
      toast.success(`Menu du ${DAY_LABEL[sel]} enregistré.`);
    } catch (e) { err(e); }  // draft kept: nothing is lost on failure
    finally { setSaving(false); }
  };

  const reset = () => { clearDraft(); toast.info("Modifications annulées."); };

  const copyFrom = async (source) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/menu/weekly/${sel}/copy-from/${source}`);
      setDays((prev) => prev.map((d) => (d.day === sel ? data : d)));
      clearDraft();
      setCopyOpen(false);
      toast.success(`Menu copié de ${DAY_LABEL[source]} vers ${DAY_LABEL[sel]}.`);
    } catch (e) { err(e); }
    finally { setBusy(false); }
  };

  const deleteConfig = async () => {
    setBusy(true);
    try {
      await api.delete(`/menu/weekly/${sel}`);
      setDays((prev) => prev.map((d) => (d.day === sel
        ? { day: sel, configured: false, active: false, item_ids: [], items: [] }
        : d)));
      clearDraft();
      setDeleteOpen(false);
      toast.success("Configuration du jour supprimée.");
    } catch (e) { err(e); }
    finally { setBusy(false); }
  };

  const openCopy = () => { if (dirty) setCopyGuard(true); else setCopyOpen(true); };
  const locked = saving || busy;

  if (loading) return <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2" data-testid="weekly-title">
          <CalendarDays className="w-7 h-7 text-primary" /> Menu hebdomadaire
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Programmation du menu du jour, du lundi au dimanche. Les produits restent ceux du catalogue.
        </p>
      </div>

      {/* ===== Day selector ===== */}
      <div className="flex gap-2 flex-wrap mb-5" data-testid="weekly-day-selector">
        {DAYS.map(([key, label]) => {
          const d = days.find((x) => x.day === key) || {};
          const configuredDay = drafts[key] ? true : !!d.configured;
          const on = drafts[key] ? drafts[key].active : !!d.active;
          const dayDirty = isDirty(key);
          return (
            <button key={key} onClick={() => setSel(key)} disabled={locked}
              data-testid={`week-day-${key}`}
              className={`px-3.5 py-2 rounded-xl text-sm font-medium border transition-colors flex items-center gap-2 disabled:opacity-60 ${
                sel === key ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card border-border hover:bg-secondary"}`}>
              {dayDirty && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" title="Modifications non enregistrées" />}
              {label}
              {configuredDay && (
                <span className={`w-2 h-2 rounded-full ${on ? "bg-emerald-500" : "bg-amber-500"}`}
                  title={on ? "Menu actif" : "Menu désactivé"} />
              )}
            </button>
          );
        })}
      </div>

      {/* ===== Selected day panel ===== */}
      <div className="bg-card border border-border rounded-2xl p-5 space-y-5" data-testid="weekly-day-panel">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="font-heading text-xl font-semibold" data-testid="weekly-day-title">{DAY_LABEL[sel]}</h2>
              {!configured && <Badge variant="secondary" data-testid="weekly-state-none">Non configuré</Badge>}
              {configured && planned.length === 0 && <Badge variant="outline" data-testid="weekly-state-empty">Menu vide</Badge>}
              {configured && !active && <Badge variant="destructive" data-testid="weekly-state-off">Désactivé</Badge>}
              {dirty && <Badge className="bg-amber-50 text-amber-600 border-0" data-testid="weekly-dirty">Modifications non enregistrées</Badge>}
            </div>
            <p className="text-xs text-muted-foreground">
              {!configured
                ? "Aucun menu n'est configuré pour ce jour."
                : active
                  ? "Ce menu est proposé aux clients pour ce jour."
                  : "Ce jour a un menu, mais il est masqué aux clients."}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {canManage && (
              <label className="flex items-center gap-2 text-sm font-medium mr-2">
                Actif
                <Switch checked={active} disabled={locked} onCheckedChange={toggleActive} data-testid="weekly-active-switch" />
              </label>
            )}
            {canManage && dirty && (
              <Button variant="outline" size="sm" onClick={reset} disabled={locked} data-testid="weekly-reset">
                <RotateCcw className="w-4 h-4 mr-1" /> Réinitialiser
              </Button>
            )}
            {canManage && dirty && (
              <Button size="sm" onClick={save} disabled={locked} data-testid="weekly-save">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
                Enregistrer
              </Button>
            )}
          </div>
        </div>

        {canManage && (
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(true)} disabled={locked} data-testid="weekly-add-btn">
              <Plus className="w-4 h-4 mr-1" /> Ajouter des produits
            </Button>
            <Button variant="outline" size="sm" onClick={openCopy} disabled={locked} data-testid="weekly-copy-btn">
              <Copy className="w-4 h-4 mr-1" /> Copier depuis…
            </Button>
            {day.configured && (
              <Button variant="outline" size="sm" onClick={() => setDeleteOpen(true)} disabled={locked}
                className="text-destructive hover:text-destructive" data-testid="weekly-delete-config">
                <Trash2 className="w-4 h-4 mr-1" /> Supprimer la configuration
              </Button>
            )}
          </div>
        )}

        {/* Planned products */}
        {planned.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground" data-testid="weekly-empty">
            {configured
              ? "Menu vide — ajoutez des produits depuis le catalogue."
              : "Non configuré — ajoutez des produits pour créer le menu de ce jour."}
          </div>
        ) : (
          <div className="divide-y divide-border" data-testid="weekly-planned-list">
            {planned.map((it) => (
              <div key={it.id} className="flex items-center gap-3 py-3 flex-wrap" data-testid={`planned-row-${it.id}`}>
                <div className="w-10 h-10 rounded-lg bg-secondary grid place-items-center overflow-hidden shrink-0">
                  {it.image_url ? <img src={it.image_url} alt="" className="w-full h-full object-cover" />
                    : <ImageIcon className="w-4 h-4 text-muted-foreground" />}
                </div>
                <div className="flex-1 min-w-[140px]">
                  <p className="font-medium flex items-center gap-2 flex-wrap">
                    {it.name}
                    {!it.active && <Badge variant="secondary" className="text-[10px]">Inactif</Badge>}
                    {!it.available && <Badge variant="destructive" className="text-[10px]">Rupture</Badge>}
                  </p>
                  {it.description && <p className="text-xs text-muted-foreground truncate max-w-xs">{it.description}</p>}
                </div>
                <span className="font-mono text-sm font-semibold w-24 text-right">{formatFCFA(it.price)}</span>
                {canManage && (
                  <div className="flex items-center gap-1">
                    <Button size="icon" variant="ghost" className="h-8 w-8" disabled={locked}
                      onClick={() => move(it.id, -1)} data-testid={`move-up-${it.id}`}>
                      <ChevronUp className="w-4 h-4" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8" disabled={locked}
                      onClick={() => move(it.id, 1)} data-testid={`move-down-${it.id}`}>
                      <ChevronDown className="w-4 h-4" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" disabled={locked}
                      onClick={() => remove(it.id)} data-testid={`remove-planned-${it.id}`}>
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {ghosts > 0 && (
          <p className="text-xs text-muted-foreground" data-testid="weekly-ghosts">
            {ghosts} produit(s) programmé(s) ont été retiré du catalogue et seront ignorés à l'enregistrement.
          </p>
        )}
        {!canManage && (
          <p className="text-xs text-muted-foreground">Lecture seule : votre rôle ne permet pas de modifier le planning.</p>
        )}
        <p className="text-xs text-muted-foreground">
          Les produits en rupture ou inactifs restent visibles ici avec leur état réel : ils sont signalés comme indisponibles aux clients.
        </p>
      </div>

      <AddProductsDialog
        open={addOpen} onClose={() => setAddOpen(false)}
        catalog={catalog} existingIds={ids} onConfirm={addItems} />

      <CopyDialog
        open={copyOpen} onClose={() => setCopyOpen(false)}
        days={days} targetDay={sel} busy={busy} onCopy={copyFrom} />

      <AlertDialog open={copyGuard} onOpenChange={setCopyGuard}>
        <AlertDialogContent data-testid="copy-guard-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Remplacer les modifications ?</AlertDialogTitle>
            <AlertDialogDescription>
              Ce jour contient des modifications non enregistrées. La copie remplacera ces modifications locales
              non enregistrées par le menu copié. Voulez-vous continuer ?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="copy-guard-cancel">Annuler</AlertDialogCancel>
            <AlertDialogAction data-testid="copy-guard-confirm"
              onClick={() => { setCopyGuard(false); setCopyOpen(true); }}>
              Continuer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent data-testid="delete-config-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer la configuration du jour ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le planning de {DAY_LABEL[sel]} sera effacé et ce jour repassera en « Non configuré ».
              Les produits du catalogue ne sont pas supprimés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-config-cancel">Annuler</AlertDialogCancel>
            <AlertDialogAction data-testid="delete-config-confirm" onClick={deleteConfig}>
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/* ---------- Add products dialog (multi-select over the existing catalogue) ---------- */
function AddProductsDialog({ open, onClose, catalog, existingIds, onConfirm }) {
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState([]);
  useEffect(() => {
    if (open) { setQ(""); setPicked([]); }
  }, [open]);

  const candidates = catalog.filter((it) => !existingIds.includes(it.id))
    .filter((it) => (q.trim() ? it.name.toLowerCase().includes(q.trim().toLowerCase()) : true));

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto" data-testid="add-products-dialog">
        <DialogHeader>
          <DialogTitle>Ajouter des produits</DialogTitle>
          <DialogDescription>Sélectionnez des produits du catalogue pour le menu de ce jour.</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Rechercher un plat…" value={q}
            onChange={(e) => setQ(e.target.value)} data-testid="add-products-search" />
        </div>
        <div className="divide-y divide-border max-h-[45vh] overflow-y-auto rounded-lg border border-border">
          {candidates.length === 0 && (
            <p className="px-4 py-6 text-sm text-muted-foreground text-center" data-testid="add-products-empty">
              Aucun produit à ajouter.
            </p>
          )}
          {candidates.map((it) => (
            <label key={it.id}
              className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-secondary/50"
              data-testid={`add-candidate-${it.id}`}>
              <input type="checkbox" checked={picked.includes(it.id)} onChange={() => toggle(it.id)} />
              <div className="w-8 h-8 rounded-lg bg-secondary grid place-items-center overflow-hidden shrink-0">
                {it.image_url ? <img src={it.image_url} alt="" className="w-full h-full object-cover" />
                  : <ImageIcon className="w-4 h-4 text-muted-foreground" />}
              </div>
              <span className="flex-1 text-sm font-medium flex items-center gap-2 flex-wrap">
                {it.name}
                {!it.active && <Badge variant="secondary" className="text-[10px]">Inactif</Badge>}
                {!it.available && <Badge variant="destructive" className="text-[10px]">Rupture</Badge>}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{formatFCFA(it.price)}</span>
            </label>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="add-products-cancel">Annuler</Button>
          <Button onClick={() => onConfirm(picked)} disabled={!picked.length} data-testid="add-products-confirm">
            <Plus className="w-4 h-4 mr-1" /> Ajouter {picked.length > 0 ? `(${picked.length})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------- Copy from another day ---------- */
function CopyDialog({ open, onClose, days, targetDay, busy, onCopy }) {
  const [source, setSource] = useState("");
  useEffect(() => { if (open) setSource(""); }, [open]);
  const sources = days.filter((d) => d.configured && d.day !== targetDay);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="copy-dialog">
        <DialogHeader>
          <DialogTitle>Copier le menu d'un autre jour</DialogTitle>
          <DialogDescription>
            Le menu du jour sélectionné ({DAY_LABEL[targetDay]}) sera remplacé par celui du jour source.
          </DialogDescription>
        </DialogHeader>
        {sources.length === 0 ? (
          <p className="text-sm text-muted-foreground" data-testid="copy-no-source">
            Aucun autre jour n'a de menu configuré.
          </p>
        ) : (
          <div className="space-y-2">
            <Label>Jour source</Label>
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger data-testid="copy-source-select"><SelectValue placeholder="Choisir un jour" /></SelectTrigger>
              <SelectContent>
                {sources.map((d) => (
                  <SelectItem key={d.day} value={d.day}>
                    {DAY_LABEL[d.day]}{d.active ? "" : " (désactivé)"} — {d.item_ids.length} produit(s)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="copy-cancel">Annuler</Button>
          <Button onClick={() => onCopy(source)} disabled={!source || busy} data-testid="copy-confirm">
            {busy ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
            Copier
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
