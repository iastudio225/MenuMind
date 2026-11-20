import React, { useContext, useEffect, useMemo, useState } from "react";
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
  ExternalLink, UtensilsCrossed, ListChecks, Image as ImageIcon, Layers,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatFCFA, formatApiErrorDetail } from "@/lib/format";
import { secteurConfig } from "@/lib/secteurs";
import { useAuth } from "@/context/AuthContext";
import { DashboardRestaurantContext } from "@/layouts/DashboardLayout";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur");

export default function MenuPage() {
  const { user } = useAuth();
  const restaurant = useContext(DashboardRestaurantContext);
  const sector = secteurConfig(restaurant?.secteur);
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
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="menu-title">{sector.value === "restaurant" ? "Menu & Carte" : sector.catalogueLabel}</h1>
          <p className="text-muted-foreground mt-1 text-sm">Gérez vos catégories, {sector.itemsPlural} et options.</p>
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
              <Input className="pl-9" placeholder={`Rechercher un ${sector.itemLabel.toLowerCase()}…`} value={search}
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
                <ItemDialog onSaved={load} categories={categories} groups={groups} sector={sector}
                  trigger={<Button data-testid="add-item-btn" disabled={!categories.length}><Plus className="w-4 h-4 mr-1" /> {sector.itemLabel}</Button>} />
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
                      description={`La catégorie ne peut être supprimée que si elle ne contient aucun ${sector.itemLabel.toLowerCase()}.`}
                      onConfirm={async () => { try { await api.delete(`/menu/categories/${cat.id}`); toast.success("Catégorie supprimée."); load(); } catch (e) { err(e); } }}
                      trigger={<Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" data-testid={`delete-category-${cat.id}`}><Trash2 className="w-4 h-4" /></Button>} />
                  </div>
                )}
              </div>
              <div className="divide-y divide-border">
                {(itemsByCat[cat.id] || []).length === 0 && (
                  <p className="px-5 py-4 text-sm text-muted-foreground">Aucun {sector.itemLabel.toLowerCase()}.</p>
                )}
                {(itemsByCat[cat.id] || []).map((it, ii) => (
                  <div key={it.id} className="flex items-center gap-3 px-5 py-3 flex-wrap" data-testid={`item-row-${it.id}`}>
                    <div className="w-10 h-10 rounded-lg bg-secondary grid place-items-center overflow-hidden shrink-0">
                      {it.image_url ? <img src={it.image_url} alt="" loading="lazy" decoding="async" className="w-full h-full object-cover" /> : <ImageIcon className="w-4 h-4 text-muted-foreground" />}
                    </div>
                    <div className="flex-1 min-w-[140px]">
                      <p className="font-medium flex items-center gap-2 flex-wrap">
                        {it.name} {!it.active && <Badge variant="secondary" className="text-[10px]">Inactif</Badge>}
                        {it.stock != null && Number(it.stock) <= 0 && <Badge variant="destructive" className="text-[10px]">Rupture</Badge>}
                        {it.stock != null && Number(it.stock) > 0 && <Badge variant="outline" className="text-[10px]">Stock {it.stock}</Badge>}
                        {it.sku && <span className="text-[10px] text-muted-foreground font-mono">{it.sku}</span>}
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
                        {(it.option_group_ids || []).length > 0 && (
                          <VariantMatrixDialog item={it} groups={groups} onSaved={load}
                            trigger={<Button size="icon" variant="ghost" className="h-8 w-8" title="Variantes" data-testid={`variants-item-${it.id}`}><Layers className="w-4 h-4" /></Button>} />
                        )}
                        <ItemDialog item={it} categories={categories} groups={groups} onSaved={load} sector={sector}
                          trigger={<Button size="icon" variant="ghost" className="h-8 w-8" data-testid={`edit-item-${it.id}`}><Pencil className="w-4 h-4" /></Button>} />
                        <ConfirmDelete title={`Supprimer l'${sector.value === "restaurant" ? "article" : "élément"} ?`} description={`« ${it.name} » sera définitivement supprimé.`}
                          onConfirm={async () => { try { await api.delete(`/menu/items/${it.id}`); toast.success("Supprimé."); load(); } catch (e) { err(e); } }}
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
                    {!o.available && <Badge variant="secondary" className="text-[10px]">Indisponible</Badge>}
                    {o.stock != null && Number(o.stock) <= 0 && <Badge variant="destructive" className="text-[10px]">Rupture</Badge>}
                    {o.stock != null && Number(o.stock) > 0 && <Badge variant="outline" className="text-[10px]">Stock {o.stock}</Badge>}
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
          <DialogDescription>Organisez votre catalogue en catégories.</DialogDescription></DialogHeader>
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

function ItemDialog({ trigger, item, categories, groups, onSaved, sector }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  useEffect(() => {
    if (open) {
      const rules = item?.pricing_rules || {};
      const mode = Number(rules.per_km || 0) > 0 && Number(rules.per_kg || 0) > 0 ? "distance_weight"
        : Number(rules.per_km || 0) > 0 ? "distance"
          : Number(rules.per_kg || 0) > 0 ? "weight" : "fixed";
      setForm(item
        ? {
          category_id: item.category_id, name: item.name, description: item.description || "", image_url: item.image_url || "",
          price: String(item.price), active: item.active, available: item.available, option_group_ids: item.option_group_ids || [],
          pricing_mode: mode, pricing_base: String(rules.base ?? item.price ?? ""),
          pricing_per_km: String(rules.per_km ?? ""), pricing_per_kg: String(rules.per_kg ?? ""), pricing_min: String(rules.min ?? ""),
          stock: item.stock != null ? String(item.stock) : "", sku: item.sku || "",
        }
        : {
          category_id: categories[0]?.id || "", name: "", description: "", image_url: "", price: "",
          active: true, available: true, option_group_ids: [],
          pricing_mode: "fixed", pricing_base: "", pricing_per_km: "", pricing_per_kg: "", pricing_min: "",
          stock: "", sku: "",
        });
    }
  }, [open, item, categories]);
  const toggleGroup = (gid) => setForm((f) => ({ ...f, option_group_ids: f.option_group_ids.includes(gid) ? f.option_group_ids.filter((x) => x !== gid) : [...f.option_group_ids, gid] }));
  const submit = async (e) => {
    e.preventDefault();
    const price = parseInt(form.price, 10);
    if (isNaN(price) || price < 0) { toast.error("Prix invalide"); return; }
    setSaving(true);
    const { pricing_mode, pricing_base, pricing_per_km, pricing_per_kg, pricing_min, ...base } = form;
    const shouldPersistPricing = sector?.value === "logistique"
      || (item?.pricing_rules && Object.keys(item.pricing_rules).length > 0);
    const pricingRules = !shouldPersistPricing
      ? (item?.pricing_rules || {})
      : (pricing_mode === "fixed" && !pricing_base && !pricing_min)
        ? {}
        : {
          base: Number(pricing_base || price),
          per_km: (pricing_mode === "distance" || pricing_mode === "distance_weight") ? Number(pricing_per_km || 0) : 0,
          per_kg: (pricing_mode === "weight" || pricing_mode === "distance_weight") ? Number(pricing_per_kg || 0) : 0,
          min: Number(pricing_min || 0),
        };
    const stockValue = form.stock === "" ? null : Number(form.stock);
    const payload = { ...base, price, pricing_rules: pricingRules, stock: stockValue, sku: form.sku || "" };
    try {
      if (item) await api.patch(`/menu/items/${item.id}`, payload);
      else await api.post("/menu/items", payload);
      toast.success(item ? `${sector?.itemLabel || "Article"} modifié.` : `${sector?.itemLabel || "Article"} ajouté avec succès.`);
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  if (!form && open) return null;
  const showPricing = sector?.value === "logistique" || (item?.pricing_rules && Object.keys(item.pricing_rules).length > 0);
  const showStock = sector?.value === "e-commerce" || item?.stock != null || !!item?.sku;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="item-dialog">
        <DialogHeader><DialogTitle>{item ? `Modifier l'${sector?.itemLabel?.toLowerCase() || "article"}` : `Nouvel ${sector?.itemLabel?.toLowerCase() || "article"}`}</DialogTitle>
          <DialogDescription>Renseignez les informations du {sector?.itemLabel?.toLowerCase() || "plat"} et ses options.</DialogDescription></DialogHeader>
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
            {showPricing && (
              <div className="space-y-3 rounded-lg border border-border p-3" data-testid="item-pricing-section">
                <p className="font-medium text-sm">Tarification du service</p>
                <Select value={form.pricing_mode} onValueChange={(v) => setForm((f) => ({ ...f, pricing_mode: v }))}>
                  <SelectTrigger data-testid="item-pricing-mode"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fixed">Prix fixe</SelectItem>
                    <SelectItem value="distance">Au kilomètre</SelectItem>
                    <SelectItem value="weight">Au poids</SelectItem>
                    <SelectItem value="distance_weight">Distance + poids</SelectItem>
                  </SelectContent>
                </Select>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><Label>Prix de base (FCFA)</Label><Input type="number" min={0} value={form.pricing_base} onChange={(e) => setForm((f) => ({ ...f, pricing_base: e.target.value }))} data-testid="item-pricing-base" /></div>
                  <div className="space-y-1"><Label>Minimum (FCFA)</Label><Input type="number" min={0} value={form.pricing_min} onChange={(e) => setForm((f) => ({ ...f, pricing_min: e.target.value }))} data-testid="item-pricing-min" /></div>
                  {(form.pricing_mode === "distance" || form.pricing_mode === "distance_weight") && (
                    <div className="space-y-1"><Label>Prix / km (FCFA)</Label><Input type="number" min={0} value={form.pricing_per_km} onChange={(e) => setForm((f) => ({ ...f, pricing_per_km: e.target.value }))} data-testid="item-pricing-per-km" /></div>
                  )}
                  {(form.pricing_mode === "weight" || form.pricing_mode === "distance_weight") && (
                    <div className="space-y-1"><Label>Prix / kg (FCFA)</Label><Input type="number" min={0} value={form.pricing_per_kg} onChange={(e) => setForm((f) => ({ ...f, pricing_per_kg: e.target.value }))} data-testid="item-pricing-per-kg" /></div>
                  )}
                </div>
              </div>
            )}
            {showStock && (
              <div className="grid grid-cols-2 gap-4" data-testid="item-stock-section">
                <div className="space-y-2">
                  <Label>Stock</Label>
                  <Input type="number" min={0} value={form.stock} placeholder="Illimité si vide"
                    onChange={(e) => setForm((f) => ({ ...f, stock: e.target.value }))} data-testid="item-stock-input" />
                </div>
                <div className="space-y-2">
                  <Label>SKU / Référence</Label>
                  <Input value={form.sku} placeholder="SKU-001"
                    onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} data-testid="item-sku-input" />
                </div>
              </div>
            )}
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

function VariantMatrixDialog({ trigger, item, groups, onSaved }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rows, setRows] = useState({});

  const applicableGroups = useMemo(
    () => groups.filter((g) => (item.option_group_ids || []).includes(g.id) && (g.options || []).length > 0),
    [groups, item],
  );
  const optionName = useMemo(() => {
    const map = {};
    applicableGroups.forEach((g) => (g.options || []).forEach((o) => { map[o.id] = `${g.name}: ${o.name}`; }));
    return map;
  }, [applicableGroups]);
  const combos = useMemo(() => {
    if (!applicableGroups.length) return [];
    return applicableGroups.reduce((acc, g) => {
      const opts = (g.options || []).filter((o) => o.active !== false);
      if (!acc.length) return opts.map((o) => [o.id]);
      return acc.flatMap((prefix) => opts.map((o) => [...prefix, o.id]));
    }, []);
  }, [applicableGroups]);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/menu/items/${item.id}/variants`);
      const byKey = {};
      (data || []).forEach((v) => { byKey[v.key] = v; });
      const next = {};
      combos.forEach((ids) => {
        const key = [...ids].sort().join("|");
        const v = byKey[key];
        next[key] = v
          ? { ...v, stock: v.stock != null ? String(v.stock) : "", price_delta: String(v.price_delta ?? 0), sku: v.sku || "" }
          : { option_ids: ids, sku: "", price_delta: "0", stock: "", active: true };
      });
      setRows(next);
    } catch (e) { err(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (open) load(); }, [open, item.id, combos]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateRow = (key, patch) => setRows((r) => ({ ...r, [key]: { ...r[key], ...patch } }));
  const isPristine = (row) => !row.id && !row.sku && (row.stock === "" || row.stock == null)
    && Number(row.price_delta || 0) === 0 && row.active !== false;

  const save = async (e) => {
    e.preventDefault();
    const toSave = Object.values(rows).filter((row) => !isPristine(row));
    if (!toSave.length) { toast.info("Aucune variante à enregistrer."); return; }
    setSaving(true);
    try {
      await Promise.all(toSave.map((row) => api.post(`/menu/items/${item.id}/variants`, {
        option_ids: row.option_ids,
        sku: row.sku || "",
        price_delta: Number(row.price_delta) || 0,
        stock: row.stock === "" ? null : Number(row.stock),
        active: row.active !== false,
      })));
      toast.success("Matrice de variantes enregistrée.");
      setOpen(false);
      onSaved();
    } catch (e) { err(e); }
    finally { setSaving(false); }
  };

  const deleteRow = async (key, row) => {
    try {
      if (row.id) await api.delete(`/menu/variants/${row.id}`);
      setRows((r) => { const next = { ...r }; delete next[key]; return next; });
      toast.success("Variante supprimée.");
    } catch (e) { err(e); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="variant-matrix-dialog">
        <DialogHeader>
          <DialogTitle>Variantes — {item.name}</DialogTitle>
          <DialogDescription>
            Chaque combinaison d'options peut avoir son stock, son SKU et son supplément de prix.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="grid place-items-center py-10"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : combos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ajoutez d'abord des groupes d'options à cet article (onglet Groupes d'options).</p>
        ) : (
          <form onSubmit={save} className="space-y-4">
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead className="bg-secondary/50 text-muted-foreground">
                  <tr>
                    <th className="text-left font-medium px-3 py-2">Combinaison</th>
                    <th className="text-left font-medium px-3 py-2">SKU</th>
                    <th className="text-left font-medium px-3 py-2">Supplément</th>
                    <th className="text-left font-medium px-3 py-2">Stock</th>
                    <th className="text-left font-medium px-3 py-2">Active</th>
                    <th className="text-right font-medium px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rows).map(([key, row]) => (
                    <tr key={key} className="border-t border-border" data-testid={`variant-row-${key}`}>
                      <td className="px-3 py-2 text-xs">{row.option_ids.map((id) => optionName[id] || id).join(" · ")}</td>
                      <td className="px-3 py-2"><Input className="h-8 w-32" value={row.sku} onChange={(e) => updateRow(key, { sku: e.target.value })} placeholder="SKU" data-testid={`variant-sku-${key}`} /></td>
                      <td className="px-3 py-2"><Input className="h-8 w-24" type="number" min={0} value={row.price_delta} onChange={(e) => updateRow(key, { price_delta: e.target.value })} data-testid={`variant-price-${key}`} /></td>
                      <td className="px-3 py-2"><Input className="h-8 w-24" type="number" min={0} value={row.stock} onChange={(e) => updateRow(key, { stock: e.target.value })} placeholder="∞" data-testid={`variant-stock-${key}`} /></td>
                      <td className="px-3 py-2"><Switch checked={row.active !== false} onCheckedChange={(v) => updateRow(key, { active: v })} data-testid={`variant-active-${key}`} /></td>
                      <td className="px-3 py-2 text-right">
                        <Button type="button" size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => deleteRow(key, row)} data-testid={`variant-delete-${key}`}><Trash2 className="w-4 h-4" /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={saving} data-testid="variant-save">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer la matrice"}</Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function OptionDialog({ trigger, groupId, option, onSaved }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", price_delta: 0, available: true, stock: "" });
  useEffect(() => {
    if (open) setForm(option
      ? { name: option.name, price_delta: option.price_delta, available: option.available,
          stock: option.stock != null ? String(option.stock) : "" }
      : { name: "", price_delta: 0, available: true, stock: "" });
  }, [open, option]);
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    const payload = {
      ...form,
      price_delta: Number(form.price_delta) || 0,
      stock: form.stock === "" ? null : Number(form.stock),
    };
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2"><Label>Supplément de prix (FCFA)</Label><Input type="number" min={0} value={form.price_delta} onChange={(e) => setForm((f) => ({ ...f, price_delta: e.target.value }))} data-testid="option-price-input" /></div>
            <div className="space-y-2"><Label>Stock variante</Label><Input type="number" min={0} value={form.stock} placeholder="Illimité si vide" onChange={(e) => setForm((f) => ({ ...f, stock: e.target.value }))} data-testid="option-stock-input" /></div>
          </div>
          <div className="flex items-center justify-between"><Label>Disponible</Label><Switch checked={form.available} onCheckedChange={(v) => setForm((f) => ({ ...f, available: v }))} data-testid="option-available-switch" /></div>
          <DialogFooter><Button type="submit" disabled={saving} data-testid="option-submit">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enregistrer"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
