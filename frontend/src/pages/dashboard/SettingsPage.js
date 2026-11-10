import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Loader2, Save, Copy, ExternalLink, Share2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatApiErrorDetail } from "@/lib/format";
import { buildExperienceUrl } from "@/lib/publicLinks";
import { useAuth } from "@/context/AuthContext";

const DAYS = [
  ["monday", "Lundi"], ["tuesday", "Mardi"], ["wednesday", "Mercredi"], ["thursday", "Jeudi"],
  ["friday", "Vendredi"], ["saturday", "Samedi"], ["sunday", "Dimanche"],
];

export default function SettingsPage() {
  const { user } = useAuth();
  const readOnly = user?.role === "RESTAURANT_STAFF";
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/restaurants/me").then(({ data }) => setData(data)).catch(() => {});
  }, []);

  const set = (k) => (e) => setData((d) => ({ ...d, [k]: e.target.value }));
  const setWidget = (k) => (e) => setData((d) => ({ ...d, widget: { ...d.widget, [k]: e.target.value } }));
  const setHour = (day, field, value) =>
    setData((d) => ({ ...d, opening_hours: { ...d.opening_hours, [day]: { ...d.opening_hours[day], [field]: value } } }));

  const save = async (fields) => {
    setSaving(true);
    try {
      const payload = {};
      fields.forEach((f) => (payload[f] = data[f]));
      await api.patch("/restaurants/me", payload);
      toast.success("Paramètres enregistrés");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const embedCode = data
    ? `<script src="${process.env.REACT_APP_BACKEND_URL}/widget.js"\n  data-restaurant="${data.public_id}"></script>`
    : "";
  const chatbotUrl = data?.public_id
    ? buildExperienceUrl(window.location.origin, data.public_id)
    : "";

  const copyEmbed = async () => {
    try {
      await navigator.clipboard.writeText(embedCode);
      toast.success("Code d'intégration copié");
    } catch {
      toast.error("Copie impossible — sélectionnez le code manuellement");
    }
  };

  const copyChatbotLink = async () => {
    try {
      await navigator.clipboard.writeText(chatbotUrl);
      toast.success("Lien du chatbot copié");
    } catch {
      toast.error("Copie impossible — sélectionnez le lien manuellement");
    }
  };

  const shareChatbotLink = async () => {
    if (typeof navigator.share !== "function") {
      await copyChatbotLink();
      return;
    }

    try {
      await navigator.share({
        title: `Chatbot de ${data.name || "votre restaurant"}`,
        text: "Découvrez le menu et commandez avec notre assistant.",
        url: chatbotUrl,
      });
      toast.success("Lien partagé");
    } catch (error) {
      if (error?.name !== "AbortError") await copyChatbotLink();
    }
  };

  if (!data) return <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;

  return (
    <div className="max-w-3xl">
      <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight mb-6" data-testid="settings-title">Paramètres</h1>
      <Tabs defaultValue="restaurant">
        <TabsList data-testid="settings-tabs">
          <TabsTrigger value="restaurant" data-testid="tab-restaurant">Restaurant</TabsTrigger>
          <TabsTrigger value="hours" data-testid="tab-hours">Horaires</TabsTrigger>
          <TabsTrigger value="widget" data-testid="tab-widget">Widget</TabsTrigger>
          <TabsTrigger value="chatbot" data-testid="tab-chatbot">Chatbot</TabsTrigger>
        </TabsList>

        <TabsContent value="restaurant" className="mt-6">
          <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
            <div className="space-y-2"><Label>Nom</Label><Input disabled={readOnly} value={data.name || ""} onChange={set("name")} data-testid="settings-name" /></div>
            <div className="space-y-2"><Label>Description</Label><Textarea disabled={readOnly} rows={3} value={data.description || ""} onChange={set("description")} data-testid="settings-description" /></div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Téléphone</Label><Input disabled={readOnly} value={data.phone || ""} onChange={set("phone")} data-testid="settings-phone" /></div>
              <div className="space-y-2"><Label>WhatsApp</Label><Input disabled={readOnly} value={data.whatsapp || ""} onChange={set("whatsapp")} data-testid="settings-whatsapp" /></div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Ville</Label><Input disabled={readOnly} value={data.city || ""} onChange={set("city")} data-testid="settings-city" /></div>
              <div className="space-y-2"><Label>Devise</Label><Input disabled={readOnly} value={data.currency || ""} onChange={set("currency")} data-testid="settings-currency" /></div>
            </div>
            {!readOnly && (
              <Button onClick={() => save(["name", "description", "phone", "whatsapp", "city", "currency"])} disabled={saving} data-testid="save-restaurant-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" /> Enregistrer</>}
              </Button>
            )}
          </div>
        </TabsContent>

        <TabsContent value="hours" className="mt-6">
          <div className="bg-card border border-border rounded-2xl p-6 space-y-3">
            {DAYS.map(([key, label]) => {
              const h = data.opening_hours?.[key] || { open: "11:00", close: "22:00", closed: false };
              return (
                <div key={key} className="flex items-center gap-3 flex-wrap" data-testid={`hours-${key}`}>
                  <span className="w-24 text-sm font-medium">{label}</span>
                  <Input type="time" disabled={readOnly || h.closed} value={h.open} onChange={(e) => setHour(key, "open", e.target.value)} className="w-32" />
                  <span className="text-muted-foreground">→</span>
                  <Input type="time" disabled={readOnly || h.closed} value={h.close} onChange={(e) => setHour(key, "close", e.target.value)} className="w-32" />
                  <label className="flex items-center gap-2 text-sm text-muted-foreground ml-auto">
                    <input type="checkbox" disabled={readOnly} checked={!!h.closed} onChange={(e) => setHour(key, "closed", e.target.checked)} /> Fermé
                  </label>
                </div>
              );
            })}
            {!readOnly && (
              <Button onClick={() => save(["opening_hours"])} disabled={saving} className="mt-2" data-testid="save-hours-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" /> Enregistrer</>}
              </Button>
            )}
          </div>
        </TabsContent>

        <TabsContent value="widget" className="mt-6">
          <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Couleur principale</Label>
                <Input type="color" disabled={readOnly} value={data.widget?.primary_color || "#E05638"} onChange={setWidget("primary_color")} className="h-11 w-full" data-testid="widget-primary-color" /></div>
              <div className="space-y-2"><Label>Couleur secondaire</Label>
                <Input type="color" disabled={readOnly} value={data.widget?.secondary_color || "#0F172A"} onChange={setWidget("secondary_color")} className="h-11 w-full" data-testid="widget-secondary-color" /></div>
            </div>
            <div className="space-y-2"><Label>Message d'accueil</Label>
              <Textarea disabled={readOnly} rows={2} value={data.widget?.welcome_message || ""} onChange={setWidget("welcome_message")} data-testid="widget-welcome-message" /></div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Code d'intégration</Label>
                <Button variant="outline" size="sm" onClick={copyEmbed} data-testid="copy-embed-button">
                  <Copy className="w-3.5 h-3.5 mr-1" /> Copier
                </Button>
              </div>
              <pre className="bg-secondary rounded-lg p-3 text-xs overflow-x-auto font-mono" data-testid="widget-embed-code">{embedCode}</pre>
              <p className="text-xs text-muted-foreground">
                Collez ce code sur votre site : le bouton de l'assistant s'affiche automatiquement.
              </p>
            </div>
            {!readOnly && (
              <Button onClick={() => save(["widget"])} disabled={saving} data-testid="save-widget-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" /> Enregistrer</>}
              </Button>
            )}
          </div>
        </TabsContent>

        <TabsContent value="chatbot" className="mt-6">
          <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
            <div className="space-y-2">
              <h2 className="font-heading text-xl font-semibold">Votre chatbot</h2>
              <p className="text-sm text-muted-foreground">
                Partagez ce lien avec vos clients pour leur permettre de découvrir votre menu et de commander directement avec votre assistant.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="chatbot-public-link">Lien public</Label>
              <Input id="chatbot-public-link" readOnly value={chatbotUrl} data-testid="chatbot-public-link" />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Button onClick={copyChatbotLink} disabled={!chatbotUrl} data-testid="copy-chatbot-link">
                <Copy className="w-4 h-4" /> Copier le lien
              </Button>
              <Button asChild variant="outline" disabled={!chatbotUrl} data-testid="open-chatbot-link">
                <a href={chatbotUrl || undefined} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="w-4 h-4" /> Ouvrir le chatbot
                </a>
              </Button>
              <Button variant="outline" onClick={shareChatbotLink} disabled={!chatbotUrl} data-testid="share-chatbot-link">
                <Share2 className="w-4 h-4" /> Partager
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
