import React, { useEffect, useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, ShoppingBag, UtensilsCrossed, Users, Truck,
  MessageSquare, Settings, LogOut, Menu as MenuIcon, X, UserCog, CalendarDays,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import BrandLogo from "@/components/BrandLogo";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/format";
import api from "@/lib/api";

const NAV = [
  { to: "/dashboard", end: true, label: "Vue d'ensemble", icon: LayoutDashboard, testid: "nav-overview" },
  { to: "/dashboard/orders", label: "Commandes", icon: ShoppingBag, testid: "nav-orders" },
  { to: "/dashboard/menu", label: "Menu & Carte", icon: UtensilsCrossed, testid: "nav-menu" },
  { to: "/dashboard/weekly-menu", label: "Menu hebdomadaire", icon: CalendarDays, testid: "nav-weekly-menu" },
  { to: "/dashboard/customers", label: "Clients", icon: Users, testid: "nav-customers" },
  { to: "/dashboard/delivery", label: "Livraison & Zones", icon: Truck, testid: "nav-delivery" },
  { to: "/dashboard/ai", label: "Réceptionniste IA", icon: MessageSquare, testid: "nav-ai" },
  { to: "/dashboard/users", label: "Utilisateurs", icon: UserCog, testid: "nav-users", ownerOnly: true },
  { to: "/dashboard/settings", label: "Paramètres", icon: Settings, testid: "nav-settings" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [restaurant, setRestaurant] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/restaurants/me").then(({ data }) => setRestaurant(data)).catch(() => {});
  }, []);

  const doLogout = async () => {
    await logout();
    navigate("/login");
  };

  const visibleNav = NAV.filter((n) => !n.ownerOnly || user?.role === "RESTAURANT_OWNER");

  const SidebarContent = () => (
    <>
      <div className="flex items-center gap-2 font-heading font-bold text-lg px-5 h-16 border-b border-border">
        <BrandLogo size="sm" />
        Menu<span className="text-primary">Mind</span>
      </div>
      <div className="px-4 py-4">
        <div className="rounded-xl bg-secondary px-3 py-2.5">
          <p className="text-xs text-muted-foreground">Restaurant</p>
          <p className="font-semibold text-sm truncate" data-testid="sidebar-restaurant-name">{restaurant?.name || "..."}</p>
        </div>
      </div>
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {visibleNav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)} data-testid={n.testid}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`}>
            <n.icon className="w-4 h-4" /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-3 px-3 py-2">
          <span className="w-9 h-9 rounded-full bg-primary/10 text-primary grid place-items-center font-semibold text-sm">
            {user?.name?.[0]?.toUpperCase() || "U"}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate" data-testid="sidebar-user-name">{user?.name}</p>
            <p className="text-xs text-muted-foreground">{ROLE_LABELS[user?.role] || user?.role}</p>
          </div>
        </div>
        <Button variant="ghost" className="w-full justify-start gap-3 text-muted-foreground" onClick={doLogout} data-testid="logout-button">
          <LogOut className="w-4 h-4" /> Déconnexion
        </Button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-background flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 flex-col bg-card border-r border-border fixed inset-y-0">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative w-64 flex flex-col bg-card border-r border-border"><SidebarContent /></aside>
        </div>
      )}

      <div className="flex-1 lg:ml-64">
        <header className="lg:hidden h-16 flex items-center justify-between px-4 border-b border-border bg-card">
          <div className="flex items-center gap-2 font-heading font-bold">
            <BrandLogo size="sm" />
            MenuMind
          </div>
          <Button variant="ghost" size="icon" onClick={() => setOpen((o) => !o)} data-testid="mobile-menu-toggle">
            {open ? <X className="w-5 h-5" /> : <MenuIcon className="w-5 h-5" />}
          </Button>
        </header>
        <main className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
