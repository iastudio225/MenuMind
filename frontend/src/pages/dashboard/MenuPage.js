import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Plus, Pencil, Trash2, ChevronUp, ChevronDown, Search, Loader2, Check, X,
  ExternalLink, UtensilsCrossed, ListChecks, Image as ImageIcon,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur");

export default function MenuPage() {
  const { user } = useAuth();
  const canManage = user?.role === "RESTAURANT_OWNER" || user?.role === "RESTAURANT_MANAGER";

  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [items, setItems] = useState([]);
  const [groups, setGroups] = useState([]);
  const [publicId, setPublicId] = useState("");
  const [search, setSearch] = useState("");
  const [filterCat, setFilterCat] = useState("all");

  // price inline edit
  const [priceEdit, setPriceEdit] = useState({ id: null, value: "" });

  const load = async () => {
    try {
      const [c, i, g] = await Promise.all([
        api.get("/menu/categories"),
        api.get("/menu/items"),
        api.get("/menu/option-groups"),
      ]);
      setCategories(c.data);
      setItems(i.data);
      setGroups(g.data);
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    api.get("/restaurants/me").then(({ data }) => setPublicId(data.public_id)).catch(() => {});
  }, []);

  const itemsByCat = useMemo(() => {
    const map = {};
    const q = search.trim().toLowerCase();
    items
      .filter((it) => (filterCat === "all" ? true : it.category_id === filterCat))
      .filter((it) => (q ? it.name.toLowerCase().includes(q) : true))
      .forEach((it) => { (map[it.category_id] = map[it.category_id] || []).push(it); });
    return map;
  }, [items, search, filterCat]);

  const visibleCategories = filterCat === "all" ? categories : categories.filter((c) => c.id === filterCat);

  // ---- Category ops ----
  const reorderCategory = async (idx, dir) => {
    const arr = [...categories];
    const j = idx + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    setCategories(arr);
    try { await api.post("/menu/categories/reorder", { ids: arr.map((c) => c.id) }); } catch (e) { err(e); load(); }
  };
  const reorderItem = async (catId, idx, dir) => {
    const arr = [...(itemsByCat[catId] || [])];
    const j = idx + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    try {
      await api.post("/menu/items/reorder", { ids: arr.map((it) => it.id), category_id: catId });
      load();
    } catch (e) { err(e); }
  };

  const toggleAvailability = async (it) => {
    try {
      await api.patch(`/menu/items/${it.id}/availability`, { available: !it.available });
      setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, available: !it.available } : x)));
      toast.success("Disponibilité mise à jour.");
    } catch (e) { err(e); }
  };

  const savePrice = async (it) => {
    const v = parseInt(priceEdit.value, 10);
    if (isNaN(v) || v < 0) { toast.error("Prix invalide"); return; }
    try {
      await api.patch(`/menu/items/${it.id}`, { price: v });
      setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, price: v } : x)));
      setPriceEdit({ id: null, value: "" });
      toast.success("Prix mis à jour.");
    } catch (e) { err(e); }
  };

  if (loading) return <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="menu-title">Menu & Carte</h1>
          <p className="text-muted-foreground mt-1 text-sm">Gérez vos catégories, plats et options.</p>
        </div>
        {publicId && (
          <a href={`${process.env.REACT_APP_BACKEND_URL}/api/menu/public/${publicId}`} target="_blank" rel="noreferrer">
            <Button variant="outline" data-testid="public-catalog-btn"><ExternalLink className="w-4 h-4 mr-1" /> Aperçu public</Button>
          </a>
        )}
      </div>

      <Tabs defaultValue="catalogue">
        <TabsList data-testid="menu-tabs">
          <TabsTrigger value="catalogue" data-testid="tab-catalogue"><UtensilsCrossed className="w-4 h-4 mr-1" /> Catalogue</TabsTrigger>
          <TabsTrigger value="options" data-testid="tab-options"><ListChecks className="w-4 h-4 mr-1" /> Groupes d'options</TabsTrigger>
        </TabsList>

        {/* ===== Catalogue ===== */}
        <TabsContent value="catalogue" className="mt-6 space-y-5">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" placeholder="Rechercher un plat…" value={search}
                onChange={(e) => setSearch(e.target.value)} data-testid="menu-search-input" />
            </div>
            <Select value={filterCat} onValueChange={setFilterCat}>
              <SelectTrigger className="w-48" data-testid="menu-filter-category"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes les catégories</SelectItem>
                {categories.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
            {canManage && (
              <>
                <CategoryDialog onSaved={load} nextOrder={categories.length + 1}
                  trigger={<Button variant="outline" data-testid="add-category-btn"><Plus className="w-4 h-4 mr-1" /> Catégorie</Button>} />
                <ItemDialog onSaved={load} categories={categories} groups={groups}
                  trigger={<Button data-testid="add-item-btn" disabled={!categories.length}><Plus className="w-4 h-4 mr-1" /> Article</Button>} />
              </>
            )}
          </div>

          {categories.length === 0 && (
            <div className="bg-card border border-border rounded-2xl p-10 text-center text-muted-foreground" data-testid="menu-empty">
              Aucune catégorie. Commencez par en créer une.
            </div>
          )}

          {visibleCategories.map((cat, ci) => (
            <div key={cat.id} className="bg-card border border-border rounded-2xl overflow-hidden" data-testid={`category-card-${cat.id}`}>
              <div className="flex items-center justify-between px-5 py-3 bg-secondary/40 border-b border-border">
                <div className="flex items-center gap-2">
                  <span className="font-heading font-semibold" data-testid={`category-name-${cat.id}`}>{cat.name}</span>
                  {!cat.active && <Badge variant="secondary">Inactive</Badge>}
                  <span className="text-xs text-muted-foreground">({(itemsByCat[cat.id] || []).length})</span>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1">
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => reorderCategory(ci, -1)} data-testid={`cat-up-${cat.id}`}><ChevronUp className="w-4 h-4" /></Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => reorderCategory(ci, 1)} data-testid={`cat-down-${cat.id}`}><ChevronDown className="w-4 h-4" /></Button>
                    <CategoryDialog category={cat} onSaved={load}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-category-${cat.id}`}><Pencil className="w-4 h-4" /></Button>} />
                    <ConfirmDelete
                      title="Supprimer la catégorie ?"
                      description="La catégorie ne peut être supprimée que si elle ne contient aucun article."
                      onConfirm={async () => { try { await api.delete(`/menu/categories/${cat.id}`); toast.success("Catégorie supprimée."); load(); } catch (e) { err(e); } }}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-category-${cat.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                  </div>
                )}
              </div>
              <div className="divide-y divide-border">
                {(itemsByCat[cat.id] || []).length === 0 && (
                  <p className="px-5 py-4 text-sm text-muted-foreground">Aucun article.</p>
                )}
                {(itemsByCat[cat.id] || []).map((it, ii) => (
                  <div key={it.id} className="flex items-center gap-3 px-5 py-3 flex-wrap" data-testid={`item-row-${it.id}`}>
                    <div className="w-10 h-10 rounded-lg bg-secondary grid place-items-center overflow-hidden shrink-0">
                      {it.image_url ? <img src={it.image_url} alt="" className="w-full h-full object-cover" /> : <ImageIcon className="w-4 h-4 text-muted-foreground" />}
                    </div>
                    <div className="flex-1 min-w-[140px]">
                      <p className="font-medium flex items-center gap-2">
                        {it.name} {!it.active && <Badge variant="secondary" className="text-[10px]">Inactif</Badge>}
                      </p>
                      {it.description && <p className="text-xs text-muted-foreground truncate max-w-xs">{it.description}</p>}
                    </div>

                    {/* Quick price */}
                    {priceEdit.id === it.id ? (
                      <div className="flex items-center gap-1">
                        <Input type="number" className="w-24 h-8" value={priceEdit.value} autoFocus
                          onChange={(e) => setPriceEdit({ id: it.id, value: e.target.value })} data-testid={`price-input-${it.id}`} />
                        <Button size="icon" className="h-8 w-8" onClick={() => savePrice(it)} data-testid={`price-save-${it.id}`}><Check className="w-4 h-4" /></Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setPriceEdit({ id: null, value: "" })}><X className="w-4 h-4" /></Button>
                      </div>
                    ) : (
                      <button className="font-mono text-sm font-semibold w-28 text-right hover:text-primary disabled:hover:text-foreground"
                        disabled={!canManage} onClick={() => setPriceEdit({ id: it.id, value: String(it.price) })}
                        data-testid={`price-display-${it.id}`}>
                        {formatFCFA(it.price)}
                      </button>
                    )}

                    {/* Availability quick toggle */}
                    <button onClick={() => toggleAvailability(it)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium w-32 justify-center ${
                        it.available ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"}`}
                      data-testid={`availability-toggle-${it.id}`}>
                      <span className={`w-2 h-2 rounded-full ${it.available ? "bg-emerald-500" : "bg-red-500"}`} />
                      {it.available ? "Disponible" : "Rupture"}
                    </button>

                    {canManage && (
                      <div className="flex items-center gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => reorderItem(cat.id, ii, -1)} data-testid={`item-up-${it.id}`}><ChevronUp className="w-4 h-4" /></Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => reorderItem(cat.id, ii, 1)} data-testid={`item-down-${it.id}`}><ChevronDown className="w-4 h-4" /></Button>
                        <ItemDialog item={it} categories={categories} groups={groups} onSaved={load}
                          trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-item-${it.id}`}><Pencil className="w-4 h-4" /></Button>} />
                        <ConfirmDelete title="Supprimer l'article ?" description={`« ${it.name} » sera définitivement supprimé.`}
                          onConfirm={async () => { try { await api.delete(`/menu/items/${it.id}`); toast.success("Article supprimé."); load(); } catch (e) { err(e); } }}
                          trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-item-${it.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </TabsContent>

        {/* ===== Options ===== */}
        <TabsContent value="options" className="mt-6 space-y-5">
          {canManage && (
            <GroupDialog onSaved={load}
              trigger={<Button data-testid="add-group-btn"><Plus className="w-4 h-4 mr-1" /> Ajouter un groupe</Button>} />
          )}
          {groups.length === 0 && (
            <div className="bg-card border border-border rounded-2xl p-10 text-center text-muted-foreground">Aucun groupe d'options.</div>
          )}
          {groups.map((g) => (
            <div key={g.id} className="bg-card border border-border rounded-2xl overflow-hidden" data-testid={`group-card-${g.id}`}>
              <div className="flex items-center justify-between px-5 py-3 bg-secondary/40 border-b border-border">
                <div>
                  <span className="font-heading font-semibold">{g.name}</span>
                  <span className="text-xs text-muted-foreground ml-2">
                    {g.required ? "Obligatoire" : "Facultatif"} · min {g.min_selections} / max {g.max_selections}
                  </span>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1">
                    <OptionDialog groupId={g.id} onSaved={load}
                      trigger={<Button size="sm" variant="outline" data-testid={`add-option-${g.id}`}><Plus className="w-4 h-4 mr-1" /> Option</Button>} />
                    <GroupDialog group={g} onSaved={load}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-group-${g.id}`}><Pencil className="w-4 h-4" /></Button>} />
                    <ConfirmDelete title="Supprimer le groupe ?" description="Les options de ce groupe seront supprimées et le groupe sera détaché des articles."
                      onConfirm={async () => { try { await api.delete(`/menu/option-groups/${g.id}`); toast.success("Groupe supprimé."); load(); } catch (e) { err(e); } }}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-group-${g.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                  </div>
                )}
              </div>
              <div className="divide-y divide-border">
                {(g.options || []).length === 0 && <p className="px-5 py-3 text-sm text-muted-foreground">Aucune option.</p>}
                {(g.options || []).map((o) => (
                  <div key={o.id} className="flex items-center gap-3 px-5 py-2.5" data-testid={`option-row-${o.id}`}>
                    <span className="flex-1 text-sm">{o.name}</span>
                    <span className="font-mono text-xs text-muted-foreground w-24 text-right">
                      {o.price_delta > 0 ? `+${formatFCFA(o.price_delta)}` : "Inclus"}
                    </span>
                    {!o.available && <Badge variant="secondary" className="text-[10px]">Rupture</Badge>}
                    {canManage && (
                      <div className="flex items-center gap-1">
                        <OptionDialog groupId={g.id} option={o} onSaved={load}
                          trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-option-${o.id}`}><Pencil className="w-4 h-4" /></Button>} />
                        <ConfirmDelete title="Supprimer l'option ?" description={`« ${o.name} » sera supprimée.`}
                          onConfirm={async () => { try { await api.delete(`/menu/options/${o.id}`); toast.success("Option supprimée."); load(); } catch (e) { err(e); } }}
                          trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-option-${o.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---------- Dialog components ---------- */
function ConfirmDelete({ trigger, title, description, onConfirm }) {
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="confirm-cancel">Annuler</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} data-testid="confirm-delete">Supprimer</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function CategoryDialog({ trigger, category, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", active: true });
  useEffect(() => {
    if (open) setForm(category ? { name: category.name, description: category.description || "", active: category.active }
      : { name: "", description: "", active: true });
  }, [open, category]);
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    try {
      if (category) await api.patch(`/menu/categories/${category.id}`, form);
      else await api.post("/menu/categories", form);
      toast.success(category ? "Catégorie modifiée." : "Catégorie ajoutée.");
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent data-testid="category-dialog">
        <DialogHeader><DialogTitle>{category ? "Modifier la catégorie" : "Nouvelle catégorie"}</DialogTitle>
          <DialogDescription>Organisez votre menu en catégories (Plats, Boissons…).</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nom</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="category-name-input" /></div>
          <div className="space-y-2"><Label>Description</Label><Textarea rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="category-description-input" /></div>
          <div className="flex items-center justify-between"><Label>Active</Label><Switch checked={form.active} onCheckedChange={(v) => setForm((f) => ({ ...f, active: v }))} data-testid="category-active-switch" /></div>
          <DialogFooter><Button type="submit" disabled={saving} data-testid="category-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ItemDialog({ trigger, item, categories, groups, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  useEffect(() => {
    if (open) setForm(item
      ? { category_id: item.category_id, name: item.name, description: item.description || "", image_url: item.image_url || "", price: String(item.price), active: item.active, available: item.available, option_group_ids: item.option_group_ids || [] }
      : { category_id: categories[0]?.id || "", name: "", description: "", image_url: "", price: "", active: true, available: true, option_group_ids: [] });
  }, [open, item, categories]);
  const toggleGroup = (gid) => setForm((f) => ({ ...f, option_group_ids: f.option_group_ids.includes(gid) ? f.option_group_ids.filter((x) => x !== gid) : [...f.option_group_ids, gid] }));
  const submit = async (e) => {
    e.preventDefault();
    const price = parseInt(form.price, 10);
    if (isNaN(price) || price < 0) { toast.error("Prix invalide"); return; }
    setSaving(true);
    const payload = { ...form, price };
    try {
      if (item) await api.patch(`/menu/items/${item.id}`, payload);
      else await api.post("/menu/items", payload);
      toast.success(item ? "Plat modifié." : "Plat ajouté avec succès.");
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  if (!form && open) return null;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="item-dialog">
        <DialogHeader><DialogTitle>{item ? "Modifier l'article" : "Nouvel article"}</DialogTitle>
          <DialogDescription>Renseignez les informations du plat et ses options.</DialogDescription></DialogHeader>
        {form && (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2"><Label>Catégorie</Label>
              <Select value={form.category_id} onValueChange={(v) => setForm((f) => ({ ...f, category_id: v }))}>
                <SelectTrigger data-testid="item-category-select"><SelectValue placeholder="Choisir" /></SelectTrigger>
                <SelectContent>{categories.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2"><Label>Nom</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="item-name-input" /></div>
            <div className="space-y-2"><Label>Description</Label><Textarea rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="item-description-input" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Prix (FCFA)</Label><Input type="number" min={0} required value={form.price} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))} data-testid="item-price-input" /></div>
              <div className="space-y-2"><Label>Image (URL)</Label><Input value={form.image_url} onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))} placeholder="https://…" data-testid="item-image-input" /></div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2"><Label>Actif</Label><Switch checked={form.active} onCheckedChange={(v) => setForm((f) => ({ ...f, active: v }))} data-testid="item-active-switch" /></div>
              <div className="flex items-center gap-2"><Label>Disponible</Label><Switch checked={form.available} onCheckedChange={(v) => setForm((f) => ({ ...f, available: v }))} data-testid="item-available-switch" /></div>
            </div>
            {groups.length > 0 && (
              <div className="space-y-2">
                <Label>Groupes d'options</Label>
                <div className="space-y-2 rounded-lg border border-border p-3">
                  {groups.map((g) => (
                    <label key={g.id} className="flex items-center gap-2 text-sm cursor-pointer" data-testid={`item-group-${g.id}`}>
                      <input type="checkbox" checked={form.option_group_ids.includes(g.id)} onChange={() => toggleGroup(g.id)} />
                      {g.name} <span className="text-xs text-muted-foreground">({g.required ? "obligatoire" : "facultatif"})</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            <DialogFooter><Button type="submit" disabled={saving} data-testid="item-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function GroupDialog({ trigger, group, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", required: false, min_selections: 0, max_selections: 1, active: true });
  useEffect(() => {
    if (open) setForm(group
      ? { name: group.name, description: group.description || "", required: group.required, min_selections: group.min_selections, max_selections: group.max_selections, active: group.active }
      : { name: "", description: "", required: false, min_selections: 0, max_selections: 1, active: true });
  }, [open, group]);
  const submit = async (e) => {
    e.preventDefault();
    if (Number(form.max_selections) < Number(form.min_selections)) { toast.error("max doit être ≥ min"); return; }
    setSaving(true);
    const payload = { ...form, min_selections: Number(form.min_selections), max_selections: Number(form.max_selections) };
    try {
      if (group) await api.patch(`/menu/option-groups/${group.id}`, payload);
      else await api.post("/menu/option-groups", payload);
      toast.success(group ? "Groupe modifié." : "Groupe ajouté.");
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent data-testid="group-dialog">
        <DialogHeader><DialogTitle>{group ? "Modifier le groupe" : "Nouveau groupe d'options"}</DialogTitle>
          <DialogDescription>Ex. « Accompagnement » (1 choix obligatoire) ou « Suppléments » (facultatif).</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nom</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="group-name-input" /></div>
          <div className="space-y-2"><Label>Description</Label><Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="group-description-input" /></div>
          <div className="flex items-center justify-between"><Label>Obligatoire</Label><Switch checked={form.required} onCheckedChange={(v) => setForm((f) => ({ ...f, required: v }))} data-testid="group-required-switch" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2"><Label>Min sélections</Label><Input type="number" min={0} value={form.min_selections} onChange={(e) => setForm((f) => ({ ...f, min_selections: e.target.value }))} data-testid="group-min-input" /></div>
            <div className="space-y-2"><Label>Max sélections</Label><Input type="number" min={0} value={form.max_selections} onChange={(e) => setForm((f) => ({ ...f, max_selections: e.target.value }))} data-testid="group-max-input" /></div>
          </div>
          <DialogFooter><Button type="submit" disabled={saving} data-testid="group-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function OptionDialog({ trigger, groupId, option, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", price_delta: 0, available: true });
  useEffect(() => {
    if (open) setForm(option ? { name: option.name, price_delta: option.price_delta, available: option.available } : { name: "", price_delta: 0, available: true });
  }, [open, option]);
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    const payload = { ...form, price_delta: Number(form.price_delta) || 0 };
    try {
      if (option) await api.patch(`/menu/options/${option.id}`, payload);
      else await api.post(`/menu/option-groups/${groupId}/options`, payload);
      toast.success(option ? "Option modifiée." : "Option ajoutée.");
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent data-testid="option-dialog">
        <DialogHeader><DialogTitle>{option ? "Modifier l'option" : "Nouvelle option"}</DialogTitle>
          <DialogDescription>Ex. « Fromage » avec un supplément de 500 FCFA.</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nom</Label><Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="option-name-input" /></div>
          <div className="space-y-2"><Label>Supplément de prix (FCFA)</Label><Input type="number" min={0} value={form.price_delta} onChange={(e) => setForm((f) => ({ ...f, price_delta: e.target.value }))} data-testid="option-price-input" /></div>
          <div className="flex items-center justify-between"><Label>Disponible</Label><Switch checked={form.available} onCheckedChange={(v) => setForm((f) => ({ ...f, available: v }))} data-testid="option-available-switch" /></div>
          <DialogFooter><Button type="submit" disabled={saving} data-testid="option-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
