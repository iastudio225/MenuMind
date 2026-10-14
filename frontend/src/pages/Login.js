import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/format";
import AuthShell from "@/components/AuthShell";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const u = await login(email, password);
      navigate(u.role === "SUPER_ADMIN" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Connexion"
      subtitle="Accédez à votre tableau de bord restaurant."
      footer={<>Pas encore de compte ? <Link to="/register" className="text-primary font-medium" data-testid="go-register-link">Créer un compte</Link></>}
    >
      <form onSubmit={submit} className="space-y-5" data-testid="login-form">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="vous@restaurant.ci" data-testid="login-email-input" />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Mot de passe</Label>
            <Link to="/forgot-password" className="text-xs text-primary" data-testid="forgot-password-link">Mot de passe oublié ?</Link>
          </div>
          <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••" data-testid="login-password-input" />
        </div>
        {error && <p className="text-sm text-destructive" data-testid="login-error">{error}</p>}
        <Button type="submit" className="w-full h-11" disabled={loading} data-testid="login-submit-button">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Se connecter"}
        </Button>
      </form>
    </AuthShell>
  );
}
