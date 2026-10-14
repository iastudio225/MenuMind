import React from "react";
import { Construction } from "lucide-react";

export default function Placeholder({ title, phase }) {
  return (
    <div className="max-w-3xl">
      <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight" data-testid="placeholder-title">{title}</h1>
      <div className="mt-8 bg-card border border-border rounded-2xl p-10 text-center">
        <span className="w-14 h-14 rounded-2xl bg-primary/10 text-primary grid place-items-center mx-auto mb-4">
          <Construction className="w-7 h-7" />
        </span>
        <h2 className="font-heading text-xl font-semibold">Bientôt disponible</h2>
        <p className="text-muted-foreground mt-2 text-sm max-w-md mx-auto">
          Ce module sera construit lors de la <span className="font-medium text-foreground">{phase}</span>.
          La fondation multi-tenant est déjà en place pour l'accueillir.
        </p>
      </div>
    </div>
  );
}
