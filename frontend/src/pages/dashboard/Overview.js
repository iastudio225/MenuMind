import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ShoppingBag, TrendingUp, Clock, ChefHat, Wallet, UtensilsCrossed,
  Users as UsersIcon, Sparkles, ArrowRight, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { formatFCFA } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

function StatCard({ icon: Icon, label, value, hint, tone = "neutral", testid }) {
  const tones = {
    positive: "text-emerald-600 bg-emerald-50",
    warning: "text-amber-600 bg-amber-50",
    neutral: "text-primary bg-primary/10",
  };
  return (
    <div className="bg-card border border-border rounded-2xl p-5 sm:p-6" data-testid={testid}>
      <div className="flex items-center justify-between mb-4">
        <span className={`w-10 h-10 rounded-xl grid place-items-center ${tones[tone]}`}><Icon className="w-5 h-5" /></span>
      </div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold font-heading mt-1">{value}</p>
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export default function Overview() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [restaurant, setRestaurant] = useState(null);

  useEffect(() => {
    api.get("/dashboard/overview").then(({ data }) => setStats(data)).catch(() => setStats({}));
    api.get("/restaurants/me").then(({ data }) => setRestaurant(data)).catch(() => {});
  }, []);

  if (!stats) {
    return <div className="grid place-items-center py-20"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;
  }

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="overview-title">
            Bonjour {user?.name?.split(" ")[0]} 👋
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">Voici l'activité de {restaurant?.name || "votre restaurant"} aujourd'hui.</p>
        </div>
        <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-600 text-sm font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> Agent IA actif
        </span>
      </div>

      {restaurant && !restaurant.onboarding_completed && (
        <Link to="/onboarding" className="block mb-6">
          <div className="rounded-2xl bg-primary/5 border border-primary/20 p-5 flex items-center justify-between hover:bg-primary/10 transition-colors"
            data-testid="onboarding-banner">
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 text-primary" />
              <div>
                <p className="font-semibold text-sm">Terminez la configuration de votre restaurant</p>
                <p className="text-xs text-muted-foreground">Ajoutez vos coordonnées et paramètres pour activer pleinement l'agent IA.</p>
              </div>
            </div>
            <ArrowRight className="w-5 h-5 text-primary" />
          </div>
        </Link>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <StatCard icon={ShoppingBag} label="Commandes aujourd'hui" value={stats.orders_today ?? 0} tone="neutral" testid="stat-orders-today" />
        <StatCard icon={Wallet} label="Chiffre d'affaires (jour)" value={formatFCFA(stats.revenue_today)} tone="positive" testid="stat-revenue" />
        <StatCard icon={TrendingUp} label="Commandes (7 jours)" value={stats.orders_week ?? 0} hint={formatFCFA(stats.revenue_week) + " cette semaine"} tone="positive" testid="stat-orders-week" />
        <StatCard icon={Clock} label="Commandes en attente" value={stats.pending ?? 0} hint={stats.pending ? "Action requise" : "Rien à traiter"}
          tone={stats.pending ? "warning" : "neutral"} testid="stat-pending" />
        <StatCard icon={ChefHat} label="En préparation" value={stats.preparing ?? 0} hint="Cuisine" tone="neutral" testid="stat-preparing" />
        <StatCard icon={Wallet} label="Panier moyen" value={formatFCFA(stats.avg_basket)} tone="positive" testid="stat-avg-basket" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-5">
        <div className="bg-card border border-border rounded-2xl p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2"><UsersIcon className="w-4 h-4 text-primary" /> Votre équipe</h3>
          <p className="text-3xl font-bold font-heading">{stats.users ?? 0}</p>
          <p className="text-sm text-muted-foreground">utilisateur(s) ayant accès au tableau de bord</p>
          {user?.role === "RESTAURANT_OWNER" && (
            <Link to="/dashboard/users"><Button variant="outline" className="mt-4" data-testid="overview-manage-users">Gérer l'équipe</Button></Link>
          )}
        </div>
        <div className="bg-[#0F172A] text-white rounded-2xl p-6 relative overflow-hidden">
          <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-primary/30 blur-3xl" />
          <h3 className="font-semibold mb-2 flex items-center gap-2 relative z-10"><Sparkles className="w-4 h-4 text-primary" /> Prochaine étape</h3>
          <p className="text-sm text-white/70 relative z-10">
            La prise de commande par agent IA et la gestion du menu arrivent dans les prochaines phases.
            Votre fondation multi-tenant est prête 🚀
          </p>
        </div>
      </div>
    </div>
  );
}
