import { landingBody, landingDisplay, landingMono } from "@/lib/landing-fonts";

import { CtaBand } from "./CtaBand";
import { AgentsSection } from "./AgentsSection";
import { ExampleSection } from "./ExampleSection";
import { Footer } from "./Footer";
import { Hero } from "./Hero";
import { Navbar } from "./Navbar";
import { QualitySection } from "./QualitySection";
import { ScrollReveal } from "./ScrollReveal";
import { StepsSection } from "./StepsSection";
import styles from "./landing.module.css";

export function LandingPage() {
  return (
    <div className={`${styles.root} ${landingDisplay.variable} ${landingBody.variable} ${landingMono.variable}`}>
      <Navbar />
      <main id="main">
        <Hero />
        <ScrollReveal><ExampleSection /></ScrollReveal>
        <ScrollReveal><AgentsSection /></ScrollReveal>
        <ScrollReveal><StepsSection /></ScrollReveal>
        <ScrollReveal><QualitySection /></ScrollReveal>
        <ScrollReveal><CtaBand /></ScrollReveal>
      </main>
      <Footer />
    </div>
  );
}
