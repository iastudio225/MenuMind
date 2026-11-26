import React from "react";
import LandingNav from "./landing/LandingNav";
import Hero from "./landing/Hero";
import Features from "./landing/Features";
import Solutions from "./landing/Solutions";
import Pricing from "./landing/Pricing";
import FinalCta from "./landing/FinalCta";
import LandingFooter from "./landing/LandingFooter";

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNav />
      <Hero />
      <Features />
      <Solutions />
      <Pricing />
      <FinalCta />
      <LandingFooter />
    </div>
  );
}
