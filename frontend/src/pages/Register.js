import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/format";
import { SECTEUR_OPTIONS, secteurConfig } from "@/lib/secteurs";
import AuthShell from "@/components/AuthShell";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", restaurant_name: "", email: "", phone: "", password: "", secteur: "restaurant" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const secteur = secteurConfig(form.secteur);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form);
      navigate("/onboarding");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Créer votre compte"
      subtitle="Lancez votre assistant IA en quelques minutes."
      footer={<>Déjà inscrit ? <Link to="/login" className="text-primary font-medium" data-testid="go-login-link">Se connecter</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        <div className="space-y-2">
          <Label htmlFor="secteur">Type d'activité</Label>
          <Select value={form.secteur} onValueChange={(value) => setForm((f) => ({ ...f, secteur: value }))}>
            <SelectTrigger id="secteur" data-testid="register-secteur-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SECTEUR_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="restaurant_name">{secteur.businessLabel}</Label>
          <Input id="restaurant_name" required value={form.restaurant_name} onChange={set("restaurant_name")}
            placeholder={secteur.businessPlaceholder} data-testid="register-restaurant-input" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Votre nom</Label>
          <Input id="name" required value={form.name} onChange={set("name")} placeholder="Awa Koné" data-testid="register-name-input" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={form.email} onChange={set("email")}
              placeholder="vous@exemple.ci" data-testid="register-email-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="phone">Téléphone</Label>
            <Input id="phone" value={form.phone} onChange={set("phone")} placeholder="+225 07 00 00 00 00" data-testid="register-phone-input" />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" required minLength={6} value={form.password} onChange={set("password")}
            placeholder="Minimum 6 caractères" data-testid="register-password-input" />
        </div>
        {error && <p className="text-sm text-destructive" data-testid="register-error">{error}</p>}
        <Button type="submit" className="w-full h-11" disabled={loading} data-testid="register-submit-button">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : `Créer mon compte ${secteur.businessNoun}`}
        </Button>
      </form>
    </AuthShell>
  );
}
