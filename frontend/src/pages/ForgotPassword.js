import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, MailCheck } from "lucide-react";
import api from "@/lib/api";
import { formatApiErrorDetail } from "@/lib/format";
import AuthShell from "@/components/AuthShell";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Mot de passe oublié"
      subtitle="Entrez votre email pour recevoir un lien de réinitialisation."
      footer={<Link to="/login" className="text-primary font-medium" data-testid="back-to-login-link">Retour à la connexion</Link>}
    >
      {sent ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center" data-testid="forgot-success">
          <MailCheck className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">
            Si cet email est enregistré, un lien de réinitialisation vous a été envoyé. Vérifiez votre boîte de réception.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5" data-testid="forgot-form">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@restaurant.ci" data-testid="forgot-email-input" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full h-11" disabled={loading} data-testid="forgot-submit-button">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Envoyer le lien"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
