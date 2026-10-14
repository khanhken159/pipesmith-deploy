"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import styles from "./landing.module.css";

type RevealPhase = "idle" | "waiting" | "shown";

export function ScrollReveal({ children }: { children: ReactNode }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<RevealPhase>("idle");

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
      setPhase("shown");
      return;
    }

    setPhase("waiting");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setPhase("shown");
        observer.disconnect();
      },
      { threshold: 0.08, rootMargin: "0px 0px -40px 0px" },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const phaseClass = phase === "waiting" ? styles.revealPending : phase === "shown" ? styles.revealShown : "";
  return (
    <div className={`${styles.reveal} ${phaseClass}`} ref={elementRef}>
      {children}
    </div>
  );
}
