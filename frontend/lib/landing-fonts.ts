import { Bricolage_Grotesque, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

export const landingDisplay = Bricolage_Grotesque({
  subsets: ["latin", "vietnamese"],
  weight: "variable",
  axes: ["opsz"],
  display: "swap",
  variable: "--landing-display",
});

export const landingBody = IBM_Plex_Sans({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--landing-body",
});

export const landingMono = IBM_Plex_Mono({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--landing-mono",
});
