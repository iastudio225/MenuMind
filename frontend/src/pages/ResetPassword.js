import React, { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { formatApiErrorDetail } from "@/lib/format";
import AuthShell from "@/components/AuthShell";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Mot de passe réinitialisé ! Connectez-vous.");
      navigate("/login");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Nouveau mot de passe"
      subtitle="Choisissez un nouveau mot de passe pour votre compte."
      footer={<Link to="/login" className="text-primary font-medium" data-testid="reset-back-login-link">Retour à la connexion</Link>}
    >
      {!token ? (
        <p className="text-sm text-destructive" data-testid="reset-no-token">Lien invalide. Veuillez redemander un lien de réinitialisation.</p>
      ) : (
        <form onSubmit={submit} className="space-y-5" data-testid="reset-form">
          <div className="space-y-2">
            <Label htmlFor="password">Nouveau mot de passe</Label>
            <Input id="password" type="password" required minLength={6} value={password}
              onChange={(e) => setPassword(e.target.value)} placeholder="Minimum 6 caractères" data-testid="reset-password-input" />
          </div>
          {error && <p className="text-sm text-destructive" data-testid="reset-error">{error}</p>}
          <Button type="submit" className="w-full h-11" disabled={loading} data-testid="reset-submit-button">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Réinitialiser"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
