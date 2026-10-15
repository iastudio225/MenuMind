import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import BrandLogo from "@/components/BrandLogo";
import api from "@/lib/api";
import { formatFCFA } from "@/lib/format";
import {
  Bot, Clock, ShoppingBag, MessageSquare, Check, Zap, Shield, BarChart3,
  Utensils, ArrowRight, Sparkles,
} from "lucide-react";

const HERO_BG =
  "https://images.unsplash.com/photo-1777502286570-2725dff09ce5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjV8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjByZXN0YXVyYW50JTIwaW50ZXJpb3IlMjBkaW5pbmclMjB0YWJsZSUyMGF0bW9zcGhlcmV8ZW58MHx8fHwxNzkxMzAwMTc5fDA&ixlib=rb-4.1.0&q=85";

const STATIC_PLANS = [
  { code: "STARTER", price: 15000, highlighted: false, badge: "Démarrage",
    desc: "Parfait pour les maquis et petits fast-foods.",
    features: ["Jusqu'à 300 commandes/mois", "Agent IA Web", "Menu digital", "Support 6j/7"] },
  { code: "BUSINESS", price: 30000, highlighted: true, badge: "Le plus populaire 🔥",
    desc: "Idéal pour les restaurants établis avec livraison.",
    features: ["Commandes illimitées", "Agent IA multi-langue", "Zones de livraison", "Multi-utilisateurs", "Branding personnalisé"] },
  { code: "PRO", price: 50000, highlighted: false, badge: "Entreprise",
    desc: "Pour les chaînes et grands établissements.",
    features: ["Multi-établissements", "Manager dédié 24/7", "Statistiques avancées", "API & webhooks"] },
];

const CHAT = [
  { from: "user", text: "Bonsoir, je voudrais deux poulets braisés avec alloco 🍗" },
  { from: "bot", text: "Bien sûr 😊 Deux poulets braisés + alloco, c'est noté. Souhaitez-vous une boisson ?" },
  { from: "user", text: "Oui, une bouteille de Coca." },
  { from: "bot", text: "Parfait ! Voici votre commande :\n2 × Poulet braisé + Alloco — 11 000 FCFA\n1 × Coca-Cola — 1 000 FCFA\nSous-total : 12 000 FCFA. Je confirme ?" },
];

export default function Landing() {
  const [plans, setPlans] = useState(STATIC_PLANS);
  const [visible, setVisible] = useState(1);

  useEffect(() => {
    api.get("/plans").then(({ data }) => {
      if (Array.isArray(data) && data.length) {
        const merged = STATIC_PLANS.map((sp) => {
          const found = data.find((d) => d.code === sp.code);
          return found ? { ...sp, price: found.price } : sp;
        });
        setPlans(merged);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setInterval(() => setVisible((v) => (v >= CHAT.length ? 1 : v + 1)), 1600);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-background/80 border-b border-border">
        <div className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex items-center justify-between h-16">
          <div className="flex items-center gap-2 font-heading font-bold text-xl" data-testid="brand-logo">
            <BrandLogo size="lg" />
            Menu<span className="text-primary">Mind</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            <a href="#features" className="hover:text-foreground transition-colors" data-testid="nav-features-link">Fonctionnalités</a>
            <a href="#pricing" className="hover:text-foreground transition-colors" data-testid="nav-pricing-link">Tarifs</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" data-testid="nav-login-btn">Connexion</Button>
            </Link>
            <Link to="/register">
              <Button data-testid="nav-register-btn">Commencer</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img src={HERO_BG} alt="" className="w-full h-full object-cover opacity-10" />
          <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background to-background" />
        </div>
        <div className="relative px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-20 lg:py-28 grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
              <Sparkles className="w-4 h-4" /> Spécial restaurants en Côte d'Ivoire
            </span>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-tight">
              Votre réceptionniste <span className="text-primary">IA</span> qui prend vos commandes 24h/24
            </h1>
            <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-xl">
              Ne manquez plus aucune commande. MenuMind comprend vos clients en langage naturel,
              consulte votre vrai menu, construit le panier et crée la commande — automatiquement.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/register">
                <Button size="lg" className="h-12 px-7 text-base" data-testid="hero-cta-signup">
                  Essayer gratuitement <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
              <a href="#pricing">
                <Button size="lg" variant="outline" className="h-12 px-7 text-base" data-testid="hero-pricing-btn">
                  Voir les tarifs
                </Button>
              </a>
            </div>
            <div className="mt-8 flex items-center gap-6 text-sm text-muted-foreground">
              <span className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Sans carte bancaire</span>
              <span className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Devise FCFA</span>
            </div>
          </motion.div>

          {/* Chat preview */}
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="relative">
            <div className="rounded-3xl border border-border bg-card shadow-2xl overflow-hidden" data-testid="hero-chat-preview">
              <div className="flex items-center gap-3 px-5 py-4 bg-[#0F172A] text-white">
                <span className="w-9 h-9 rounded-full bg-primary grid place-items-center"><Bot className="w-5 h-5" /></span>
                <div>
                  <p className="font-semibold text-sm font-heading">Chez Awa</p>
                  <p className="text-xs text-emerald-400 flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> En ligne
                  </p>
                </div>
              </div>
              <div className="p-5 space-y-3 h-[360px] overflow-hidden bg-[#FAF7F2]">
                {CHAT.slice(0, visible).map((m, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-line ${
                      m.from === "user" ? "bg-primary text-primary-foreground rounded-br-sm"
                        : "bg-white border border-border rounded-bl-sm"}`}>
                      {m.text}
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-16 lg:py-24">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">Bien plus qu'un simple chatbot</h2>
          <p className="mt-4 text-muted-foreground">Une plateforme complète pour automatiser la prise de commande de votre restaurant.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            { icon: Bot, title: "Agent IA intelligent", desc: "Comprend le langage naturel et l'argot local, propose uniquement vos vrais plats." },
            { icon: Clock, title: "Disponible 24h/24", desc: "Vos clients commandent même quand vous dormez. Aucune commande manquée." },
            { icon: ShoppingBag, title: "Panier & commandes", desc: "Calcul du total côté serveur, création de commande exploitable immédiatement." },
            { icon: Shield, title: "Multi-tenant sécurisé", desc: "Chaque restaurant totalement isolé. Vos données ne sont jamais mélangées." },
            { icon: BarChart3, title: "Tableau de bord", desc: "Suivez vos commandes, votre chiffre d'affaires et vos clients en temps réel." },
            { icon: MessageSquare, title: "Widget intégrable", desc: "Un simple script à ajouter sur votre site. Bientôt WhatsApp & Instagram." },
          ].map((f, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.05 }}
              className="p-6 sm:p-8 rounded-2xl bg-card border border-border hover:shadow-lg hover:-translate-y-1 transition-all">
              <span className="w-12 h-12 rounded-xl bg-primary/10 text-primary grid place-items-center mb-5">
                <f.icon className="w-6 h-6" />
              </span>
              <h3 className="text-xl font-semibold mb-2">{f.title}</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-16 lg:py-24">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">Des tarifs simples et transparents</h2>
          <p className="mt-4 text-muted-foreground">Choisissez le plan adapté à votre restaurant. Résiliable à tout moment.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {plans.map((p) => (
            <div key={p.code}
              className={`relative rounded-2xl p-8 border transition-all ${
                p.highlighted ? "border-primary bg-card shadow-2xl md:-translate-y-3" : "border-border bg-card"}`}
              data-testid={`pricing-card-${p.code.toLowerCase()}`}>
              {p.badge && (
                <span className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold ${
                  p.highlighted ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
                  {p.badge}
                </span>
              )}
              <h3 className="font-heading font-bold text-lg">{p.code}</h3>
              <p className="text-sm text-muted-foreground mt-1 mb-5">{p.desc}</p>
              <div className="mb-6">
                <span className="text-3xl font-bold font-heading">{formatFCFA(p.price)}</span>
                <span className="text-muted-foreground text-sm"> /mois</span>
              </div>
              <ul className="space-y-3 mb-8">
                {p.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" /> {f}
                  </li>
                ))}
              </ul>
              <Link to="/register">
                <Button className="w-full" variant={p.highlighted ? "default" : "outline"}
                  data-testid={`pricing-plan-${p.code.toLowerCase()}-btn`}>
                  Choisir {p.code}
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto pb-24">
        <div className="rounded-3xl bg-[#0F172A] text-white px-8 py-14 lg:py-20 text-center relative overflow-hidden">
          <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-primary/30 blur-3xl" />
          <Utensils className="w-10 h-10 text-primary mx-auto mb-6" />
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight max-w-2xl mx-auto">
            Prêt à ne plus jamais manquer une commande ?
          </h2>
          <p className="mt-4 text-white/70 max-w-xl mx-auto">Créez votre compte restaurant en 2 minutes et activez votre réceptionniste IA.</p>
          <Link to="/register">
            <Button size="lg" className="mt-8 h-12 px-8 text-base" data-testid="cta-bottom-signup">
              Créer mon compte <Zap className="w-4 h-4 ml-1" />
            </Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-muted-foreground">
        © {new Date().getFullYear()} MenuMind — Réceptionniste IA pour restaurants. Abidjan, Côte d'Ivoire.
      </footer>
    </div>
  );
}
