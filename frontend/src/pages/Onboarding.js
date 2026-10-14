import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Check, Store, MapPin, Settings2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatApiErrorDetail } from "@/lib/format";

const STEPS = [
  { key: "identity", label: "Identité", icon: Store },
  { key: "location", label: "Localisation", icon: MapPin },
  { key: "config", label: "Configuration", icon: Settings2 },
];

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);

  useEffect(() => {
    api.get("/restaurants/me").then(({ data }) => {
      if (data.onboarding_completed) {
        navigate("/dashboard");
        return;
      }
      setForm({
        name: data.name || "", description: data.description || "", logo: data.logo || "",
        phone: data.phone || "", whatsapp: data.whatsapp || "", email: data.email || "",
        address: data.address || "", city: data.city || "Abidjan", country: data.country || "Côte d'Ivoire",
        currency: data.currency || "FCFA", timezone: data.timezone || "Africa/Abidjan",
      });
    }).catch(() => navigate("/dashboard"));
  }, [navigate]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const finish = async () => {
    setLoading(true);
    try {
      await api.patch("/restaurants/me", { ...form, onboarding_completed: true });
      toast.success("Restaurant configuré avec succès !");
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  if (!form) {
    return <div className="min-h-screen grid place-items-center"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;
  }

  return (
    <div className="min-h-screen bg-background py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight text-center">Configurez votre restaurant</h1>
        <p className="text-muted-foreground text-center mt-2 text-sm">Ces informations seront utilisées par votre agent IA.</p>

        {/* Stepper */}
        <div className="flex items-center justify-center gap-2 my-8">
          {STEPS.map((s, i) => (
            <React.Fragment key={s.key}>
              <div className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium ${
                i <= step ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}
                data-testid={`onboarding-step-${i}`}>
                {i < step ? <Check className="w-4 h-4" /> : <s.icon className="w-4 h-4" />}
                <span className="hidden sm:inline">{s.label}</span>
              </div>
              {i < STEPS.length - 1 && <div className={`w-6 h-0.5 ${i < step ? "bg-primary" : "bg-border"}`} />}
            </React.Fragment>
          ))}
        </div>

        <div className="bg-card border border-border rounded-2xl p-6 sm:p-8 space-y-5">
          {step === 0 && (
            <>
              <div className="space-y-2">
                <Label>Nom du restaurant</Label>
                <Input value={form.name} onChange={set("name")} data-testid="onboarding-name-input" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={form.description} onChange={set("description")} rows={3}
                  placeholder="Maquis ivoirien — grillades, poissons et plats traditionnels." data-testid="onboarding-description-input" />
              </div>
              <div className="space-y-2">
                <Label>Logo (URL)</Label>
                <Input value={form.logo} onChange={set("logo")} placeholder="https://..." data-testid="onboarding-logo-input" />
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Téléphone</Label>
                  <Input value={form.phone} onChange={set("phone")} data-testid="onboarding-phone-input" />
                </div>
                <div className="space-y-2">
                  <Label>WhatsApp</Label>
                  <Input value={form.whatsapp} onChange={set("whatsapp")} data-testid="onboarding-whatsapp-input" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Email de contact</Label>
                <Input type="email" value={form.email} onChange={set("email")} data-testid="onboarding-email-input" />
              </div>
              <div className="space-y-2">
                <Label>Adresse</Label>
                <Input value={form.address} onChange={set("address")} placeholder="Rue des Jardins, Cocody" data-testid="onboarding-address-input" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Ville</Label>
                  <Input value={form.city} onChange={set("city")} data-testid="onboarding-city-input" />
                </div>
                <div className="space-y-2">
                  <Label>Pays</Label>
                  <Input value={form.country} onChange={set("country")} data-testid="onboarding-country-input" />
                </div>
              </div>
            </>
          )}
          {step === 2 && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Devise</Label>
                  <Input value={form.currency} onChange={set("currency")} data-testid="onboarding-currency-input" />
                </div>
                <div className="space-y-2">
                  <Label>Fuseau horaire</Label>
                  <Input value={form.timezone} onChange={set("timezone")} data-testid="onboarding-timezone-input" />
                </div>
              </div>
              <div className="rounded-xl bg-primary/5 border border-primary/20 p-4 text-sm text-muted-foreground">
                Les horaires d'ouverture et zones de livraison détaillés se configurent ensuite depuis le tableau de bord.
              </div>
            </>
          )}

          <div className="flex justify-between pt-4">
            <Button variant="ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}
              data-testid="onboarding-prev-step">Précédent</Button>
            {step < STEPS.length - 1 ? (
              <Button onClick={() => setStep((s) => s + 1)} data-testid="onboarding-next-step">Suivant</Button>
            ) : (
              <Button onClick={finish} disabled={loading} data-testid="onboarding-finish-button">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Terminer"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
