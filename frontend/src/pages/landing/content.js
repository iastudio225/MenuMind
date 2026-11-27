import { Building2, Clock3, ClipboardCheck, Layers, Palette, BookOpen, BarChart3 } from "lucide-react";

export const STATIC_PLANS = [
  {
    code: "STARTER", price: 15000, highlighted: false, badge: "Démarrage",
    desc: "Pour lancer votre assistant et traiter vos premières demandes.",
  },
  {
    code: "BUSINESS", price: 30000, highlighted: true, badge: "Recommandé",
    desc: "Pour automatiser le quotidien d'une équipe qui grandit.",
  },
  {
    code: "PRO", price: 50000, highlighted: false, badge: "Avancé",
    desc: "Pour les organisations aux besoins opérationnels plus larges.",
  },
];

// Capabilities available on every plan (verified in the product, not plan-gated).
export const PLAN_INCLUDES = [
  "Assistant IA en français",
  "Catalogue, horaires et base de connaissances",
  "Demandes structurées, total calculé côté serveur",
  "Widget, lien partagé et QR code",
];

// Conversation illustrative d'entreprise (aucune donnée réelle).
export const CHAT = [
  { from: "user", text: "Bonjour, j'aimerais connaître vos services." },
  { from: "bot", text: "Bonjour ! Je peux vous présenter nos services, répondre à vos questions ou vous orienter vers notre équipe. Que souhaitez-vous savoir ?" },
  { from: "user", text: "Quels sont vos horaires ?" },
  { from: "bot", text: "Nous sommes disponibles du lundi au samedi. Je peux également vous aider à faire une demande." },
];

export const FEATURES = [
  {
    key: "understanding",
    icon: Building2,
    title: "Comprend votre activité",
    description: "Catalogue, horaires, zones de livraison, documents internes : l'assistant s'appuie sur vos vraies informations pour répondre juste, sans inventer.",
    chips: ["Catalogue", "Horaires", "Zones", "Documents"],
    span: "sm:col-span-2 lg:col-span-4",
    highlight: true,
    testid: "feature-understanding",
  },
  {
    key: "always-on",
    icon: Clock3,
    title: "Répond à toute heure",
    description: "Vos clients obtiennent une réponse immédiate, même en dehors de vos horaires d'ouverture.",
    span: "sm:col-span-1 lg:col-span-2",
    testid: "feature-always-on",
  },
  {
    key: "requests",
    icon: ClipboardCheck,
    title: "Transforme l'échange en demande",
    description: "Panier, récapitulatif, confirmation : la demande arrive structurée, avec un total calculé côté serveur.",
    span: "sm:col-span-1 lg:col-span-2",
    testid: "feature-requests",
  },
  {
    key: "sectors",
    icon: Layers,
    title: "S'adapte à votre métier",
    description: "Restaurant, livraison ou e-commerce : le vocabulaire et le parcours suivent votre activité.",
    chips: ["Restaurant", "Logistique", "E-commerce"],
    span: "sm:col-span-1 lg:col-span-2",
    testid: "feature-sectors",
  },
  {
    key: "branding",
    icon: Palette,
    title: "À votre image",
    description: "Couleurs, message d'accueil et logo : votre assistant reste cohérent avec votre marque.",
    chips: ["Couleurs", "Accueil", "Logo"],
    span: "sm:col-span-1 lg:col-span-2",
    testid: "feature-branding",
  },
  {
    key: "knowledge",
    icon: BookOpen,
    title: "Votre base de connaissances",
    description: "Ajoutez vos documents, pages web ou textes : l'assistant retrouve la bonne information et cite sa source.",
    chips: ["PDF", "Page web", "Texte"],
    span: "sm:col-span-2 lg:col-span-3",
    testid: "feature-knowledge",
  },
  {
    key: "dashboard",
    icon: BarChart3,
    title: "Un espace pour piloter",
    description: "Demandes, clients, catalogue et sources d'acquisition : tout se suit depuis un tableau de bord unique.",
    chips: ["Demandes", "Clients", "Sources"],
    span: "sm:col-span-2 lg:col-span-3",
    testid: "feature-dashboard",
  },
];
